"""Eulerian / ALE fluid solver.

The air part of the K file is an ALE multi-material part (ELFORM 11, AET 1)
driven by ``*MAT_NULL`` + ``*EOS_LINEAR_POLYNOMIAL``.  No
``*ALE_MULTI-MATERIAL_GROUP`` card is active in the deck, therefore the
material is a single ideal gas and the governing equations are the
compressible Euler equations written in ALE flux form

    d/dt ∫ U dV + ∮ (F(U) - w·U) · n dA = 0

with ``w`` the grid velocity.  The grid is kept fixed (w = 0) which is the
Eulerian limit used by LS-DYNA whenever no ALE re-meshing / smoothing is
requested, and the face flux is evaluated with a Rusanov (local Lax-Friedrichs)
approximation, i.e. a first order donor-cell transport as selected by
``*CONTROL_ALE DCT = 2``.

State vector (per unit volume):  rho, rho*u_x, rho*u_y, rho*u_z, rho*E
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from .mesh import HexGrid


@dataclass
class IdealGas:
    """Linear-polynomial EOS reduced to the ideal-gas branch."""
    rho0: float
    c4: float
    c5: float
    c6: float
    e0: float          # initial internal energy per unit volume
    pref: float

    @classmethod
    def from_model(cls, model, mid: int, eosid: int | None = None):
        mat = model.materials[mid]
        eosid = int(eosid) if eosid else int(mat.get("eosid", 0))
        eos = model.eos.get(eosid, {})
        c4 = float(eos.get("c4", 0.4))
        c5 = float(eos.get("c5", 0.0))
        c6 = float(eos.get("c6", 0.0))
        e0 = float(eos.get("e0", 250000.0))
        # The EOS fixes the undisturbed ambient state: p0 = c4 e0 (mu = 0).
        # *CONTROL_ALE PREF (101300 Pa in this deck) is *not* the ambient
        # pressure of the gas -- the deck's e0 gives 100000 Pa.  Using the
        # card value would put a 1.3 kPa uniform bias into every pressure
        # perturbation, so pref is taken from the EOS instead.
        ambient = c4 * e0
        return cls(rho0=float(mat["ro"]), c4=c4, c5=c5, c6=c6, e0=e0,
                   pref=ambient)

    def pressure(self, rho: np.ndarray, e_int: np.ndarray) -> np.ndarray:
        mu = rho / self.rho0 - 1.0
        a = self.c4 + self.c5 * mu + self.c6 * mu * mu
        return a * e_int

    def gamma(self, rho: np.ndarray) -> np.ndarray:
        mu = rho / self.rho0 - 1.0
        return 1.0 + self.c4 + self.c5 * mu

    def sound_speed(self, rho: np.ndarray, p: np.ndarray) -> np.ndarray:
        g = self.gamma(rho)
        return np.sqrt(np.maximum(g * p / np.maximum(rho, 1e-12), 1e-12))


class ALEFluid:
    """Cell-centred finite-volume ALE fluid on a hexahedral grid."""

    def __init__(self, grid: HexGrid, gas: IdealGas, cfl: float = 0.5,
                 wall_normals: Optional[np.ndarray] = None):
        self.g = grid
        self.gas = gas
        self.cfl = cfl
        n = grid.ncell
        self.U = np.zeros((n, 5))
        self.U[:, 0] = gas.rho0
        self.U[:, 4] = gas.e0
        self._init_face_arrays()
        self.driven_cells: np.ndarray = np.zeros(0, dtype=np.int64)
        self.driven_value = 0.0
        self.driven_dof = 1
        # per-cell accumulated wave speed (updated every step); initialised
        # from the undisturbed state so that the first time step is sane
        areas = np.bincount(grid.owner, weights=grid.area, minlength=n)
        inr = grid.neigh >= 0
        areas += np.bincount(grid.neigh[inr], weights=grid.area[inr], minlength=n)
        p0 = float(gas.pressure(np.array([gas.rho0]), np.array([gas.e0]))[0])
        c0 = float(gas.sound_speed(np.array([gas.rho0]), np.array([p0]))[0])
        self._wave = areas * c0

    # ------------------------------------------------------------------ setup
    def _init_face_arrays(self) -> None:
        g = self.g
        self._L = g.owner
        self._R = g.neigh
        self._is_b = g.neigh < 0
        self._bnd = np.nonzero(self._is_b)[0]
        self._bL = g.owner[self._bnd]
        self._bR = g.neigh[self._bnd]          # -1
        self._nb = self._bnd.size
        self._bcb = g.bc[self._bnd]
        self._area = g.area
        self._nvec = g.n
        self._vol = g.vol
        self._invV = 1.0 / g.vol

    # ------------------------------------------------------------- primitives
    def primitive(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        U = self.U
        rho = U[:, 0]
        u = U[:, 1:4] / rho[:, None]
        rhov2 = np.sum(U[:, 1:4] ** 2, axis=1) / rho
        e_int = U[:, 4] - 0.5 * rhov2
        p = self.gas.pressure(rho, e_int)
        c = self.gas.sound_speed(rho, p)
        return rho, u, p, c

    def _primitive_from(self, U: np.ndarray):
        rho = U[..., 0]
        u = U[..., 1:4] / rho[..., None]
        rhov2 = np.sum(U[..., 1:4] ** 2, axis=-1) / rho
        e_int = U[..., 4] - 0.5 * rhov2
        p = self.gas.pressure(rho, e_int)
        c = self.gas.sound_speed(rho, p)
        return rho, u, p, c

    def _flux_normal(self, U, u, p, nvec):
        """F(U)·n for a set of states."""
        un = np.einsum("...i,...i->...", u, nvec)
        F = np.empty_like(U)
        F[..., 0] = U[..., 0] * un
        F[..., 1:4] = U[..., 1:4] * un[..., None] + p[..., None] * nvec
        F[..., 4] = (U[..., 4] + p) * un
        return F

    # ------------------------------------------------------------- boundaries
    def _ghost_states(self, U_L, nvec, bc):
        """Return conservative ghost states for boundary faces.

        Three categories:

        * ``bc == 0``: solid wall.  Ghost = mirrored interior normal velocity
          so that mass flux through the face is zero.

        * ``bc == 1``: non-reflecting *outflow*.  The complete ghost state is
          the zero-order extrapolation of the interior state (density,
          momentum and total energy), which makes the Riemann flux equal to
          the interior flux, i.e. the boundary is transparent (free outflow).

          Note that the previous implementation pinned the ghost *internal*
          energy to ``p_ref`` but stored it in the total-energy slot.  That
          subtracts the kinetic energy ``0.5 rho u^2`` from the pressure:
          ``p_ghost = 0.4 (e_int_ref - 0.5 rho u^2) = 89.4 kPa`` for the
          220 m/s upstream layer instead of ``100 kPa``.  The whole inflow
          stream was thus 11 % too cold, and the "wake vacuum" reported by the
          diagnostics was this boundary artefact rather than a physical base
          pressure.  Zero-order extrapolation removes it.

        The inflow is *not* a boundary condition in this deck: it is imposed
        by ``*BOUNDARY_PRESCRIBED_MOTION_SET`` on an interior node layer and
        is handled as a driven reservoir in :meth:`_apply_drive`.
        """
        rho = U_L[:, 0]
        u = U_L[:, 1:4] / rho[:, None]
        rhov2 = np.sum(U_L[:, 1:4] ** 2, axis=1) / rho
        e_int = U_L[:, 4] - 0.5 * rhov2
        un = np.einsum("ij,ij->i", u, nvec)

        UG = U_L.copy()

        # -- solid wall: mirror normal velocity -----------------------------
        wall = bc == 0
        if wall.any():
            u_w = u[wall] - 2.0 * un[wall, None] * nvec[wall]
            UG[wall, 1:4] = rho[wall, None] * u_w
            UG[wall, 4] = e_int[wall] + 0.5 * rho[wall] * np.sum(u_w ** 2, axis=1)

        # -- non-reflecting outflow: ambient ghost state -------------------
        # Anchor the ghost pressure to the ambient state while keeping the
        # interior velocity (zero-order extrapolation of the velocity only),
        # so the boundary lets the stream leave without reflecting acoustic
        # waves and still fixes the far-field pressure.
        #
        # The previous version pinned the ghost *internal* energy into the
        # total-energy slot, which subtracts ``0.5 rho u^2`` from the pressure:
        # ``p_ghost = 0.4 (e_int - 0.5*1.225*220^2) = 89.4 kPa`` for the
        # 220 m/s stream instead of the ambient 100 kPa.  The whole inflow was
        # 10 kPa too cold, and the reported p_min was this artefact rather
        # than a physical base pressure.  The total energy below restores the
        # kinetic part, so ``p_ghost`` is exactly the ambient pressure.
        out = bc == 1
        if out.any():
            g = self.gas
            rho_g = g.rho0
            u_g = U_L[out, 1:4] / np.maximum(U_L[out, 0:1], 1e-30)
            UG[out, 0] = rho_g
            UG[out, 1:4] = rho_g * u_g
            UG[out, 4] = g.e0 + 0.5 * rho_g * np.sum(u_g ** 2, axis=1)
        return UG

    # ------------------------------------------------------------------- flux
    def residual(self) -> np.ndarray:
        g = self.g
        U = self.U
        rho, u, p, c = self.primitive()

        bnd = self._bnd
        UL = U[g.owner]
        UR = np.empty_like(UL)
        UR[~self._is_b] = U[g.neigh[~self._is_b]]
        if bnd.size:
            UR[bnd] = self._ghost_states(UL[bnd], g.n[bnd], g.bc[bnd])

        pL = p[g.owner]
        # right pressure from ghost / neighbour state
        rhoR = UR[:, 0]
        uR = UR[:, 1:4] / rhoR[:, None]
        pR = self.gas.pressure(rhoR, UR[:, 4] - 0.5 * np.sum(UR[:, 1:4] ** 2, axis=1) / rhoR)
        cR = self.gas.sound_speed(rhoR, pR)

        uL = u[g.owner]
        FL = self._flux_normal(UL, uL, pL, g.n)
        FR = self._flux_normal(UR, uR, pR, g.n)

        lam = np.maximum(np.abs(np.einsum("ij,ij->i", uL, g.n)) + c[g.owner],
                         np.abs(np.einsum("ij,ij->i", uR, g.n)) + cR)
        flux = 0.5 * (FL + FR) - 0.5 * lam[:, None] * (UR - UL)
        flux *= g.area[:, None]

        nc = g.ncell
        d = np.empty_like(U)
        for k in range(5):
            d[:, k] = (-np.bincount(g.owner, weights=flux[:, k], minlength=nc)
                       + np.bincount(g.neigh[~self._is_b],
                                     weights=flux[~self._is_b, k], minlength=nc))
            d[:, k] *= self._invV

        # store the per-cell spectral radius used for the time step
        speed_flux = lam * g.area
        self._wave = (np.bincount(g.owner, weights=speed_flux, minlength=nc)
                      + np.bincount(g.neigh[~self._is_b],
                                    weights=speed_flux[~self._is_b], minlength=nc))
        return d

    # ------------------------------------------------------------- time step
    def stable_dt(self) -> float:
        w = self._wave
        m = np.maximum(w * self._invV, 1e-30)
        return self.cfl / float(np.max(m))

    # --------------------------------------------------------------- stepping
    def step(self, dt: float) -> None:
        """SSP-RK2 (Heun): U2 = 1/2 U0 + 1/2 (U1 + dt*R(U1)), U1 = U0 + dt*R(U0)."""
        # the driven layer is a reservoir: refresh it before the predictor so
        # that both stages see the prescribed velocity and ambient state
        self._apply_drive(self.U)
        U0 = self.U
        k1 = self.residual()              # R(U0)
        U1 = U0 + dt * k1
        self._enforce(U1)
        self._apply_drive(U1)
        self.U = U1
        k2 = self.residual()              # R(U1)
        U2 = 0.5 * U0 + 0.5 * (U1 + dt * k2)
        self._enforce(U2)
        self._apply_drive(U2)
        self.U = U2

    def _enforce(self, U: np.ndarray) -> None:
        rho = U[:, 0]
        bad = rho < 0.05 * self.gas.rho0
        if bad.any():
            U[bad, 0] = self.gas.rho0
            U[bad, 1:4] = 0.0
            U[bad, 4] = self.gas.e0
        ke = 0.5 * np.sum(U[:, 1:4] ** 2, axis=1) / np.maximum(U[:, 0], 1e-12)
        low = (U[:, 4] - ke) < 0.02 * self.gas.e0
        if low.any():
            U[low, 4] = ke[low] + 0.02 * self.gas.e0

    def _apply_drive(self, U: np.ndarray) -> None:
        """Impose ``*BOUNDARY_PRESCRIBED_MOTION_SET`` on the interior node layer.

        The deck does not use an inflow boundary: the upstream 0.035 m thick
        node layer (``SET_NODE_LIST 23``) is prescribed a +Y velocity through
        ``*DEFINE_CURVE 11``.  In a fixed Eulerian grid the equivalent is a
        *reservoir*: the control volumes covering that layer are reset to the
        ambient state with the prescribed velocity every stage.  That supplies
        the correct mass and energy flux through the layer's downstream faces
        (a velocity inlet) without needing a separate ghost state, and avoids
        draining the layer to vacuum as would happen if only the momentum
        were overwritten.
        """
        if self.driven_cells.size == 0:
            return
        c = self.driven_cells
        g = self.gas
        rho = g.rho0
        dof = self.driven_dof - 1
        u = np.zeros((c.size, 3))
        u[:, dof] = self.driven_value
        U[c, 0] = rho
        U[c, 1:4] = rho * u
        # total energy per unit volume: ambient internal + drive kinetic
        U[c, 4] = g.e0 + 0.5 * rho * np.sum(u ** 2, axis=1)

    # ------------------------------------------------------------- diagnostics
    def mass(self) -> float:
        return float(np.sum(self.U[:, 0] * self._vol))

    def momentum(self) -> np.ndarray:
        return np.sum(self.U[:, 1:4] * self._vol[:, None], axis=0)

    def energy(self) -> float:
        return float(np.sum(self.U[:, 4] * self._vol))

    def kinetic(self) -> float:
        return float(np.sum(0.5 * np.sum(self.U[:, 1:4] ** 2, axis=1)
                            / self.U[:, 0] * self._vol))

    def internal(self) -> float:
        return self.energy() - self.kinetic()

    def cfl_number(self, dt: float) -> float:
        return float(np.max(self._wave * self._invV) * dt)

    def set_drive(self, cells: np.ndarray, dof: int, value: float) -> None:
        self.driven_cells = np.asarray(cells, dtype=np.int64)
        self.driven_dof = int(dof)
        self.driven_value = float(value)
