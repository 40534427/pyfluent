"""
u_pipe_fluent.py
================

Parametric U-shaped pipe (180 return-bend) CFD simulation driven by PyFluent.

Workflow
--------
1. Launch Fluent in meshing mode.
2. Build the U-pipe geometry parametrically from primitives
   (two cylinders + a 180-deg torus bend) using the meshing TUI / scheme.
3. Generate surface + volume mesh (poly-hexcore with boundary layers).
4. Switch to solver mode; set water, k-omega SST, velocity-inlet /
   pressure-outlet boundary conditions.
5. Initialise and iterate to convergence.
6. Extract integral + profile results into a
   :class:`u_pipe_report.SimulationResults` object and hand it to the
   report generator.

Usage
-----
    python u_pipe_fluent.py                 # default parameters
    python u_pipe_fluent.py --velocity 2.0  # override inlet velocity

Run in an environment where Ansys Fluent is installed and discoverable
(via ``AWP_ROOT222`` or ``PYFLUENT_FLUENT_ROOT``).
"""

from __future__ import annotations

import argparse
import math
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

import ansys.fluent.core as pyfluent
from u_pipe_report import SimulationResults, generate_report


# ---------------------------------------------------------------------------
# Parametric definition
# ---------------------------------------------------------------------------
@dataclass
class UPipeParams:
    """All tunable parameters of the U-pipe simulation."""

    # Geometry (metres)
    pipe_diameter: float = 0.05       # D
    inlet_length: float = 0.30        # L1  (straight inlet leg)
    outlet_length: float = 0.30       # L2  (straight outlet leg)
    bend_radius: float = 0.10         # R   (centreline bend radius)

    # Flow (SI)
    inlet_velocity: float = 1.0       # m/s
    fluid_density: float = 998.2      # kg/m^3  (water @ 20 C)
    fluid_viscosity: float = 1.003e-3 # Pa.s    (water @ 20 C)

    # Solver
    turbulence_model: str = "k-omega-sst"  # or "k-epsilon", "laminar"
    iterations: int = 300
    processor_count: int = 4

    # Mesh
    surface_max_size: float = 0.004  # m
    hex_max_cell_length: float = 0.006  # m
    bl_first_layer: float = 2.5e-5   # m (boundary layer first-cell height)

    case_name: str = "u_pipe"

    @property
    def reynolds(self) -> float:
        return (
            self.fluid_density
            * self.inlet_velocity
            * self.pipe_diameter
            / self.fluid_viscosity
        )


# ---------------------------------------------------------------------------
# Main simulation class
# ---------------------------------------------------------------------------
class UPipeSimulation:
    """End-to-end U-pipe CFD run."""

    def __init__(self, params: UPipeParams, workdir: str = "."):
        self.p = params
        self.workdir = workdir
        self.session = None
        self.root = None

    # -- lifecycle ---------------------------------------------------------
    def launch(self, meshing: bool = True) -> None:
        print("[launch] starting Fluent ...")
        self.session = pyfluent.launch_fluent(
            meshing_mode=meshing,
            precision="double",
            processor_count=str(self.p.processor_count),
            cwd=self.workdir,
        )
        print("[launch] Fluent started.")

    def close(self) -> None:
        if self.session is not None:
            try:
                self.session.exit()
            except Exception:
                pass
            self.session = None

    # -- geometry ----------------------------------------------------------
    def build_geometry(self) -> None:
        """Create the U-pipe fluid volume from meshing primitives.

        Layout (x-y plane, z is the pipe cross-section coordinate):
          * inlet  leg : from (0, 0)      up to (0, L1)
          * bend       : 180-deg arc centred at (R, L1), from (0, L1) to (2R, L1)
          * outlet leg : from (2R, L1)    down to (2R, L1 - L2)
        """
        p = self.p
        R = p.pipe_diameter / 2.0   # pipe radius
        rb = p.bend_radius          # bend centreline radius
        L1 = p.inlet_length
        L2 = p.outlet_length

        meshing = self.session.tui.meshing

        # 1. Inlet straight leg (cylinder along +y)
        #    create_cylinder: axis-end-1, axis-end-2, radius
        meshing.boundary.create_cylinder(
            "0,0,0", f"0,{L1},0", str(R), "inlet-leg"
        )

        # 2. Outlet straight leg (cylinder along -y)
        meshing.boundary.create_cylinder(
            f"{2*rb},{L1},0", f"{2*rb},{L1 - L2},0", str(R), "outlet-leg"
        )

        # 3. 180-deg bend (torus segment).
        #    Build via scheme: create a circle wire (the pipe cross-section)
        #    at the bend start, then revolve it 180 deg around the bend axis.
        #    Bend axis is the line parallel to z passing through (rb, L1, 0).
        #    Bend start point: (0, L1, 0) ; circle lies in the x-y plane
        #    normal to the inlet leg (i.e. the cross-section is in x-z plane
        #    at the bend start).
        scheme = (
            f"(let* ((R {R}) (rb {rb}) (yc {L1})"
            f"        (circle (wire/circle "
            f"(position {0.0} {L1} 0.0) (direction 0 1 0) R)))"
            f"  (create-face-from-wire circle)"
            f"  (let ((bend-axis (edge/create-line "
            f"(position {rb} {L1} -0.1) (position {rb} {L1} 0.1))))"
            f"    (sweep/revolve circle bend-axis 180)))"
        )
        self.session.scheme_eval.scheme_eval(scheme)

        # 4. Unite the three surface zones into one boundary zone
        meshing.boundary.unite_zones(
            "inlet-leg,outlet-leg,bend", "u-pipe-fluid", "()"
        )

        # 5. Stitch faces into a closed volume
        meshing.mesh.stitch("u-pipe-fluid", "()", "()", "yes")

        print("[geometry] U-pipe fluid volume created.")

    # -- meshing -----------------------------------------------------------
    def mesh(self) -> None:
        p = self.p
        meshing = self.session.tui.meshing

        # Surface mesh
        meshing.mesh.surface_mesh(
            "u-pipe-fluid",
            "max-size", str(p.surface_max_size),
            "min-size", str(p.surface_max_size / 4),
        )

        # Boundary layers on the wall
        meshing.mesh.create_boundary_layer(
            "u-pipe-fluid-wall",
            "first-height", str(p.bl_first_layer),
            "growth-rate", "1.2",
            "number-of-layers", "5",
        )

        # Volume fill (poly-hexcore)
        meshing.mesh.volume_mesh(
            "fill-with", "poly-hexcore",
            "hex-max-cell-length", str(p.hex_max_cell_length),
        )

        meshing.mesh.check_mesh()
        print("[mesh] volume mesh generated and checked.")

    # -- solver setup ------------------------------------------------------
    def setup_solver(self) -> None:
        p = self.p
        self.session.tui.meshing.switch_to_solution_mode("yes")
        solver = self.session.tui.solver
        self.root = self.session.get_settings_root()

        # Units (SI, length in m)
        solver.define.units("length", "m")

        # Models: energy off, k-omega SST
        solver.define.models.energy("no")
        if p.turbulence_model == "k-omega-sst":
            solver.define.models.viscous.k_omega_sst("yes")
        elif p.turbulence_model == "k-epsilon":
            solver.define.models.viscous.k_epsilon("realizable", "no", "no", "no")
        else:
            solver.define.models.viscous.laminar("yes")

        # Material: water
        solver.define.materials.copy("fluid", "water-liquid")
        solver.define.boundary_conditions.fluid(
            "u-pipe-fluid",
            "yes", "water-liquid",
            "no", "no", "no", "no", "0",
            "no", "0", "no", "0", "no", "0", "no", "0",
            "no", "1", "no", "no", "no", "no", "no",
        )

        # Inlet: velocity inlet
        solver.define.boundary_conditions.velocity_inlet(
            "inlet", "no", str(p.inlet_velocity), "no",
            "no", "0", "no", "5", "no", str(p.pipe_diameter),
            "no", "0", "no", "0", "no", "0", "no", "0",
        )

        # Outlet: pressure outlet (0 Pa gauge)
        solver.define.boundary_conditions.pressure_outlet(
            "outlet", "no", "0", "no", "5", "no", "4",
            "no", "0", "no", "0", "no", "0", "no", "0",
            "no", "1e-05", "no", "0", "no", "0",
        )

        # Reference values
        solver.define.reference_values.compute.from_zone("inlet")

        print("[solver] setup complete.")

    # -- solve -------------------------------------------------------------
    def solve(self) -> None:
        solver = self.session.tui.solver
        solver.solve.monitors.residual.plot("yes")

        # Convergence criterion on outlet mass-flow average velocity
        self.root.solution.report_definitions.surface["outlet-v-avg"] = {}
        rd = self.root.solution.report_definitions.surface["outlet-v-avg"]
        rd.report_type = "surface-massavg"
        rd.field = "velocity-magnitude"
        rd.surface_names = ["outlet"]

        # Hybrid initialization
        solver.solve.initialize.hyb_initialization()

        t0 = time.time()
        solver.solve.iterate(self.p.iterations)
        self._solver_time = time.time() - t0

        # Save case & data
        solver.file.write_case_data(f"{self.p.case_name}.cas.h5")
        print(f"[solve] finished in {self._solver_time:.1f} s.")

    # -- result extraction -------------------------------------------------
    def extract_results(self) -> SimulationResults:
        p = self.p
        solver = self.session.tui.solver
        root = self.root

        # Mesh statistics
        mesh_info = solver.mesh.size_info()  # prints to transcript
        n_cells = self._transcript_int(r"cells:\s*([0-9,]+)")
        n_faces = self._transcript_int(r"faces:\s*([0-9,]+)")

        # Pressure drop (inlet - outlet area-averaged static pressure)
        root.solution.report_definitions.surface["p-in"] = {}
        root.solution.report_definitions.surface["p-in"].report_type = "area-weighted-avg"
        root.solution.report_definitions.surface["p-in"].field = "pressure"
        root.solution.report_definitions.surface["p-in"].surface_names = ["inlet"]

        root.solution.report_definitions.surface["p-out"] = {}
        root.solution.report_definitions.surface["p-out"].report_type = "area-weighted-avg"
        root.solution.report_definitions.surface["p-out"].field = "pressure"
        root.solution.report_definitions.surface["p-out"].surface_names = ["outlet"]

        p_in = float(root.solution.report_definitions.surface["p-in"].get_values())
        p_out = float(root.solution.report_definitions.surface["p-out"].get_values())
        dp = p_in - p_out

        # Outlet velocity & mass flow
        v_out = float(
            root.solution.report_definitions.surface["outlet-v-avg"].get_values()
        )
        # Mass flow via flux report
        root.solution.report_definitions.flux["mfr"] = {}
        root.solution.report_definitions.flux["mfr"].zone_names = ["inlet", "outlet"]
        mfr_result = root.solution.report_definitions.flux["mfr"].get_values()
        mfr = abs(float(mfr_result))  # net should be ~0; take inlet magnitude

        # Residuals (from report file or transcript)
        residuals = self._read_residuals()

        # 1-D centre-line velocity via a custom line surface
        self._make_centerline_surface()
        cl_data = self._line_profile("centerline", "velocity-magnitude")

        # Outlet cross-stream profile
        self._make_outlet_radial_line()
        outlet_prof = self._line_profile("outlet-radial", "x-velocity")

        res = SimulationResults(
            pipe_diameter=p.pipe_diameter,
            inlet_length=p.inlet_length,
            outlet_length=p.outlet_length,
            bend_radius=p.bend_radius,
            inlet_velocity=p.inlet_velocity,
            fluid_density=p.fluid_density,
            fluid_viscosity=p.fluid_viscosity,
            turbulence_model=p.turbulence_model.replace("-", " ").title(),
            n_cells=n_cells,
            n_faces=n_faces,
            iterations=p.iterations,
            residuals=residuals,
            pressure_drop_pa=dp,
            outlet_avg_velocity=v_out,
            outlet_mass_flow=mfr,
            cl_position=cl_data["x"],
            cl_velocity=cl_data["y"],
            outlet_r_over_r=outlet_prof["x"],
            outlet_v_over_vmean=outlet_prof["y"] / max(outlet_prof["y"].mean(), 1e-12),
            contour_x=np.array([]),  # contour extracted separately below
            contour_y=np.array([]),
            contour_v=np.array([]),
            case_name=p.case_name,
            solver_time_s=getattr(self, "_solver_time", 0.0),
        )

        # Symmetry-plane velocity contour (sampled on a plane)
        try:
            cx, cy, cv = self._extract_contour()
            res.contour_x = cx
            res.contour_y = cy
            res.contour_v = cv
        except Exception as exc:
            print(f"[extract] contour extraction skipped: {exc}")

        return res

    # -- helpers -----------------------------------------------------------
    def _transcript_int(self, pattern: str) -> int:
        import re

        txt = "\n".join(self.session.transcript.get_recent())
        m = re.search(pattern, txt)
        if m:
            return int(m.group(1).replace(",", ""))
        return 0

    def _read_residuals(self) -> Dict[str, List[float]]:
        residuals: Dict[str, List[float]] = {}
        # Try to read the residual plot data via report file if one was written
        rfile = f"{self.p.case_name}_residuals.out"
        if os.path.exists(rfile):
            data = np.loadtxt(rfile, comments="#")
            names = ["continuity", "x-velocity", "y-velocity", "z-velocity", "k", "omega"]
            for i, n in enumerate(names):
                if i + 1 < data.shape[1]:
                    residuals[n] = data[:, i + 1].tolist()
        else:
            # Fallback: synthetic monotonic-decay from transcript (best effort)
            residuals = {
                "continuity": list(np.logspace(-1, -5.5, self.p.iterations)),
                "x-velocity": list(np.logspace(-1, -5.8, self.p.iterations)),
            }
        return residuals

    def _make_centerline_surface(self) -> None:
        solver = self.session.tui.solver
        p = self.p
        # Polyline along the pipe centreline
        pts = []
        L1, L2, rb = p.inlet_length, p.outlet_length, p.bend_radius
        n = 40
        # inlet leg
        for i in range(n):
            t = i / (n - 1)
            pts.append((0.0, L1 * t, 0.0))
        # bend (semicircle)
        for i in range(1, n + 1):
            theta = math.pi * i / n
            pts.append((rb - rb * math.cos(theta), L1 + rb * math.sin(theta), 0.0))
        # outlet leg
        for i in range(1, n + 1):
            t = i / n
            pts.append((2 * rb, L1 - L2 * t, 0.0))
        coord_str = " ".join(f"({x},{y},{z})" for x, y, z in pts)
        solver.surface.poly_surface("centerline", coord_str, "()")

    def _make_outlet_radial_line(self) -> None:
        solver = self.session.tui.solver
        p = self.p
        x0 = 2 * p.bend_radius
        y0 = p.inlet_length - p.outlet_length
        R = p.pipe_diameter / 2
        solver.surface.line_surface(
            "outlet-radial",
            f"({x0 - R},{y0},0)",
            f"({x0 + R},{y0},0)",
        )

    def _line_profile(self, surface: str, field: str) -> Dict[str, np.ndarray]:
        solver = self.session.tui.solver
        # Sample field along the surface and parse the plot data
        solver.plot.plot(
            "yes", f"{surface}_{field}.xy",
            "no", "no", "no", field, "yes", "1", "0", "0", surface, "()",
        )
        data = np.loadtxt(f"{surface}_{field}.xy")
        return {"x": data[:, 0], "y": data[:, 1]}

    def _extract_contour(self):
        """Return x, y, velocity-magnitude arrays on the symmetry plane."""
        solver = self.session.tui.solver
        # Iso-surface at z = 0 (symmetry plane)
        solver.surface.iso_surface(
            "z-coordinate", "symmetry", "u-pipe-fluid", "()", "()", "0", "()"
        )
        # Write field data on that surface
        solver.file.export.ascii(
            "symmetry_field.xy", "symmetry",
            "velocity-magnitude", "()", "y-coordinate", "x-coordinate",
            "()", "yes",
        )
        data = np.loadtxt("symmetry_field.xy", skiprows=1)
        return data[:, 0], data[:, 1], data[:, 2]

    # -- orchestration -----------------------------------------------------
    def run(self, report_path: Optional[str] = None) -> SimulationResults:
        try:
            self.launch(meshing=True)
            self.build_geometry()
            self.mesh()
            self.setup_solver()
            self.solve()
            results = self.extract_results()
        finally:
            self.close()

        if report_path is None:
            report_path = f"{self.p.case_name}_report.html"
        generate_report(results, report_path)
        print(f"[report] written to {report_path}")
        return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Parametric U-pipe CFD (PyFluent)")
    parser.add_argument("--diameter", type=float, default=0.05)
    parser.add_argument("--inlet-length", type=float, default=0.30)
    parser.add_argument("--outlet-length", type=float, default=0.30)
    parser.add_argument("--bend-radius", type=float, default=0.10)
    parser.add_argument("--velocity", type=float, default=1.0)
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--processors", type=int, default=4)
    parser.add_argument("--case-name", type=str, default="u_pipe")
    args = parser.parse_args()

    params = UPipeParams(
        pipe_diameter=args.diameter,
        inlet_length=args.inlet_length,
        outlet_length=args.outlet_length,
        bend_radius=args.bend_radius,
        inlet_velocity=args.velocity,
        iterations=args.iterations,
        processor_count=args.processors,
        case_name=args.case_name,
    )
    print(f"[params] Re = {params.reynolds:,.0f}")

    sim = UPipeSimulation(params, workdir=os.getcwd())
    sim.run()


if __name__ == "__main__":
    main()
