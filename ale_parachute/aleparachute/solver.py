"""Explicit time integration driver for the parachute inflation problem."""

from __future__ import annotations

import csv
import os
import time as wallclock
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from scipy.spatial import cKDTree

from .coupling import PenaltyCoupler
from .fluid import ALEFluid, IdealGas
from .kfile import Model, timeseries
from .mesh import HexGrid, Structure, build_structure
from .structure import StructureSolver
from . import vtkio


@dataclass
class Options:
    endtime: float = 0.02
    vel_scale: float = 1.0        # scale on *BOUNDARY_PRESCRIBED_MOTION curve
    cfl: float = 0.5
    tssfac: float = 0.9
    coupling: bool = True
    structure: bool = True
    mass_scale: float = 1.0      # structure mass scaling (explicit FSI aid)
    omega: float = 0.2           # under-relaxation of the exchanged traction
    cdamp: float = 1.0           # acoustic impedance damping of the penalty
    hg_qh: float = 0.1           # *CONTROL_HOURGLASS qh for the quad flap mode
    alt_floor: float = 0.1       # min altitude fraction for the shell time step
    vtk_every: float = 0.0        # <=0 -> only the final state
    outdir: str = "out"
    max_steps: int = 100000
    verbose: bool = True


def driven_cells(grid: HexGrid, model: Model) -> np.ndarray:
    """Fluid cells that carry the *BOUNDARY_PRESCRIBED_MOTION node set.

    The K file prescribes the velocity on ALE nodes of the upstream boundary
    layer; here every node is mapped to its nearest cell so that the same
    layer of control volumes is driven.
    """
    ids = []
    for pm in model.bc.get("prescribed_motion", []):
        s = model.sets_by_type.get(("node", pm["nsid"]))
        if s is not None:
            ids.append(s)
    if not ids:
        return np.zeros(0, dtype=np.int64)
    s = np.concatenate(ids)
    nodes = model.mesh["nodes"]
    sel = np.isin(nodes[:, 0].astype(np.int64), s)
    if sel.sum() == 0:
        return np.zeros(0, dtype=np.int64)
    xyz = nodes[sel, 1:4]
    dist, cel = cKDTree(grid.center).query(xyz)
    h = np.cbrt(grid.vol[cel])
    ok = dist <= 2.0 * h
    return np.unique(cel[ok]).astype(np.int64)


class Simulation:
    def __init__(self, model: Model, grid: HexGrid, options: Options):
        self.model = model
        self.grid = grid
        self.opt = options

        pid_air = None
        for p in model.parts.values():
            if p["title"].lower().startswith("air"):
                pid_air = p["pid"]
        if pid_air is None:
            pid_air = max(model.parts)
        self.fluid = ALEFluid(
            grid,
            IdealGas.from_model(model, model.parts[pid_air]["mid"],
                                model.parts[pid_air]["eosid"]),
            cfl=options.cfl)
        self.struct = build_structure(model)
        if options.mass_scale != 1.0:
            self.struct.mass *= float(options.mass_scale)
        self.ssolver = StructureSolver(self.struct, tension_only=True,
                                       hg_qh=options.hg_qh,
                                       alt_floor=options.alt_floor)
        self.ssolver.update_kinematics()      # nodal areas for the coupler
        self.coupler = PenaltyCoupler(self.fluid, self.ssolver, model,
                                      enabled=options.coupling)
        self.coupler.omega = float(options.omega)
        self.coupler.cdamp = float(options.cdamp)

        cells = driven_cells(grid, model)
        self.driven_cells = cells
        pm = model.bc.get("prescribed_motion", [])
        self.pm = pm[0] if pm else None
        if self.pm is not None:
            self.fluid.set_drive(cells, self.pm["dof"],
                                 timeseries(model.curve(self.pm["lcid"]), 0.0) * options.vel_scale)

        self.history: List[dict] = []
        self.t = 0.0
        self.step_count = 0
        self.dt_last = 0.0
        self.wall0 = wallclock.time()

    # ------------------------------------------------------------- diagnostics
    def diagnostics(self, f_couple: np.ndarray) -> dict:
        rho, u, p, c = self.fluid.primitive()
        st = self.struct
        if st.nodal_area.size and float(st.nodal_area.sum()) > 0:
            wa = st.nodal_area / max(float(st.nodal_area.sum()), 1e-30)
            r = np.linalg.norm(st.x[:, [0, 2]], axis=1)
            radius = float(np.sum(wa * r))
            height = float(np.sum(wa * st.x[:, 1]))
        else:
            radius = height = 0.0
        return {
            "time": self.t,
            "step": self.step_count,
            "fluid_mass": self.fluid.mass(),
            "fluid_energy": self.fluid.energy(),
            "fluid_kinetic": self.fluid.kinetic(),
            "fluid_internal": self.fluid.internal(),
            "p_max": float(p.max()),
            "p_min": float(p.min()),
            "u_max": float(np.linalg.norm(u, axis=1).max()),
            "canopy_radius": radius,
            "canopy_y": height,
            "struct_kinetic": float(np.sum(0.5 * st.mass * np.sum(st.v ** 2, axis=1))),
            "coupling_drag": self.coupler.drag(f_couple),
            "dt": self.dt_last,
        }

    # ----------------------------------------------------------------- outputs
    def write_state(self, path: str) -> None:
        g = self.grid
        rho, u, p, c = self.fluid.primitive()
        st = self.struct
        cells = [[int(v) for v in row] for row in g.conn]
        types = np.full(len(cells), 12)
        vtkio.write_vtk(
            path + "_fluid.vtk", g.x, cells, types,
            {"pressure": p, "density": rho, "velocity": u, "sound_speed": c},
            None, title=f"ALE fluid t={self.t:.5f}")

        scells = [list(map(int, t)) for t in st.tris]
        stypes = np.full(len(scells), 5)
        if st.beams.size:
            for b in st.beams:
                scells.append(list(map(int, b)))
            stypes = np.concatenate([stypes, np.full(st.beams.shape[0], 3)])
        vtkio.write_vtk(
            path + "_structure.vtk", st.x, scells, stypes,
            None,
            {"mass": st.mass, "velocity": st.v, "normal": st.nodal_normal},
            title=f"canopy t={self.t:.5f}")

    def write_history(self, path: str) -> None:
        if not self.history:
            return
        keys = list(self.history[0].keys())
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            for row in self.history:
                w.writerow(row)

    # -------------------------------------------------------------------- run
    def run(self) -> dict:
        opt = self.opt
        os.makedirs(opt.outdir, exist_ok=True)
        endtime = opt.endtime
        dt = min(self.fluid.stable_dt(), self.ssolver.stable_dt()) * opt.tssfac
        self.dt_last = dt
        next_vtk = 0.0
        hist_every = max(endtime / 200.0, 1e-9)
        next_hist = hist_every
        f_c = np.zeros_like(self.struct.x)
        if opt.vtk_every > 0:
            self.write_state(os.path.join(opt.outdir, "state_0000"))

        curves = self.model.curves if self.pm is not None else {}
        while self.t < endtime and self.step_count < opt.max_steps:
            # ---- coupling force at t
            f_c = self.coupler.force(self.t) if opt.coupling else np.zeros_like(self.struct.x)
            # ---- structure
            if opt.structure:
                self.ssolver.step(dt, self.t, curves, opt.vel_scale, f_ext=f_c)
            # ---- fluid reaction
            if opt.coupling:
                self.coupler.transfer(f_c, dt)
            # ---- driven flow (prescribed motion card)
            if self.pm is not None:
                val = timeseries(self.model.curve(self.pm["lcid"]), self.t) * opt.vel_scale
                self.fluid.set_drive(self.driven_cells, self.pm["dof"], val)
            # ---- fluid
            self.fluid.step(dt)

            self.t += dt
            self.step_count += 1

            if self.t >= next_hist - 1e-15 or self.step_count == 1:
                next_hist += hist_every
                row = self.diagnostics(f_c)
                self.history.append(row)
                if opt.verbose:
                    print(f"t={self.t:.5f} dt={dt:.3e} dt_fluid={self.fluid.stable_dt():.3e} "
                          f"R={row['canopy_radius']:.4f} y={row['canopy_y']:.4f} "
                          f"pmax={row['p_max']:.3e} umax={row['u_max']:.2f} "
                          f"drag={row['coupling_drag']:.3e}")

            if opt.vtk_every > 0 and self.t >= next_vtk + opt.vtk_every - 1e-12:
                next_vtk += opt.vtk_every
                self.write_state(os.path.join(opt.outdir,
                                              f"state_{next_vtk:8.4f}"))

            dt_new = min(self.fluid.stable_dt(), self.ssolver.stable_dt()) * opt.tssfac
            dt = min(dt_new, 1.3 * dt)      # gentle growth
            dt = max(dt, 2e-9)
            self.dt_last = dt

            if not np.all(np.isfinite(self.fluid.U)):
                raise RuntimeError("fluid state became non finite")

        final = self.diagnostics(f_c)
        self.history.append(final)
        self.write_history(os.path.join(opt.outdir, "history.csv"))
        self.write_state(os.path.join(opt.outdir, "final"))
        return {"history": self.history, "wall": wallclock.time() - self.wall0,
                "steps": self.step_count, "dt": self.dt_last}
