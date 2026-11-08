#!/usr/bin/env python3
"""Build Parachute_0903_rev.k applying review fixes 1-9.

Only card data lines are rewritten; the mesh (53 MB) is copied verbatim.
"""
import io
import os

SRC = "/workspace/run_150ms_vent/Parachute_0903.k"
DST = "/workspace/run_150ms_vent/Parachute_0903_rev.k"

EA_OLD, T_OLD = 4.309e7, 9.0e-4
EA_NEW, T_NEW = 3.877e8, 1.0e-4          # keeps EA*t = 3.88e4 N/m
EB_NEW = 0.05 * EA_NEW                    # hoop modulus (fix 4)
E0_NEW = 101325.0 / (0.4 * 1.18)          # 1 atm at rho=1.18 (fix 6)
LINE_E, LINE_RHO = 2.0e9, 1200.0
LINE_A = 5.0e-5
TS_NEW = LINE_A ** 0.5


def f10(v):
    return "%10.4E" % v


def i10(v):
    return "%10d" % int(v)


with io.open(SRC, "r", errors="replace") as fh:
    lines = fh.read().split("\n")


def setline(no, new, expect):
    old = lines[no - 1]
    assert expect in old, "line %d mismatch: %r" % (no, old)
    lines[no - 1] = new


# --- fix 8: canopy thickness / modulus / density -------------------------
setline(43, f10(T_NEW) * 4 + f10(0.0) + f10(0.0) + f10(0.0) + f10(0.0),
        "9.000E-4")
setline(48, i10(21) + f10(1100.0) + f10(EA_NEW) + f10(EB_NEW) +
        f10(0.0) + f10(0.14) + f10(0.0) + f10(0.0),
        "533.77")

# --- fix 9: suspension-line section and material -------------------------
setline(68, f10(TS_NEW) * 4 + f10(0.0) + f10(0.0), "0.006")
setline(73, i10(22) + f10(LINE_RHO) + f10(LINE_E) + f10(0.35) +
        f10(1.0e9) + f10(0.0) + f10(0.0), "9.7000E+8")

# --- fix 6: EOS initial internal energy for 1 atm ------------------------
setline(96, "%10.4g" % E0_NEW + "%10.4f" % 1.0, "250000.0")

# --- fix 1: 3 ms inflow ramp instead of 40 ms ---------------------------
setline(19, "%18.4f%18.4f" % (0.003, 220.0), "0.040")

# --- fix 7: single-surface contact over canopy + lines ------------------
setline(27, i10(110) + i10(0) + i10(2) + i10(0) + i10(0) + i10(0) +
        i10(0) + i10(0), "3         0         0")

# --- fix 5: stiffer penalty coupling ------------------------------------
setline(915879, "%10.3f%10.1E%10.4f%10.4f%10.4f%10d%10d%10.4f" %
        (0.0, 1.0e10, 0.5, 0.0, 0.3, 0, 0, 1.0), "0.3         0")

# --- fix 2: termination time -------------------------------------------
setline(915957, "%10.4f%10d%10.4f%10.4f%10.4f%10d" %
        (0.15, 0, 0.0, 0.0, 0.0, 0), "0.08")

# --- fix 7: part set used by the contact -------------------------------
assert lines[915870].startswith("*CONSTRAINED_LAGRANGE_IN_SOLID")
lines.insert(915870,
             "*SET_PART_LIST\n"
             "$#     sid       da1       da2       da3       da4      solver\n"
             + i10(110) + "%10.4f" % 0.0 + "%10.4f" % 0.0 + "%10.4f" % 0.0 +
             "%10.4f" % 0.0 + "\n"
             "$#    pid1      pid2      pid3      pid4      pid5      pid6"
             "      pid7      pid8\n"
             + i10(11) + i10(12))

with io.open(DST, "w", errors="replace") as fh:
    fh.write("\n".join(lines))

print("wrote", DST, os.path.getsize(DST) / 1048576.0, "MB")
print("EA*t old %.4g  new %.4g" % (EA_OLD * T_OLD, EA_NEW * T_NEW))
print("EB %.4g  e0 %.1f  ts %.5f" % (EB_NEW, E0_NEW, TS_NEW))
