"""Make single-fix variants of the revised K for bisection."""
import sys, io

REV = "/workspace/run_150ms_vent/Parachute_0903_rev.k"
with io.open(REV, errors="replace") as fh:
    L = fh.read().split("\n")

which = sys.argv[1]

if which == "fabric":           # revert fix 8 only
    L[42] = "%10d%10.1f%10.4E%10.4f%10.4f%10.4f%10.4f%10.4f" % (
        21, 533.774, 4.309e7, 0.0, 0.0, 0.14, 0.0, 0.0)
    L[41] = "%10.4E" % 9.0e-4 * 4 + "%10.4E" % 0.0 * 4
elif which == "line":           # revert fix 9 only
    L[67] = "%10.4f" % 0.006 * 4 + "%10.4f" % 0.0 * 2
    L[72] = "%10d%10.1f%10.4E%10.4f%10.4E%10.4f%10.4f" % (
        22, 462.0, 9.7e8, 0.35, 1.0e9, 0.0, 0.0)
elif which == "eos":            # revert fix 6 only
    L[95] = "%10.1f%10.4f" % (250000.0, 1.0)
out = "/workspace/run_150ms_vent/Parachute_rev_%s.k" % which
with io.open(out, "w", errors="replace") as fh:
    fh.write("\n".join(L))
print("wrote", out)
