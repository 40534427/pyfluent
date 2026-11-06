"""LS-DYNA keyword reader.

Only the cards used by the parachute ALE model are interpreted, but the
tokenizer is generic: any card is stored as :class:`Card` and can be
inspected.  Numeric cards use the LS-DYNA fixed field widths:

* general cards    : 10 characters per field
* node / element   : 8 characters per id field (nodes use E16 for x/y/z)
* curve abscissa   : 20 characters
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


# ----------------------------------------------------------------------------
# low level tokenizer
# ----------------------------------------------------------------------------
@dataclass
class Card:
    name: str
    options: List[str]
    lines: List[str]          # data lines only (comments removed)

    @property
    def key(self) -> str:
        return self.name.upper()


def parse_keyword_file(path: str) -> List[Card]:
    """Split a keyword file into cards.  ``$`` comment lines are dropped."""
    cards: List[Card] = []
    cur: Optional[Card] = None
    with open(path, "r", errors="ignore") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line:
                continue
            if line[0] == "$":
                continue
            if line[0] == "*":
                parts = line.split()
                name = parts[0][1:]
                cur = Card(name=name, options=parts[1:], lines=[])
                cards.append(cur)
                continue
            if cur is not None:
                cur.lines.append(line)
    return cards


def _slice(line: str, width: int, count: int = 0) -> List[Optional[str]]:
    s = line.rstrip()
    n = len(s) // width + (1 if len(s) % width else 0)
    if count:
        n = min(n, count)
    out = []
    for k in range(n):
        f = s[k * width:(k + 1) * width].strip()
        out.append(f if f else None)
    return out


def fields10(line: str, count: int = 8) -> List[Optional[str]]:
    return _slice(line, 10, count)


def fields8(line: str, count: int = 10) -> List[Optional[str]]:
    return _slice(line, 8, count)


def fnum(tok: Optional[str], default: float = 0.0) -> float:
    if tok is None:
        return default
    try:
        return float(tok)
    except ValueError:
        return default


def inum(tok: Optional[str], default: int = 0) -> int:
    if tok is None:
        return default
    try:
        return int(float(tok))
    except ValueError:
        return default


def _numeric_lines(card: Card) -> List[str]:
    """Drop title lines (first token not numeric) from a numeric card."""
    out = []
    for ln in card.lines:
        s = ln.strip()
        if not s:
            continue
        c = s[0]
        if c.isdigit() or c in "+-.":
            out.append(ln)
    return out


def _first_card(cards: List[Card], key: str) -> Optional[Card]:
    for c in cards:
        if c.key == key:
            return c
    return None


def _all_cards(cards: List[Card], key: str) -> List[Card]:
    return [c for c in cards if c.key == key]


# ----------------------------------------------------------------------------
# mesh blocks
# ----------------------------------------------------------------------------
def read_nodes(card: Card) -> np.ndarray:
    """Return (nid, x, y, z) as float64."""
    rows = [ln for ln in _numeric_lines(card)]
    if not rows:
        return np.zeros((0, 4))
    # fixed width 8 / 16 / 16 / 16
    out = np.empty((len(rows), 4), dtype=np.float64)
    for i, ln in enumerate(rows):
        out[i, 0] = float(ln[0:8])
        out[i, 1] = float(ln[8:24])
        out[i, 2] = float(ln[24:40])
        out[i, 3] = float(ln[40:56])
    return out


def read_shells(card: Card) -> Tuple[np.ndarray, np.ndarray]:
    eids, pids, conn = [], [], []
    for ln in _numeric_lines(card):
        f = fields8(ln, 10)
        eids.append(inum(f[0]))
        pids.append(inum(f[1]))
        c = [inum(x) for x in f[2:6]]
        if c[3] == 0:                       # triangle
            c[3] = c[2]
        conn.append(c)
    return (np.asarray(eids, int), np.asarray(pids, int),
            np.asarray(conn, int).reshape(-1, 4))


def read_beams(card: Card) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Beam cards come in 2-node and 3-node flavours."""
    eids, pids, conn, third = [], [], [], []
    for ln in _numeric_lines(card):
        f = fields8(ln, 10)
        eids.append(inum(f[0]))
        pids.append(inum(f[1]))
        n1, n2, n3 = inum(f[2]), inum(f[3]), inum(f[4])
        conn.append([n1, n2])
        third.append(n3)
    return (np.asarray(eids, int), np.asarray(pids, int),
            np.asarray(conn, int).reshape(-1, 2), np.asarray(third, int))


def read_solids(card: Card) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Hex solids written in the 'ten nodes' two-line format."""
    eids, pids, conn = [], [], []
    lines = _numeric_lines(card)
    i = 0
    while i < len(lines):
        f = fields8(lines[i], 10)
        # an element header has exactly two integer fields
        if len([x for x in f if x is not None]) == 2 and i + 1 < len(lines):
            eids.append(inum(f[0]))
            pids.append(inum(f[1]))
            nf = fields8(lines[i + 1], 10)
            c = [inum(x, -1) for x in nf[:8]]
            c = [n if n > 0 else c[0] for n in c]      # collapse unused slots
            conn.append(c)
            i += 2
        else:
            i += 1
    return (np.asarray(eids, int), np.asarray(pids, int),
            np.asarray(conn, int).reshape(-1, 8))


def read_set_ids(card: Card) -> np.ndarray:
    """SET_NODE_LIST / SET_PART_LIST item ids (skips the sid card)."""
    lines = _numeric_lines(card)
    vals: List[int] = []
    for ln in lines[1:]:
        for tok in ln.split():
            if tok.isdigit() and int(tok) > 0:
                vals.append(int(tok))
    return np.asarray(vals, int)


def read_segments(card: Card) -> np.ndarray:
    """SET_SEGMENT -> (n,4) node quads (skips the sid card)."""
    lines = _numeric_lines(card)
    rows = []
    for ln in lines[1:]:
        f = fields10(ln, 8)
        n = [inum(x) for x in f[:4]]
        if min(n) <= 0:
            continue
        rows.append(n)
    return np.asarray(rows, int).reshape(-1, 4)


# ----------------------------------------------------------------------------
# model
# ----------------------------------------------------------------------------
@dataclass
class Model:
    title: str = ""
    units: str = ""
    curves: Dict[int, Tuple[np.ndarray, np.ndarray]] = field(default_factory=dict)
    parts: Dict[int, dict] = field(default_factory=dict)
    sections: Dict[int, dict] = field(default_factory=dict)
    materials: Dict[int, dict] = field(default_factory=dict)
    eos: Dict[int, dict] = field(default_factory=dict)
    hourglass: Dict[int, dict] = field(default_factory=dict)
    controls: Dict[str, dict] = field(default_factory=dict)
    coupling: dict = field(default_factory=dict)
    bc: dict = field(default_factory=dict)
    sets: Dict[int, dict] = field(default_factory=dict)
    database: Dict[str, dict] = field(default_factory=dict)
    ale: dict = field(default_factory=dict)
    contact: List[dict] = field(default_factory=list)
    mesh: dict = field(default_factory=dict)

    # convenience -----------------------------------------------------------
    def part_by_name(self, name: str) -> int:
        for pid, p in self.parts.items():
            if p.get("title") == name:
                return pid
        raise KeyError(name)

    def curve(self, lcid: int) -> Tuple[np.ndarray, np.ndarray]:
        if lcid not in self.curves:
            raise KeyError(f"curve {lcid} not found")
        return self.curves[lcid]


def _parse_nodes_card(card: Card) -> np.ndarray:
    return read_nodes(card)


def load_model(path: str, mesh: bool = True) -> Model:
    cards = parse_keyword_file(path)
    m = Model()

    # title
    t = _first_card(cards, "TITLE")
    if t and t.lines:
        m.title = t.lines[-1].strip()
    if m.title:
        tok = m.title.split()
        if tok and tok[-1] == "kg-m-s":
            m.units = "kg-m-s"

    # curves ---------------------------------------------------------------
    for c in _all_cards(cards, "DEFINE_CURVE"):
        if not c.lines:
            continue
        head = _numeric_lines(c)
        if not head:
            continue
        f = fields10(head[0], 8)
        lcid = inum(f[0])
        sfa, sfo = fnum(f[2], 1.0), fnum(f[3], 1.0)
        offa, offo = fnum(f[4]), fnum(f[5])
        a, o = [], []
        for ln in head[1:]:
            fa = _slice(ln, 20, 2)
            a.append(fnum(fa[0]))
            o.append(fnum(fa[1]))
        arr_a = np.asarray(a) * sfa + offa
        arr_o = np.asarray(o) * sfo + offo
        m.curves[lcid] = (arr_a, arr_o)

    # parts ----------------------------------------------------------------
    for c in _all_cards(cards, "PART"):
        lines = c.lines
        title = ""
        nums = []
        for ln in lines:
            s = ln.strip()
            if not s:
                continue
            if not (s[0].isdigit() or s[0] in "+-."):
                title = s
                continue
            nums.append(ln)
        if not nums:
            continue
        f = fields10(nums[0], 8)
        pid = inum(f[0])
        m.parts[pid] = {
            "title": title,
            "pid": pid,
            "secid": inum(f[1]),
            "mid": inum(f[2]),
            "eosid": inum(f[3]),
            "hgid": inum(f[4]),
        }

    # sections -------------------------------------------------------------
    for c in _all_cards(cards, "SECTION_SHELL"):
        n = _numeric_lines(c)
        if not n:
            continue
        f = fields10(n[0], 8)
        sid = inum(f[0])
        d = {"type": "SHELL", "secid": sid, "elform": inum(f[1], 2),
             "shrf": fnum(f[2], 1.0), "nip": inum(f[3], 2)}
        if len(n) > 1:
            g = fields10(n[1], 8)
            for i, key in enumerate(("t1", "t2", "t3", "t4")):
                d[key] = fnum(g[i], 0.0)
        m.sections[sid] = d

    for c in _all_cards(cards, "SECTION_BEAM"):
        n = _numeric_lines(c)
        if not n:
            continue
        f = fields10(n[0], 8)
        sid = inum(f[0])
        d = {"type": "BEAM", "secid": sid, "elform": inum(f[1], 1),
             "shrf": fnum(f[2], 1.0), "cst": inum(f[4], 0)}
        if len(n) > 1:
            g = fields10(n[1], 8)
            for i, key in enumerate(("ts1", "ts2", "tt1", "tt2")):
                d[key] = fnum(g[i], 0.0)
        m.sections[sid] = d

    for c in _all_cards(cards, "SECTION_SOLID"):
        n = _numeric_lines(c)
        if not n:
            continue
        f = fields10(n[0], 8)
        m.sections[inum(f[0])] = {"type": "SOLID", "secid": inum(f[0]),
                                  "elform": inum(f[1], 1), "aet": inum(f[2], 0)}

    # materials ------------------------------------------------------------
    for c in _all_cards(cards, "MAT_FABRIC"):
        n = _numeric_lines(c)
        if not n:
            continue
        f = fields10(n[0], 8)
        d = {"type": "FABRIC", "mid": inum(f[0]), "ro": fnum(f[1]),
             "ea": fnum(f[2]), "eb": fnum(f[3]), "prba": fnum(f[5]),
             "prab": fnum(f[6])}
        g = fields10(n[1], 8) if len(n) > 1 else [None] * 8
        d.update({"gab": fnum(g[0]), "cse": fnum(g[3]), "el": fnum(g[4]),
                  "prl": fnum(g[5]), "lratio": fnum(g[6]), "damp": fnum(g[7])})
        g = fields10(n[2], 8) if len(n) > 2 else [None] * 8
        d.update({"aopt": fnum(g[0]), "tsrfac": fnum(g[7])})
        g = fields10(n[3], 8) if len(n) > 3 else [None] * 8
        d.update({"a1": fnum(g[3]), "a2": fnum(g[4]), "a3": fnum(g[5])})
        m.materials[d["mid"]] = d

    for c in _all_cards(cards, "MAT_PLASTIC_KINEMATIC"):
        n = _numeric_lines(c)
        if not n:
            continue
        f = fields10(n[0], 8)
        m.materials[inum(f[0])] = {
            "type": "PLASTIC_KINEMATIC", "mid": inum(f[0]), "ro": fnum(f[1]),
            "e": fnum(f[2]), "pr": fnum(f[3]), "sigy": fnum(f[4]),
            "etan": fnum(f[5]), "beta": fnum(f[6]),
        }

    for c in _all_cards(cards, "MAT_NULL"):
        n = _numeric_lines(c)
        if not n:
            continue
        f = fields10(n[0], 8)
        m.materials[inum(f[0])] = {
            "type": "NULL", "mid": inum(f[0]), "ro": fnum(f[1]),
            "pc": fnum(f[2]), "mu": fnum(f[3]),
        }

    # eos ------------------------------------------------------------------
    for c in _all_cards(cards, "EOS_LINEAR_POLYNOMIAL"):
        n = _numeric_lines(c)
        if not n:
            continue
        f = fields10(n[0], 8)
        d = {"type": "LINEAR_POLYNOMIAL", "eosid": inum(f[0])}
        for i, key in enumerate(("c0", "c1", "c2", "c3", "c4", "c5", "c6")):
            d[key] = fnum(f[1 + i])
        if len(n) > 1:
            g = fields10(n[1], 8)
            d["e0"] = fnum(g[0])
            d["v0"] = fnum(g[1], 1.0)
        m.eos[d["eosid"]] = d

    # hourglass ------------------------------------------------------------
    for c in _all_cards(cards, "HOURGLASS"):
        n = _numeric_lines(c)
        if not n:
            continue
        f = fields10(n[0], 8)
        m.hourglass[inum(f[0])] = {
            "hgid": inum(f[0]), "ihq": inum(f[1], 1), "qm": fnum(f[2], 0.1)}

    # control cards --------------------------------------------------------
    control_map = {
        "CONTROL_ALE": ("dct", "nadv", "meth", "afac", "bfac", "cfac", "dfac", "efac"),
        "CONTROL_TERMINATION": ("endtim", "endcyc", "dtmin", "endeng", "endmas"),
        "CONTROL_TIMESTEP": ("dtinit", "tssfac", "isdo", "tslimt", "dt2ms"),
        "CONTROL_SHELL": ("wrpang", "esort", "irnxx", "istupd", "theory", "bwc"),
        "CONTROL_BULK_VISCOSITY": ("q1", "q2", "type", "btype"),
        "CONTROL_ENERGY": ("hgen", "rwen", "slnten", "rylen", "irgen"),
        "CONTROL_HOURGLASS": ("ihq", "qh"),
    }
    for key, names in control_map.items():
        card = _first_card(cards, key)
        if card is None:
            continue
        n = _numeric_lines(card)
        if not n:
            continue
        f = fields10(n[0], 8)
        m.controls[key] = {nm: fnum(f[i]) for i, nm in enumerate(names)
                           if i < len(f)}
    # extra ALE cards
    card = _first_card(cards, "CONTROL_ALE")
    if card is not None:
        n = _numeric_lines(card)
        if len(n) > 1:
            g = fields10(n[1], 8)
            m.controls["CONTROL_ALE"].update(
                {"start": fnum(g[0]), "end": fnum(g[1]), "aafac": fnum(g[2]),
                 "vfact": fnum(g[3]), "prit": fnum(g[4]), "ebc": fnum(g[5]),
                 "pref": fnum(g[6], 101300.0)})
        if len(n) > 2:
            g = fields10(n[2], 8)
            m.controls["CONTROL_ALE"].update(
                {"ncpl": inum(g[0], 1), "nbkt": inum(g[1], 50),
                 "imascl": inum(g[2], 0)})
    m.controls.setdefault("CONTROL_ALE", {})["pref"] = \
        m.controls["CONTROL_ALE"].get("pref", 101300.0)

    # coupling -------------------------------------------------------------
    card = _first_card(cards, "CONSTRAINED_LAGRANGE_IN_SOLID_TITLE")
    if card is None:
        card = _first_card(cards, "CONSTRAINED_LAGRANGE_IN_SOLID")
    if card is not None:
        n = _numeric_lines(card)
        d = {}
        if n:
            f = fields10(n[0], 8)
            d["coupid"] = inum(f[0])
            rest = n[0][10:].strip()
            d["title"] = rest
        if len(n) > 1:
            f = fields10(n[1], 8)
            d.update({"slave": inum(f[0]), "master": inum(f[1]),
                      "sstyp": inum(f[2]), "mstyp": inum(f[3]),
                      "nquad": inum(f[4]), "ctype": inum(f[5]),
                      "direc": inum(f[6]), "mcoup": inum(f[7])})
        if len(n) > 2:
            f = fields10(n[2], 8)
            d.update({"start": fnum(f[0]), "end": fnum(f[1]), "pfac": fnum(f[2], 0.1),
                      "fric": fnum(f[3]), "frcmin": fnum(f[4], 0.3),
                      "norm": inum(f[5]), "normtyp": inum(f[6]), "damp": fnum(f[7])})
        if len(n) > 3:
            f = fields10(n[3], 8)
            d.update({"cq": fnum(f[0]), "hmin": fnum(f[1]), "hmax": fnum(f[2]),
                      "ileak": inum(f[3]), "pleak": fnum(f[4], 0.1)})
        if len(n) > 4:
            f = fields10(n[4], 8)
            d.update({"iboxid": inum(f[0]), "ipenchk": inum(f[1]),
                      "intforc": inum(f[2]), "ialesof": inum(f[3]),
                      "lagmul": fnum(f[4], 1.0), "pfacmm": fnum(f[5]),
                      "thkf": fnum(f[6], 1.0)})
        if len(n) > 5:
            f = fields10(n[5], 8)
            d.update({"a1": fnum(f[0]), "b1": fnum(f[1]), "a2": fnum(f[2]),
                      "b2": fnum(f[3]), "a3": fnum(f[4]), "b3": fnum(f[5])})
        m.coupling = d
    m.coupling.setdefault("pfac", 0.1)

    # boundary -------------------------------------------------------------
    nr = []
    for c in _all_cards(cards, "BOUNDARY_NON_REFLECTING"):
        n = _numeric_lines(c)
        if n:
            f = fields10(n[0], 8)
            nr.append(inum(f[0]))
    pm = []
    for c in _all_cards(cards, "BOUNDARY_PRESCRIBED_MOTION_SET"):
        n = _numeric_lines(c)
        if n:
            f = fields10(n[0], 8)
            pm.append({"nsid": inum(f[0]), "dof": inum(f[1]), "vad": inum(f[2]),
                       "lcid": inum(f[3]), "sf": fnum(f[4], 1.0),
                       "vid": inum(f[5]), "death": fnum(f[6], 1.0e28),
                       "birth": fnum(f[7], 0.0)})
    spc = []
    for c in _all_cards(cards, "BOUNDARY_SPC_SET"):
        n = _numeric_lines(c)
        if n:
            f = fields10(n[0], 8)
            spc.append({"nsid": inum(f[0]), "cid": inum(f[1]),
                        "dofx": inum(f[2]), "dofy": inum(f[3]),
                        "dofz": inum(f[4]), "dofrx": inum(f[5]),
                        "dofry": inum(f[6]), "dofrz": inum(f[7])})
    m.bc = {"non_reflecting": nr, "prescribed_motion": pm, "spc": spc}

    # sets -----------------------------------------------------------------
    for c in _all_cards(cards, "SET_PART_LIST"):
        n = _numeric_lines(c)
        if not n:
            continue
        sid = inum(fields10(n[0], 8)[0])
        m.sets[sid] = {"type": "part", "items": read_set_ids(c)}
    for c in _all_cards(cards, "SET_NODE_LIST"):
        n = _numeric_lines(c)
        if not n:
            continue
        sid = inum(fields10(n[0], 8)[0])
        m.sets[sid] = {"type": "node", "items": read_set_ids(c)}
    for c in _all_cards(cards, "SET_SEGMENT"):
        n = _numeric_lines(c)
        if not n:
            continue
        sid = inum(fields10(n[0], 8)[0])
        m.sets[sid] = {"type": "segment", "segments": read_segments(c)}
    # SET_PART_LIST id 11 and 2 must not collide with node sets -> key by type
    m.sets_by_type = {}
    for c in _all_cards(cards, "SET_PART_LIST"):
        n = _numeric_lines(c)
        if not n:
            continue
        sid = inum(fields10(n[0], 8)[0])
        m.sets_by_type[("part", sid)] = read_set_ids(c)
    for c in _all_cards(cards, "SET_NODE_LIST"):
        n = _numeric_lines(c)
        if not n:
            continue
        sid = inum(fields10(n[0], 8)[0])
        m.sets_by_type[("node", sid)] = read_set_ids(c)
    for c in _all_cards(cards, "SET_SEGMENT"):
        n = _numeric_lines(c)
        if not n:
            continue
        sid = inum(fields10(n[0], 8)[0])
        m.sets_by_type[("segment", sid)] = read_segments(c)

    # database -------------------------------------------------------------
    for key in ("DATABASE_BINARY_D3PLOT", "DATABASE_GLSTAT", "DATABASE_MATSUM",
                "DATABASE_NODOUT", "DATABASE_DISBOUT"):
        c = _first_card(cards, key)
        if c is None:
            continue
        n = _numeric_lines(c)
        if n:
            m.database[key] = {"dt": fnum(fields10(n[0], 8)[0])}
        if key == "DATABASE_BINARY_D3PLOT" and n:
            m.database[key] = {"dt": fnum(fields10(n[0], 10)[0])}

    # ALE multi material group --------------------------------------------
    for c in _all_cards(cards, "ALE_MULTI-MATERIAL_GROUP"):
        n = _numeric_lines(c)
        if n:
            f = fields10(n[0], 8)
            m.ale = {"sid": inum(f[0]), "idtype": inum(f[1], 1)}

    # contact --------------------------------------------------------------
    for c in _all_cards(cards, "CONTACT_AUTOMATIC_SINGLE_SURFACE_ID"):
        n = _numeric_lines(c)
        if not n:
            continue
        d = {}
        f = fields10(n[0], 8)
        d.update({"cid": inum(f[0]), "title": n[0][10:].strip()})
        if len(n) > 1:
            f = fields10(n[1], 8)
            d.update({"ssid": inum(f[0]), "msid": inum(f[1]),
                      "sstyp": inum(f[2]), "mstyp": inum(f[3]),
                      "sboxid": inum(f[4]), "mboxid": inum(f[5]),
                      "spr": inum(f[6]), "mpr": inum(f[7])})
        if len(n) > 2:
            f = fields10(n[2], 8)
            d.update({"fs": fnum(f[0]), "fd": fnum(f[1]), "dc": fnum(f[2]),
                      "vc": fnum(f[3]), "vdc": fnum(f[4]),
                      "penchk": inum(f[5]), "bt": inum(f[6], 0),
                      "dt": fnum(f[7], 1e20)})
        if len(n) > 3:
            f = fields10(n[3], 8)
            d.update({"sfs": fnum(f[0], 1.0), "sfm": fnum(f[1], 1.0),
                      "sst": fnum(f[2], 0.0), "mst": fnum(f[3], 0.0),
                      "sfst": fnum(f[4], 1.0), "sfmt": fnum(f[5], 1.0),
                      "fsf": fnum(f[6], 1.0), "vsf": fnum(f[7], 1.0)})
        d.setdefault("sstyp", 0)
        d.setdefault("ssid", 0)
        d.setdefault("sfs", 1.0)
        d.setdefault("sfm", 1.0)
        d.setdefault("vdc", 0.0)
        d.setdefault("penchk", 0)
        m.contact.append(d)

    # mesh -----------------------------------------------------------------
    if mesh:
        nc = _first_card(cards, "NODE")
        m.mesh["nodes"] = read_nodes(nc) if nc else np.zeros((0, 4))
        sc = _first_card(cards, "ELEMENT_SHELL")
        if sc:
            m.mesh["shell_eid"], m.mesh["shell_pid"], m.mesh["shell_conn"] = read_shells(sc)
        bc_ = _first_card(cards, "ELEMENT_BEAM")
        if bc_:
            (m.mesh["beam_eid"], m.mesh["beam_pid"], m.mesh["beam_conn"],
             m.mesh["beam_n3"]) = read_beams(bc_)
        so = _first_card(cards, "ELEMENT_SOLID")
        if so:
            m.mesh["solid_eid"], m.mesh["solid_pid"], m.mesh["solid_conn"] = read_solids(so)
    return m


def timeseries(curve: Tuple[np.ndarray, np.ndarray], t: float) -> float:
    a, o = curve
    if a.size == 0:
        return 0.0
    return float(np.interp(t, a, o))
