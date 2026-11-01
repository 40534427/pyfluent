"""Legacy VTK writers (no external dependency)."""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np

VTK_TYPES = {5: "5", 12: "12", 3: "3"}


def write_vtk(path: str, points: np.ndarray, cells: list,
              cell_types: np.ndarray, cell_data: Optional[Dict[str, np.ndarray]] = None,
              point_data: Optional[Dict[str, np.ndarray]] = None,
              title: str = "aleparachute") -> None:
    points = np.asarray(points, dtype=np.float64)
    ncells = len(cells)
    offsets = np.zeros(ncells + 1, dtype=np.int64)
    for i, c in enumerate(cells):
        offsets[i + 1] = offsets[i] + len(c) + 1

    with open(path, "w") as fh:
        fh.write("# vtk DataFile Version 3.0\n")
        fh.write(f"{title}\n")
        fh.write("ASCII\n")
        fh.write("DATASET UNSTRUCTURED_GRID\n")
        fh.write(f"POINTS {points.shape[0]} double\n")
        np.savetxt(fh, points, fmt="%.9g")
        total = int(offsets[-1])
        fh.write(f"CELLS {ncells} {total}\n")
        for c in cells:
            fh.write(f"{len(c)} " + " ".join(str(int(v)) for v in c) + "\n")
        fh.write(f"CELL_TYPES {ncells}\n")
        for t in cell_types:
            fh.write(f"{int(t)}\n")
        if cell_data:
            fh.write(f"CELL_DATA {ncells}\n")
            for name, arr in cell_data.items():
                arr = np.asarray(arr)
                if arr.ndim == 1:
                    fh.write(f"SCALARS {name} double 1\nLOOKUP_TABLE default\n")
                    np.savetxt(fh, arr, fmt="%.9g")
                else:
                    fh.write(f"VECTORS {name} double\n")
                    np.savetxt(fh, arr, fmt="%.9g")
        if point_data:
            fh.write(f"POINT_DATA {points.shape[0]}\n")
            for name, arr in point_data.items():
                arr = np.asarray(arr)
                if arr.ndim == 1:
                    fh.write(f"SCALARS {name} double 1\nLOOKUP_TABLE default\n")
                    np.savetxt(fh, arr, fmt="%.9g")
                else:
                    fh.write(f"VECTORS {name} double\n")
                    np.savetxt(fh, arr, fmt="%.9g")
