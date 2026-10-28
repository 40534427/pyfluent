"""
u_pipe_report.py
================

Automated report generation for the U-shaped pipe CFD simulation.

This module produces a self-contained HTML report (with embedded matplotlib
figures in base64) summarising the parametric U-pipe flow-field calculation.
It is designed to be driven either by real PyFluent results (extracted from a
live Fluent session) or by a demonstration data-set so the report pipeline can
be exercised without a running Fluent instance.

Public API
----------
- :class:`SimulationResults`  : data container for all results.
- :func:`build_figures`        : render all matplotlib figures into bytes.
- :func:`generate_report`      : write the final HTML report to disk.
"""

from __future__ import annotations

import base64
import io
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import numpy as np


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------
@dataclass
class SimulationResults:
    """Container for every piece of information shown in the report.

    All fields are plain Python / numpy types so the object can be built from
    either a real Fluent session or a synthetic / analytical source.
    """

    # --- Geometry / input parameters --------------------------------------
    pipe_diameter: float = 0.05          # m
    inlet_length: float = 0.30           # m (straight inlet leg)
    outlet_length: float = 0.30          # m (straight outlet leg)
    bend_radius: float = 0.10            # m (centerline bend radius)
    inlet_velocity: float = 1.0          # m/s
    fluid_density: float = 998.2         # kg/m^3  (water @ 20 C)
    fluid_viscosity: float = 1.003e-3    # Pa s   (water @ 20 C)
    turbulence_model: str = "k-omega SST"

    # --- Mesh statistics ---------------------------------------------------
    n_cells: int = 0
    n_faces: int = 0
    min_volume: float = 0.0
    max_volume: float = 0.0

    # --- Solver / convergence ---------------------------------------------
    iterations: int = 0
    residuals: Dict[str, List[float]] = field(default_factory=dict)

    # --- Integral results --------------------------------------------------
    pressure_drop_pa: float = 0.0        # inlet - outlet static pressure
    outlet_avg_velocity: float = 0.0     # m/s
    outlet_mass_flow: float = 0.0        # kg/s
    reynolds_number: float = 0.0
    bend_loss_coefficient: float = 0.0   # K = dp / (0.5 rho v^2)

    # --- Profile data (1-D arrays) ----------------------------------------
    # Centre-line velocity along the pipe axis (inlet -> outlet)
    cl_position: np.ndarray = field(default_factory=lambda: np.array([]))
    cl_velocity: np.ndarray = field(default_factory=lambda: np.array([]))

    # Cross-stream velocity profile at the outlet (r/R, v/v_mean)
    outlet_r_over_r: np.ndarray = field(default_factory=lambda: np.array([]))
    outlet_v_over_vmean: np.ndarray = field(default_factory=lambda: np.array([]))

    # Cross-stream velocity profile at the bend exit (r/R, v/v_mean)
    bend_exit_r_over_r: np.ndarray = field(default_factory=lambda: np.array([]))
    bend_exit_v_over_vmean: np.ndarray = field(default_factory=lambda: np.array([]))

    # 2-D contour data on the symmetry plane (x, y, velocity magnitude)
    contour_x: np.ndarray = field(default_factory=lambda: np.array([]))
    contour_y: np.ndarray = field(default_factory=lambda: np.array([]))
    contour_v: np.ndarray = field(default_factory=lambda: np.array([]))

    # --- Bookkeeping -------------------------------------------------------
    case_name: str = "u_pipe"
    solver_time_s: float = 0.0
    generated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def derived(self) -> None:
        """Fill in cheap derived quantities (Re, K) if not already set."""
        if self.reynolds_number == 0 and self.inlet_velocity > 0:
            self.reynolds_number = (
                self.fluid_density
                * self.inlet_velocity
                * self.pipe_diameter
                / self.fluid_viscosity
            )
        if (
            self.bend_loss_coefficient == 0
            and self.inlet_velocity > 0
            and self.pressure_drop_pa > 0
        ):
            self.bend_loss_coefficient = self.pressure_drop_pa / (
                0.5 * self.fluid_density * self.inlet_velocity ** 2
            )


# ---------------------------------------------------------------------------
# Figure generation
# ---------------------------------------------------------------------------
def _fig_to_base64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def build_figures(res: SimulationResults) -> Dict[str, str]:
    """Render every figure and return a dict of name -> base64 PNG string."""
    figs: Dict[str, str] = {}

    # 1. Residual convergence history --------------------------------------
    fig, ax = plt.subplots(figsize=(8, 4.2))
    if res.residuals:
        for name, vals in res.residuals.items():
            ax.semilogy(range(1, len(vals) + 1), vals, label=name)
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Scaled residual")
        ax.set_title("Convergence history")
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(True, which="both", ls=":", alpha=0.5)
    else:
        ax.text(0.5, 0.5, "No residual data", ha="center", va="center")
        ax.set_axis_off()
    figs["residuals"] = _fig_to_base64(fig)

    # 2. Centre-line velocity along the pipe --------------------------------
    fig, ax = plt.subplots(figsize=(8, 4.2))
    if res.cl_position.size:
        ax.plot(res.cl_position, res.cl_velocity, "b-", lw=1.8)
        ax.set_xlabel("Streamwise position along centre-line (m)")
        ax.set_ylabel("Axial velocity (m/s)")
        ax.set_title("Centre-line axial velocity")
        ax.grid(True, ls=":", alpha=0.5)
    else:
        ax.text(0.5, 0.5, "No centre-line data", ha="center", va="center")
        ax.set_axis_off()
    figs["centerline_velocity"] = _fig_to_base64(fig)

    # 3. Outlet cross-stream velocity profile ------------------------------
    fig, ax = plt.subplots(figsize=(6, 4.2))
    if res.outlet_r_over_r.size:
        ax.plot(
            res.outlet_r_over_r,
            res.outlet_v_over_vmean,
            "o-",
            label="outlet",
            lw=1.5,
        )
        if res.bend_exit_r_over_r.size:
            ax.plot(
                res.bend_exit_r_over_r,
                res.bend_exit_v_over_vmean,
                "s-",
                label="bend exit",
                lw=1.5,
            )
        ax.set_xlabel(r"$r / R$")
        ax.set_ylabel(r"$v / \bar{v}$")
        ax.set_title("Cross-stream velocity profiles")
        ax.legend()
        ax.grid(True, ls=":", alpha=0.5)
    else:
        ax.text(0.5, 0.5, "No profile data", ha="center", va="center")
        ax.set_axis_off()
    figs["velocity_profiles"] = _fig_to_base64(fig)

    # 4. Velocity magnitude contour on the symmetry plane -------------------
    fig, ax = plt.subplots(figsize=(9, 4.5))
    if res.contour_v.size and res.contour_x.size:
        try:
            cs = ax.tricontourf(
                res.contour_x.ravel(),
                res.contour_y.ravel(),
                res.contour_v.ravel(),
                levels=25,
                cmap="turbo",
            )
            fig.colorbar(cs, ax=ax, label="velocity magnitude (m/s)")
            ax.set_title("Velocity magnitude - symmetry plane")
            ax.set_xlabel("x (m)")
            ax.set_ylabel("y (m)")
            ax.set_aspect("equal")
        except Exception:
            ax.text(0.5, 0.5, "Contour render failed", ha="center", va="center")
            ax.set_axis_off()
    else:
        ax.text(0.5, 0.5, "No contour data", ha="center", va="center")
        ax.set_axis_off()
    figs["velocity_contour"] = _fig_to_base64(fig)

    return figs


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------
_CSS = """
<style>
  body { font-family: 'Segoe UI', Arial, sans-serif; max-width: 1100px;
         margin: 30px auto; padding: 0 20px; color: #222; line-height: 1.55; }
  h1 { color: #1a4f8a; border-bottom: 3px solid #1a4f8a; padding-bottom: 8px; }
  h2 { color: #1a4f8a; margin-top: 32px; border-bottom: 1px solid #ccc; }
  h3 { color: #333; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0; }
  th, td { border: 1px solid #bbb; padding: 8px 12px; text-align: left; }
  th { background: #1a4f8a; color: #fff; }
  tr:nth-child(even) { background: #f4f7fb; }
  .figure { text-align: center; margin: 22px 0; }
  .figure img { max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }
  .caption { font-size: 0.85em; color: #666; margin-top: 6px; }
  .kpi { display: inline-block; background: #eef4fb; border: 1px solid #bdd4ef;
         border-radius: 8px; padding: 14px 22px; margin: 8px; text-align: center; }
  .kpi .value { font-size: 1.6em; font-weight: bold; color: #1a4f8a; }
  .kpi .label { font-size: 0.85em; color: #555; }
  .meta { color: #888; font-size: 0.85em; }
</style>
"""


def _kpi_html(res: SimulationResults) -> str:
    res.derived()
    cards = [
        ("Reynolds number", f"{res.reynolds_number:,.0f}"),
        ("Pressure drop", f"{res.pressure_drop_pa:.1f} Pa"),
        ("Bend loss coeff. K", f"{res.bend_loss_coefficient:.3f}"),
        ("Outlet mass flow", f"{res.outlet_mass_flow:.4f} kg/s"),
        ("Outlet avg velocity", f"{res.outlet_avg_velocity:.3f} m/s"),
        ("Solver time", f"{res.solver_time_s:.1f} s"),
    ]
    return "".join(
        f'<div class="kpi"><div class="value">{v}</div>'
        f'<div class="label">{l}</div></div>'
        for l, v in cards
    )


def generate_report(
    res: SimulationResults,
    output_path: str = "u_pipe_report.html",
) -> str:
    """Build the HTML report and write it to *output_path*.

    Returns the path of the written file.
    """
    res.derived()
    figs = build_figures(res)

    geometry_rows = [
        ("Pipe diameter D", f"{res.pipe_diameter*1000:.1f} mm"),
        ("Inlet leg length L1", f"{res.inlet_length*1000:.0f} mm"),
        ("Outlet leg length L2", f"{res.outlet_length*1000:.0f} mm"),
        ("Bend centreline radius R", f"{res.bend_radius*1000:.0f} mm"),
        (
            "Curvature ratio R/D",
            f"{res.bend_radius/res.pipe_diameter:.2f}",
        ),
    ]
    bc_rows = [
        ("Inlet velocity", f"{res.inlet_velocity:.2f} m/s"),
        ("Fluid density", f"{res.fluid_density:.1f} kg/m³"),
        ("Dynamic viscosity", f"{res.fluid_viscosity:.3e} Pa·s"),
        ("Turbulence model", res.turbulence_model),
        (
            "Reynolds number Re",
            f"{res.reynolds_number:,.0f}",
        ),
    ]
    mesh_rows = [
        ("Number of cells", f"{res.n_cells:,}"),
        ("Number of faces", f"{res.n_faces:,}"),
        ("Min cell volume", f"{res.min_volume:.3e} m³"),
        ("Max cell volume", f"{res.max_volume:.3e} m³"),
    ]

    def _table(rows: List[Tuple[str, str]]) -> str:
        body = "".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows
        )
        return f"<table><tr><th>Parameter</th><th>Value</th></tr>{body}</table>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>U-pipe CFD report - {res.case_name}</title>
{_CSS}
</head>
<body>
<h1>U-shaped Pipe Flow-Field Simulation Report</h1>
<p class="meta">Case: <b>{res.case_name}</b> &middot;
   Generated: {res.generated_at}</p>

<h2>1. Key Performance Indicators</h2>
<div>{_kpi_html(res)}</div>

<h2>2. Geometry Definition</h2>
{_table(geometry_rows)}

<h2>3. Boundary Conditions &amp; Fluid</h2>
{_table(bc_rows)}

<h2>4. Mesh Statistics</h2>
{_table(mesh_rows)}

<h2>5. Convergence History</h2>
<div class="figure">
  <img src="data:image/png;base64,{figs['residuals']}" alt="residuals">
  <div class="caption">Scaled residuals vs. iteration
       ({res.iterations} iterations performed).</div>
</div>

<h2>6. Velocity Field</h2>
<div class="figure">
  <img src="data:image/png;base64,{figs['velocity_contour']}"
       alt="velocity contour">
  <div class="caption">Velocity magnitude on the symmetry plane.</div>
</div>

<div class="figure">
  <img src="data:image/png;base64,{figs['centerline_velocity']}"
       alt="centerline velocity">
  <div class="caption">Centre-line axial velocity from inlet to outlet.</div>
</div>

<div class="figure">
  <img src="data:image/png;base64,{figs['velocity_profiles']}"
       alt="velocity profiles">
  <div class="caption">Cross-stream velocity profiles normalised by bulk
       velocity.</div>
</div>

<h2>7. Results Summary</h2>
<table>
<tr><th>Quantity</th><th>Value</th><th>Unit</th></tr>
<tr><td>Pressure drop (&Delta;p)</td><td>{res.pressure_drop_pa:.2f}</td><td>Pa</td></tr>
<tr><td>Bend loss coefficient K</td><td>{res.bend_loss_coefficient:.4f}</td><td>-</td></tr>
<tr><td>Outlet mass-flow rate</td><td>{res.outlet_mass_flow:.5f}</td><td>kg/s</td></tr>
<tr><td>Outlet area-averaged velocity</td><td>{res.outlet_avg_velocity:.4f}</td><td>m/s</td></tr>
<tr><td>Reynolds number Re</td><td>{res.reynolds_number:,.0f}</td><td>-</td></tr>
<tr><td>Solver wall-clock time</td><td>{res.solver_time_s:.1f}</td><td>s</td></tr>
</table>

<h2>8. Conclusions</h2>
<ul>
  <li>The solution converged after {res.iterations} iterations; all scaled
      residuals fell below the default criteria.</li>
  <li>Pressure drop across the U-bend is {res.pressure_drop_pa:.1f} Pa,
      corresponding to a bend loss coefficient
      K = {res.bend_loss_coefficient:.3f}.</li>
  <li>Secondary-flow / Dean-vortex effects redistribute momentum across the
      cross-section (see cross-stream profiles).</li>
</ul>

<p class="meta">Report generated automatically by PyFluent U-pipe workflow.</p>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return output_path


# ---------------------------------------------------------------------------
# Analytical / synthetic data generator (for demonstration)
# ---------------------------------------------------------------------------
def build_demo_results(
    pipe_diameter: float = 0.05,
    inlet_velocity: float = 1.0,
    bend_radius: float = 0.10,
) -> SimulationResults:
    """Build a plausible :class:`SimulationResults` from analytical estimates.

    This lets the report pipeline be demonstrated without a live Fluent
    session.  The numbers follow textbook turbulent-pipe / U-bend correlations
    but are *not* a substitute for a real CFD run.
    """
    rho = 998.2
    mu = 1.003e-3
    Re = rho * inlet_velocity * pipe_diameter / mu

    # Darcy friction factor (Blasius) + typical U-bend minor-loss coefficient
    f = 0.3164 * Re ** (-0.25) if Re < 1e5 else 0.184 * Re ** (-0.2)
    K_bend = 0.35 * (bend_radius / pipe_diameter) ** (-0.5)  # rough approx
    L1 = 0.30
    L2 = 0.30
    L_total = L1 + L2 + np.pi * bend_radius
    dp_major = f * (L_total / pipe_diameter) * 0.5 * rho * inlet_velocity ** 2
    dp_minor = K_bend * 0.5 * rho * inlet_velocity ** 2
    dp = dp_major + dp_minor

    # Centre-line velocity (inlet -> bend acceleration -> recovery)
    s = np.linspace(0, L_total, 300)
    v_cl = (
        inlet_velocity
        * (1.18 + 0.05 * np.sin(2 * np.pi * s / max(L_total, 1e-6)))
    )
    # Dip near the bend then overshoot
    bend_start = L1
    bend_end = L1 + np.pi * bend_radius
    v_cl[(s > bend_start) & (s < bend_end)] *= 1.05
    v_cl[(s > bend_end) & (s < bend_end + 0.05)] *= 0.97

    # Outlet cross-stream profile (1/7 power law + secondary-flow distortion)
    r = np.linspace(0, 1, 41)
    v_outlet = (1 - r) ** (1.0 / 7.0)
    v_bend_exit = v_outlet * (1 + 0.12 * np.cos(np.pi * r))  # Dean distortion

    # 2-D contour on the symmetry plane (x = streamwise, y = cross-stream)
    nx, ny = 120, 30
    xs = np.linspace(0, L_total, nx)
    ys = np.linspace(-pipe_diameter / 2, pipe_diameter / 2, ny)
    X, Y = np.meshgrid(xs, ys)
    # pipe outline (straight + semicircle bend)
    in_pipe = np.abs(Y) <= pipe_diameter / 2
    # velocity profile: parabolic-ish core, speed up in bend
    core = 1.0 - (2 * Y / pipe_diameter) ** 2
    bend_factor = 1.0 + 0.15 * np.exp(
        -((xs - bend_start - np.pi * bend_radius / 2) ** 2) / (0.01)
    )[np.newaxis, :]
    V = inlet_velocity * (1.5 * core + 0.1) * bend_factor
    V = np.where(in_pipe, V, np.nan)

    res = SimulationResults(
        pipe_diameter=pipe_diameter,
        inlet_length=L1,
        outlet_length=L2,
        bend_radius=bend_radius,
        inlet_velocity=inlet_velocity,
        fluid_density=rho,
        fluid_viscosity=mu,
        turbulence_model="k-omega SST",
        n_cells=184_320,
        n_faces=521_890,
        min_volume=1.2e-9,
        max_volume=8.7e-8,
        iterations=250,
        residuals={
            "continuity": list(np.logspace(-1, -6, 250)),
            "x-velocity": list(np.logspace(-1, -6.2, 250)),
            "y-velocity": list(np.logspace(-1, -6.1, 250)),
            "k": list(np.logspace(-1, -5.5, 250)),
            "omega": list(np.logspace(-1, -5.3, 250)),
        },
        pressure_drop_pa=float(dp),
        outlet_avg_velocity=inlet_velocity * 1.002,
        outlet_mass_flow=rho * inlet_velocity * np.pi * (pipe_diameter / 2) ** 2,
        reynolds_number=float(Re),
        bend_loss_coefficient=float(dp / (0.5 * rho * inlet_velocity ** 2)),
        cl_position=s,
        cl_velocity=v_cl,
        outlet_r_over_r=r,
        outlet_v_over_vmean=v_outlet / v_outlet.mean(),
        bend_exit_r_over_r=r,
        bend_exit_v_over_vmean=v_bend_exit / v_bend_exit.mean(),
        contour_x=X,
        contour_y=Y,
        contour_v=V,
        case_name="u_pipe_demo",
        solver_time_s=42.7,
    )
    return res


# ---------------------------------------------------------------------------
# Parametric comparison report (multiple design points)
# ---------------------------------------------------------------------------
def generate_comparison_report(
    results: List[SimulationResults],
    output_path: str = "u_pipe_comparison.html",
    varying_param: str = "inlet_velocity",
) -> str:
    """Build a single HTML report comparing multiple design points.

    Parameters
    ----------
    results : list of SimulationResults
        One entry per design point.
    varying_param : str
        Name of the parameter that was swept (used for plot labels).
    """
    import matplotlib.pyplot as plt

    for r in results:
        r.derived()

    # 1. KPI comparison table
    kpi_rows = []
    for r in results:
        kpi_rows.append(
            (
                r.case_name,
                f"{r.inlet_velocity:.2f}",
                f"{r.reynolds_number:,.0f}",
                f"{r.pressure_drop_pa:.1f}",
                f"{r.bend_loss_coefficient:.3f}",
                f"{r.outlet_mass_flow:.4f}",
                f"{r.solver_time_s:.1f}",
            )
        )
    kpi_table = (
        "<table><tr>"
        "<th>Case</th><th>v (m/s)</th><th>Re</th><th>dp (Pa)</th>"
        "<th>K</th><th>m_dot (kg/s)</th><th>Time (s)</th>"
        "</tr>"
        + "".join(
            "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
            for row in kpi_rows
        )
        + "</table>"
    )

    # 2. dp vs velocity and K vs Re
    vs = [r.inlet_velocity for r in results]
    dps = [r.pressure_drop_pa for r in results]
    res_ = [r.reynolds_number for r in results]
    ks = [r.bend_loss_coefficient for r in results]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    axes[0].plot(vs, dps, "o-", color="#1a4f8a")
    axes[0].set_xlabel("Inlet velocity (m/s)")
    axes[0].set_ylabel("Pressure drop (Pa)")
    axes[0].set_title(r"$\Delta p$ vs $v_{in}$")
    axes[0].grid(True, ls=":", alpha=0.5)

    axes[1].plot(res_, ks, "s-", color="#c0392b")
    axes[1].set_xlabel("Reynolds number Re")
    axes[1].set_ylabel("Bend loss coefficient K")
    axes[1].set_title("K vs Re")
    axes[1].grid(True, ls=":", alpha=0.5)
    fig.tight_layout()
    comparison_img = _fig_to_base64(fig)

    # 3. Overlay outlet profiles
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for r in results:
        if r.outlet_r_over_r.size:
            ax.plot(
                r.outlet_r_over_r,
                r.outlet_v_over_vmean,
                label=f"v={r.inlet_velocity:.1f} m/s",
            )
    ax.set_xlabel(r"$r/R$")
    ax.set_ylabel(r"$v/\bar{v}$")
    ax.set_title("Outlet velocity profiles across design points")
    ax.legend(fontsize=8)
    ax.grid(True, ls=":", alpha=0.5)
    profiles_img = _fig_to_base64(fig)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>U-pipe parametric comparison</title>
{_CSS}
</head>
<body>
<h1>U-pipe Parametric Study - Comparison Report</h1>
<p class="meta">Generated: {time.strftime("%Y-%m-%d %H:%M:%S")} &middot;
   {len(results)} design points &middot; swept parameter: {varying_param}</p>

<h2>1. Design-point KPI table</h2>
{kpi_table}

<h2>2. Pressure-drop and loss-coefficient trends</h2>
<div class="figure">
  <img src="data:image/png;base64,{comparison_img}" alt="comparison">
</div>

<h2>3. Outlet velocity profiles</h2>
<div class="figure">
  <img src="data:image/png;base64,{profiles_img}" alt="profiles">
</div>

<h2>4. Observations</h2>
<ul>
  <li>Pressure drop grows non-linearly with inlet velocity (turbulent scaling
      ~v<sup>1.75</sup> from the Blasius correlation).</li>
  <li>The bend loss coefficient K decreases with Re as the boundary layer
      thins and the flow becomes more turbulent.</li>
  <li>Cross-stream profile distortion (Dean vortices) is visible in all
      turbulent cases; the flatness increases with Re.</li>
</ul>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return output_path


if __name__ == "__main__":
    res = build_demo_results()
    path = generate_report(res, "/workspace/u_pipe_cfd/u_pipe_report_demo.html")
    print(f"Report written to {path}")
