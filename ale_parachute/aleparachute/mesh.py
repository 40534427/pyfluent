"""Spatial discretisation.

Two pieces are built here:

* :class:`HexGrid`   -- an Eulerian hexahedral control-volume grid used by the
  ALE/fluid solver.  It can either be generated automatically around the
  canopy or taken directly from the K file solid connectivity.
* :class:`Structure` -- the Lagrangian fabric canopy (triangulated shell) and
  the suspension lines (2-node cables).

Both are derived from the K file so that every geometric parameter (canopy
radius, fluid domain, membrane thickness, ...) comes from the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np

# local node ordering of a hexahedron face (inward/outward orientation is
# fixed numerically below)
HEX_FACES = (
    (0, 1, 2, 3),
    (4, 7, 6, 5),
    (0, 4, 5, 1),
    (1, 5, 6, 2),
    (2, 6, 7, 3),
    (3, 7, 4, 0),
)


@dataclass
class HexGrid:
    x: np.ndarray                  # (Nn,3) node coordinates
    conn: np.ndarray               # (Nc,8) node indices
    vol: np.ndarray                # (Nc,) cell volume
    center: np.ndarray             # (Nc,3) cell centroid
    owner: np.ndarray              # (Nf,) owner cell
    neigh: np.ndarray              # (Nf,) neighbour cell (-1 = boundary)
    fnode: np.ndarray              # (Nf,4) face node indices
    S: np.ndarray                  # (Nf,3) area vector (owner outward)
    area: np.ndarray               # (Nf,)
    n: np.ndarray                  # (Nf,3) unit normal
    fc: np.ndarray                 # (Nf,3) face centroid
    bc: np.ndarray                 # (Nf,) 0=wall 1=non-reflecting
    tag: str = ""

    @property
    def ncell(self) -> int:
        return self.vol.size

    @property
    def nface(self) -> int:
        return self.area.size

    def boundary_info(self) -> Dict[str, int]:
        nb = int((self.neigh < 0).sum())
        return {"cells": int(self.ncell), "faces": int(self.nface),
                "internal_faces": int((self.neigh >= 0).sum()),
                "boundary_faces": nb}


def build_hex_grid(x: np.ndarray, conn: np.ndarray, bc_nonreflecting=None,
                   tag: str = "") -> HexGrid:
    """Build the control-volume description of a hexahedral mesh.

    ``conn`` must use 0-based local node indices.  ``bc_nonreflecting`` is an
    optional (Nf,)-like set/list of face ids already known to be non
    reflecting; by default every boundary face is non reflecting.
    """
    nc = conn.shape[0]
    nf_occ = 6 * nc
    fn = conn[:, np.array(HEX_FACES)].reshape(nf_occ, 4)      # unsorted order

    # ---- face deduplication ------------------------------------------------
    key = np.sort(fn, axis=1)
    uniq, inv, cnt = np.unique(key, axis=0, return_inverse=True,
                               return_counts=True)
    nfaces = uniq.shape[0]

    order = np.argsort(inv, kind="stable")
    offsets = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    first_occ = order[offsets]
    owner = first_occ // 6
    neigh = np.full(nfaces, -1, dtype=np.int64)
    two = np.nonzero(cnt == 2)[0]
    neigh[two] = order[offsets[two] + 1] // 6

    # ---- geometry ---------------------------------------------------------
    fnode = fn[first_occ]                                   # owner node order
    p0, p1, p2, p3 = (x[fnode[:, k]] for k in range(4))
    fc = 0.25 * (p0 + p1 + p2 + p3)
    # area vector from two triangles (p0,p1,p2) + (p0,p2,p3)
    S = 0.5 * (np.cross(p1 - p0, p2 - p0) + np.cross(p2 - p0, p3 - p0))

    # outward orientation w.r.t. the owner cell
    ccell = np.mean(x[conn], axis=1)
    sign = np.einsum("ij,ij->i", S, fc - ccell[owner])
    flip = sign < 0.0
    S[flip] *= -1.0
    area = np.linalg.norm(S, axis=1)
    nvec = S / np.maximum(area[:, None], 1e-30)

    # ---- cell volumes (divergence theorem, works for wedges too) ----------
    # every face contributes to both of its cells, with the surface vector
    # seen as outward from each cell in turn
    vol = np.zeros(nc)
    contrib = np.einsum("ij,ij->i", fc - ccell[owner], S) / 3.0
    np.add.at(vol, owner, contrib)
    inr = neigh >= 0
    contrib = np.einsum("ij,ij->i", fc[inr] - ccell[neigh[inr]], -S[inr]) / 3.0
    np.add.at(vol, neigh[inr], contrib)
    vol = np.abs(vol)
    bad = vol < 1e-30
    if bad.any():
        vol[bad] = 1e-30

    bc = np.zeros(nfaces, dtype=np.int64)
    bnd = neigh < 0
    bc[bnd] = 1
    if bc_nonreflecting is not None:
        ids = np.asarray(bc_nonreflecting, dtype=np.int64)
        bc[:] = 0
        bc[ids] = 1

    return HexGrid(x=x, conn=conn, vol=vol, center=ccell, owner=owner,
                   neigh=neigh, fnode=fnode, S=S, area=area, n=nvec, fc=fc,
                   bc=bc, tag=tag)


def auto_cylinder_grid(y0: float, y1: float, radius: float, nx: int, ny: int,
                       nz: int, cx: float = 0.0, cz: float = 0.0) -> HexGrid:
    """Cartesian hexahedral grid clipped to a circular cylinder (axis = y).

    Cells whose centre lies outside the cylinder are removed; the remaining
    outer faces become the non-reflecting boundary.  This reproduces the fluid
    domain of the K file (circular cross-section, radius ``radius``) without
    introducing degenerate wedge cells along the axis.
    """
    xlo, xhi = cx - radius, cx + radius
    zlo, zhi = cz - radius, cz + radius

    xs = np.linspace(xlo, xhi, nx + 1)
    zs = np.linspace(zlo, zhi, nz + 1)
    ys = np.linspace(y0, y1, ny + 1)

    # cell centres
    xc = 0.5 * (xs[:-1] + xs[1:])
    zc = 0.5 * (zs[:-1] + zs[1:])
    yc = 0.5 * (ys[:-1] + ys[1:])
    XC, ZC, YC = np.meshgrid(xc, zc, yc, indexing="ij")
    active = ((XC - cx) ** 2 + (ZC - cz) ** 2) <= radius ** 2
    I, K, J = np.nonzero(active)

    nxn = nx + 1
    nzn = nz + 1
    nyn = ny + 1

    def nid(i, j, k):
        # C-order index of np.meshgrid(xs, ys, zs, indexing="ij").ravel()
        return (i * nyn + j) * nzn + k

    n0 = nid(I, J, K)
    n1 = nid(I + 1, J, K)
    n2 = nid(I + 1, J + 1, K)
    n3 = nid(I, J + 1, K)
    n4 = nid(I, J, K + 1)
    n5 = nid(I + 1, J, K + 1)
    n6 = nid(I + 1, J + 1, K + 1)
    n7 = nid(I, J + 1, K + 1)
    conn_raw = np.stack([n0, n1, n2, n3, n4, n5, n6, n7], axis=1)

    used = np.unique(conn_raw)
    remap = -np.ones(nxn * nzn * nyn, dtype=np.int64)
    remap[used] = np.arange(used.size)
    conn = remap[conn_raw]

    gx = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), axis=-1)
    gx = gx.reshape(-1, 3)[used]

    return build_hex_grid(gx, conn, tag="auto-cylinder")


def fluid_geometry(model) -> Tuple[float, float, float, float, float]:
    """(y0, y1, radius, cx, cz) of the ALE fluid domain taken from the K file."""
    nodes = model.mesh["nodes"]
    ids = nodes[:, 0].astype(np.int64)
    conn = model.mesh["solid_conn"]
    used = np.unique(conn[conn > 0])
    sel = np.isin(ids, used)
    xyz = nodes[sel, 1:4]
    y0, y1 = float(xyz[:, 1].min()), float(xyz[:, 1].max())
    cx = 0.5 * float(xyz[:, 0].min() + xyz[:, 0].max())
    cz = 0.5 * float(xyz[:, 2].min() + xyz[:, 2].max())
    r = max(float(xyz[:, 0].max() - xyz[:, 0].min()),
            float(xyz[:, 2].max() - xyz[:, 2].min())) * 0.5
    return y0, y1, r, cx, cz


def native_grid(model) -> HexGrid:
    """Use the K file fluid mesh (``*ELEMENT_SOLID``) directly."""
    nodes = model.mesh["nodes"]
    ids = nodes[:, 0].astype(np.int64)
    n2i = {int(v): i for i, v in enumerate(ids)}
    conn_ids = model.mesh["solid_conn"]
    used = np.unique(conn_ids)
    lut = np.zeros(int(ids.max()) + 1, dtype=np.int64)
    lut[used] = np.arange(used.size)
    conn = lut[conn_ids]
    x = np.array([nodes[n2i[int(v)], 1:4] for v in used])

    # The K file marks the three outer surface groups (100/102/104) as
    # non-reflecting; together they cover the complete outer boundary.
    g = build_hex_grid(x, conn, tag="native")
    g.bc[:] = 0
    g.bc[g.neigh < 0] = 1
    return g


# ----------------------------------------------------------------------------
# Lagrangian structure
# ----------------------------------------------------------------------------
@dataclass
class Structure:
    x: np.ndarray                  # (Nn,3) current coordinates
    v: np.ndarray                  # (Nn,3)
    f: np.ndarray                  # (Nn,3) nodal force
    mass: np.ndarray               # (Nn,)
    node_ids: np.ndarray           # K file node ids
    tris: np.ndarray               # (Nt,3)
    tri_area0: np.ndarray
    tri_thk: np.ndarray
    tri_ea: np.ndarray
    tri_eb: np.ndarray
    tri_g: np.ndarray
    tri_nu: np.ndarray
    quads: np.ndarray = field(default_factory=lambda: np.zeros((0, 4), int))
    tri_rho: np.ndarray = field(default_factory=lambda: np.zeros(0))
    tri_edge0: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))
    tri_area: np.ndarray = field(default_factory=lambda: np.zeros(0))
    tri_normal: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))
    nodal_area: np.ndarray = field(default_factory=lambda: np.zeros(0))
    nodal_normal: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))
    nodal_coherence: np.ndarray = field(default_factory=lambda: np.zeros(0))
    beams: np.ndarray = field(default_factory=lambda: np.zeros((0, 2), int))
    beam_area: np.ndarray = field(default_factory=lambda: np.zeros(0))
    beam_E: np.ndarray = field(default_factory=lambda: np.zeros(0))
    beam_L0: np.ndarray = field(default_factory=lambda: np.zeros(0))
    beam_mass: np.ndarray = field(default_factory=lambda: np.zeros(0))
    beam_eid: np.ndarray = field(default_factory=lambda: np.zeros(0, int))
    fixed: np.ndarray = field(default_factory=lambda: np.zeros(0, int))
    driven: np.ndarray = field(default_factory=lambda: np.zeros(0, int))
    driven_dof: np.ndarray = field(default_factory=lambda: np.zeros(0, int))
    driven_curve: np.ndarray = field(default_factory=lambda: np.zeros(0, int))
    driven_sf: np.ndarray = field(default_factory=lambda: np.zeros(0))

    @property
    def nnode(self) -> int:
        return self.x.shape[0]

    def summary(self) -> dict:
        return {"nodes": int(self.nnode), "triangles": int(self.tris.shape[0]),
                "cables": int(self.beams.shape[0]),
                "mass": float(self.mass.sum())}

def build_structure(model) -> Structure:
    nodes = model.mesh["nodes"]
    ids = nodes[:, 0].astype(np.int64)
    n2i = {int(v): i for i, v in enumerate(ids)}

    shell_conn = model.mesh["shell_conn"]
    beam_conn = model.mesh["beam_conn"]

    used_ids = np.unique(np.concatenate([shell_conn.ravel(), beam_conn.ravel()]))
    used_ids = used_ids[used_ids > 0]
    nloc = {int(v): i for i, v in enumerate(used_ids)}
    x0 = np.array([nodes[n2i[int(v)], 1:4] for v in used_ids])

    # ---- triangles from quads --------------------------------------------
    a = np.array([[nloc[int(v)] for v in row] for row in shell_conn])
    t1 = a[:, [0, 1, 2]]
    t2 = a[:, [0, 2, 3]]
    tris = np.vstack([t1, t2])

    pid = int(model.mesh["shell_pid"][0])
    part = model.parts[pid]
    sec = model.sections[part["secid"]]
    mat = model.materials[part["mid"]]
    t = float(sec.get("t1", 1.0e-3))
    ea = float(mat["ea"])
    # *MAT_FABRIC  EB = 0 in the deck: the fill (b) direction carries no
    # stiffness, i.e. the canopy behaves as a uniaxial fibre membrane
    # (meridional fibres only).  Do *not* fall back to EA here -- that would
    # turn the fabric into an isotropic sheet and change the inflation shape.
    eb = float(mat["eb"])
    nu = float(mat.get("prba", 0.0))
    gab = float(mat.get("gab", 0.0))
    if gab <= 0.0:
        gab = ea / (2.0 * (1.0 + nu))
    rho_s = float(mat["ro"])

    p0 = x0[tris[:, 0]]
    p1 = x0[tris[:, 1]]
    p2 = x0[tris[:, 2]]
    area0 = 0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)

    nt = tris.shape[0]
    tri_thk = np.full(nt, t)
    tri_ea = np.full(nt, ea)
    tri_eb = np.full(nt, eb)
    tri_g = np.full(nt, gab)
    tri_nu = np.full(nt, nu)
    tri_rho = np.full(nt, rho_s)
    tri_edge0 = np.stack([np.linalg.norm(x0[tris[:, 1]] - x0[tris[:, 0]], axis=1),
                          np.linalg.norm(x0[tris[:, 2]] - x0[tris[:, 1]], axis=1),
                          np.linalg.norm(x0[tris[:, 0]] - x0[tris[:, 2]], axis=1)], axis=1)

    # ---- cables -----------------------------------------------------------
    bp = int(model.mesh["beam_pid"][0])
    bpart = model.parts[bp]
    bsec = model.sections[bpart["secid"]]
    bmat = model.materials[bpart["mid"]]
    b_area_s = float(bsec.get("ts1", 0.0)) * float(bsec.get("tt1", 0.0))
    b_E = float(bmat["e"])
    b_rho = float(bmat["ro"])

    beams = np.array([[nloc[int(v)] for v in row] for row in beam_conn])
    L0 = np.linalg.norm(x0[beams[:, 1]] - x0[beams[:, 0]], axis=1)
    beam_area = np.full(beams.shape[0], b_area_s)
    beam_E = np.full(beams.shape[0], b_E)
    beam_mass_e = b_rho * b_area_s * L0

    # ---- lumped mass ------------------------------------------------------
    mass = np.zeros(len(used_ids))
    np.add.at(mass, tris.ravel(), np.repeat(rho_s * t * area0 / 3.0, 3))
    np.add.at(mass, beams.ravel(), np.repeat(beam_mass_e / 2.0, 2))
    mass = np.maximum(mass, 1e-12)

    # ---- BCs --------------------------------------------------------------
    fixed = np.zeros(0, dtype=np.int64)
    for s in model.bc.get("spc", []):
        sid = s["nsid"]
        ids_ = model.sets_by_type.get(("node", sid))
        if ids_ is None:
            continue
        fixed = np.union1d(fixed, [nloc[int(v)] for v in ids_ if int(v) in nloc])

    driven, driven_dof, driven_curve, driven_sf = [], [], [], []
    for pm in model.bc.get("prescribed_motion", []):
        ids_ = model.sets_by_type.get(("node", pm["nsid"]))
        if ids_ is None:
            continue
        sel = [nloc[int(v)] for v in ids_ if int(v) in nloc]
        driven += sel
        driven_dof += [int(pm["dof"])] * len(sel)
        driven_curve += [int(pm["lcid"])] * len(sel)
        driven_sf += [float(pm["sf"])] * len(sel)

    return Structure(
        x=x0, v=np.zeros_like(x0), f=np.zeros_like(x0), mass=mass,
        node_ids=used_ids, tris=tris, tri_area0=area0, tri_thk=tri_thk,
        tri_ea=tri_ea, tri_eb=tri_eb, tri_g=tri_g, tri_nu=tri_nu,
        quads=a,
        tri_rho=tri_rho, tri_edge0=tri_edge0,
        tri_area=area0.copy(), tri_normal=np.zeros((nt, 3)),
        nodal_area=np.zeros(len(used_ids)), nodal_normal=np.zeros((len(used_ids), 3)),
        beams=beams, beam_area=beam_area, beam_E=beam_E, beam_L0=L0,
        beam_mass=beam_mass_e, beam_eid=model.mesh["beam_eid"],
        fixed=fixed.astype(np.int64),
        driven=np.asarray(driven, dtype=np.int64),
        driven_dof=np.asarray(driven_dof, dtype=np.int64),
        driven_curve=np.asarray(driven_curve, dtype=np.int64),
        driven_sf=np.asarray(driven_sf, dtype=np.float64),
    )
