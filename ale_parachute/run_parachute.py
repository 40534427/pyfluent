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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ALE / Lagrangian penalty coupling solver for the "
                    "parachute inflation K file.")
    p.add_argument("--k", required=True, help="LS-DYNA keyword file")
    p.add_argument("--mesh", choices=("auto", "native"), default="auto",
                   help="auto = cartesian grid clipped to the K file cylinder, "
                        "native = reuse *ELEMENT_SOLID (large, slow)")
    p.add_argument("--nx", type=int, default=20, help="auto grid cells in x")
    p.add_argument("--ny", type=int, default=32, help="auto grid cells in y")
    p.add_argument("--nz", type=int, default=20, help="auto grid cells in z")
    p.add_argument("--endtime", type=float, default=None,
                   help="physical end time [s] (default: *CONTROL_TERMINATION)")
    p.add_argument("--vel-scale", type=float, default=1.0,
                   help="scale factor on the prescribed velocity curve")
    p.add_argument("--cfl", type=float, default=0.5)
    p.add_argument("--tssfac", type=float, default=0.9)
    p.add_argument("--mass-scale", type=float, default=1.0,
                   help="scale the structure mass (explicit-FSI added-mass aid)")
    p.add_argument("--omega", type=float, default=0.2,
                   help="under-relaxation of the exchanged traction (0..1)")
    p.add_argument("--cdamp", type=float, default=1.0,
                   help="acoustic impedance damping coefficient of the penalty")
    p.add_argument("--hg-qh", type=float, default=0.1,
                   help="*CONTROL_HOURGLASS qh for the quad flap mode")
    p.add_argument("--no-coupling", action="store_true",
                   help="disable the penalty fluid-structure coupling")
    p.add_argument("--vtk-every", type=float, default=0.0,
                   help="write VTK states every dt [s] (0 = final state only)")
    p.add_argument("--outdir", default="out")
    p.add_argument("--max-steps", type=int, default=100000)
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

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
        print(f"fluid domain y=[{y0:.4f},{y1:.4f}] R={r:.4f} centre=({cx:.4f},{cz:.4f})")
        grid = auto_cylinder_grid(y0, y1, r, args.nx, args.ny, args.nz, cx, cz)
    print(f"  grid: {grid.boundary_info()}")

    opt = Options(
        endtime=args.endtime if args.endtime is not None
        else float(model.controls.get("CONTROL_TERMINATION", {}).get("endtim", 0.02)),
        vel_scale=args.vel_scale, cfl=args.cfl, tssfac=args.tssfac,
        mass_scale=args.mass_scale, omega=args.omega, cdamp=args.cdamp,
        hg_qh=args.hg_qh,
        coupling=not args.no_coupling, vtk_every=args.vtk_every,
        outdir=args.outdir, max_steps=args.max_steps, verbose=not args.quiet,
    )
    sim = Simulation(model, grid, opt)
    st = sim.struct
    print(f"structure: {st.summary()}  fixed={st.fixed.size} driven={st.driven.size}")
    print(f"driven fluid cells: {sim.driven_cells.size}")

    res = sim.run()

    print(f"done: {res['steps']} steps, wall {res['wall']:.1f} s")
    hist = np.array([[h["time"], h["canopy_radius"], h["canopy_y"],
                      h["p_max"], h["coupling_drag"]] for h in sim.history])
    print("  t_end={:.4f}s  R={:.4f}m  y={:.4f}m  pmax={:.3e}Pa  drag={:.3e}N"
          .format(*hist[-1]))
    print(f"  outputs in {os.path.abspath(args.outdir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
