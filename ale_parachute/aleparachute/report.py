"""Automatic calculation-report generator for the ALE parachute solver.

After a run (or on an existing ``outdir``), :func:`generate_report` produces a
self-contained HTML report plus the underlying data files (``.dat`` tables,
PNG figures, and an MP4 animation) that the report references.

Coverage (matches the user requirements):

a) Calculation conditions  - domain, mesh, solver settings, material cards
b) Line-force / confluence-force curves (with .dat raw data)
c) Canopy shape evolution, velocity / pressure fields, canopy stress / strain
   contours (with a video animation as backup)
d) CPU model, physical cores, base frequency, wall-clock time

The module is importable and also runnable as ``python -m aleparachute.report
--outdir ...`` for post-hoc generation on an existing result directory.
"""

from __future__ import annotations

import csv
import glob
import html
import json
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation


META_NAME = "run_meta.json"
R_AIR = 287.05          # J/(kg.K), dry air


# ---------------------------------------------------------------------------
# Run metadata (persisted so the report can be rebuilt afterwards)
# ---------------------------------------------------------------------------
def _deep_update(dst: dict, src: dict) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_update(dst[k], v)
        else:
            dst[k] = v


def write_run_meta(outdir: str, payload: dict, merge: bool = True) -> str:
    """Write ``run_meta.json`` (merged with the existing one by default)."""
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, META_NAME)
    data = read_run_meta(outdir) or {} if merge else {}
    _deep_update(data, payload)
    data.setdefault("schema", 1)
    data.setdefault("generated", datetime.now().isoformat(timespec="seconds"))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
    return path


def read_run_meta(outdir: str) -> Optional[dict]:
    path = os.path.join(outdir, META_NAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# CPU information
# ---------------------------------------------------------------------------
def get_cpu_info() -> Dict[str, str]:
    """Return CPU model, physical cores, base frequency as strings."""
    info = {"model": "",
            "physical_cores": "?", "base_frequency_ghz": "?",
            "logical_cores": "?"}
    try:
        import psutil
        phy = psutil.cpu_count(logical=False)
        log = psutil.cpu_count(logical=True)
        if phy:
            info["physical_cores"] = str(phy)
        if log:
            info["logical_cores"] = str(log)
        freq = psutil.cpu_freq()
        if freq and getattr(freq, "max", 0):
            info["base_frequency_ghz"] = f"{freq.max / 1000.0:.2f}"
        elif freq:
            info["base_frequency_ghz"] = f"{freq.current / 1000.0:.2f}"
    except Exception:
        pass
    # model name from /proc/cpuinfo (Linux) or system_profiler (macOS)
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    info["model"] = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass
    if info["model"] in ("", "unknown", "x86_64"):
        try:
            out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"],
                                          stderr=subprocess.DEVNULL).decode().strip()
            if out:
                info["model"] = out
        except Exception:
            pass
    if info["model"] in ("", "unknown", "x86_64") and os.name == "nt":
        # Windows: CIM first, wmic as a legacy fallback
        ps = ("Get-CimInstance Win32_Processor | Select-Object Name,"
              "NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | "
              "ConvertTo-Json -Compress")
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps],
                stderr=subprocess.DEVNULL, timeout=20).decode(errors="ignore").strip()
            d = json.loads(out)
            if isinstance(d, list):
                d = d[0]
            info["model"] = str(d.get("Name", "")).strip() or info["model"]
            info["physical_cores"] = str(d.get("NumberOfCores", info["physical_cores"]))
            info["logical_cores"] = str(d.get("NumberOfLogicalProcessors",
                                              info["logical_cores"]))
            mhz = d.get("MaxClockSpeed")
            if mhz:
                info["base_frequency_ghz"] = f"{float(mhz) / 1000.0:.2f}"
        except Exception:
            try:
                out = subprocess.check_output(
                    ["wmic", "cpu", "get", "Name,NumberOfCores,"
                     "NumberOfLogicalProcessors,MaxClockSpeed", "/format:list"],
                    stderr=subprocess.DEVNULL, timeout=20).decode(errors="ignore")
                for line in out.splitlines():
                    if "=" not in line:
                        continue
                    k, v = [s.strip() for s in line.split("=", 1)]
                    if not v:
                        continue
                    if k == "Name":
                        info["model"] = v
                    elif k == "NumberOfCores":
                        info["physical_cores"] = v
                    elif k == "NumberOfLogicalProcessors":
                        info["logical_cores"] = v
                    elif k == "MaxClockSpeed":
                        info["base_frequency_ghz"] = f"{float(v) / 1000.0:.2f}"
            except Exception:
                pass
    if not info["model"]:
        info["model"] = platform.processor() or platform.platform() or "unknown"
    return info


# ---------------------------------------------------------------------------
# VTK reader (ASCII unstructured grid, no external dependency)
# ---------------------------------------------------------------------------
@dataclass
class VtkDataSet:
    points: np.ndarray
    cells: List[List[int]]
    cell_types: np.ndarray
    cell_data: Dict[str, np.ndarray] = field(default_factory=dict)
    point_data: Dict[str, np.ndarray] = field(default_factory=dict)
    title: str = ""


_VTK_KW = ("POINTS", "CELLS", "CELL_TYPES", "CELL_DATA", "POINT_DATA",
           "SCALARS", "VECTORS", "FIELD", "LOOKUP_TABLE", "DATASET",
           "METADATA")


def _is_kw(s: str) -> bool:
    u = s.strip().upper()
    return any(u.startswith(k) for k in _VTK_KW)


def read_vtk(path: str) -> VtkDataSet:
    """Read a legacy ASCII VTK unstructured-grid file written by vtkio.

    Keyword-driven state machine: every data array ends either when its
    expected element count is reached or when the next keyword line starts,
    so missing blank lines between CELL_DATA / POINT_DATA sections and
    SCALARS headers with/without a component count are all handled.
    """
    with open(path) as fh:
        lines = fh.readlines()
    ds = VtkDataSet(points=np.zeros((0, 3)), cells=[],
                    cell_types=np.zeros(0, int))
    title = ""
    i, n = 0, len(lines)
    while i < n:
        tok = lines[i].strip()
        up = tok.upper()
        if tok.startswith("# vtk"):
            i += 1
            if i < n:
                title = lines[i].strip()
            i += 1
            continue
        if up == "ASCII" or up.startswith("DATASET"):
            i += 1
            continue
        m = re.match(r"POINTS\s+(\d+)\s+(\w+)", tok, re.IGNORECASE)
        if m:
            cnt = int(m.group(1))
            i += 1
            pts = []
            while len(pts) < cnt and i < n and not _is_kw(lines[i]):
                row = lines[i].split()
                if len(row) >= 3:
                    pts.append([float(row[0]), float(row[1]), float(row[2])])
                i += 1
            ds.points = np.array(pts)
            continue
        m = re.match(r"CELLS\s+(\d+)\s+(\d+)", tok, re.IGNORECASE)
        if m:
            cnt = int(m.group(1))
            i += 1
            cells = []
            while len(cells) < cnt and i < n and not _is_kw(lines[i]):
                row = lines[i].split()
                if row:
                    nv = int(row[0])
                    cells.append([int(row[j + 1]) for j in range(nv)])
                i += 1
            ds.cells = cells
            continue
        m = re.match(r"CELL_TYPES\s+(\d+)", tok, re.IGNORECASE)
        if m:
            cnt = int(m.group(1))
            i += 1
            types = []
            while len(types) < cnt and i < n and not _is_kw(lines[i]):
                s = lines[i].strip()
                if s:
                    types.append(int(s))
                i += 1
            ds.cell_types = np.array(types)
            continue
        m = re.match(r"(CELL_DATA|POINT_DATA)\s+(\d+)", tok, re.IGNORECASE)
        if m:
            is_cell = m.group(1).upper() == "CELL_DATA"
            target = ds.cell_data if is_cell else ds.point_data
            cnt = len(ds.cells) if is_cell else len(ds.points)
            i += 1
            while i < n:
                line = lines[i].strip()
                up2 = line.upper()
                if up2.startswith("CELL_DATA") or up2.startswith("POINT_DATA"):
                    break          # next section (blank line not required)
                ms = re.match(r"SCALARS\s+(\S+)\s+\w+(?:\s+\d+)?", line,
                              re.IGNORECASE)
                mv = re.match(r"VECTORS\s+(\S+)\s+(\w+)", line, re.IGNORECASE)
                if ms:
                    name = ms.group(1)
                    i += 1
                    if i < n and lines[i].strip().upper().startswith(
                            "LOOKUP_TABLE"):
                        i += 1
                    vals = []
                    while len(vals) < cnt and i < n and not _is_kw(lines[i]):
                        for tk in lines[i].split():
                            if len(vals) < cnt:
                                vals.append(float(tk))
                        i += 1
                    target[name] = np.array(vals)
                    continue
                if mv:
                    name = mv.group(1)
                    i += 1
                    vals = []
                    while len(vals) < cnt and i < n and not _is_kw(lines[i]):
                        row = lines[i].split()
                        if len(row) >= 3:
                            vals.append([float(row[0]), float(row[1]),
                                         float(row[2])])
                        i += 1
                    target[name] = np.array(vals)
                    continue
                i += 1
            continue
        i += 1
    ds.title = title
    return ds


# ---------------------------------------------------------------------------
# History / line-force readers
# ---------------------------------------------------------------------------
def read_history(outdir: str) -> Tuple[List[str], np.ndarray]:
    path = os.path.join(outdir, "history.csv")
    with open(path, newline="") as fh:
        r = csv.reader(fh)
        head = next(r)
        rows = [[float(v) for v in row] for row in r if row]
    return head, np.array(rows)


def read_line_force(outdir: str) -> Tuple[List[str], np.ndarray]:
    path = os.path.join(outdir, "line_force.csv")
    if not os.path.exists(path):
        return [], np.zeros((0, 0))
    with open(path, newline="") as fh:
        r = csv.reader(fh)
        head = next(r)
        rows = [[float(v) for v in row] for row in r if row]
    return head, np.array(rows)


# ---------------------------------------------------------------------------
# .dat writers
# ---------------------------------------------------------------------------
def write_dat(path: str, data: np.ndarray, header: str) -> None:
    """Write a plain-text .dat table: comment header line(s) then columns."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        for line in header.strip().splitlines():
            fh.write(f"# {line}\n")
        np.savetxt(fh, data, fmt="%.9g")


# ---------------------------------------------------------------------------
# Figure helpers
# ---------------------------------------------------------------------------
def _save(fig, path: str, dpi: int = 150) -> None:
    try:
        fig.tight_layout()
    except Exception:
        pass            # e.g. incompatible with layout="constrained"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def _final_time_ms(outdir: str) -> Optional[float]:
    """Physical time [ms] of the last history sample."""
    try:
        head, h = read_history(outdir)
        idx = {k: n for n, k in enumerate(head)}
        return float(h[-1, idx["time"]] * 1.0e3)
    except Exception:
        return None


def _t_title(t_ms: Optional[float]) -> str:
    return f"t = {t_ms:.1f} ms" if t_ms is not None else "final state"


def _peak_time_ms(outdir: str) -> Optional[float]:
    """Time [ms] of the peak convergence-point line force.

    The t=0 sample is skipped: the very first history row can hold a
    transient spike from the initial penalty contact.
    """
    try:
        head, h = read_history(outdir)
        idx = {k: n for n, k in enumerate(head)}
        t = h[:, idx["time"]] * 1.0e3
        f = np.maximum(h[:, idx["line_anchor_force"]], 0.0)
        keep = t > 0.0
        if not keep.any():
            return None
        k = int(np.argmax(f[keep]))
        return float(t[keep][k])
    except Exception:
        return None


def _nearest_state(states: List[Tuple], t_ms: Optional[float]) -> Tuple:
    """State (t, fluid, struct) whose time is closest to ``t_ms``."""
    if t_ms is None:
        return states[-1]
    best, dbest = states[-1], float("inf")
    for s in states:
        if s[0] is None:
            continue
        d = abs(s[0] - t_ms)
        if d < dbest:
            best, dbest = s, d
    return best


def _disc_mask(tri: Triangulation, r: np.ndarray) -> np.ndarray:
    """True for triangles whose centroid leaves the cylindrical domain.

    ``r`` is the radial distance of every plotted point from the cylinder
    axis; the 2 % margin keeps the outermost ring of cells visible.
    """
    rmax = float(r.max()) * 1.02
    return r[tri.triangles].mean(axis=1) > rmax


# ---------------------------------------------------------------------------
# (b) Force / area curves + .dat
# ---------------------------------------------------------------------------
def plot_force_curves(outdir: str, figdir: str, datdir: str) -> List[str]:
    head, h = read_history(outdir)
    idx = {k: n for n, k in enumerate(head)}
    t_ms = h[:, idx["time"]] * 1.0e3
    drag = h[:, idx["coupling_drag"]]
    anchor = np.maximum(h[:, idx["line_anchor_force"]], 0.0)
    area = h[:, idx["canopy_area"]]
    radi = h[:, idx["canopy_radius"]]
    vmax = h[:, idx["struct_vmax"]]

    figs = []

    # --- line tension (per line) ---
    lhead, lh = read_line_force(outdir)
    if lh.size:
        lt = lh[:, 0] * 1.0e3
        lines = lh[:, 1:]
        nline = lines.shape[1]
        fig, ax = plt.subplots(figsize=(10, 5.5))
        cmap = plt.cm.viridis(np.linspace(0, 0.9, max(nline, 1)))
        for k in range(nline):
            ax.plot(lt, lines[:, k], color=cmap[k], lw=0.8, alpha=0.85)
        ax.set_xlabel("time [ms]")
        ax.set_ylabel("suspension-line tension [N]")
        ax.set_title(f"Per-line suspension-line tension ({nline} lines)")
        ax.set_xlim(0, lt[-1])
        ax.grid(alpha=0.3)
        p = os.path.join(figdir, "line_tension_per_line.png")
        _save(fig, p)
        figs.append(p)
        # .dat
        dat = np.column_stack([lt, lines])
        hdr = "time(ms)  " + "  ".join(lhead[1:])
        write_dat(os.path.join(datdir, "line_tension_per_line.dat"), dat, hdr)

    # --- anchor (convergence-point) force ---
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(t_ms, anchor, color="tab:red", lw=1.4,
            label="convergence-point resultant line force")
    ka = int(np.argmax(anchor))
    ax.plot(t_ms[ka], anchor[ka], "o", ms=6, color="tab:red")
    ax.annotate(f"peak {anchor[ka]:.0f} N @ {t_ms[ka]:.1f} ms",
                xy=(t_ms[ka], anchor[ka]), xytext=(10, -18),
                textcoords="offset points", fontsize=10, color="tab:red")
    ax.set_xlabel("time [ms]")
    ax.set_ylabel("force [N]")
    ax.set_title("Convergence-point (anchor) resultant line force vs time")
    ax.set_xlim(0, t_ms[-1])
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    p = os.path.join(figdir, "anchor_force_time.png")
    _save(fig, p)
    figs.append(p)
    write_dat(os.path.join(datdir, "anchor_force_time.dat"),
              np.column_stack([t_ms, anchor]),
              "time(ms)  anchor_force(N)")

    # --- canopy resultant (aerodynamic) drag ---
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(t_ms, drag, color="tab:blue", lw=1.4,
            label="canopy resultant aerodynamic force")
    kd = int(np.argmax(drag))
    ax.plot(t_ms[kd], drag[kd], "o", ms=6, color="tab:blue")
    ax.annotate(f"peak {drag[kd]:.0f} N @ {t_ms[kd]:.1f} ms",
                xy=(t_ms[kd], drag[kd]), xytext=(10, -18),
                textcoords="offset points", fontsize=10, color="tab:blue")
    ax.set_xlabel("time [ms]")
    ax.set_ylabel("force [N]")
    ax.set_title("Canopy resultant aerodynamic force vs time")
    ax.set_xlim(0, t_ms[-1])
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    p = os.path.join(figdir, "canopy_drag_time.png")
    _save(fig, p)
    figs.append(p)
    write_dat(os.path.join(datdir, "canopy_drag_time.dat"),
              np.column_stack([t_ms, drag]),
              "time(ms)  canopy_drag(N)")

    # --- area + radius ---
    fig, ax = plt.subplots(figsize=(10, 5.5))
    l1, = ax.plot(t_ms, area, color="tab:green", lw=1.4, label="canopy area")
    ax.set_xlabel("time [ms]")
    ax.set_ylabel("canopy area [m$^2$]")
    ax.set_title("Canopy area and mean radius vs time")
    ax.set_xlim(0, t_ms[-1])
    ax.grid(alpha=0.3)
    ax2 = ax.twinx()
    l2, = ax2.plot(t_ms, radi, color="tab:orange", ls="--", lw=1.2,
                   label="mean radius")
    ax2.set_ylabel("mean canopy radius [m]")
    ax.legend(handles=[l1, l2], loc="lower right")
    p = os.path.join(figdir, "canopy_area_radius_time.png")
    _save(fig, p)
    figs.append(p)
    write_dat(os.path.join(datdir, "canopy_area_radius_time.dat"),
              np.column_stack([t_ms, area, radi]),
              "time(ms)  canopy_area(m2)  mean_radius(m)")

    # --- vmax (smart-damping diagnostic) ---
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(t_ms, vmax, color="tab:purple", lw=1.3)
    ax.set_xlabel("time [ms]")
    ax.set_ylabel("max node velocity [m/s]")
    ax.set_title("Structure max nodal velocity (vmax) vs time")
    ax.set_xlim(0, t_ms[-1])
    ax.grid(alpha=0.3)
    p = os.path.join(figdir, "struct_vmax_time.png")
    _save(fig, p)
    figs.append(p)
    write_dat(os.path.join(datdir, "struct_vmax_time.dat"),
              np.column_stack([t_ms, vmax]),
              "time(ms)  struct_vmax(m/s)")

    return figs


# ---------------------------------------------------------------------------
# VTK state listing
# ---------------------------------------------------------------------------
def list_states(outdir: str) -> List[Tuple[float, str, str]]:
    """Return sorted list of (time_ms, fluid_path, struct_path) for every
    state_*.vtk pair in outdir, plus the final state."""
    pairs = []
    for fp in glob.glob(os.path.join(outdir, "state_*_fluid.vtk")):
        sp = fp.replace("_fluid.vtk", "_structure.vtk")
        # note: the state name is f"{t:8.4f}" so there may be TWO spaces
        # between "state_" and the number -> allow whitespace in the regex
        m = re.search(r"state_\s*([\d.]+)_fluid", os.path.basename(fp))
        t = float(m.group(1)) * 1.0e3 if m else None
        if os.path.exists(sp):
            pairs.append((t, fp, sp))
    # sort by the PHYSICAL time, not by the (space-padded) file name
    pairs.sort(key=lambda s: (s[0] is None, s[0] if s[0] is not None else 0.0))
    # final state
    ff = os.path.join(outdir, "final_fluid.vtk")
    fs = os.path.join(outdir, "final_structure.vtk")
    if os.path.exists(ff) and os.path.exists(fs):
        pairs.append((None, ff, fs))
    return pairs


# ---------------------------------------------------------------------------
# (c) Canopy shape evolution
# ---------------------------------------------------------------------------
def plot_canopy_evolution(outdir: str, figdir: str) -> List[str]:
    states = list_states(outdir)
    if not states:
        return []
    # pick up to 6 states, sampled uniformly in PHYSICAL time
    n = len(states)
    idx = np.unique(np.round(np.linspace(0, n - 1, min(6, n))).astype(int))
    picks = [states[k] for k in idx]

    ncol = min(3, len(picks))
    nrow = (len(picks) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 3.6 * nrow),
                             squeeze=False)
    figs = []
    for ax, (t, _fp, sp) in zip(axes.ravel(), picks):
        ds = read_vtk(sp)
        x = ds.points
        # only triangle cells (type 5)
        tri_mask = ds.cell_types == 5
        tris = np.array([c for c, m in zip(ds.cells, tri_mask) if m])
        if tris.size == 0:
            ax.set_title(_t_title(t))
            continue
        tri = Triangulation(x[:, 0], x[:, 2], tris)
        ax.triplot(tri, lw=0.2, color="tab:blue", alpha=0.6)
        ax.set_aspect("equal")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("z [m]")
        ax.set_title(_t_title(t))
        ax.grid(alpha=0.2)
    for ax in axes.ravel()[len(picks):]:
        ax.axis("off")
    fig.suptitle("Canopy shape evolution (x-z projection)", fontsize=12)
    p = os.path.join(figdir, "canopy_shape_evolution.png")
    _save(fig, p)
    figs.append(p)

    # side view (x-y)
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 3.6 * nrow),
                             squeeze=False)
    for ax, (t, _fp, sp) in zip(axes.ravel(), picks):
        ds = read_vtk(sp)
        x = ds.points
        tri_mask = ds.cell_types == 5
        tris = np.array([c for c, m in zip(ds.cells, tri_mask) if m])
        if tris.size:
            tri = Triangulation(x[:, 0], x[:, 1], tris)
            ax.triplot(tri, lw=0.2, color="tab:blue", alpha=0.6)
        ax.set_aspect("equal")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_title(_t_title(t))
        ax.grid(alpha=0.2)
    for ax in axes.ravel()[len(picks):]:
        ax.axis("off")
    fig.suptitle("Canopy shape evolution (x-y side view)", fontsize=12)
    p = os.path.join(figdir, "canopy_shape_side_evolution.png")
    _save(fig, p)
    figs.append(p)
    return figs


# ---------------------------------------------------------------------------
# (c) Field contours: pressure & velocity on a mid-plane slice
# ---------------------------------------------------------------------------
def _slice_2d(ds: VtkDataSet, axis: int = 2, value: float = 0.0,
              tol: float = 1e-6):
    """Project cells whose centroid is near ``value`` along ``axis`` to 2D."""
    centers = np.array([ds.points[c].mean(axis=0) for c in ds.cells])
    sel = np.abs(centers[:, axis] - value) <= tol
    if sel.sum() < 4:
        # widen tolerance to the nearest layer
        dists = np.abs(centers[:, axis] - value)
        uniq = np.unique(np.round(dists, 8))
        if uniq.size:
            sel = dists <= uniq[min(2, uniq.size - 1)]
    centers = centers[sel]
    if centers.size == 0:
        return None, None, None
    axes2 = [0, 1, 2]
    axes2.remove(axis)
    xs = centers[:, axes2[0]]
    ys = centers[:, axes2[1]]
    return xs, ys, sel


def plot_field_contours(outdir: str, figdir: str) -> List[str]:
    """Pressure / velocity-magnitude fields at the PEAK line-force instant
    and at the FINAL state (two panels per figure)."""
    states = list_states(outdir)
    if not states:
        return []
    peak_t = _peak_time_ms(outdir)
    shots = [_nearest_state(states, peak_t), states[-1]]
    figs = []
    for name, label, cmap, scale in [
            ("pressure", "pressure [kPa]", "RdBu_r", 1.0e3),
            ("velocity", "|velocity| [m/s]", "viridis", 1.0)]:
        fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.9),
                                 layout="constrained")
        drawn = False
        for ax, (t, fp, _sp) in zip(axes, shots):
            ds = read_vtk(fp)
            data = ds.cell_data.get(name)
            if data is None:
                ax.axis("off")
                continue
            vals = (np.linalg.norm(data, axis=1) if data.ndim == 2
                    else data) / scale
            zval = float(ds.points[:, 2].mean())
            xp, yp, sel = _slice_2d(ds, axis=2, value=zval, tol=0.05)
            if xp is None or xp.size <= 4:
                ax.axis("off")
                continue
            tri = Triangulation(xp, yp)
            # mask the triangles that leave the circular fluid domain
            cx = 0.5 * (ds.points[:, 0].min() + ds.points[:, 0].max())
            cz = 0.5 * (ds.points[:, 2].min() + ds.points[:, 2].max())
            r = np.sqrt((xp - cx) ** 2 + (zval - cz) ** 2)
            tri.set_mask(_disc_mask(tri, r))
            tc = ax.tripcolor(tri, vals[sel], cmap=cmap, shading="gouraud")
            fig.colorbar(tc, ax=ax, label=label, shrink=0.9)
            tag = "peak" if (t is not None and peak_t is not None
                             and abs(t - peak_t) < 1e-6) else "final"
            ax.set_title(f"{tag}: {_t_title(t)}", fontsize=10)
            ax.set_xlabel("x [m]")
            ax.set_ylabel("y [m]")
            ax.set_aspect("equal")
            drawn = True
        if drawn:
            p = os.path.join(figdir, f"field_{name}.png")
            _save(fig, p)
            figs.append(p)
        else:
            plt.close(fig)
    return figs


# ---------------------------------------------------------------------------
# (c) Canopy stress / strain contours
# ---------------------------------------------------------------------------
def plot_canopy_stress(outdir: str, figdir: str) -> List[str]:
    """Membrane stress / strain contours at the PEAK line-force instant
    and at the FINAL state (two panels per figure, x-z projection)."""
    states = list_states(outdir)
    if not states:
        return []
    peak_t = _peak_time_ms(outdir)
    shots = [_nearest_state(states, peak_t), states[-1]]
    figs = []
    for name, label, cmap in [("stress_11", "membrane stress S11 [Pa]",
                               "inferno"),
                              ("strain_11", "membrane strain E11", "plasma")]:
        fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.9),
                                 layout="constrained")
        drawn = False
        for ax, (t, _fp, sp) in zip(axes, shots):
            ds = read_vtk(sp)
            vals = ds.cell_data.get(name)
            tri_mask = ds.cell_types == 5
            tris = np.array([c for c, m in zip(ds.cells, tri_mask) if m])
            if vals is None or tris.size == 0:
                ax.axis("off")
                continue
            x = ds.points
            tri = Triangulation(x[:, 0], x[:, 2], tris)
            tc = ax.tripcolor(tri, facecolors=vals[tri_mask],
                              cmap=cmap, shading="flat")
            fig.colorbar(tc, ax=ax, label=label, shrink=0.9)
            tag = "peak" if (t is not None and peak_t is not None
                             and abs(t - peak_t) < 1e-6) else "final"
            ax.set_title(f"{tag}: {_t_title(t)}", fontsize=10)
            ax.set_aspect("equal")
            ax.set_xlabel("x [m]")
            ax.set_ylabel("z [m]")
            drawn = True
        if drawn:
            p = os.path.join(figdir, f"canopy_{name}.png")
            _save(fig, p)
            figs.append(p)
        else:
            plt.close(fig)
    return figs


# ---------------------------------------------------------------------------
# (c) Video animation of canopy shape + pressure field
# ---------------------------------------------------------------------------
def make_video(outdir: str, figdir: str) -> Optional[str]:
    states = list_states(outdir)
    if len(states) < 3:
        return None
    tmp = os.path.join(figdir, "_frames")
    os.makedirs(tmp, exist_ok=True)
    frames = []
    for k, (t, fp, sp) in enumerate(states):
        fds = read_vtk(fp)
        sds = read_vtk(sp)
        p = fds.cell_data.get("pressure", np.zeros(len(fds.cells)))
        zval = float(fds.points[:, 2].mean())
        xp, yp, sel = _slice_2d(fds, axis=2, value=zval, tol=0.05)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
        if xp is not None and xp.size > 4:
            sc = ax1.scatter(xp, yp, c=p[sel] / 1.0e3, s=6, cmap="RdBu_r",
                             vmin=p.min() / 1e3, vmax=p.max() / 1e3)
            plt.colorbar(sc, ax=ax1, label="pressure [kPa]")
        ax1.set_aspect("equal")
        ax1.set_xlabel("x [m]"); ax1.set_ylabel("y [m]")
        tlabel = f"{t:.1f} ms" if t is not None else "final"
        ax1.set_title(f"pressure field  t={tlabel}")
        # canopy
        tri_mask = sds.cell_types == 5
        tris = np.array([c for c, m in zip(sds.cells, tri_mask) if m])
        if tris.size:
            tri = Triangulation(sds.points[:, 0], sds.points[:, 2], tris)
            tens = sds.cell_data.get("tension", np.zeros(len(sds.cells)))
            v = tens[tri_mask] if tens.size else None
            if v is not None:
                ax2.tripcolor(tri, v, cmap="viridis", shading="flat")
            else:
                ax2.triplot(tri, lw=0.2, color="tab:blue")
        ax2.set_aspect("equal")
        ax2.set_xlabel("x [m]"); ax2.set_ylabel("z [m]")
        ax2.set_title(f"canopy tension  t={tlabel}")
        fp_ = os.path.join(tmp, f"frame_{k:04d}.png")
        fig.tight_layout()
        fig.savefig(fp_, dpi=100)
        plt.close(fig)
        frames.append(fp_)
    out = os.path.join(figdir, "canopy_inflation.mp4")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-framerate", "4", "-i",
             os.path.join(tmp, "frame_%04d.png"),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", out],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        out = None
    # cleanup frames
    for f in frames:
        try:
            os.remove(f)
        except OSError:
            pass
    try:
        os.rmdir(tmp)
    except OSError:
        pass
    return out


# ---------------------------------------------------------------------------
# (a) Conditions text
# ---------------------------------------------------------------------------
def conditions_from_objects(model, opt, grid, sim) -> Dict[str, Any]:
    """Collect the report 'calculation conditions' from the live objects.

    Returns ``{"groups": [{"title": ..., "rows": [...]}...], "domain": {...}}``
    where a row is either a ``(label, value)`` pair or a plain string
    (rendered across both columns).  ``domain`` carries the numbers the
    report needs afterwards (final blockage-ratio backfill).
    """
    gas = sim.fluid.gas
    rho0, e0 = float(gas.rho0), float(gas.e0)
    p0 = float(gas.c4 * gas.e0)
    T0 = p0 / (rho0 * R_AIR) if rho0 > 0 else 0.0
    c0 = float(np.sqrt(1.4 * p0 / rho0)) if rho0 > 0 else 0.0
    vel = float(opt.constant_vel) if opt.constant_vel else 0.0
    mach = vel / c0 if c0 > 0 else 0.0
    qinf = 0.5 * rho0 * vel * vel

    y0, y1 = float(grid.x[:, 1].min()), float(grid.x[:, 1].max())
    r_env = float(np.max(np.sqrt(grid.x[:, 0] ** 2 + grid.x[:, 2] ** 2)))
    r_design = float(opt.domain_radius) if opt.domain_radius else r_env
    xs = sim.struct.x
    r_can0 = float(np.max(np.sqrt(xs[:, 0] ** 2 + xs[:, 2] ** 2)))
    block0 = (r_can0 / r_design) ** 2 * 100.0 if r_design > 0 else 0.0

    bi = grid.boundary_info()

    def _spacing(coord) -> float:
        u = np.unique(np.round(coord, 9))
        if u.size > 1:
            return float(np.diff(u).min())
        return 0.0

    dx = _spacing(grid.x[:, 0])
    dy = _spacing(grid.x[:, 1])
    dz = _spacing(grid.x[:, 2])
    try:
        dt0 = float(sim.stable_dt()) * opt.tssfac
    except Exception:
        dt0 = 0.0

    parts = "; ".join(f"PID {p['pid']} {p['title']}"
                      for p in model.parts.values())
    inflow = (f"恒定 {vel:.1f} m/s（Ma∞ = {mach:.3f}）"
              if opt.constant_vel else "K 文件速度曲线"
              f"（vel_scale={opt.vel_scale}）")
    g11 = {"title": "1.1 计算工况", "rows": [
        ("K 文件", f"{os.path.basename(opt.kfile) or '(unknown)'} — "
                   f"{model.title}"),
        ("单位制", model.units or "(K 文件)"),
        ("部件", parts),
        ("计算时长", f"{opt.endtime * 1.0e3:.1f} ms"),
        ("来流条件", inflow),
    ]}
    g12 = {"title": "1.2 计算流域与气体参考态", "rows": [
        ("流域类型", "圆柱形外流场（结构化自动网格）"
                     + (f"，下游延伸 +{opt.y1_extension:.4f} m"
                        if opt.y1_extension else "")),
        ("轴向范围", f"y ∈ [{y0:.4f}, {y1:.4f}] m"),
        ("截面半径 R", f"{r_design:.4f} m（设计值；K 文件原始流域半径 "
                       f"{r_env:.4f} m）"),
        ("伞衣初始折叠半径", f"{r_can0:.4f} m"),
        ("初始阻塞比", f"{block0:.2f} %（按初始折叠半径 / 设计半径）"),
        ("气体参考态", f"ρ0 = {rho0:.4f} kg/m³，p0 = {p0:.1f} Pa，"
                       f"T0 = {T0:.1f} K，c0 = {c0:.1f} m/s，"
                       f"动压 q = {qinf:.0f} Pa"),
    ]}
    g13 = {"title": "1.3 流场网格", "rows": [
        ("网格分辨率", (f"{opt.nx} × {opt.ny} × {opt.nz}"
                        if opt.nx else "(native 实体网格)")),
        ("单元 / 面", f"{bi['cells']} 单元，{bi['faces']} 面"),
        ("网格尺度", f"dx ≈ {dx:.4f} m，dy ≈ {dy:.4f} m，dz ≈ {dz:.4f} m"),
    ]}
    g14 = {"title": "1.4 求解器与耦合设置", "rows": [
        ("时间积分", f"显式时间推进，CFL = {opt.cfl}，TSSFAC = {opt.tssfac}"
                     + (f"，初始 dt ≈ {dt0:.3e} s" if dt0 else "")),
        ("流体", "ALE Eulerian 有限体积，一阶 Rusanov 数值通量"),
        ("气体状态方程", f"LINEAR_POLYNOMIAL 理想气体分支 "
                         f"p = (c4 + c5·μ)·e_int，c4 = {gas.c4}，"
                         f"e0 = {gas.e0:.1f}，p0 = {p0:.1f} Pa"),
        ("FSI 耦合", f"CLLS 罚函数：omega = {opt.omega}，cdamp = {opt.cdamp}，"
                     f"pfac = {opt.pfac}，pleak = {opt.pleak}，"
                     f"leak_cap = {opt.leak_cap}，"
                     f"mach_cap = {opt.fsi_mach_cap}，p_cap = {opt.p_cap}"),
        ("结构", f"mass_scale = {opt.mass_scale}，tension_only = "
                 f"{opt.membrane_tension_only}，eb_frac = {opt.eb_frac}，"
                 f"eb_stab_frac = {opt.eb_stab_frac}，"
                 f"vent_radius = {opt.vent_radius} m"),
        ("弯曲 / 阻尼", f"bend_scale = {opt.bend_scale}，"
                        f"bend_damp = {opt.bend_damp}，"
                        f"struct_damping = {opt.struct_damping} 1/s，"
                        f"vmax 门限 = {opt.struct_damping_vmax} m/s"),
        ("壳 / 沙漏", f"THEORY = {sim.theory}，BWC = {sim.bwc}，"
                      f"IHQ = {sim.ihq}，hg_qh = {opt.hg_qh}"),
        ("接触", f"enabled = {opt.contact}，scale = {opt.contact_scale}，"
                 f"vdc = {opt.contact_vdc}"),
    ]}
    mat_rows: List[Any] = []
    for mid, mm in model.materials.items():
        kv = ", ".join(f"{k} = {mm[k]}" for k in mm
                       if k not in ("type", "mid")
                       and isinstance(mm[k], (int, float)))
        mat_rows.append(f"MID {mid}（{mm.get('type', '?')}）: {kv}")
    for eid, e in model.eos.items():
        kv = ", ".join(f"{k} = {e[k]}" for k in e
                       if k != "type" and isinstance(e[k], (int, float)))
        mat_rows.append(f"EOS {eid}（{e.get('type', '?')}）: {kv}")
    g15 = {"title": "1.5 材料与状态方程卡片", "rows": mat_rows or ["(none)"]}

    return {"groups": [g11, g12, g13, g14, g15],
            "domain": {"r_design": r_design, "r_env": r_env,
                       "y0": y0, "y1": y1, "r_canopy0": r_can0}}


def _conditions_html(cond: Dict[str, Any]) -> str:
    """Render the grouped conditions; plain-string rows span both columns."""
    out = []
    for g in cond.get("groups", []):
        out.append(f"<h3 style='margin:14px 0 4px'>{html.escape(g['title'])}"
                   f"</h3>")
        rows = []
        for r in g["rows"]:
            if isinstance(r, str):
                rows.append(f"<tr><td colspan='2'><pre>{html.escape(r)}"
                            f"</pre></td></tr>")
            else:
                k, v = r
                rows.append(f"<tr><th class='k'>{html.escape(str(k))}</th>"
                            f"<td><pre>{html.escape(str(v))}</pre></td></tr>")
        out.append("<table class='cond'>" + "".join(rows) + "</table>")
    return "".join(out)


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;
     color:#222;max-width:1100px}
h1{border-bottom:2px solid #444;padding-bottom:6px}
h2{margin-top:28px;border-left:4px solid #3a7;color:#2a5;padding-left:10px}
table.cond{border-collapse:collapse;width:100%;margin:8px 0}
table.cond th.k{background:#eef;text-align:left;vertical-align:top;
     padding:8px;width:220px;border:1px solid #ccd}
table.cond td{padding:8px;border:1px solid #ccd;background:#fafafa}
table.cond pre{margin:0;white-space:pre-wrap;font-size:12px}
.fig{margin:14px 0}
.fig img{max-width:100%;border:1px solid #ccc}
.meta{background:#f4f4f4;padding:10px 14px;border-radius:6px;margin:10px 0}
.tag{display:inline-block;background:#3a7;color:#fff;padding:2px 8px;
     border-radius:10px;font-size:12px;margin-right:6px}
"""


def generate_report(outdir: str, model=None, opt=None, grid=None, sim=None,
                    wall_time: Optional[float] = None,
                    cpu_info: Optional[Dict[str, str]] = None) -> str:
    """Generate the full HTML report + figures + .dat + video.

    ``model/opt/grid/sim`` are optional; when omitted the conditions, CPU
    info and wall time fall back to ``run_meta.json`` so the function also
    works post-hoc on an existing outdir (``--report-only``).
    """
    figdir = os.path.join(outdir, "figures")
    datdir = os.path.join(outdir, "data")
    os.makedirs(figdir, exist_ok=True)
    os.makedirs(datdir, exist_ok=True)

    meta = read_run_meta(outdir) or {}

    figures: List[str] = []
    # (b) curves
    figures += plot_force_curves(outdir, figdir, datdir)
    # (c) evolution, fields, stress
    figures += plot_canopy_evolution(outdir, figdir)
    figures += plot_field_contours(outdir, figdir)
    figures += plot_canopy_stress(outdir, figdir)
    # (c) video
    video = make_video(outdir, figdir)

    # ---- (a) conditions: live objects first, run_meta.json fallback ------
    cond: Dict[str, Any] = {}
    if model is not None and opt is not None and grid is not None \
            and sim is not None:
        cond = conditions_from_objects(model, opt, grid, sim)
    elif meta.get("conditions"):
        cond = meta["conditions"]

    # backfill the FINAL blockage ratio into group 1.2
    try:
        head, h = read_history(outdir)
        idx = {k: n for n, k in enumerate(head)}
        r_fin = float(h[-1, idx["canopy_radius"]])
        r_design = float((cond.get("domain") or {}).get("r_design") or 0.0)
        if r_design > 0:
            for g in cond.get("groups", []):
                if g.get("title", "").startswith("1.2"):
                    g["rows"] = [r for r in g["rows"]
                                 if not (isinstance(r, tuple)
                                         and r[0] == "末态阻塞比")]
                    g["rows"].append(
                        ("末态阻塞比",
                         f"{(r_fin / r_design) ** 2 * 100.0:.2f} %"
                         f"（末态平均半径 {r_fin:.4f} m / 设计半径）"))
    except Exception:
        pass

    if wall_time is None:
        wall_time = (meta.get("run") or {}).get("wall_time")
    cpu = cpu_info or meta.get("cpu") or get_cpu_info()

    # ---- summary numbers (peak search skips the t = 0 transient) --------
    summary = ""
    try:
        head, h = read_history(outdir)
        idx = {k: n for n, k in enumerate(head)}
        t_ms = h[:, idx["time"]] * 1e3
        drag = h[:, idx["coupling_drag"]]
        anchor = np.maximum(h[:, idx["line_anchor_force"]], 0.0)
        area = h[:, idx["canopy_area"]]
        radi = h[:, idx["canopy_radius"]]
        kd = int(np.argmax(drag))
        keep = t_ms > 0.0
        ka = int(np.argmax(anchor[keep])) if keep.any() \
            else int(np.argmax(anchor))
        ka_t = t_ms[keep][ka] if keep.any() else t_ms[ka]
        ka_f = anchor[keep][ka] if keep.any() else anchor[ka]
        summary = (
            f"<div class='meta'>"
            f"<span class='tag'>峰值伞衣气动力</span> "
            f"{drag[kd]:.0f} N @ {t_ms[kd]:.1f} ms &nbsp;&nbsp; "
            f"<span class='tag'>峰值汇聚点伞绳力</span> "
            f"{ka_f:.0f} N @ {ka_t:.1f} ms &nbsp;&nbsp; "
            f"<span class='tag'>末态面积</span> {area[-1]:.3f} m&sup2; "
            f"&nbsp;&nbsp; "
            f"<span class='tag'>末态平均半径</span> {radi[-1]:.3f} m"
            f"</div>")
    except Exception:
        pass

    # ---- (d) compute-time / CPU block -----------------------------------
    ct = ""
    if wall_time is not None:
        h_ = int(wall_time // 3600)
        m_ = int((wall_time % 3600) // 60)
        s_ = wall_time - h_ * 3600 - m_ * 60
        ct += (f"计算用时（wall-clock）：<b>{wall_time:.1f} s</b>"
               f"（{h_} h {m_} min {s_:.1f} s）<br>")
    steps = (meta.get("run") or {}).get("steps")
    if steps:
        ct += f"时间步数：<b>{steps}</b><br>"
    ct += (f"CPU 型号：<b>{cpu['model']}</b><br>"
           f"物理核心：<b>{cpu['physical_cores']}</b> &nbsp; "
           f"逻辑核心：{cpu['logical_cores']}<br>"
           f"基准频率：<b>{cpu['base_frequency_ghz']} GHz</b>")

    # ---- figure list -----------------------------------------------------
    fig_html = []
    captions = {
        "line_tension_per_line": "逐根伞绳张力时程曲线",
        "anchor_force_time": "汇聚点伞绳合力时程曲线",
        "canopy_drag_time": "伞衣气动力合力时程曲线",
        "canopy_area_radius_time": "伞衣面积与平均半径时程曲线",
        "struct_vmax_time": "结构最大节点速度（vmax）时程曲线",
        "canopy_shape_evolution": "伞衣形态演化（x-z 投影，均采样 6 时刻）",
        "canopy_shape_side_evolution": "伞衣形态演化（x-y 侧视，均采样 6 时刻）",
        "field_pressure": "压力场云图（中截面；左：峰值时刻，右：末态）",
        "field_velocity": "速度场云图（中截面；左：峰值时刻，右：末态）",
        "canopy_stress_11": "伞衣膜应力 S11 云图（左：峰值时刻，右：末态）",
        "canopy_strain_11": "伞衣膜应变 E11 云图（左：峰值时刻，右：末态）",
    }
    for f in figures:
        bn = os.path.basename(f)
        key = os.path.splitext(bn)[0]
        cap = captions.get(key, key)
        fig_html.append(
            f"<div class='fig'><img src='figures/{bn}' alt='{bn}'>"
            f"<div style='font-size:13px;color:#555;margin-top:4px'>{cap}</div>"
            f"</div>")

    video_html = ""
    if video and os.path.exists(video):
        video_html = (f"<h2>8 展开过程动画</h2>"
                      f"<video controls width='100%' "
                      f"src='figures/{os.path.basename(video)}'>"
                      f"Your browser does not support video.</video>"
                      f"<p style='color:#666;font-size:13px'>左：压力场中截面；"
                      f"右：伞衣张力分布，覆盖整个展开过程。</p>")

    cond_html = _conditions_html(cond) if cond else \
        "<p style='color:#888'>（工况信息不可用——请在求解器内部生成报告，" \
        "或保留 run_meta.json 后使用 --report-only。）</p>"

    html_doc = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>减速伞展开过程数值计算报告</title>
<style>{CSS}</style></head><body>
<h1>减速伞展开过程数值计算报告</h1>
<div class='meta'>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp;
结果目录: <code>{html.escape(os.path.abspath(outdir))}</code></div>

{summary}

<h2>1 计算条件</h2>
{cond_html}

<h2>2 计算资源与用时</h2>
<div class='meta'>{ct}</div>

<h2>3 伞绳力与汇聚点受力时程曲线</h2>
{fig_html[0] if fig_html else ''}
{fig_html[1] if len(fig_html) > 1 else ''}
<p style='color:#666;font-size:13px'>原始数据见 <code>data/</code> 目录下的
<code>.dat</code> 文件（列：时间 ms，力 N）。</p>

<h2>4 伞衣气动力、面积与速度时程</h2>
{fig_html[2] if len(fig_html) > 2 else ''}
{fig_html[3] if len(fig_html) > 3 else ''}
{fig_html[4] if len(fig_html) > 4 else ''}

<h2>5 伞衣形态变化</h2>
{fig_html[5] if len(fig_html) > 5 else ''}
{fig_html[6] if len(fig_html) > 6 else ''}

<h2>6 流场云图（速度 / 压力，峰值时刻与末态）</h2>
{fig_html[7] if len(fig_html) > 7 else ''}
{fig_html[8] if len(fig_html) > 8 else ''}

<h2>7 伞衣应力 / 应变云图（峰值时刻与末态）</h2>
{fig_html[9] if len(fig_html) > 9 else ''}
{fig_html[10] if len(fig_html) > 10 else ''}

{video_html}

<h2>9 数据文件说明</h2>
<ul>
<li><code>data/*.dat</code> — 所有曲线的原始数据（空格分隔，首行为列名注释）</li>
<li><code>figures/*.png</code> — 报告中所有图片</li>
<li><code>figures/canopy_inflation.mp4</code> — 展开过程动画</li>
<li><code>history.csv</code> — 完整时程历史</li>
<li><code>line_force.csv</code> — 逐伞绳张力时程</li>
<li><code>state_*_fluid.vtk / *_structure.vtk</code> — 各时刻流场/结构 VTK</li>
<li><code>run_meta.json</code> — 工况/选项/CPU/用时元数据（供 --report-only 重出报告）</li>
<li><code>checkpoint.npz</code> — 断点续算检查点（--restart 恢复）</li>
</ul>
</body></html>"""

    report_path = os.path.join(outdir, "calculation_report.html")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    print(f"[report] wrote {report_path}")
    print(f"[report] {len(figures)} figures, video={'yes' if video else 'no'}")
    return report_path


# ---------------------------------------------------------------------------
# CLI for post-hoc report generation
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Generate calculation report "
                                            "from an existing result directory.")
    p.add_argument("--outdir", required=True, help="result directory")
    p.add_argument("--wall-time", type=float, default=None,
                   help="wall-clock time of the run [s] (optional)")
    a = p.parse_args(argv)
    cpu = get_cpu_info()
    generate_report(a.outdir, wall_time=a.wall_time, cpu_info=cpu)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
