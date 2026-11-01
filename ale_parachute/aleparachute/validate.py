"""Self contained verification cases for the ALE parachute solver.

Three independent checks are provided:

``sod``        -- Sod shock tube: validates the ALE finite-volume flux,
                  the EOS and the time integration against the exact Riemann
                  solution (L1 error on density).
``uniform``    -- a uniform fluid at rest must stay exactly at rest, i.e. the
                  scheme is freestream preserving.
``membrane``   -- a single fabric patch under a prescribed uniaxial strain
                  must reproduce the analytic CST membrane force EA*t*eps.
"""

from __future__ import annotations

import numpy as np

from .fluid import ALEFluid, IdealGas
from .mesh import HEX_FACES, Structure, build_hex_grid, build_structure
from .structure import StructureSolver


# ----------------------------------------------------------------------------
# Sod shock tube
# ----------------------------------------------------------------------------
def _sod_exact(x: np.ndarray, t: float, gamma: float = 1.4):
    """Exact Sod solution sampled at ``x`` at time ``t`` (p*, u*, rho(x))."""
    rhoL, uL, pL = 1.0, 0.0, 1.0
    rhoR, uR, pR = 0.125, 0.0, 0.1
    aL = np.sqrt(gamma * pL / rhoL)
    aR = np.sqrt(gamma * pR / rhoR)

    def u_left(p):                       # rarefaction / shock on the left state
        if p > pL:
            return uL - (p - pL) / np.sqrt(
                rhoL * (0.5 * (gamma + 1) * p + 0.5 * (gamma - 1) * pL))
        return uL + 2 * aL / (gamma - 1) * (1 - (p / pL) **
                                            ((gamma - 1) / (2 * gamma)))

    def u_right(p):                      # rarefaction / shock on the right state
        if p > pR:
            return uR + (p - pR) / np.sqrt(
                rhoR * (0.5 * (gamma + 1) * p + 0.5 * (gamma - 1) * pR))
        return uR - 2 * aR / (gamma - 1) * (1 - (p / pR) **
                                             ((gamma - 1) / (2 * gamma)))

    lo, hi = 1e-6, 20.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if u_left(mid) - u_right(mid) < 0:
            hi = mid
        else:
            lo = mid
    p_star = 0.5 * (lo + hi)
    u_star = 0.5 * (u_left(p_star) + u_right(p_star))

    rhoL_star = rhoL * (p_star / pL) ** (1.0 / gamma)
    rhoR_star = rhoR * ((p_star / pR + (gamma - 1) / (gamma + 1))
                        / ((gamma - 1) / (gamma + 1) * p_star / pR + 1.0))
    aL_star = aL * (p_star / pL) ** ((gamma - 1) / (2 * gamma))
    shock_speed = aR * np.sqrt((gamma - 1) / (2 * gamma)
                                + (gamma + 1) / (2 * gamma) * p_star / pR)

    x0 = 0.5
    x_head = x0 - aL * t
    x_tail = x0 + (u_star - aL_star) * t
    x_cont = x0 + u_star * t
    x_shock = x0 + shock_speed * t

    out = np.where(x <= x_shock, rhoR_star, rhoR)
    out = np.where(x <= x_cont, rhoL_star, out)
    fan = (x >= x_head) & (x <= x_tail)
    u_fan = 2.0 / (gamma + 1) * (aL + (x - x0) / t)
    a_fan = aL * (2.0 / (gamma + 1) - (gamma - 1) / (gamma + 1) * (x - x0) / (t * aL))
    rho_fan = rhoL * (np.maximum(a_fan / aL, 1e-12)) ** (2.0 / (gamma - 1))
    out = np.where(fan, rho_fan, out)
    out = np.where(x <= x_head, rhoL, out)
    return out, p_star, u_star


def sod_case(nx: int = 200, endtime: float = 0.2) -> dict:
    """Run the Sod shock tube on a quasi-1-D hexahedral grid."""
    xs = np.linspace(0.0, 1.0, nx + 1)
    xc = 0.5 * (xs[:-1] + xs[1:])
    y = np.array([0.0, 0.01])
    z = np.array([0.0, 0.01])

    def nid(i, j, k):
        # C-order index of np.meshgrid(xs, y, z, indexing="ij").ravel()
        return (i * 2 + j) * 2 + k

    I, J, K = np.meshgrid(np.arange(nx), np.arange(1), np.arange(1), indexing="ij")
    I, J, K = I.ravel(), J.ravel(), K.ravel()
    n0 = nid(I, J, K)
    n1 = nid(I + 1, J, K)
    n2 = nid(I + 1, J + 1, K)
    n3 = nid(I, J + 1, K)
    n4 = nid(I, J, K + 1)
    n5 = nid(I + 1, J, K + 1)
    n6 = nid(I + 1, J + 1, K + 1)
    n7 = nid(I, J + 1, K + 1)
    conn = np.stack([n0, n1, n2, n3, n4, n5, n6, n7], axis=1)

    X, Y, Z = np.meshgrid(xs, y, z, indexing="ij")
    pts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    g = build_hex_grid(pts, conn, tag="sod")
    # walls in y/z (|n_x| < 0.5), non-reflecting at both x ends
    g.bc[:] = 0
    g.bc[(g.neigh < 0) & (np.abs(g.n[:, 0]) > 0.5)] = 1

    gas = IdealGas(rho0=1.0, c4=0.4, c5=0.0, c6=0.0, e0=2.5, pref=101300.0)
    f = ALEFluid(g, gas, cfl=0.5)
    left = xc < 0.5
    f.U[:, 0] = np.where(left, 1.0, 0.125)
    f.U[:, 4] = np.where(left, 2.5, 0.25)

    t = 0.0
    while t < endtime:
        dt = min(f.stable_dt() * 0.9, endtime - t)
        f.step(dt)
        t += dt
    rho, u, p, c = f.primitive()
    exact, p_star, u_star = _sod_exact(xc, endtime)
    l1 = float(np.mean(np.abs(rho - exact)) / np.mean(exact))
    return {"grid": g, "fluid": f, "rho": rho, "exact": exact, "l1": l1,
            "p_star": p_star, "u_star": u_star, "steps": None}


# ----------------------------------------------------------------------------
# freestream preservation
# ----------------------------------------------------------------------------
def uniform_case(nstep: int = 200) -> dict:
    """A uniform fluid at rest must remain exactly at rest."""
    from .mesh import auto_cylinder_grid
    g = auto_cylinder_grid(-0.9, 0.16, 0.23, 8, 8, 8)
    gas = IdealGas(1.18, 0.4, 0.0, 0.0, 250000.0, 101300.0)
    f = ALEFluid(g, gas, cfl=0.5)
    m0, e0 = f.mass(), f.energy()
    umax = 0.0
    for _ in range(nstep):
        f.step(f.stable_dt() * 0.9)
        umax = max(umax, float(np.linalg.norm(f.primitive()[1], axis=1).max()))
    return {"dm": abs(f.mass() - m0) / m0, "de": abs(f.energy() - e0) / abs(e0),
            "umax": umax}


# ----------------------------------------------------------------------------
# membrane patch
# ----------------------------------------------------------------------------
def membrane_case(eps: float = 1e-3, t: float = 9e-4, EA: float = 4.309e7,
                  nu: float = 0.0) -> dict:
    x = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0],
                  [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]])
    tris = np.array([[0, 1, 2], [0, 2, 3]])
    n = x.shape[0]
    area0 = 0.5 * np.linalg.norm(
        np.cross(x[tris[:, 1]] - x[tris[:, 0]], x[tris[:, 2]] - x[tris[:, 0]]),
        axis=1)
    edge0 = np.stack([np.linalg.norm(x[tris[:, 1]] - x[tris[:, 0]], axis=1),
                      np.linalg.norm(x[tris[:, 2]] - x[tris[:, 1]], axis=1),
                      np.linalg.norm(x[tris[:, 0]] - x[tris[:, 2]], axis=1)], axis=1)
    st = Structure(
        x=x.copy(), v=np.zeros_like(x), f=np.zeros_like(x),
        mass=np.full(n, 533.77 * t * 0.25), node_ids=np.arange(n) + 1,
        tris=tris, tri_area0=area0, tri_thk=np.full(2, t),
        tri_ea=np.full(2, EA), tri_eb=np.full(2, EA),
        tri_g=np.full(2, EA / (2.0 * (1.0 + nu))), tri_nu=np.full(2, nu),
        tri_rho=np.full(2, 533.77), tri_edge0=edge0,
        tri_area=area0.copy(), tri_normal=np.zeros((2, 3)),
        nodal_area=np.zeros(n), nodal_normal=np.zeros((n, 3)),
    )
    s = StructureSolver(st, tension_only=False)
    # affine uniaxial extension, no lateral contraction
    st.x[:, 0] *= (1.0 + eps)
    s.update_kinematics()
    f = s.internal_forces()
    # analytic: right edge carries C11*eps*t over unit width
    expected = EA * t * eps * 1.0
    got = abs(float(f[1, 0] + f[2, 0]))    # total force on the right edge
    return {"expected": expected, "got": got, "rel": abs(got / expected - 1.0),
            "sum": float(np.abs(f.sum(axis=0)).max())}


def run_all(verbose: bool = True) -> dict:
    res = {}
    res["uniform"] = uniform_case()
    res["membrane"] = membrane_case()
    res["sod"] = sod_case()
    if verbose:
        u = res["uniform"]
        print(f"uniform  : dm={u['dm']:.3e} de={u['de']:.3e} umax={u['umax']:.3e}")
        mm = res["membrane"]
        print(f"membrane : force={mm['got']:.4e} N expected={mm['expected']:.4e} N "
              f"rel={mm['rel']:.2e} reaction={mm['sum']:.2e}")
        s = res["sod"]
        print(f"sod      : p*={s['p_star']:.4f} (exact 0.30313) "
              f"u*={s['u_star']:.4f} (exact 0.92745) L1(rho)={s['l1']:.3f}")
    return res
