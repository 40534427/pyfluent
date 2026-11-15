#!/bin/sh
# 交付包 Linux（麒麟 V10 / 其他 x86_64）自检脚本
# 用法：在交付包根目录执行  ./verify_linux.sh
# 退出码：0 全部通过，1 存在失败项
cd "$(dirname "$0")"
PKG="$(pwd)"
EXE="bin/linux-x86_64/run_parachute"
PY="bin/linux-x86_64/runtime/bin/python3"
WORK="$PKG/verify_out"
FAIL=0

say() { printf '%s\n' "$*"; }
ok()  { printf '[ OK ] %s\n' "$*"; }
bad() { printf '[FAIL] %s\n' "$*"; FAIL=1; }

say "=========================================================="
say " T5J delivery package self-check (Linux x86_64)"
say "=========================================================="

# 1. system ---------------------------------------------------------------
say ""
say "[1/6] System"
say "  kernel : $(uname -r)"
say "  arch   : $(uname -m)"
if [ "$(uname -m)" != "x86_64" ]; then
    bad "this package is built for x86_64"
else
    ok "x86_64"
fi
if command -v ldd >/dev/null 2>&1; then
    say "  glibc  : $(ldd --version 2>&1 | head -1)"
fi
if [ -r /etc/os-release ]; then
    say "  distro : $(. /etc/os-release; printf '%s %s' "$NAME" "$VERSION_ID")"
fi
if [ -r /etc/kylin-release ]; then
    say "  kylin  : $(cat /etc/kylin-release)"
fi

# 2. files ----------------------------------------------------------------
say ""
say "[2/6] Package files"
for f in "$EXE" "$PY" "src/run_parachute.py" "src/aleparachute/solver.py" \
         "kinput/Parachute_0903.k" "results/history.csv"; do
    if [ -e "$f" ]; then ok "$f"; else bad "missing $f"; fi
done

# 3. runtime --------------------------------------------------------------
say ""
say "[3/6] Bundled Python runtime"
if [ -x "$PY" ]; then
    say "  version: $("$PY" -V 2>&1)"
    if "$PY" -c "import numpy, scipy, matplotlib, psutil; matplotlib.use('Agg'); import matplotlib.pyplot as plt" 2>/dev/null; then
        ok "numpy / scipy / matplotlib / psutil import"
    else
        bad "scientific stack import failed"
    fi
    if "$PY" -c "import sys; sys.path.insert(0,'src'); import aleparachute" 2>/dev/null; then
        ok "solver package import"
    else
        bad "solver package import failed"
    fi
else
    bad "bundled python missing"
fi

# 4. launcher -------------------------------------------------------------
say ""
say "[4/6] Launcher"
if [ -x "$EXE" ]; then
    if "$EXE" --help >/dev/null 2>&1; then
        ok "run_parachute --help"
    else
        bad "run_parachute --help failed"
    fi
    say "  $(file "$EXE" 2>/dev/null | sed 's/^[^:]*: //')"
else
    bad "$EXE not executable"
fi

# 5. report regeneration --------------------------------------------------
say ""
say "[5/6] Report regeneration"
rm -rf "$WORK"; mkdir -p "$WORK"
cp -a results/. "$WORK"/ 2>/dev/null
if "$EXE" --report-only --outdir "$WORK" >"$WORK/report.log" 2>&1; then
    if [ -s "$WORK/calculation_report.html" ]; then
        ok "calculation_report.html rebuilt"
    else
        bad "calculation_report.html missing"
    fi
else
    bad "report-only failed (see $WORK/report.log)"
fi
NFIG=$(ls "$WORK/figures" 2>/dev/null | wc -l)
if [ "$NFIG" -ge 5 ]; then ok "$NFIG figures"; else bad "only $NFIG figures"; fi

# 6. smoke solve + checkpoint + restart -----------------------------------
say ""
say "[6/6] Smoke solve (8x8x8 grid, 4 steps) and resume"
SMK="$WORK/solve"
mkdir -p "$SMK"
COMMON="--k kinput/Parachute_0903.k --nx 8 --ny 8 --nz 8 --no-contact \
--constant-vel 220 --endtime 0.01 --vtk-every 0 --checkpoint-every 1e-6 --quiet"
if "$EXE" $COMMON --max-steps 4 --outdir "$SMK" >"$SMK/run1.log" 2>&1; then
    ok "4-step solve"
else
    bad "4-step solve failed (see $SMK/run1.log)"
fi
if [ -s "$SMK/history.csv" ]; then ok "history.csv written"; else bad "history.csv missing"; fi
if [ -s "$SMK/line_force.csv" ]; then ok "line_force.csv written"; else bad "line_force.csv missing"; fi
if [ -s "$SMK/checkpoint.npz" ]; then ok "checkpoint.npz written"; else bad "checkpoint.npz missing"; fi
if [ -f "$SMK/final_structure.vtk" ]; then ok "VTK written"; else bad "VTK missing"; fi

if [ -s "$SMK/checkpoint.npz" ]; then
    if "$EXE" $COMMON --max-steps 6 --outdir "$SMK" \
            --restart "$SMK/checkpoint.npz" >"$SMK/run2.log" 2>&1; then
        if grep -q '\[restart\] resumed' "$SMK/run2.log"; then
            ok "restart from checkpoint"
        else
            bad "restart message missing (see $SMK/run2.log)"
        fi
        LAST=$(tail -1 "$SMK/history.csv" | cut -d, -f2)
        if [ "${LAST:-0}" -ge 6 ]; then
            ok "resumed to step $LAST"
        else
            bad "resume did not advance (last step ${LAST:-?})"
        fi
    else
        bad "restart run failed (see $SMK/run2.log)"
    fi
fi

say ""
say "----------------------------------------------------------"
if [ "$FAIL" -eq 0 ]; then
    say " RESULT: PASS  (temporary files in verify_out, safe to delete)"
else
    say " RESULT: FAIL  (see messages above)"
fi
say "----------------------------------------------------------"
exit "$FAIL"
