"""
run_demo.py
===========

Demonstration of the parametric U-pipe workflow **without** a running Fluent
instance.

It drives :func:`u_pipe_report.build_demo_results` for a small parametric
sweep (varying inlet velocity / bend radius) and writes one consolidated HTML
report per design point.  This lets you inspect the report output and the
parametric plumbing before running the real PyFluent job in
``u_pipe_fluent.py``.
"""

from __future__ import annotations

import os

from u_pipe_report import (
    build_demo_results,
    generate_report,
    generate_comparison_report,
    SimulationResults,
)


def sweep_velocity(velocities=(0.5, 1.0, 2.0, 5.0)):
    """Generate a report for each inlet velocity in the sweep."""
    os.makedirs("reports", exist_ok=True)
    all_res = []
    for v in velocities:
        res = build_demo_results(inlet_velocity=v)
        res.case_name = f"u_pipe_v{v:.1f}"
        all_res.append(res)
        path = f"reports/u_pipe_v{v:.1f}.html"
        generate_report(res, path)
        print(
            f"v={v:5.2f} m/s | Re={res.reynolds_number:8,.0f} | "
            f"dp={res.pressure_drop_pa:8.1f} Pa | K={res.bend_loss_coefficient:.3f}"
            f"  -> {path}"
        )

    comp_path = "reports/u_pipe_comparison.html"
    generate_comparison_report(all_res, comp_path, varying_param="inlet_velocity")
    print(f"\nComparison report -> {comp_path}")


def single_demo() -> SimulationResults:
    """Single default-case report, written next to the script."""
    res = build_demo_results()
    generate_report(res, "u_pipe_report_demo.html")
    print(f"Demo report -> u_pipe_report_demo.html")
    return res


if __name__ == "__main__":
    print("=== U-pipe parametric demo (analytical estimates) ===\n")
    single_demo()
    print()
    sweep_velocity()
