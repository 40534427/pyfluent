"""Parametric LS-DYNA keyword (.k) generator for the ALE parachute model.

Pure standard library (json / math / gzip / struct / array) so it can be
frozen into a small dependency-free Windows executable.

Inputs : params.json (all editable values, Chinese annotations)
Outputs: a new .k file with identical topology to the reference model but
         with canopy / suspension-line / air / solver parameters taken from
         params.json.  Also writes build_log.json with a parameter snapshot,
         mesh statistics and a diff vs. the previous run (if present).
"""
from __future__ import annotations

import argparse
import difflib
import gzip
import json
import math
import os
import re
import struct
import sys
import time
from array import array


# ===========================================================================
# resource paths (frozen exe / source checkout)
# ===========================================================================
def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


# ===========================================================================
# packed template
# ===========================================================================
def load_template(path: str | None = None) -> dict:
    if path is None:
        base = _base_dir()
        for cand in (os.path.join(base, "_template.pkb.gz"),
                     os.path.join(base, "paramk", "_template.pkb.gz"),
                     os.path.join(os.path.dirname(base), "_template.pkb.gz")):
            if os.path.exists(cand):
                path = cand
                break
        else:
            path = os.path.join(base, "_template.pkb.gz")
    raw = gzip.decompress(open(path, "rb").read())
    assert raw[:4] == b"PKP1", "bad template magic"
    pos = 4

    def i32():
        nonlocal pos
        v = struct.unpack_from("<i", raw, pos)[0]
        pos += 4
        return v

    nc = i32()
    canopy = array("f")
    canopy.frombytes(raw[pos:pos + nc * 12]); pos += nc * 12
    nq = i32()
    quads = array("i")
    quads.frombytes(raw[pos:pos + nq * 16]); pos += nq * 16
    nbxyz = i32()
    beam_xyz = array("f")
    beam_xyz.frombytes(raw[pos:pos + nbxyz * 12]); pos += nbxyz * 12
    nbc = i32()
    beam_conn = array("i")
    beam_conn.frombytes(raw[pos:pos + nbc * 12]); pos += nbc * 12
    anchor_local = i32()
    nsk = i32()
    skirt = array("i")
    skirt.frombytes(raw[pos:pos + nsk * 4]); pos += nsk * 4
    n_struct = i32()
    nmeta = i32()
    meta = json.loads(raw[pos:pos + nmeta])
    return {
        "nc": nc, "canopy": canopy, "nq": nq, "quads": quads,
        "nbxyz": nbxyz, "beam_xyz": beam_xyz, "nbc": nbc,
        "beam_conn": beam_conn, "anchor_local": anchor_local,
        "skirt": skirt, "n_struct": n_struct, "meta": meta,
    }


# ===========================================================================
# LS-DYNA fixed-field writers
# ===========================================================================
def f10(v) -> str:
    """Right-justified 10-column numeric field."""
    if isinstance(v, bool):
        v = int(v)
    if isinstance(v, int):
        return f"{v:10d}"
    if float(v).is_integer() and abs(v) < 1e14:
        return f"{int(v):10d}"
    for fmt in ("#.5g", "#.4g", "#.3g", ".5g", ".4g", ".3g"):
        s = f"{float(v):{fmt}}"
        if len(s) <= 10:
            return s.rjust(10)
    raise ValueError(f"value {v} cannot fit a 10-col field")


def i10(*vals) -> str:
    return "".join(f10(v) for v in vals)


def node_line(nid: int, x: float, y: float, z: float) -> str:
    return f"{nid:8d}{x:16.9E}{y:16.9E}{z:16.9E}"


# ===========================================================================
# geometry transforms (canopy cone + suspension-line chain)
# ===========================================================================
def transform_geometry(tpl: dict, P: dict) -> tuple:
    """Return (canopy_xyz list[[x,y,z]], beam_xyz list[[x,y,z]], anchor_y)."""
    canopy = tpl["canopy"]
    nc = tpl["nc"]
    can = [[canopy[3 * i], canopy[3 * i + 1], canopy[3 * i + 2]]
           for i in range(nc)]

    cone_new = math.radians(0.5 * float(P("canopy.cone_angle_deg")))
    cone_ref = math.radians(0.5 * float(tpl["meta"]
                                        ["folded_envelope_full_cone_angle_deg"]))
    k_cone = math.tan(cone_new) / math.tan(cone_ref)
    for pnt in can:
        pnt[0] *= k_cone
        pnt[2] *= k_cone

    sk_locals = list(tpl["skirt"])
    sk_pts = [can[i] for i in sk_locals]
    sk_y = sum(p[1] for p in sk_pts) / len(sk_pts)
    sk_r0 = tpl["meta"]["skirt_attach_radius"]
    sk_r1 = math.sqrt(
        sum(p[0] ** 2 + p[2] ** 2 for p in sk_pts) / len(sk_pts))

    line_L = float(P("suspension_lines.line_length"))
    anchor_y = sk_y - math.sqrt(max(line_L ** 2 - sk_r1 ** 2, 0.0))

    bxyz = tpl["beam_xyz"]
    beams = [list(bxyz[3 * i:3 * i + 3]) for i in range(tpl["nbxyz"])]
    conn = tpl["beam_conn"]
    chain_set, ori_set = set(), set()
    for i in range(tpl["nbc"]):
        n1, n2, n3 = conn[3 * i], conn[3 * i + 1], conn[3 * i + 2]
        for v in (n1, n2):
            if v >= nc:
                chain_set.add(v - nc)
        if n3 >= nc:
            ori_set.add(n3 - nc)
    anchor0 = beams[tpl["anchor_local"] - nc]
    y_anch0 = anchor0[1]
    span0 = y_anch0 - sk_y

    def map_y(y: float) -> float:
        s = (y - sk_y) / span0
        s = min(1.0, max(0.0, s))
        return sk_y + s * (anchor_y - sk_y)

    rfac = sk_r1 / sk_r0 if sk_r0 > 0 else 1.0
    for j, pnt in enumerate(beams):
        if j == tpl["anchor_local"] - nc:
            pnt[0], pnt[1], pnt[2] = 0.0, anchor_y, 0.0
        elif j in chain_set or j in ori_set:
            pnt[1] = map_y(pnt[1])
            pnt[0] *= rfac
            pnt[2] *= rfac
    return can, beams, anchor_y


# ===========================================================================
# suspension-line beam-chain resampling  (NEW in v2)
#
#  The template has 16 lines x 10 segments = 160 beams.  Each beam row is
#  anchored to a canopy skirt node at one end and converges on the common
#  anchor point at the other.  When the user asks for a different number
#  of segments we rebuild each chain by uniform arclength interpolation
#  between the skirt node (known from geometry scaling above) and the
#  common anchor.
#
#  Returns (new_beams, new_conn, new_anchor_local)
#    new_beams      : list of [x,y,z] beam-only node coords (anchor last)
#    new_conn       : list of [n1_local, n2_local, n3_local] beam connectivities
#    new_anchor_local : structure-local index of the common anchor node
# ===========================================================================
def resample_beam_chains(tpl: dict, P, can: list, anchor_y: float) -> tuple:
    """Resample every suspension line to ``line_segments`` segments.

    Design notes
    ------------
    Original template topology (understood after reverse engineering)::

        anchor (shared by all 16 lines, at y=anchor_y, r=0)
          ^
          |  beam n1=chain0, n2=anchor   <-- beam 0 of each row
          |
        chain0
          ^
          |  beam n1=chain1, n2=chain0
          |
        chain1
          ^
         ...
          ^
          |  beam n1=skirt_canopy_node, n2=chainN   <-- last beam of each row
          |
        skirt node on canopy (structure-local id in tpl['skirt'])

    So each beam connects ``n1`` (closer to skirt) to ``n2`` (closer to
    anchor).  For LS-DYNA BEAM elements this direction only matters for the
    element frame; we keep it.

    The template has a perfect straight-line chain.  We rebuild it here with
    ``segments`` uniform subdivisions per line (both chain endpoints and
    direction nodes are regenerated, per-segment).
    """
    nc = tpl["nc"]
    n_lines = int(tpl["meta"].get("n_suspension_lines", 16))
    segments = int(P("suspension_lines.line_segments"))
    if segments < 2:
        segments = 2
    if segments > 50:
        segments = 50

    skirt_locals = list(tpl["skirt"])
    assert len(skirt_locals) == n_lines

    anchor_xyz = [0.0, anchor_y, 0.0]

    # Step 1 -- build chain nodes (one list per line).
    #   Convention used below (matches the original template topology)::
    #
    #       chain[0]   = anchor   (shared by every line, at (0, anchor_y, 0))
    #       chain[1..N-1] = interior nodes from anchor toward skirt
    #       chain[N]    = skirt   (on canopy, already transformed)
    #
    # Uniform linear interpolation along the straight skirt->anchor segment.
    # We place nodes at t=0 (skirt) ... t=1 (anchor) and then REVERSE so that
    # chain[0] is anchor and chain[N] is skirt.  This matches the original
    # template convention where beam 0 connects (chain[1], chain[0]).
    new_beams: list[list[float]] = []
    chain_per_line: list[list[int]] = []

    for sk_local in skirt_locals:
        sk_xyz = can[sk_local]
        # t=0 → skirt, t=1 → anchor  (uniform spacing)
        raw = []
        for k in range(segments + 1):
            t = k / segments
            pt = [
                sk_xyz[0] + t * (anchor_xyz[0] - sk_xyz[0]),
                sk_xyz[1] + t * (anchor_xyz[1] - sk_xyz[1]),
                sk_xyz[2] + t * (anchor_xyz[2] - sk_xyz[2]),
            ]
            raw.append(pt)
        # raw[0]=skirt, raw[-1]=anchor  → reverse
        chain_local_indices = []
        for pt in reversed(raw):
            chain_local_indices.append(len(new_beams))
            new_beams.append(pt)
        chain_per_line.append(chain_local_indices)

    # Deduplicate the anchor: every line's chain[0] ends at anchor_xyz.
    # We keep the anchor of the LAST line and have every other line point to
    # it.  This gives us ONE shared anchor node (structure-local id).
    anchor_beam_local = chain_per_line[-1][0]  # last line's chain[0] = anchor
    for chain in chain_per_line:
        chain[0] = anchor_beam_local
    anchor_local_new = nc + anchor_beam_local

    # Step 2 -- build beam connectivities.  Original template pattern::
    #     beam 0: (chain[1], chain[0])          connects chain1 ↔ anchor
    #     beam 1: (chain[2], chain[1])          connects chain2 ↔ chain1
    #     ...
    #     beam N-1: (skirt_canopy, chain[N])    connects skirt ↔ chainN
    #
    # In our representation the canopy skirt node is NOT part of new_beams
    # — it lives in ``can`` at structure-local id ``sk_local``.  So the last
    # beam of each row connects ``sk_local`` (structure-local, canopy node)
    # to ``chain[N]`` (structure-local, beam-only node).
    new_conn: list[list[int]] = []

    for li, sk_local in enumerate(skirt_locals):
        chain = chain_per_line[li]
        # beams 0 .. segments-2  : chain[k+1] ↔ chain[k]  (beam-only nodes)
        for seg in range(segments - 1):
            n1 = nc + chain[seg + 1]
            n2 = nc + chain[seg]
            new_conn.append([n1, n2, -1])
        # last beam (segments-1): skirt (canopy) ↔ chain[segments-1]
        n1 = int(sk_local)          # canopy node id (structure-local!)
        n2 = nc + chain[segments - 1]
        new_conn.append([n1, n2, -1])

    # Step 3 -- direction nodes (one per beam).
    # The (n1, n2) pair can mix canopy and beam-only nodes (the last beam of
    # each row has n1=canopy skirt).  We resolve each endpoint to its 3-D
    # coord before computing the perpendicular offset.
    dir_base = len(new_beams)
    for bi, (n1_sl, n2_sl, _) in enumerate(new_conn):
        if n1_sl < nc:
            p1 = can[n1_sl]  # canopy node coords
        else:
            p1 = new_beams[n1_sl - nc]
        if n2_sl < nc:
            p2 = can[n2_sl]
        else:
            p2 = new_beams[n2_sl - nc]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dz = p2[2] - p1[2]
        L = math.sqrt(dx * dx + dy * dy + dz * dz) + 1e-30
        ox = -dz / L
        oy = 0.0
        oz = dx / L
        dm = 0.5 * (p1[0] + p2[0]) + ox * 1e-4
        em = 0.5 * (p1[1] + p2[1]) + oy * 1e-4
        fm = 0.5 * (p1[2] + p2[2]) + oz * 1e-4
        new_beams.append([dm, em, fm])
        new_conn[bi][2] = nc + dir_base + bi

    assert all(n3 >= 0 for _n1, _n2, n3 in new_conn)
    assert len(new_conn) == n_lines * segments, (
        f"expected {n_lines*segments} beams, got {len(new_conn)}")

    return new_beams, new_conn, anchor_local_new


# ===========================================================================
# structured fluid box mesh
# ===========================================================================
def build_fluid(P):
    R = float(P("fluid_domain_in_k.R_native"))
    y0 = float(P("fluid_domain_in_k.y0"))
    y1 = float(P("fluid_domain_in_k.y1_native"))
    cx = float(P("fluid_domain_in_k.cx"))
    cz = float(P("fluid_domain_in_k.cz"))
    nx = int(P("fluid_domain_in_k.box_nx"))
    ny = int(P("fluid_domain_in_k.box_ny"))
    nz = int(P("fluid_domain_in_k.box_nz"))

    xs = [cx - R + 2 * R * i / nx for i in range(nx + 1)]
    ys = [y0 + (y1 - y0) * j / ny for j in range(ny + 1)]
    zs = [cz - R + 2 * R * k / nz for k in range(nz + 1)]

    def gid(i, j, k):
        return 1 + i * (ny + 1) * (nz + 1) + j * (nz + 1) + k

    nodes = [(xs[i], ys[j], zs[k])
             for i in range(nx + 1) for j in range(ny + 1)
             for k in range(nz + 1)]
    hexes = [(i, j, k) for i in range(nx) for j in range(ny)
             for k in range(nz)]
    inlet = [gid(i, 0, k) for i in range(nx + 1) for k in range(nz + 1)
             if (xs[i] - cx) ** 2 + (zs[k] - cz) ** 2 <= R ** 2 + 1e-12]

    segs_bottom = [[gid(i, 0, k), gid(i + 1, 0, k),
                    gid(i + 1, 0, k + 1), gid(i, 0, k + 1)]
                   for i in range(nx) for k in range(nz)]
    segs_top = [[gid(i, ny, k), gid(i, ny, k + 1),
                 gid(i + 1, ny, k + 1), gid(i + 1, ny, k)]
                for i in range(nx) for k in range(nz)]
    sides = []
    for j in range(ny):
        for k in range(nz):
            sides.append([gid(0, j, k), gid(0, j + 1, k),
                          gid(0, j + 1, k + 1), gid(0, j, k + 1)])
            sides.append([gid(nx, j, k), gid(nx, j, k + 1),
                          gid(nx, j + 1, k + 1), gid(nx, j + 1, k)])
    for i in range(nx):
        for j in range(ny):
            sides.append([gid(i, j, 0), gid(i + 1, j, 0),
                          gid(i + 1, j + 1, 0), gid(i, j + 1, 0)])
            sides.append([gid(i, j, nz), gid(i, j + 1, nz),
                          gid(i + 1, j + 1, nz), gid(i + 1, j, nz)])
    return {"nodes": nodes, "hexes": hexes, "inlet": sorted(set(inlet)),
            "segments": {"side": sides, "bottom": segs_bottom, "top": segs_top},
            "nfluid": len(nodes), "gid": gid}


# ===========================================================================
# mesh statistics (for build_log.json)
# ===========================================================================
def compute_mesh_stats(can, beams, beam_conn, flu, nq, tpl, segments):
    """Return a dict of human-readable mesh statistics."""
    nc = tpl["nc"]
    nbxyz = len(beams)
    nbc = len(beam_conn)

    # canopy shell area (approximate)
    shell_area = 0.0
    quads = tpl["quads"]
    for qi in range(nq):
        pids = [quads[4 * qi + a] for a in range(4)]
        # 4 points, average of 2 triangles
        pts = [can[p] for p in pids]

        def tri_area(a, b, c):
            import math as _m
            ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
            vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
            cx_ = uy * vz - uz * vy
            cy_ = uz * vx - ux * vz
            cz_ = ux * vy - uy * vx
            return 0.5 * _m.sqrt(cx_ * cx_ + cy_ * cy_ + cz_ * cz_)

        shell_area += tri_area(pts[0], pts[1], pts[2])
        shell_area += tri_area(pts[0], pts[2], pts[3])

    beam_length = 0.0
    for n1, n2, _n3 in beam_conn:
        b1 = beams[n1 - nc] if n1 >= nc else can[n1]
        b2 = beams[n2 - nc] if n2 >= nc else can[n2]
        beam_length += math.sqrt(
            (b1[0] - b2[0]) ** 2 + (b1[1] - b2[1]) ** 2
            + (b1[2] - b2[2]) ** 2)

    nfluid_nodes = flu["nfluid"]
    nfluid_solids = len(flu["hexes"])
    nfluid_total_nodes = nfluid_nodes + nc + nbxyz
    nfluid_total_elems = nq + nbc + nfluid_solids

    return {
        "结构": {
            "伞衣节点数_canopy_nodes": nc,
            "伞衣壳单元数_quads": nq,
            "伞衣总表面积_m2": round(shell_area, 6),
            "伞绳梁单元数_beams": nbc,
            "伞绳梁节点数_beam_nodes": nbxyz,
            "每绳分段数_segments_per_line": segments,
            "伞绳总长度_m": round(beam_length, 4),
            "结构总节点数": nc + nbxyz,
            "结构总单元数": nq + nbc,
        },
        "流体_K内置": {
            "流体节点数_nfluid_nodes": nfluid_nodes,
            "流体实体单元数_solids_in_k": nfluid_solids,
            "box_nx": int(len(set(pt[0] for pt in flu["nodes"])) - 1),
            "box_ny": int(len(set(pt[1] for pt in flu["nodes"])) - 1),
            "box_nz": int(len(set(pt[2] for pt in flu["nodes"])) - 1),
        },
        "总计": {
            "K文件总节点数_total_nodes": nfluid_total_nodes,
            "K文件总单元数_total_elements": nfluid_total_elems,
            "其中结构单元_structural": nq + nbc,
            "其中流体单元_fluid_solids": nfluid_solids,
        },
        "求解器运行_auto模式": {
            "说明": "实际参与 FSI 计算的流体网格由 solver_run_settings.nx/ny/nz 决定，"
                   "与 K 内置盒网格独立",
        },
    }


# ===========================================================================
# build_log.json  writer
# ===========================================================================
def _leaf_str(params: dict) -> dict:
    """Flatten params.json into {dotted.key:  value} for easy diffing."""
    flat = {}

    def walk(node, prefix=""):
        if isinstance(node, dict):
            if "值" in node and "单位" in node and "说明" in node:
                flat[prefix] = node["值"]
            else:
                for k, v in node.items():
                    walk(v, f"{prefix}.{k}" if prefix else k)

    walk(params)
    return flat


def _diff_params(old_flat: dict, new_flat: dict) -> list:
    """Return list of {key, old, new} for changed leaf values."""
    keys = sorted(set(old_flat) | set(new_flat))
    changes = []
    for k in keys:
        ov = old_flat.get(k, "<新增>")
        nv = new_flat.get(k, "<已删除>")
        if ov != nv:
            changes.append({"参数": k, "旧值": ov, "新值": nv})
    return changes


def write_build_log(params: dict, stats: dict, k_path: str, segments: int) -> str:
    """Write build_log.json next to the K file, with optional diff."""
    k_dir = os.path.dirname(os.path.abspath(k_path)) or "."
    fname = _try_leaf(lambda k: _leaf(params, k),
                       "output.build_log_filename") or "build_log.json"
    log_path = os.path.join(k_dir, fname)

    prev = None
    if os.path.exists(log_path):
        try:
            prev = json.load(open(log_path, encoding="utf-8"))
        except Exception:
            prev = None

    new_flat = _leaf_str(params)
    old_flat = _leaf_str(prev["参数快照"]) if prev and "参数快照" in prev else {}
    changes = _diff_params(old_flat, new_flat)

    # pretty summary
    summary_lines = []
    summary_lines.append("=== 生成日志 make_kfile.exe  ===")
    summary_lines.append(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    summary_lines.append(f"K 文件: {k_path}")
    summary_lines.append("")
    summary_lines.append("--- 参数变更 ---")
    if changes:
        for c in changes:
            summary_lines.append(
                f"  {c['参数']}: {c['旧值']!r} → {c['新值']!r}")
    else:
        summary_lines.append("  (与上次相比无参数变化)")
    summary_lines.append("")
    summary_lines.append("--- 网格统计 ---")
    for group_name, group_vals in stats.items():
        summary_lines.append(f"  [{group_name}]")
        if isinstance(group_vals, dict):
            for kk, vv in group_vals.items():
                summary_lines.append(f"    {kk}: {vv}")
    summary_lines.append("")
    summary_lines.append(f"  K 文件总节点数: {stats['总计']['K文件总节点数_total_nodes']}")
    summary_lines.append(f"  K 文件总单元数: {stats['总计']['K文件总单元数_total_elements']}")

    log = {
        "版本": "1.0",
        "生成时间": time.strftime('%Y-%m-%d %H:%M:%S'),
        "K文件路径": os.path.abspath(k_path),
        "伞绳分段数_segments_per_line": segments,
        "参数变更diff": changes,
        "网格统计": stats,
        "参数快照": params,  # full snapshot for future diff
        "_summary_text": "\n".join(summary_lines),
    }
    with open(log_path, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=2)

    # also print summary to stdout
    print("\n".join(summary_lines))
    return log_path


# ===========================================================================
# helper: try leaf access (returns None if missing)
# ===========================================================================
def _try_leaf(P, dotted: str):
    try:
        return _leaf(P, dotted)
    except (KeyError, TypeError):
        return None


def _leaf(params: dict, dotted: str):
    node = params
    for part in dotted.split("."):
        node = node[part]
    if isinstance(node, dict) and "值" in node:
        return node["值"]
    return node


# ===========================================================================
# K file assembly
# ===========================================================================
def generate(params: dict, tpl: dict, out_path: str) -> tuple:
    """Write K file and return (beams, beam_conn, segments, stats_dict)."""
    P = lambda key: _leaf(params, key)  # noqa: E731
    L: list[str] = []

    def w(line=""):
        L.append(line)

    can, beams_orig, anchor_y = transform_geometry(tpl, P)

    # resample beam chains
    segments = int(P("suspension_lines.line_segments"))
    beams_new, beam_conn_new, anchor_local_new = resample_beam_chains(
        tpl, P, can, anchor_y)

    flu = build_fluid(P)
    Nf = flu["nfluid"]
    nc = tpl["nc"]
    nq = tpl["nq"]
    nbc = len(beam_conn_new)  # resampled

    def cg(local_or_gid: int) -> int:
        return Nf + 1 + local_or_gid

    def bg(beam_local: int) -> int:
        return Nf + 1 + beam_local

    # ---- header -----------------------------------------------------------
    w("$# LS-DYNA Keyword file generated by make_kfile.exe (paramk)")
    w("*KEYWORD")
    w("*TITLE")
    w(str(P("solver_cards_in_k.title")))

    # ---- velocity curve ----------------------------------------------------
    vy = float(P("inflow_air.Vy"))
    t_ramp = float(P("velocity_curve.ramp_time"))
    t_hold = float(P("velocity_curve.hold_end"))
    t_endc = float(P("velocity_curve.table_end_time"))
    w("*DEFINE_CURVE")
    w("$#    lcid      sidr       sfa       sfo      offa      offo    dattyp     lcint")
    w(i10(int(P("velocity_curve.lcid")), 0, 1.0, 1.0, 0.0, 0.0, 0, 0))
    w("$#                a1                  o1")
    for a, o in ((0.0, 0.0), (1.0e-4, vy / 220.0), (t_ramp, vy),
                 (t_hold, vy), (t_endc, vy)):
        w(f"{a:20.9E}{o:20.9E}")

    # ---- contact -----------------------------------------------------------
    if bool(P("solver_cards_in_k.contact_enabled_in_k")):
        w("*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID")
        w(i10(1) + "ASingSurf_1")
        w(i10(11, 0, 3, 0, 0, 0, 0))
        w(i10(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.01, 1.0e20))
        w(i10(1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0))

    # ---- parts / sections / materials -------------------------------------
    t_fab = float(P("canopy.fabric_thickness"))
    w("*PART"); w("Para_Surf")
    w(i10(11, 11, 21, 0, 0, 0, 0))
    w("*SECTION_SHELL")
    w("$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp")
    w(i10(11, 5, 1.0, 3, 1.0, 0, 0, 1))
    w(i10(t_fab, t_fab, t_fab, t_fab, 0.0, 0.0, 0.0, 0))
    ro_c = float(P("canopy.fabric_density"))
    ea = float(P("canopy.fabric_E"))
    eb = float(P("canopy.fabric_EB"))
    nu_c = float(P("canopy.fabric_nu"))
    w("*MAT_FABRIC")
    w("$#     mid        ro        ea        eb         -      prba      prab         -")
    w(i10(21, ro_c, ea, eb, 0.0, nu_c, 0.0, 0.0))
    w(i10(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
    w(i10(0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0.0))
    w(i10(0.0, 0.0, 0, 0.0, 0.0, 0.0, 0.0, 0.0))
    w(i10(0.0, 0.0, 0, 0.0, 0.0, 0.0, 0.0, 0.0))

    area_l = float(P("suspension_lines.line_area"))
    ts = math.sqrt(area_l)
    w("*PART"); w("PARA_String")
    w(i10(12, 12, 22, 0, 0, 0, 0))
    w("*SECTION_BEAM")
    w("$#   secid    elform      shrf   qr/irid       cst     scoor       nsm     naupd")
    w(i10(12, 1, 1.0, 0.0, 2, 0.0, 0.0, 0))
    w(i10(ts, ts, ts, ts, 0.0, 0.0))
    w("*MAT_PLASTIC_KINEMATIC")
    w("$#     mid        ro         e        pr      sigy      etan      beta")
    w(i10(22, float(P("suspension_lines.line_density")),
          float(P("suspension_lines.line_E")), float(P("suspension_lines.line_nu")),
          float(P("suspension_lines.line_yield")), 0.0, 0.0))
    w(i10(0.0, 0.0, 0.0, 0.0))

    ro_a = float(P("inflow_air.air_density"))
    P0 = float(P("inflow_air.ambient_pressure"))
    e0 = P0 / (float(P("inflow_air.gamma")) - 1.0)
    w("*PART"); w("Air")
    w(i10(14, 14, 24, 24, 2, 0, 0))
    w("*SECTION_SOLID")
    w(i10(14, 11, 1))
    w("*MAT_NULL")
    w("$#     mid        ro        pc        mu     terod     cerod        ym        pr")
    w(i10(24, ro_a, float(P("inflow_air.air_pc")), float(P("inflow_air.air_mu")),
          0.0, 0.0, 0.0, 0.0))
    w("*EOS_LINEAR_POLYNOMIAL")
    w("$#   eosid        c0        c1        c2        c3        c4        c5        c6")
    gmc = float(P("inflow_air.gamma")) - 1.0
    w(i10(24, 0.0, 0.0, 0.0, 0.0, gmc, gmc, 0.0))
    w(i10(e0, 1.0))

    w("*HOURGLASS")
    w(i10(1, int(P("solver_cards_in_k.hg_ihq")), float(P("solver_cards_in_k.hg_qh"))))

    # ---- fluid solid elements ---------------------------------------------
    w("*ELEMENT_SOLID (ten nodes format)")
    eid0 = nq + nbc + 1
    for k_i, (i, j, k) in enumerate(flu["hexes"]):
        g = flu["gid"]
        n = [g(i, j, k), g(i + 1, j, k), g(i + 1, j + 1, k), g(i, j + 1, k),
             g(i, j, k + 1), g(i + 1, j, k + 1), g(i + 1, j + 1, k + 1),
             g(i, j + 1, k + 1)]
        w(f"{eid0 + k_i:8d}{14:8d}")
        w("".join(f"{v:8d}" for v in n) + f"{0:8d}{0:8d}")

    # ---- shells -------------------------------------------------------------
    w("*ELEMENT_SHELL")
    quads = tpl["quads"]
    for qi in range(nq):
        q = [quads[4 * qi + a] for a in range(4)]
        w(f"{qi + 1:8d}{11:8d}" + "".join(f"{cg(q[a]):8d}" for a in range(4))
          + f"{0:8d}{0:8d}{0:8d}{0:8d}")

    # ---- beams  (resampled!) ------------------------------------------------
    w("*ELEMENT_BEAM")
    for bi, (n1, n2, n3) in enumerate(beam_conn_new):
        w(f"{nq + 1 + bi:8d}{12:8d}{bg(n1):8d}{bg(n2):8d}{bg(n3):8d}"
          + f"{0:8d}{0:8d}{0:8d}{0:8d}{2:8d}")

    # ---- databases ----------------------------------------------------------
    for key in ("DATABASE_DISBOUT", "DATABASE_GLSTAT", "DATABASE_MATSUM",
                "DATABASE_NODOUT"):
        w(f"*{key}")
        w(i10(1.0e-3, 0.0, 0.0, 0.0))
    w("*DATABASE_BINARY_D3PLOT")
    w(i10(0.005, 0.0, 0.0, 0.0, 0.0, 1, 0.0, 0.0, 0.0, 0.0)[:10 * 10])

    # ---- nodes (fluid first, then canopy, then beam-only) ------------------
    w("*NODE")
    nid = 0
    for (x, y, z) in flu["nodes"]:
        nid += 1
        w(node_line(nid, x, y, z))
    for i, pnt in enumerate(can):
        nid += 1
        w(node_line(nid, pnt[0], pnt[1], pnt[2]))
    for pnt in beams_new:
        nid += 1
        w(node_line(nid, pnt[0], pnt[1], pnt[2]))

    # ---- coupling / boundaries ---------------------------------------------
    w("*CONSTRAINED_LAGRANGE_IN_SOLID_TITLE")
    w(i10(200) + "ConLagSolid_200")
    w(i10(2, 11, 0, 0, int(P("solver_cards_in_k.clis_nquad")),
          int(P("solver_cards_in_k.clis_ctype")),
          int(P("solver_cards_in_k.clis_direc")), 0))
    w(i10(0.0, 1.0e20, float(P("solver_cards_in_k.clis_pfac")), 0.0,
          float(P("solver_cards_in_k.clis_frcmin")), 0, 0, 0.0))
    w(i10(0.0, 0.0, 0.0, int(P("solver_cards_in_k.clis_ileak")),
          float(P("solver_cards_in_k.clis_pleak")), 0, 0, 0))
    w(i10(0, 0, 0, 0, 1.0, 0, 1.0))

    w("*BOUNDARY_NON_REFLECTING"); w(i10(100, 0, 0, 0))
    w("*BOUNDARY_NON_REFLECTING"); w(i10(102, 0, 0, 0))
    w("*BOUNDARY_NON_REFLECTING"); w(i10(104, 0, 0, 0))

    w("*BOUNDARY_PRESCRIBED_MOTION_SET")
    w(i10(23, 2, 0, int(P("velocity_curve.lcid")), 1.0, 0, 1.0e28, 0.0))
    w("*BOUNDARY_SPC_SET")
    w(i10(22, 0, 1, 1, 1, 1, 1, 1))

    # anchor_gid uses the RESAMPLED anchor_local
    anchor_gid = bg(anchor_local_new)
    w("*SET_NODE_LIST")
    w("$#     sid       da1       da2       da3       da4    solver")
    w(i10(22, 0.0, 0.0, 0.0, 0.0))
    w("".join(f"{anchor_gid:10d}" + f"{0:10d}" * 7))
    w("*SET_NODE_LIST")
    w(i10(23, 0.0, 0.0, 0.0, 0.0))
    ids = sorted(flu["inlet"])
    for i in range(0, len(ids), 8):
        w("".join(f"{v:10d}" for v in ids[i:i + 8])
          + f"{0:10d}" * (8 - len(ids[i:i + 8])))

    # ---- controls -----------------------------------------------------------
    w("*CONTROL_ALE")
    w(i10(2, 1, 2, -1.0, 0.0, 0.0, 0.0, 0.0))
    w(i10(0.0, 1.0e20, 1.0, 1.0e-6, 0, 0, P0, 0))
    w(i10(1, 50, 0, 0.0, 0.0, 0.0, 0.0, 0.0))
    w("*CONTROL_BULK_VISCOSITY")
    w(i10(float(P("solver_cards_in_k.bulk_q1")),
          float(P("solver_cards_in_k.bulk_q2")), 1, 0))
    w("*CONTROL_ENERGY"); w(i10(2, 2, 2, 2, 2))
    w("*CONTROL_HOURGLASS")
    w(i10(int(P("solver_cards_in_k.hg_ihq")),
          float(P("solver_cards_in_k.hg_qh"))))
    w("*CONTROL_SHELL")
    w(i10(float(P("solver_cards_in_k.shell_wrpang")), 1, -1, 0,
          int(P("solver_cards_in_k.shell_theory")),
          int(P("solver_cards_in_k.shell_bwc")), 1, 0))
    w(i10(1.0, 0.0, 0.0, 1.0, 0.0))
    w(i10(0, 0, 0, 0, 2, 0.0, 0.0, 0.0))
    w(i10(0, 0, 0, 0, 0, 0, 1.0, 0.0))
    w("*CONTROL_TERMINATION")
    w(i10(float(P("solver_cards_in_k.endtim")), 0, 0.0, 0.0, 0.0, 0.0))
    w("*CONTROL_TIMESTEP")
    w(i10(0.0, float(P("solver_cards_in_k.tssfac")), 0, 0.0, 0.0, 0.0, 0.0))
    w(i10(0.0, 0.0, 0.0, 0.0))

    # ---- sets ---------------------------------------------------------------
    for sid, pids in ((2, (11, 12)), (3, (11,)), (4, (12,)), (11, (14,))):
        w("*SET_PART_LIST")
        w(i10(sid, 0.0, 0.0, 0.0, 0.0))
        w("".join(f"{v:10d}" for v in pids) + f"{0:10d}" * (8 - len(pids)))

    def segment_block(sid, quads_):
        w("*SET_SEGMENT")
        w(i10(sid, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        for q in quads_:
            w(i10(*q))

    segment_block(100, flu["segments"]["side"])
    segment_block(102, flu["segments"]["bottom"])
    segment_block(104, flu["segments"]["top"])

    w("*END")
    with open(out_path, "w", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")

    stats = compute_mesh_stats(can, beams_new, beam_conn_new, flu, nq, tpl, segments)
    return stats, segments


# ===========================================================================
# solver run-bat emitter
# ===========================================================================
RUN_BAT = """@echo off
setlocal
cd /d "%~dp0"
rem ============================================================
rem  Run the ALE solver on the generated K file (T5J settings)
rem  Generated from params.json by make_kfile.exe - do not edit.
rem ============================================================
set "SOLVER=%~dp0run_parachute.exe"
set "KFILE=%~dp0{K}"
if not exist "%SOLVER%" goto :nosolver
"%SOLVER%" --k "%KFILE%" --outdir {OUT} --mesh {MESH} --nx {NX} --ny {NY} --nz {NZ} --domain-radius {DR} --y1-extension {Y1E} --cfl {CFL} --omega {OMEGA} --cdamp {CDAMP} --fsi-mach-cap {MCAP} --constant-vel {VEL} --endtime {ET} --vtk-every {VTK} --tssfac {TSS} --vent-radius {VENT} --bend-scale {BEND} --bend-damp {BENDD} --struct-damping {SD} --struct-damping-vmax {SVM} --eb-frac {EBF} {TENS} {NOCONTACT} --generate-report
if errorlevel 1 goto :failed
echo.
echo === Done === Report: {OUT}\\calculation_report.html
pause
exit /b 0
:nosolver
echo [ERROR] run_parachute.exe not found next to this script.
echo Copy run_parachute.exe from the T5J delivery package here.
pause
exit /b 1
:failed
echo [ERROR] Solver exited with an error. See messages above.
pause
exit /b 1
"""


def write_run_bat(params: dict, k_filename: str, dirpath: str) -> str:
    P = lambda key: _leaf(params, key)  # noqa: E731
    R = params["solver_run_settings"]
    kv = lambda k: R[k]["值"]
    flags = {
        "K": k_filename,
        "OUT": P("output.results_dirname"),
        "MESH": str(kv("mesh_mode")), "NX": kv("nx"), "NY": kv("ny"), "NZ": kv("nz"),
        "DR": kv("domain_radius"), "Y1E": kv("y1_extension"), "CFL": kv("cfl"),
        "OMEGA": kv("omega"), "CDAMP": kv("cdamp"), "MCAP": kv("fsi_mach_cap"),
        "VEL": P("inflow_air.Vy"), "ET": kv("endtime"), "VTK": kv("vtk_every"),
        "TSS": P("solver_cards_in_k.tssfac"), "VENT": kv("vent_radius"),
        "BEND": kv("bend_scale"), "BENDD": kv("bend_damp"),
        "SD": kv("struct_damping"), "SVM": kv("struct_damping_vmax"),
        "EBF": P("canopy.eb_fraction"),
        "TENS": "--tension-only-membrane" if P("canopy.tension_only_membrane") else "",
        "NOCONTACT": "--no-contact" if not kv("contact_enabled") else "",
    }
    txt = RUN_BAT
    for key, val in flags.items():
        txt = txt.replace("{" + key + "}", str(val))
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    path = os.path.join(dirpath, "run_solver.bat")
    with open(path, "w", newline="\r\n") as fh:
        fh.write(txt)
    return path


# ===========================================================================
# CLI
# ===========================================================================
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate a parametric LS-DYNA .k file from params.json")
    ap.add_argument("--params", default="params.json", help="params.json path")
    ap.add_argument("--template", default=None, help="override _template.pkb.gz")
    ap.add_argument("--output", default=None, help="output .k path "
                    "(default: output.output_k_filename in params.json)")
    ap.add_argument("--outdir", default=None, help="write K, run_solver.bat "
                    "and build_log.json into this directory")
    ap.add_argument("--no-bat", action="store_true")
    ap.add_argument("--no-log", action="store_true",
                    help="skip writing build_log.json")
    args = ap.parse_args(argv)

    with open(args.params, encoding="utf-8") as fh:
        params = json.load(fh)
    tpl = load_template(args.template)

    k_name = args.output or _leaf(params, "output.output_k_filename")
    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
        k_path = os.path.join(args.outdir, os.path.basename(k_name))
    else:
        k_path = k_name

    stats, segments = generate(params, tpl, k_path)
    k_size = os.path.getsize(k_path) / 1024
    total_nodes = stats["总计"]["K文件总节点数_total_nodes"]
    total_elems = stats["总计"]["K文件总单元数_total_elements"]
    print(f"[kgen] wrote {os.path.abspath(k_path)} ({k_size:.0f} KB)")
    print(f"[kgen]  mesh: {total_nodes} nodes, {total_elems} elems "
          f"(beams={stats['结构']['伞绳梁单元数_beams']}, "
          f"quads={stats['结构']['伞衣壳单元数_quads']}, "
          f"solids={stats['流体_K内置']['流体实体单元数_solids_in_k']})")

    # write build_log.json
    log_enabled = _try_leaf(lambda k: _leaf(params, k), "output.write_build_log")
    if not args.no_log and log_enabled is not False:
        lp = write_build_log(params, stats, k_path, segments)
        print(f"[kgen] wrote build log -> {lp}")

    if not args.no_bat:
        d = args.outdir or os.path.dirname(os.path.abspath(k_path)) or "."
        bp = write_run_bat(params, os.path.basename(k_path), d)
        print(f"[kgen] wrote {bp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
