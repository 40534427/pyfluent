"""ALE parachute inflation solver (LS-DYNA keyword driven).

Example
-------
>>> from aleparachute.kfile import load_model
>>> from aleparachute.mesh import auto_cylinder_grid, fluid_geometry
>>> m = load_model("Parachute.k")
>>> geo = fluid_geometry(m)
>>> g = auto_cylinder_grid(*geo, nx=24, ny=40, nz=24)
"""

from .kfile import load_model, Model           # noqa: F401
from .mesh import (HexGrid, Structure, auto_cylinder_grid,   # noqa: F401
                   build_hex_grid, build_structure, fluid_geometry, native_grid)
from .fluid import ALEFluid, IdealGas          # noqa: F401
from .structure import StructureSolver         # noqa: F401
from .coupling import PenaltyCoupler           # noqa: F401
from .solver import Options, Simulation        # noqa: F401
