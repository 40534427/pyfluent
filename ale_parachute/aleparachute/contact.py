"""Automatic single-surface penalty contact (``*CONTACT_AUTOMATIC_SINGLE_SURFACE``).

The deck activates one single-surface contact on the canopy part

    *CONTACT_AUTOMATIC_SINGLE_SURFACE_ID  cid = 1
        ssid = 11, sstyp = 3 (part id)   -> Part 11 ``Para_Surf`` (canopy)
        fs = fd = 0 (frictionless), penchk = 0, bt = 0 (penalty), dt = 1e20
        sfs = 1.0

The algorithm implemented here is LS-DYNA's node-to-segment penalty contact
for a *single* surface: a canopy node is projected onto nearby canopy
segments of the same part, the signed gap is compared with the shell
thickness and a normal spring force

    f = sfs * k_pair * pen * n

is applied to the node while the opposite force is distributed to the
segment nodes with the bilinear shape functions (momentum conserving).

* ``pen`` is the penetration measured beyond the shell thickness;
* triangles / quads that share a node with the slave node are skipped;
* one initial nearest-neighbour search (direct search) is stored and
  refreshed only when the surface has moved, so that the cost stays low;
* initially interpenetrating folds (folding a *flat pattern* always has
  contacting layers) are offset by their initial gap, the LS-DYNA
  ``ignore initial penetration`` behaviour.  No huge start-up force is
  produced but a *further* approach still activates the penalty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.spatial import cKDTree

from .mesh import Structure


@dataclass
class ContactStats:
    fmax: float = 0.0
    pairs: int = 0
    pen_max: float = 0.0
    nodes: int = 0


class SelfContact:
    def __init__(self, st: Structure, enabled: bool = True,
                 scale: float = 1.0, sfs: float = 1.0, sfm: float = 1.0,
                 vdc: float = 0.0, thickness_scale: float = 1.0,
                 ignore_initial: bool = True, nsearch: int = 6,
                 rebuild_move: float = 0.5):
        self.st = st
        self.enabled = enabled
        self.scale = float(scale)
        self.sfs = float(sfs)
        self.sfm = float(sfm)
        self.vdc = float(vdc)
        self.thickness_scale = float(thickness_scale)
        self.ignore_initial = bool(ignore_initial)
        self.nsearch = int(nsearch)
        self.rebuild_move = float(rebuild_move)
        self.stats = ContactStats()

        q = st.quads if st.quads.shape[0] else None
        self.faces = q                       # (Nf,4) local node indices
        self.nface = 0 if q is None else q.shape[0]
        self._empty = self.nface == 0
        if self._empty:
            return

        f = self.faces
        self.face_thk = st.tri_thk[:self.nface].copy()
        self.node_thk = np.zeros(st.nnode)
        cnt = np.zeros(st.nnode)
        for k in range(4):
            np.add.at(self.node_thk, f[:, k], self.face_thk)
            np.add.at(cnt, f[:, k], 1.0)
        self.node_thk /= np.maximum(cnt, 1.0)

        # stiffness per pair [N/m]: LS-DYNA shell penalty
        #   k ~ SLSFAC * E * t  (element membrane stiffness of a unit patch)
        e = st.tri_ea[:self.nface]
        t = st.tri_thk[:self.nface]
        self.face_k = self.scale * self.sfs * e * t * 0.5

        self.edge0 = np.stack([np.linalg.norm(st.x[f[:, k]] - st.x[f[:, (k + 1) % 4]],
                                              axis=1) for k in range(4)], axis=1)
        self.lchar = np.max(self.edge0, axis=1)
        self.x0 = st.x.copy()                # reference for initial penetrations
        self.tree = cKDTree(np.mean(st.x[f], axis=1))
        self._x_ref = st.x.copy()
        self._pairs = self._build_pairs(self.x0)
        self._kmax = float(np.max(self._pairs["k"])) if self._pairs["n"] else 0.0

    # ------------------------------------------------------------- pair search
    def _build_pairs(self, xref: np.ndarray, prev: Optional[dict] = None) -> dict:
        st = self.st
        f = self.faces
        nodes = np.nonzero(self.node_thk > 0.0)[0]
        if nodes.size == 0:
            return {"n": 0}
        kk = min(self.nsearch, self.nface)
        dist, fidx = self.tree.query(st.x[nodes], k=kk)
        fidx = np.asarray(fidx).reshape(-1, kk)
        dist = np.asarray(dist).reshape(-1, kk)
        pn = np.repeat(nodes, fidx.shape[1])
        pf = fidx.ravel()
        pd = dist.ravel()

        # skip segments that share a node with the slave node
        shared = np.zeros(pn.size, dtype=bool)
        for k in range(4):
            shared |= (f[pf, k] == pn)

        # the initial gap is measured in the reference configuration so that
        # a pair keeps its "ignore initial penetration" offset when the
        # direct search is repeated.  The signed distance is kept as is: a
        # node that starts below the segment must be pushed back towards it,
        # so the *relative approach* (gap0 - gap) is the penetration.  Flipping
        # the sign of either start value turns the pair into a negative
        # stiffness and the whole surface diverges exponentially.
        gap, xi, et = self._gap_and_params(pn, pf, xref)
        tcg = 0.5 * (self.node_thk[pn] + self.face_thk[pf]) * self.thickness_scale
        # initial gap within the thickness: shift the segment by this depth.
        # The penetration is measured on the *absolute* distance to the
        # segment plane so that a node which has already crossed the mid-plane
        # is still pushed back to the side it came from.
        off = (np.where(np.abs(gap) < tcg, tcg - np.abs(gap), 0.0)
               if self.ignore_initial else np.zeros_like(gap))
        # A direct search repeated during the motion must not switch a node to
        # a *new* segment that already carries a "reference" penetration: the
        # new pair would start with a finite penetration and deliver an
        # impulsive penalty force (one step jumps the nodal speed from 5 to
        # 30 m/s).  New pairs therefore start at zero penetration, while a
        # pair that is found again keeps its stored offset so that the
        # accumulated approach is continuous across the rebuild.
        if prev is not None and prev.get("n", 0):
            gapc, _, _ = self._gap_and_params(pn, pf)
            off = np.maximum(tcg - np.abs(gapc), 0.0)
            key_prev = (prev["node"].astype(np.int64) * self.nface
                        + prev["face"].astype(np.int64))
            order = np.argsort(key_prev, kind="stable")
            kp = key_prev[order]
            op = np.asarray(prev["off"])[order]
            key_new = pn.astype(np.int64) * self.nface + pf.astype(np.int64)
            pos = np.clip(np.searchsorted(kp, key_new), 0, max(kp.size - 1, 0))
            hit = kp[pos] == key_new
            off[hit] = op[pos[hit]]
        k = 0.5 * (self.face_k[pf] + (self.scale * self.sfs
                                      * st.tri_ea[:self.nface][pf]
                                      * st.tri_thk[:self.nface][pf]))

        keep = (~shared) & (pd < 2.5 * self.lchar[pf])
        # only keep the closest valid segment per node to limit the pair count
        out = {"n": 0}
        if keep.any():
            idx = np.nonzero(keep)[0]
            order = np.argsort(pd[idx], kind="stable")
            idx = idx[order]
            _, first = np.unique(pn[idx], return_index=True)
            idx = idx[first]
            out = {"n": idx.size, "node": pn[idx], "face": pf[idx],
                   "gap0": gap[idx], "off": off[idx],
                   "side": np.where(gap[idx] >= 0.0, 1.0, -1.0),
                   "k": k[idx], "tc": tcg[idx], "xi": xi[idx], "et": et[idx]}
        return out

    # ------------------------------------------------------------ geometry
    def _gap_and_params(self, pn, pf, x: Optional[np.ndarray] = None):
        """Signed distance node -> plane of quad and clamped (xi, eta)."""
        st = self.st
        f = self.faces
        x = st.x if x is None else x
        x0 = x[pn]
        p = x[f[pf]]                                     # (m,4,3)
        e1 = p[:, 1] - p[:, 0]
        e2 = p[:, 3] - p[:, 0]
        n = np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 1])
        nn = np.linalg.norm(n, axis=1, keepdims=True)
        n = n / np.maximum(nn, 1e-30)
        gap = np.einsum("ij,ij->i", x0 - p[:, 0], n)
        xp = x0 - gap[:, None] * n
        q = xp - np.mean(p, axis=1)
        c = np.einsum("ij,ij->i", e1, e2)
        A = np.einsum("ij,ij->i", e1, e1)
        B = np.einsum("ij,ij->i", e2, e2)
        aa = np.einsum("ij,ij->i", q, e1)
        bb = np.einsum("ij,ij->i", q, e2)
        det = np.maximum(A * B - c * c, 1e-30)
        xi = (aa * B - bb * c) / det * 2.0
        et = (bb * A - aa * c) / det * 2.0
        xi = np.clip(xi, -1.0, 1.0)
        et = np.clip(et, -1.0, 1.0)
        return gap, xi, et

    # ------------------------------------------------------------------ force
    def force(self) -> np.ndarray:
        st = self.st
        f = np.zeros((st.nnode, 3))
        if not self.enabled or self._empty:
            self.stats = ContactStats()
            return f
        if not (np.isfinite(st.x).all() and np.isfinite(st.v).all()):
            raise RuntimeError("structure state became non finite")
        move = float(np.max(np.linalg.norm(st.x - self._x_ref, axis=1)))
        if move > self.rebuild_move * float(np.min(self.lchar)):
            self.tree = cKDTree(np.mean(st.x[self.faces], axis=1))
            self._pairs = self._build_pairs(st.x, self._pairs)
            self._kmax = float(np.max(self._pairs["k"])) if self._pairs["n"] else 0.0
            self._x_ref = st.x.copy()
        pr = self._pairs
        if pr.get("n", 0) == 0:
            self.stats = ContactStats()
            return f

        pn = pr["node"]
        pf = pr["face"]
        gap, xi, et = self._gap_and_params(pn, pf)
        # penetration beyond the shell thickness, measured from the nearest
        # side of the segment.  A node that has crossed the mid-plane keeps
        # its penetration sign and is pushed back the way it came; using the
        # signed gap here would accelerate it through the segment instead.
        pen = pr["tc"] - np.abs(gap)
        if self.ignore_initial:
            pen = pen - pr["off"]
        act = pen > 0.0
        if not act.any():
            self.stats = ContactStats(pairs=0)
            return f

        idx = np.nonzero(act)[0]
        pn = pn[idx]
        pf = pf[idx]
        pen = pen[idx]
        xi = xi[idx]
        et = et[idx]
        k = pr["k"][idx]
        # The side of the segment a node belongs to is fixed by the reference
        # configuration of the pair.  Using the instantaneous sign of the gap
        # makes a node sitting on the mid-plane flip its force direction every
        # step (a high-frequency penalty oscillation).  The reference side
        # instead always pushes the node back to where it came from.
        side = pr["side"][idx]

        fq = self.faces[pf]
        p = st.x[fq]
        n = np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 1])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
        n = side[:, None] * n                  # points away from the segment

        fmag = k * pen
        if self.vdc > 0.0:
            # normal closing speed, damped only when approaching.  The
            # damping coefficient uses the *local* pair mass (slave node and
            # master segment) rather than the global minimum, which is the
            # consistent LS-DYNA VC scaling  c = 2 * VC * sqrt(k m).
            vn = np.einsum("ij,ij->i", st.v[pn] - np.mean(st.v[fq], axis=1), n)
            m_pair = np.minimum(st.mass[pn], np.mean(st.mass[fq], axis=1))
            cff = 2.0 * self.vdc * np.sqrt(k * m_pair)
            fmag += cff * np.maximum(-vn, 0.0)
        fvec = fmag[:, None] * n

        # distribute -f on the segment nodes with bilinear weights
        w0 = 0.25 * (1.0 - xi) * (1.0 - et)
        w1 = 0.25 * (1.0 + xi) * (1.0 - et)
        w2 = 0.25 * (1.0 + xi) * (1.0 + et)
        w3 = 0.25 * (1.0 - xi) * (1.0 + et)
        wsum = w0 + w1 + w2 + w3
        w = np.stack([w0, w1, w2, w3], axis=1) / np.maximum(wsum, 1e-30)[:, None]

        np.add.at(f, pn, fvec)
        for kk in range(4):
            for c in range(3):
                np.add.at(f[:, c], fq[:, kk], -fvec[:, c] * w[:, kk])

        self.stats = ContactStats(
            fmax=float(np.max(np.linalg.norm(fvec, axis=1))) if fvec.size else 0.0,
            pairs=int(idx.size),
            pen_max=float(np.max(pen)) if pen.size else 0.0,
            nodes=int(np.unique(pn).size))
        return f

    # -------------------------------------------------------------- time step
    def stable_dt(self) -> float:
        if not self.enabled or self._empty:
            return np.inf
        k = max(self._kmax, 1e-12)
        m = float(np.min(self.st.mass[self.node_thk > 0.0])) if self.node_thk.any() \
            else float(np.min(self.st.mass))
        return 0.9 * np.sqrt(max(m, 1e-15) / k)
