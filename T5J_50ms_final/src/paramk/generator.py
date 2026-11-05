"""Parametric LS-DYNA keyword (.k) generator for the ALE parachute model.

Pure standard library (json / math / gzip / struct / array) so it can be
frozen into a small dependency-free Windows executable.

Inputs : params.json (all editable values, Chinese annotations)
Outputs: a new .k file with identical topology to the reference model but with
         canopy / suspension-line / air / solver parameters taken from
         params.json.  The produced file is consumed directly by
         run_parachute.exe (the ALE solver) in the T5J delivery package.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import struct
import sys
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
# geometry transforms
# ===========================================================================
def transform_geometry(tpl: dict, P: dict) -> tuple:
    """Return (canopy_xyz list[[x,y,z]], beam_xyz list[[x,y,z]])."""
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

    # skirt attachment geometry after canopy scaling
    sk_locals = list(tpl["skirt"])
    sk_pts = [can[i] for i in sk_locals]
    sk_y = sum(p[1] for p in sk_pts) / len(sk_pts)
    sk_r0 = tpl["meta"]["skirt_attach_radius"]
    sk_r1 = math.sqrt(
        sum(p[0] ** 2 + p[2] ** 2 for p in sk_pts) / len(sk_pts))

    # suspension-line chains
    line_L = float(P("suspension_lines.line_length"))
    anchor_y = sk_y - math.sqrt(max(line_L ** 2 - sk_r1 ** 2, 0.0))

    bxyz = tpl["beam_xyz"]
    nb = tpl["nbxyz"]
    beams = [list(tpl["beam_xyz"][3 * i:3 * i + 3]) for i in range(nb)]
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
# K file assembly
# ===========================================================================
def generate(params: dict, tpl: dict, out_path: str) -> None:
    P = lambda key: _leaf(params, key)  # noqa: E731
    L: list[str] = []

    def w(line=""):
        L.append(line)

    can, beams, anchor_y = transform_geometry(tpl, P)
    flu = build_fluid(P)
    Nf = flu["nfluid"]
    nc = tpl["nc"]
    nq = tpl["nq"]
    nbc = tpl["nbc"]

    def cg(local_or_gid: int) -> int:
        """canopy node local id -> global id."""
        return Nf + 1 + local_or_gid

    def bg(beam_local: int) -> int:
        """structure-local beam-node index -> global id."""
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
        w(i10(11, 0, 3, 0, 0, 0, 0, 0))
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

    # ---- beams --------------------------------------------------------------
    w("*ELEMENT_BEAM")
    for bi in range(nbc):
        n1 = tpl["beam_conn"][3 * bi]
        n2 = tpl["beam_conn"][3 * bi + 1]
        n3 = tpl["beam_conn"][3 * bi + 2]
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
    for pnt in beams:
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

    anchor_gid = bg(tpl["anchor_local"])
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


# ===========================================================================
# params helpers
# ===========================================================================
def _leaf(params: dict, dotted: str):
    node = params
    for part in dotted.split("."):
        node = node[part]
    if isinstance(node, dict) and "值" in node:
        return node["值"]
    return node


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
        "K": k_filename, "OUT": kv("results_dirname") if False else P("output.results_dirname"),
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
    # collapse the double spaces left by empty optional flags
    import re as _re
    txt = _re.sub(r"[ \t]{2,}", " ", txt)
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
    ap.add_argument("--outdir", default=None, help="write K and run_solver.bat "
                    "into this directory")
    ap.add_argument("--no-bat", action="store_true")
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
    generate(params, tpl, k_path)
    print(f"[kgen] wrote {os.path.abspath(k_path)} "
          f"({os.path.getsize(k_path)/1024:.0f} KB)")

    if not args.no_bat:
        d = args.outdir or os.path.dirname(os.path.abspath(k_path)) or "."
        bp = write_run_bat(params, os.path.basename(k_path), d)
        print(f"[kgen] wrote {bp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
