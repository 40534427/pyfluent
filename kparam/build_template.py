#!/usr/bin/env python3
"""DEV-TIME parameter inversion for the parachute K file.

Reads the reference LS-DYNA keyword file, inverts every geometry / material /
domain parameter, and writes:

  * paramk/_template.pkb      - packed mesh template (canopy + lines)
  * inversion_report.json     - every inverted scalar (for review / params.json)

The generator at run time never needs numpy: the packed template is consumed
with stdlib ``struct``/``array``/``zlib`` only.

Usage:  python3 build_template.py <reference.k>
"""
import gzip
import json
import math
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def sections(path):
    cur, buf = None, []
    with open(path, errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("*") and not s.startswith("$"):
                if cur:
                    yield cur, buf
                import re
                cur = re.split(r"[\s,]", s)[0].upper().lstrip("*")
                buf = []
            elif cur:
                buf.append(line.rstrip("\n"))
        if cur:
            yield cur, buf


def numeric(buf):
    return [l for l in buf if l.strip() and not l.lstrip().startswith("$")]


def load(path):
    secs = {}
    for name, buf in sections(path):
        secs.setdefault(name, []).extend(buf)
    nodes = {}
    for l in numeric(secs["NODE"]):
        p = l.split()
        nodes[int(p[0])] = (float(p[1]), float(p[2]), float(p[3]))
    shells, beams, solids = [], [], []
    for l in numeric(secs["ELEMENT_SHELL"]):
        p = l.split()
        shells.append([int(v) for v in p[2:6]])
    for l in numeric(secs["ELEMENT_BEAM"]):
        p = l.split()
        beams.append([int(v) for v in p[2:5]])
    so = numeric(secs["ELEMENT_SOLID"])
    i = 0
    while i + 1 < len(so):
        p = so[i + 1].split()[:8]
        solids.append([int(v) for v in p])
        i += 2
    return nodes, shells, beams, solids


def main(kpath):
    nodes, shells, beams, solids = load(kpath)

    # ---- structure topology (canopy shells + suspension beams) -----------
    shell_ids = sorted({v for q in shells for v in q})
    s2l = {g: i for i, g in enumerate(shell_ids)}
    nc = len(shell_ids)
    canopy = np.array([nodes[g] for g in shell_ids], dtype=np.float32)
    quads = np.array([[s2l[v] for v in q] for q in shells], dtype=np.int32)

    beam_ids = sorted({v for b in beams for v in b if v > 0} - set(shell_ids))
    b2l0 = {g: nc + i for i, g in enumerate(beam_ids)}  # structure-local
    s2l_full = {g: i for i, g in enumerate(shell_ids)}
    s2l_full.update(b2l0)
    beam_xyz = np.array([nodes[g] for g in beam_ids], dtype=np.float32)
    beam_conn = np.array([[s2l_full[v] if v > 0 else -1 for v in b]
                          for b in beams], dtype=np.int32)
    anchor_g = 8073
    anchor_local = int(s2l_full[anchor_g])
    shared = sorted(set(shell_ids) & {v for b in beams for v in b if v > 0})
    skirt_local = np.array([s2l_full[g] for g in shared], dtype=np.int32)
    n_struct_local = nc + len(beam_ids)

    # ---- geometry inversion ----------------------------------------------
    sx = canopy.astype(np.float64)
    r = np.sqrt(sx[:, 0] ** 2 + sx[:, 2] ** 2)
    y = sx[:, 1]
    ytop, ybot = float(y.max()), float(y.min())
    top_r = float(r[np.abs(y - ytop) < 1e-4].mean())
    # silhouette: max shell radius at the skirt band
    band = np.abs(y - ybot) < 0.002
    skirt_outer_r = float(r[band].max())
    # beam skirt attachments (the 16 shared nodes)
    sk_xyz = np.array([nodes[g] for g in shared], dtype=np.float64)
    sk_y = float(sk_xyz[:, 1].mean())
    sk_r = float(np.sqrt(sk_xyz[:, 0] ** 2 + sk_xyz[:, 2] ** 2).mean())
    anch = np.array(nodes[anchor_g], dtype=np.float64)
    line_len = float(np.sqrt(((sk_xyz - anch) ** 2).sum(axis=1)).mean())
    # folded-envelope effective full cone angle (flare envelope)
    cone_ref_deg = float(math.degrees(
        math.atan2(sk_r - top_r, abs(sk_y - ytop)))) * 2.0

    # gore count = distinct skirt attachment nodes
    n_lines = len(shared)
    n_gores = n_lines  # 16 gores / 16 lines for this canopy

    # ---- fluid domain inversion (from solid nodes) ------------------------
    fu = sorted({v for h in solids for v in h if v > 0})
    fx = np.array([nodes[i] for i in fu], dtype=np.float64)
    y0, y1 = float(fx[:, 1].min()), float(fx[:, 1].max())
    cx = 0.5 * (float(fx[:, 0].min()) + float(fx[:, 0].max()))
    cz = 0.5 * (float(fx[:, 2].min()) + float(fx[:, 2].max()))
    Rf = max(float(fx[:, 0].max() - fx[:, 0].min()),
             float(fx[:, 2].max() - fx[:, 2].min())) * 0.5

    # ---- pack --------------------------------------------------------------
    out = bytearray()
    out += b"PKP1"
    out += struct.pack("<i", nc)
    out += canopy.tobytes()
    out += struct.pack("<i", len(quads))
    out += quads.tobytes()
    out += struct.pack("<i", len(beam_ids))
    out += beam_xyz.tobytes()
    out += struct.pack("<i", len(beam_conn))
    out += beam_conn.tobytes()
    out += struct.pack("<i", anchor_local)
    out += struct.pack("<i", len(skirt_local))
    out += skirt_local.tobytes()
    out += struct.pack("<i", n_struct_local)
    inv = {  # noqa: F841 (serialised once below)
        "canopy_nodes": int(nc), "shell_quads": int(len(quads)),
        "beam_only_nodes": int(len(beam_ids)), "beams": int(len(beam_conn)),
        "n_gores": int(n_gores), "n_suspension_lines": int(n_lines),
        "canopy_y_top": ytop, "canopy_y_bottom": ybot,
        "apex_ring_radius": top_r, "skirt_band_outer_radius": skirt_outer_r,
        "skirt_attach_y": sk_y, "skirt_attach_radius": sk_r,
        "line_length_m": line_len,
        "folded_envelope_full_cone_angle_deg": cone_ref_deg,
        "fluid_y0": y0, "fluid_y1": y1, "fluid_R": Rf, "fluid_cx": cx,
        "fluid_cz": cz, "solid_elements_in_template": int(len(solids)),
    }
    inv_bytes = json.dumps(inv, indent=1, ensure_ascii=False).encode("utf-8")
    out += struct.pack("<i", len(inv_bytes))
    out += inv_bytes
    packed = gzip.compress(bytes(out), compresslevel=9)
    pkb = os.path.join(HERE, "paramk", "_template.pkb.gz")
    os.makedirs(os.path.dirname(pkb), exist_ok=True)
    with open(pkb, "wb") as fh:
        fh.write(packed)
    with open(os.path.join(HERE, "inversion_report.json"), "w", encoding="utf-8") as fh:
        fh.write(inv_bytes.decode("utf-8"))
    print(json.dumps(inv, indent=2, ensure_ascii=False))
    print(f"\ntemplate -> {pkb}  ({len(packed)/1024:.1f} KB gz, "
          f"{len(out)/1024:.1f} KB raw)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         "/workspace/T5IJ_damping_compare_50ms/input/Parachute_F28.k")
