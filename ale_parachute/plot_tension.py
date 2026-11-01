#!/usr/bin/env python3
"""Plot the suspension-line tensions written by run_parachute.py.

Reads ``history.csv`` and ``line_force.csv`` from an output directory and
writes a two-panel PNG:

* top    : tension of the bottom (anchor) segment of every line,
           overlaid with the DYNA / PARASIM-Explicit reference curves
           digitised from the project presentation.
* bottom : total force at the line convergence point (``line_anchor_force``)
           together with the maximum single-line tension and the PPT
           reference (~2000 N at full canopy opening).
"""

from __future__ import annotations

import argparse
import csv
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ---- Reference data digitised from the project PPT
#      (降落伞展开伞绳张力计算问题分析v3_0829.pptx, slide 4).
#      The PPT drives the inlet with a 0 -> 220 m/s ramp over 0.04 s,
#      while this solver run uses a *constant* 220 m/s from t = 0, so the
#      rise time differs even though the terminal dynamic pressure matches.
PPT_DYNA = np.array([
    (0.000,   0), (0.005,  -5), (0.010,  -8), (0.015,  -6),
    (0.020,   0), (0.025,   5), (0.028,  20), (0.030,  30),
    (0.033,  15), (0.036,  90), (0.040, 190), (0.043, 240),
    (0.046, 200), (0.050, 180), (0.053, 240), (0.056, 200),
    (0.060, 220), (0.064, 180), (0.068, 170), (0.072, 220),
    (0.076, 210), (0.080, 190),
])
PPT_PARASIM = np.array([
    (0.000,   0), (0.010,  -5), (0.020,  -3), (0.030,  -2),
    (0.035,   0), (0.040,   5), (0.045,   8), (0.050,  20),
    (0.053,  40), (0.056, 230), (0.059, 130), (0.062,  70),
    (0.065, 130), (0.068,  90), (0.071, 170), (0.074, 130),
    (0.077, 170), (0.080, 170),
])
PPT_ANCHOR_2000N = 2000.0  # convergence-point total force at full opening


def read_csv(path):
    with open(path, newline="") as fh:
        r = csv.reader(fh)
        head = next(r)
        rows = [[float(v) for v in row] for row in r if row]
    return head, np.array(rows)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--outdir", default="out")
    p.add_argument("--output", default=None)
    a = p.parse_args(argv)

    hist = os.path.join(a.outdir, "history.csv")
    lines = os.path.join(a.outdir, "line_force.csv")
    output = a.output or os.path.join(a.outdir, "line_tension.png")

    h_head, h = read_csv(hist)
    l_head, l = read_csv(lines)
    t = l[:, 0]
    tension = np.maximum(l[:, 1:], 0.0)

    fig, ax = plt.subplots(2, 1, figsize=(10, 7.2), sharex=True)

    # ---------- top: per-line tension + PPT reference ----------
    ax[0].plot(t, tension, lw=0.8, alpha=0.55,
               label="this solver (16 lines)")
    ax[0].plot(PPT_DYNA[:, 0], PPT_DYNA[:, 1], "b-", lw=1.6,
               label="PPT  DYNA (ramp 0\u2192220)")
    ax[0].plot(PPT_PARASIM[:, 0], PPT_PARASIM[:, 1], "r-", lw=1.6,
               label="PPT  PARASIM Explicit")
    ax[0].axhline(0, color="grey", lw=0.5)
    ax[0].set_ylabel("line tension [N]")
    ax[0].set_title("Suspension-line tension  (bottom/anchor segment)")
    ax[0].grid(alpha=0.3)
    ax[0].legend(loc="upper left", fontsize=9)

    # ---------- bottom: convergence point + PPT reference ----------
    i = {k: n for n, k in enumerate(h_head)}
    ax[1].plot(h[:, i["time"]], h[:, i["line_anchor_force"]],
               color="k", lw=1.5, label="convergence-point total")
    ax[1].plot(h[:, i["time"]], h[:, i["line_tension_max"]],
               color="tab:red", lw=1.0, label="max single line")
    ax[1].plot(h[:, i["time"]], h[:, i["line_tension_sum"]],
               color="tab:blue", lw=1.0, ls="--", label="sum of 16 lines")
    ax[1].axhline(PPT_ANCHOR_2000N, color="purple", lw=1.2, ls=":",
                  label=f"PPT reference ~{PPT_ANCHOR_2000N:.0f} N")
    ax[1].set_xlabel("time [s]")
    ax[1].set_ylabel("force [N]")
    ax[1].set_title("Convergence-point force and line-tension statistics")
    ax[1].grid(alpha=0.3)
    ax[1].legend(loc="upper left", fontsize=9)

    fig.suptitle(
        "Inflow: constant 220 m/s  (PPT uses 0\u2192220 m/s ramp over 0.04 s)",
        fontsize=10, style="italic")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(output, dpi=150)
    print(f"wrote {output}")
    pk_anchor = float(h[:, i["line_anchor_force"]].max())
    pk_t = float(h[h[:, i["line_anchor_force"]].argmax(), i["time"]])
    pk_line = float(h[:, i["line_tension_max"]].max())
    print(f"  peak anchor force {pk_anchor:.1f} N at t={pk_t:.4f} s"
          f"  (PPT ~{PPT_ANCHOR_2000N:.0f} N)")
    print(f"  peak single-line tension {pk_line:.1f} N"
          f"  (PPT DYNA ~{PPT_DYNA[:, 1].max():.0f} N, "
          f"PARASIM ~{PPT_PARASIM[:, 1].max():.0f} N)")


if __name__ == "__main__":
    raise SystemExit(main())
