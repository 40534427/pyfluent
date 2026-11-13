#!/usr/bin/env python3
"""Command line driver: solve the 3-D parachute inflation with an ALE fluid.

Example
-------
    python run_parachute.py --k Parachute.k --nx 20 --ny 32 --nz 20 \
                            --endtime 0.02 --vel-scale 0.2 --vtk-every 0.005
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aleparachute import (load_model, auto_cylinder_grid, native_grid,  # noqa: E402
                          fluid_geometry, Simulation, Options)
from aleparachute.report import generate_report, get_cpu_info  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ALE / Lagrangian penalty coupling solver for the "
                    "parachute inflation K file.")
    p.add_argument("--k", help="LS-DYNA keyword file "
                               "(required unless --report-only is used)")
    p.add_argument("--mesh", choices=("auto", "native"), default="auto",
                   help="auto = cartesian grid clipped to the K file cylinder, "
                        "native = reuse *ELEMENT_SOLID (large, slow)")
    p.add_argument("--nx", type=int, default=20, help="auto grid cells in x")
    p.add_argument("--ny", type=int, default=32, help="auto grid cells in y")
    p.add_argument("--nz", type=int, default=20, help="auto grid cells in z")
    p.add_argument("--domain-radius", type=float, default=None,
                   help="override the cylinder radius of the auto grid [m] "
                        "(default: K-file fluid domain).  Enlarging it removes "
                        "the blockage of the canopy; the whole inlet layer is "
                        "then driven")
    p.add_argument("--y1-extension", type=float, default=0.0,
                   help="extend the downstream (y1) boundary of the auto grid "
                        "by this many metres [m] (default 0).  Gives the wake "
                        "more room to develop before the non-reflecting outlet")
    p.add_argument("--endtime", type=float, default=None,
                   help="physical end time [s] (default: *CONTROL_TERMINATION)")
    p.add_argument("--vel-scale", type=float, default=1.0,
                   help="scale factor on the prescribed velocity curve")
    p.add_argument("--constant-vel", type=float, default=None,
                   help="override the inlet velocity with this constant value "
                        "[m/s] (ignores the K-file curve ramp)")
    p.add_argument("--cfl", type=float, default=0.5)
    p.add_argument("--tssfac", type=float, default=0.9)
    p.add_argument("--mass-scale", type=float, default=1.0,
                   help="scale the structure mass (explicit-FSI added-mass aid)")
    p.add_argument("--omega", type=float, default=0.2,
                   help="under-relaxation of the exchanged traction (0..1)")
    p.add_argument("--cdamp", type=float, default=1.0,
                   help="acoustic impedance damping coefficient of the penalty")
    p.add_argument("--fsi-implicit", action="store_true",
                   help="treat the penalty stiffness semi-implicitly, which "
                        "removes the CLLS sqrt(m/k) step limit (use together "
                        "with --max-dt; the default explicit scheme is the "
                        "validated physics)")
    p.add_argument("--threads", type=int, default=0,
                   help="worker threads for the element kernels (0 = auto, "
                        "1 = serial)")
    p.add_argument("--max-dt", type=float, default=0.0,
                   help="hard cap on the time step [s] (0 = no cap; e.g. 3e-6 "
                        "to keep the structure stable during the inflation peak)")
    p.add_argument("--fsi-mach-cap", type=float, default=0.3,
                   help="max Mach number of the velocity increment fed back "
                        "into a fluid cell (0 = no cap)")
    p.add_argument("--no-fsi-leak", action="store_true",
                   help="disable the CLLS leakage control (card ILEAK)")
    p.add_argument("--pleak", type=float, default=None,
                   help="leakage coefficient PLEAK (default: K file)")
    p.add_argument("--leak-cap", type=float, default=None,
                   help="per-step mass-leak cap as a fraction of donor-cell "
                        "mass (default: 0.1); raise for strong inflation")
    p.add_argument("--p-cap", type=float, default=None,
                   help="cap of the pressure perturbation (p - p_ref) that "
                        "enters the coupling traction [Pa] (default: no cap; "
                        "use ~1e6 for constant 220 m/s to avoid trapped-air "
                        "runaway)")
    p.add_argument("--pfac", type=float, default=None,
                   help="override the CLLS penalty stiffness multiplier "
                        "(default: K file value = 0.1; try 0.5 or 1.0 for "
                        "stronger fluid-structure binding)")
    p.add_argument("--eb-stab-frac", type=float, default=None,
                   help="override eb_stab / ea stabilising modulus for the "
                        "membrane b-direction (default: 0.001; try 0.005 or "
                        "0.01 to resist wrinkling)")
    p.add_argument("--eb-frac", type=float, default=None,
                   help="explicit eb / ea for the membrane b-direction "
                        "(overrides --eb-stab-frac; T4 uses 0.3)")
    p.add_argument("--tension-only-membrane", action="store_true",
                   help="slack-fibre membrane: a compressed fibre direction "
                        "carries no stress (*MAT_FABRIC semantics)")
    p.add_argument("--vent-radius", type=float, default=0.02,
                   help="radius [m] of a tension-only reinforcement ring "
                        "threaded through the apex nodes; the ring is slack "
                        "until the vent opens to this radius (0 = off). "
                        "Default 0.02 m; use smaller for a tighter vent")
    p.add_argument("--vent-ring-E-factor", type=float, default=5.0,
                   help="elastic-modulus multiplier for the vent ring "
                        "beams relative to the suspension lines (default 5.0); "
                        "0 = rigid hoop enforced by radial projection, which "
                        "keeps the vent at the design radius without the tiny "
                        "chord acoustic time-step limit")
    p.add_argument("--vent-ring-A-factor", type=float, default=2.0,
                   help="cross-sectional-area multiplier for the vent ring "
                        "beams relative to the suspension lines (default 2.0)")
    p.add_argument("--hg-qh", type=float, default=0.1,
                   help="*CONTROL_HOURGLASS qh for the quad flap mode")
    p.add_argument("--struct-damping", type=float, default=0.0,
                   help="mass-proportional velocity damping [1/s] "
                        "(0 = off; use ~50-500 for constant high-speed inflow)")
    p.add_argument("--struct-damping-vmax", type=float, default=0.0,
                   help="smart damping: when > 0 the damping turns OFF above "
                        "this node-vmax threshold (m/s) and fully ON below ~60%% "
                        "of it, so fast inflation is not suppressed while the "
                        "post-peak ring-down is damped.  Typical 20-50 m/s")
    p.add_argument("--bend-scale", type=float, default=0.0,
                   help="amplification of the edge-hinge plate bending "
                        "stiffness D = E t^3 / (12 (1-nu^2)).  1 = physical "
                        "fabric, 0 = pure membrane (LS-DYNA BWC=2); use "
                        "~1e3 to suppress membrane wrinkling")
    p.add_argument("--bend-damp", type=float, default=0.5,
                   help="viscous damping ratio of the bending hinges")
    p.add_argument("--theory", type=int, default=None,
                   help="*CONTROL_SHELL THEORY override (default: K file)")
    p.add_argument("--bwc", type=int, default=None,
                   help="*CONTROL_SHELL BWC override (default: K file)")
    p.add_argument("--ihq", type=int, default=None,
                   help="*CONTROL_HOURGLASS IHQ override (default: K file)")
    p.add_argument("--no-contact", action="store_true",
                   help="disable the automatic single-surface self contact")
    p.add_argument("--contact-scale", type=float, default=1.0,
                   help="penalty stiffness multiplier of the self contact")
    p.add_argument("--contact-vdc", type=float, default=None,
                   help="viscous damping coefficient (card VDC)")
    p.add_argument("--contact-thk-scale", type=float, default=1.0,
                   help="multiplication of the contact thickness")
    p.add_argument("--no-coupling", action="store_true",
                   help="disable the penalty fluid-structure coupling")
    p.add_argument("--vtk-every", type=float, default=0.0,
                   help="write VTK states every dt [s] (0 = final state only)")
    p.add_argument("--outdir", default="out")
    p.add_argument("--checkpoint-every", type=float, default=0.02,
                   help="write checkpoint.npz every this many seconds "
                        "(default 0.02; <=0 = every VTK state)")
    p.add_argument("--restart", default="",
                   help="resume a long run from the checkpoint.npz written "
                        "alongside the VTK states (e.g. "
                        "--restart outdir/checkpoint.npz)")
    p.add_argument("--max-steps", type=int, default=100000)
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--generate-report", action="store_true",
                   help="after the run, generate the full calculation report "
                        "(HTML + figures + .dat tables + video) in --outdir")
    p.add_argument("--report-only", action="store_true",
                   help="skip the solve and rebuild the report from the "
                        "existing outputs + run_meta.json (combine with "
                        "--wall-time to correct the recorded duration)")
    p.add_argument("--wall-time", type=float, default=None,
                   help="wall-clock seconds to record in the report "
                        "(normally measured automatically)")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.report_only:
        print("rebuilding report from existing outputs ...")
        generate_report(args.outdir, wall_time=args.wall_time)
        print(f"  report: {os.path.join(args.outdir, 'calculation_report.html')}")
        return 0
    if not args.k:
        parser.error("--k is required unless --report-only is used")

    print(f"reading {args.k} ...")
    model = load_model(args.k)
    print(f"  title : {model.title}")
    print(f"  parts : {[(p, v['title']) for p, v in model.parts.items()]}")
    print(f"  shell quads {model.mesh['shell_conn'].shape[0]}, "
          f"beams {model.mesh['beam_conn'].shape[0]}, "
          f"solids {model.mesh['solid_conn'].shape[0]}")

    if args.mesh == "native":
        print("building native ALE grid from *ELEMENT_SOLID ...")
        grid = native_grid(model)
    else:
        y0, y1, r, cx, cz = fluid_geometry(model)
        if args.domain_radius is not None:
            r = float(args.domain_radius)
            print(f"fluid domain radius overridden: R={r:.4f} m "
                  f"(K file: {fluid_geometry(model)[2]:.4f} m)")
        if args.y1_extension > 0.0:
            y1 = y1 + float(args.y1_extension)
            print(f"fluid domain downstream extended: y1={y1:.4f} m "
                  f"(+{args.y1_extension:.4f} m)")
        print(f"fluid domain y=[{y0:.4f},{y1:.4f}] R={r:.4f} centre=({cx:.4f},{cz:.4f})")
        grid = auto_cylinder_grid(y0, y1, r, args.nx, args.ny, args.nz, cx, cz)
    print(f"  grid: {grid.boundary_info()}")

    opt = Options(
        endtime=args.endtime if args.endtime is not None
        else float(model.controls.get("CONTROL_TERMINATION", {}).get("endtim", 0.02)),
        vel_scale=args.vel_scale, constant_vel=args.constant_vel, cfl=args.cfl, tssfac=args.tssfac,
        mass_scale=args.mass_scale, omega=args.omega, cdamp=args.cdamp,
        fsi_implicit=args.fsi_implicit, threads=args.threads,
        max_dt=args.max_dt,
        fsi_mach_cap=args.fsi_mach_cap, fsi_leak=not args.no_fsi_leak,
        drive_full_inlet_layer=args.domain_radius is not None,
        pleak=args.pleak, leak_cap=args.leak_cap, p_cap=args.p_cap,
        pfac=args.pfac, eb_stab_frac=args.eb_stab_frac,
        eb_frac=args.eb_frac, membrane_tension_only=args.tension_only_membrane,
        vent_radius=args.vent_radius,
        vent_ring_E_factor=args.vent_ring_E_factor,
        vent_ring_A_factor=args.vent_ring_A_factor,
        hg_qh=args.hg_qh, struct_damping=args.struct_damping,
        struct_damping_vmax=args.struct_damping_vmax,
        bend_scale=args.bend_scale, bend_damp=args.bend_damp,
        theory=args.theory, bwc=args.bwc, ihq=args.ihq,
        contact=not args.no_contact, contact_scale=args.contact_scale,
        contact_vdc=args.contact_vdc,
        contact_thk_scale=args.contact_thk_scale,
        coupling=not args.no_coupling, vtk_every=args.vtk_every,
        checkpoint_every=args.checkpoint_every,
        outdir=args.outdir, max_steps=args.max_steps, verbose=not args.quiet,
        restart=args.restart, kfile=os.path.abspath(args.k),
        nx=(0 if args.mesh == "native" else args.nx),
        ny=(0 if args.mesh == "native" else args.ny),
        nz=(0 if args.mesh == "native" else args.nz),
        y1_extension=(args.y1_extension if args.mesh != "native" else 0.0),
        domain_radius=(args.domain_radius or 0.0),
    )
    sim = Simulation(model, grid, opt)
    st = sim.struct
    print(f"structure: {st.summary()}  fixed={st.fixed.size} driven={st.driven.size}")
    print(f"driven fluid cells: {sim.driven_cells.size}")
    gas = sim.fluid.gas
    print(f"gas: rho0={gas.rho0:.4f}  e0={gas.e0:.1f}  ambient p0={gas.c4 * gas.e0:.1f} Pa  "
          f"pref={gas.pref:.1f} Pa")

    conditions = None
    try:
        from aleparachute.report import conditions_from_objects, write_run_meta
        conditions = conditions_from_objects(model, opt, grid, sim)
        write_run_meta(args.outdir, {
            "kfile": {"path": os.path.abspath(args.k),
                      "name": os.path.basename(args.k)},
            "options": {k: v for k, v in vars(opt).items()
                        if isinstance(v, (bool, int, float, str)) or v is None},
            "conditions": conditions,
            "cpu": get_cpu_info(),
            "run": {"start": __import__("datetime").datetime.now().isoformat(
                timespec="seconds"), "wall_time": None, "steps": None},
        }, merge=False)
    except Exception as exc:
        print(f"[meta] WARNING: {exc}")

    res = sim.run()

    print(f"done: {res['steps']} steps, wall {res['wall']:.1f} s")
    hist = np.array([[h["time"], h["canopy_radius"], h["canopy_y"],
                      h["p_max"], h["coupling_drag"]] for h in sim.history])
    print("  t_end={:.4f}s  R={:.4f}m  y={:.4f}m  pmax={:.3e}Pa  drag={:.3e}N"
          .format(*hist[-1]))
    print(f"  outputs in {os.path.abspath(args.outdir)}")

    if args.generate_report:
        print("generating calculation report ...")
        try:
            from aleparachute.report import write_run_meta as _wmeta
            _wmeta(args.outdir, {
                "run": {"end": __import__("datetime").datetime.now().isoformat(
                    timespec="seconds"),
                    "wall_time": float(res["wall"]),
                    "steps": int(res["steps"]),
                    "endtime": float(opt.endtime)},
                "conditions": conditions,
            })
            generate_report(args.outdir, model=model, opt=opt, grid=grid,
                            sim=sim, wall_time=float(res["wall"]),
                            cpu_info=get_cpu_info())
            print(f"  report: {os.path.join(args.outdir, 'calculation_report.html')}")
        except Exception as exc:
            print(f"[report] WARNING: report generation failed: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
