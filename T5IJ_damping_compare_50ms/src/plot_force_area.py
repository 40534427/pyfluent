#!/usr/bin/env python3
"""Plot the canopy resultant force and the canopy area against time.

Reads ``history.csv`` written by ``run_parachute.py`` and writes two PNGs:

* ``canopy_force_time_<name>.png``
      canopy resultant aerodynamic force (``coupling_drag``) together with the
      total suspension-line force at the convergence point
      (``line_anchor_force``);
* ``canopy_area_time_<name>.png``
      canopy surface area (``canopy_area``) and the area-weighted mean radius
      (``canopy_radius``).

Usage
-----
    python3 plot_force_area.py --workdir results --name T5_bend10_const220_80ms
"""

from __future__ import annotations

import argparse
import csv
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_history(path):
    with open(path, newline="") as fh:
        r = csv.reader(fh)
        head = next(r)
        rows = [[float(v) for v in row] for row in r if row]
    return head, np.array(rows)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--workdir", required=True,
                   help="directory containing history.csv")
    p.add_argument("--name", default=None,
                   help="file-name tag (default: workdir basename)")
    p.add_argument("--outdir", default=None,
                   help="figure directory (default: workdir)")
    a = p.parse_args(argv)

    head, h = read_history(os.path.join(a.workdir, "history.csv"))
    i = {k: n for n, k in enumerate(head)}
    t = h[:, i["time"]] * 1.0e3          # ms
    drag = h[:, i["coupling_drag"]]
    anchor = np.maximum(h[:, i["line_anchor_force"]], 0.0)
    area = h[:, i["canopy_area"]]
    radi = h[:, i["canopy_radius"]]

    name = a.name or os.path.basename(os.path.normpath(a.workdir))
    out = a.outdir or a.workdir
    os.makedirs(out, exist_ok=True)

    dpi = 160
    common = dict(lw=1.4)

    # ------------------------------------------------------------ force vs t
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    ax.plot(t, drag, color="tab:blue", label="canopy resultant force "
                                            "(coupling_drag)", **common)
    ax.plot(t, anchor, color="tab:red", ls="--",
            label="convergence-point line force", **common)
    kd = int(np.argmax(drag))
    ka = int(np.argmax(anchor))
    ax.plot(t[kd], drag[kd], "o", ms=5, color="tab:blue")
    ax.annotate(f"peak canopy force {drag[kd]:.0f} N\n@ t = {t[kd]:.1f} ms",
                xy=(t[kd], drag[kd]), xytext=(8, 10),
                textcoords="offset points", fontsize=9, color="tab:blue")
    ax.plot(t[ka], anchor[ka], "o", ms=5, color="tab:red")
    ax.annotate(f"peak line force {anchor[ka]:.0f} N\n@ t = {t[ka]:.1f} ms",
                xy=(t[ka], anchor[ka]), xytext=(0.55, 0.32),
                textcoords="axes fraction", fontsize=9, color="tab:red",
                arrowprops=dict(arrowstyle="->", color="tab:red", lw=0.8))
    ax.axhline(0, color="grey", lw=0.5)
    ax.set_xlim(0, t[-1])
    ax.set_ylim(bottom=0)
    ax.set_xlabel("time [ms]")
    ax.set_ylabel("force [N]")
    ax.set_title("Canopy force vs time  (constant inflow 220 m/s, "
                 "bending-stiff membrane)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    f1 = os.path.join(out, f"canopy_force_time_{name}.png")
    fig.savefig(f1, dpi=dpi)
    plt.close(fig)

    # ------------------------------------------------------------- area vs t
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    l_area, = ax.plot(t, area, color="tab:green", label="canopy surface area",
                      **common)
    ax.set_xlabel("time [ms]")
    ax.set_ylabel("canopy area [m$^2$]")
    ax.set_title("Canopy area vs time  (constant inflow 220 m/s, "
                 "bending-stiff membrane)")
    ax.grid(alpha=0.3)
    ax2 = ax.twinx()
    l_rad, = ax2.plot(t, radi, color="tab:orange", ls="--", lw=1.2,
                      label="mean radius $\\bar{R}$")
    ax2.set_ylabel("mean canopy radius [m]")
    ka = int(np.argmax(area))
    ax.plot(t[ka], area[ka], "o", ms=5, color="tab:green")
    ax.annotate(f"peak area {area[ka]:.3f} m$^2$\n@ t = {t[ka]:.1f} ms",
                xy=(t[ka], area[ka]), xytext=(-55, -34),
                textcoords="offset points", fontsize=9, color="tab:green",
                ha="right",
                arrowprops=dict(arrowstyle="->", color="tab:green", lw=0.8))
    imin = int(np.argmin(area[:int(0.3 * len(area))]))
    ax.annotate("stowed bundle:\ncompaction before inflation",
                xy=(t[imin], area[imin]), xytext=(0.30, 0.08),
                textcoords="axes fraction", fontsize=8, color="grey",
                arrowprops=dict(arrowstyle="->", color="grey", lw=0.7))
    ax.legend(handles=[l_area, l_rad], loc="lower right", fontsize=9)
    fig.tight_layout()
    f2 = os.path.join(out, f"canopy_area_time_{name}.png")
    fig.savefig(f2, dpi=dpi)
    plt.close(fig)

    print(f"wrote {f1}")
    print(f"wrote {f2}")
    print(f"  t_end={t[-1]:.1f} ms  A_end={area[-1]:.4f} m^2  "
          f"A_peak={area.max():.4f} m^2  F_peak={drag.max():.1f} N  "
          f"line_peak={anchor.max():.1f} N")


if __name__ == "__main__":
    main()
