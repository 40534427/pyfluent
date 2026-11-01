#!/usr/bin/env python3
"""Plot the suspension-line tensions written by run_parachute.py.

Reads ``history.csv`` and ``line_force.csv`` from an output directory and
writes a two-panel PNG:

* top    : tension of the bottom (anchor) segment of every line
* bottom : total force at the line convergence point (``line_anchor_force``)
           together with the maximum single-line tension
"""

from __future__ import annotations

import argparse
import csv
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


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

    fig, ax = plt.subplots(2, 1, figsize=(9, 6.4), sharex=True)
    ax[0].plot(t, tension, lw=0.9)
    ax[0].set_ylabel("line tension [N]")
    ax[0].set_title("Suspension line tension (bottom segment of each line)")
    ax[0].grid(alpha=0.3)

    i = {k: n for n, k in enumerate(h_head)}
    ax[1].plot(h[:, i["time"]], h[:, i["line_anchor_force"]],
               color="k", lw=1.4, label="convergence point total")
    ax[1].plot(h[:, i["time"]], h[:, i["line_tension_max"]],
               color="tab:red", lw=1.0, label="max single line")
    ax[1].plot(h[:, i["time"]], h[:, i["line_tension_sum"]],
               color="tab:blue", lw=1.0, ls="--", label="sum of lines")
    ax[1].set_xlabel("time [s]")
    ax[1].set_ylabel("force [N]")
    ax[1].grid(alpha=0.3)
    ax[1].legend(loc="upper left")

    fig.tight_layout()
    fig.savefig(output, dpi=150)
    print(f"wrote {output}")
    print(f"  peak anchor force {h[:, i['line_anchor_force']].max():.1f} N "
          f"at t={h[h[:, i['line_anchor_force']].argmax(), i['time']]:.4f} s")
    print(f"  peak line tension {h[:, i['line_tension_max']].max():.1f} N")


if __name__ == "__main__":
    raise SystemExit(main())
