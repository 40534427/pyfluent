"""Explicit time integration driver for the parachute inflation problem."""

from __future__ import annotations

import csv
import os
import time as wallclock
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from scipy.spatial import cKDTree

from .contact import SelfContact
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
    fsi_mach_cap: float = 0.3    # max Mach number of the injected FSI source
    fsi_leak: bool = True         # CLLS leakage control (card ILEAK)
    pleak: Optional[float] = None # PLEAK override
    hg_qh: float = 0.1           # *CONTROL_HOURGLASS qh for the quad flap mode
    alt_floor: float = 0.1       # min altitude fraction for the shell time step
    # *CONTROL_SHELL THEORY / BWC and *CONTROL_HOURGLASS IHQ.  ``None``
    # means: take the value from the keyword file.
    theory: Optional[int] = None
    bwc: Optional[int] = None
    ihq: Optional[int] = None
    contact: bool = True         # *CONTACT_AUTOMATIC_SINGLE_SURFACE
    contact_scale: float = 1.0   # penalty stiffness multiplier
    contact_vdc: Optional[float] = None   # viscous damping (card VDC)
    contact_thk_scale: float = 1.0
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

        cs = model.controls.get("CONTROL_SHELL", {})
        chg = model.controls.get("CONTROL_HOURGLASS", {})
        self.theory = int(options.theory if options.theory is not None
                          else cs.get("theory", 5))
        self.bwc = int(options.bwc if options.bwc is not None
                       else cs.get("bwc", 2))
        self.ihq = int(options.ihq if options.ihq is not None
                       else chg.get("ihq", 1))
        self.ssolver = StructureSolver(
            self.struct, tension_only=True,
            hg_qh=float(chg.get("qh", options.hg_qh)),
            alt_floor=options.alt_floor,
            theory=self.theory, bwc=self.bwc, ihq=self.ihq)
        self.ssolver.update_kinematics()      # nodal areas for the coupler
        self.coupler = PenaltyCoupler(self.fluid, self.ssolver, model,
                                      enabled=options.coupling)
        self.coupler.omega = float(options.omega)
        self.coupler.cdamp = float(options.cdamp)
        self.coupler.mach_cap = float(options.fsi_mach_cap)
        if not options.fsi_leak:
            self.coupler.ileak = 0
        if options.pleak is not None:
            self.coupler.pleak = float(options.pleak)

        # *CONTACT_AUTOMATIC_SINGLE_SURFACE on the canopy part
        self.contact = None
        self.contact_card = model.contact[0] if model.contact else {}
        if options.contact and self.struct.quads.shape[0] > 0:
            cc = self.contact_card
            vdc = (float(options.contact_vdc)
                   if options.contact_vdc is not None
                   else float(cc.get("vdc", 0.0)))
            self.contact = SelfContact(
                self.struct, enabled=True,
                scale=float(options.contact_scale),
                sfs=float(cc.get("sfs", 1.0)),
                sfm=float(cc.get("sfm", 1.0)),
                vdc=vdc,
                thickness_scale=float(options.contact_thk_scale))

        cells = driven_cells(grid, model)
        self.driven_cells = cells
        pm = model.bc.get("prescribed_motion", [])
        self.pm = pm[0] if pm else None
        if self.pm is not None:
            self.fluid.set_drive(cells, self.pm["dof"],
                                 timeseries(model.curve(self.pm["lcid"]), 0.0) * options.vel_scale)

        self.history: List[dict] = []
        self.line_history: List[list] = []
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
        if st.beams.size:
            lt = self.ssolver.line_tension()
            line_max = float(lt.max()) if lt.size else 0.0
            line_sum = float(lt.sum()) if lt.size else 0.0
            line_anchor = self.ssolver.beam_anchor_force()
        else:
            lt = np.zeros(0)
            line_max = line_sum = line_anchor = 0.0
        cstat = self.contact.stats if self.contact is not None else None
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
            "struct_vmax": float(np.max(np.linalg.norm(st.v, axis=1))) if st.nnode else 0.0,
            "coupling_drag": self.coupler.drag(f_couple),
            "line_tension_max": line_max,
            "line_tension_sum": line_sum,
            "line_anchor_force": line_anchor,
            "contact_force_max": cstat.fmax if cstat else 0.0,
            "contact_pairs": cstat.pairs if cstat else 0,
            "contact_penetration": cstat.pen_max if cstat else 0.0,
            "fsi_stiffness": self.coupler.k_fsi,
            "fsi_impedance": self.coupler.impedance,
            "fsi_dt": self.coupler.fsi_dt if np.isfinite(self.coupler.fsi_dt) else 0.0,
            "dt_fluid": self.fluid.stable_dt(),
            "dt_struct": self.ssolver.stable_dt(),
            "dt_contact": (self.contact.stable_dt() if self.contact is not None
                           else 0.0),
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
        tension = np.zeros(len(scells))
        if st.beams.size:
            for b in st.beams:
                scells.append(list(map(int, b)))
            stypes = np.concatenate([stypes, np.full(st.beams.shape[0], 3)])
            tension = np.concatenate([tension, self.ssolver.beam_tension()])
        vtkio.write_vtk(
            path + "_structure.vtk", st.x, scells, stypes,
            {"tension": tension},
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
        if self.line_history:
            nline = self.ssolver.line_count
            lpath = os.path.join(os.path.dirname(path), "line_force.csv")
            with open(lpath, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["time"] + [f"line_{k + 1}" for k in range(nline)])
                for row in self.line_history:
                    t = row[0]
                    vals = list(row[1]) + [0.0] * (nline - len(row[1]))
                    w.writerow([t] + vals[:nline])

    # ------------------------------------------------------------ combined dt
    def stable_dt(self) -> float:
        """Smallest explicit stable step over all physics.

        fluid (CFL / spectral radius) -- structure (membrane + cable) --
        penalty contact -- CLLS interface stiffness.
        """
        dt = min(self.fluid.stable_dt(), self.ssolver.stable_dt())
        if self.contact is not None:
            dt = min(dt, self.contact.stable_dt())
        if np.isfinite(self.coupler.fsi_dt):
            dt = min(dt, self.coupler.fsi_dt)
        return float(dt)

    # -------------------------------------------------------------------- run
    def run(self) -> dict:
        opt = self.opt
        os.makedirs(opt.outdir, exist_ok=True)
        endtime = opt.endtime
        dt = self.stable_dt() * opt.tssfac
        self.dt_last = dt
        next_vtk = 0.0
        hist_every = max(endtime / 200.0, 1e-9)
        next_hist = hist_every
        f_c = np.zeros_like(self.struct.x)
        f_ct = np.zeros_like(self.struct.x)
        if opt.vtk_every > 0:
            self.write_state(os.path.join(opt.outdir, "state_0000"))

        curves = self.model.curves if self.pm is not None else {}
        while self.t < endtime and self.step_count < opt.max_steps:
            # ---- coupling force at t
            f_c = (self.coupler.force(self.t, dt) if opt.coupling
                   else np.zeros_like(self.struct.x))
            # ---- penalty self-contact of the canopy at t
            f_ct = (self.contact.force() if self.contact is not None
                    else np.zeros_like(self.struct.x))
            f_ext = f_c + f_ct
            # ---- structure
            if opt.structure:
                self.ssolver.step(dt, self.t, curves, opt.vel_scale, f_ext=f_ext)
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
                self.line_history.append([self.t, self.ssolver.line_tension().copy()])
                if opt.verbose:
                    print(f"t={self.t:.5f} dt={dt:.3e} dt_f={row['dt_fluid']:.3e} "
                          f"R={row['canopy_radius']:.4f} y={row['canopy_y']:.4f} "
                          f"pmax={row['p_max']:.3e} umax={row['u_max']:.2f} "
                          f"drag={row['coupling_drag']:.3e} "
                          f"vmax={row['struct_vmax']:.3e} "
                          f"Tc={row['line_tension_max']:.1f}N "
                          f"ct={row['contact_pairs']} "
                          f"pen={row['contact_penetration']:.3e} "
                          f"ctf={row['contact_force_max']:.3e}")

            if opt.vtk_every > 0 and self.t >= next_vtk + opt.vtk_every - 1e-12:
                next_vtk += opt.vtk_every
                self.write_state(os.path.join(opt.outdir,
                                              f"state_{next_vtk:8.4f}"))

            dt_new = self.stable_dt() * opt.tssfac
            dt = min(dt_new, 1.3 * dt)      # gentle growth
            dt = max(dt, 2e-9)
            self.dt_last = dt

            if not np.all(np.isfinite(self.fluid.U)):
                raise RuntimeError("fluid state became non finite")
            if not (np.all(np.isfinite(self.struct.x))
                    and np.all(np.isfinite(self.struct.v))):
                raise RuntimeError("structure state became non finite")

        final = self.diagnostics(f_c)
        self.history.append(final)
        self.write_history(os.path.join(opt.outdir, "history.csv"))
        self.write_state(os.path.join(opt.outdir, "final"))
        return {"history": self.history, "wall": wallclock.time() - self.wall0,
                "steps": self.step_count, "dt": self.dt_last}
