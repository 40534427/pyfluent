#!/usr/bin/env python3
"""3-hour long-run test supervisor for the 150 ms parachute solve.

Samples every 60 s, records progress, auto-resumes from checkpoint if the
solver disappears, and stops when the 3 h window elapses (or the solve
reaches t = 0.150 s).
"""
import os
import subprocess
import time
import numpy as np

ROOT = "/workspace/run_150ms_vent"
RES = os.path.join(ROOT, "results")
LOG = os.path.join(ROOT, "longrun_test.log")
SOLVER_LOG = os.path.join(ROOT, "run_resume.log")
DURATION = 3 * 3600.0

CMD = [
    "python3", "run_parachute.py",
    "--k", os.path.join(ROOT, "Parachute_0903.k"),
    "--nx", "30", "--ny", "40", "--nz", "30",
    "--domain-radius", "0.5", "--y1-extension", "0.4",
    "--endtime", "0.150", "--tssfac", "0.8",
    "--vtk-every", "0.005", "--checkpoint-every", "0.010",
    "--cfl", "0.5", "--constant-vel", "220",
    "--bend-scale", "1", "--bend-damp", "0",
    "--pleak", "0.1",
    "--struct-damping", "100", "--struct-damping-vmax", "30",
    "--eb-frac", "0.05",
    "--vent-radius", "0.02", "--vent-ring-E-factor", "5",
    "--vent-ring-A-factor", "2",
    "--tension-only-membrane", "--no-contact",
    "--max-steps", "400000", "--generate-report",
    "--restart", os.path.join(RES, "checkpoint.npz"),
    "--outdir", RES,
]


def stamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def solver_pids():
    out = subprocess.run(["pgrep", "-f", "run_parachute.py --k"],
                         capture_output=True, text=True).stdout.split()
    return [p for p in out if int(p) != os.getpid()]


def checkpoint_state():
    try:
        d = np.load(os.path.join(RES, "checkpoint.npz"), allow_pickle=True)
        return float(d["t"]), int(d["step"])
    except Exception:
        return float("nan"), -1


def history_last_t():
    try:
        with open(os.path.join(RES, "history.csv")) as fh:
            last = None
            for line in fh:
                last = line
        return float(last.split(",")[0])
    except Exception:
        return float("nan")


def launch():
    fh = open(SOLVER_LOG, "a")
    fh.write(f"\n=== [{stamp()}] monitor relaunch ===\n")
    fh.flush()
    return subprocess.Popen(CMD, cwd="/workspace/ale_parachute",
                            stdout=fh, stderr=subprocess.STDOUT)


def main():
    t0 = time.time()
    fh = open(LOG, "a")
    fh.write(f"\n===== 3h long-run test start {stamp()} =====\n")
    fh.write("time,alive,ckpt_t,step,hist_t,event\n")
    fh.flush()

    restarts = 0
    missing_since = None
    while True:
        elapsed = time.time() - t0
        if elapsed >= DURATION:
            fh.write(f"{stamp()},, , , ,TEST_WINDOW_ELAPSED\n")
            fh.flush()
            break

        hist_t = history_last_t()
        if hist_t >= 0.1499:
            fh.write(f"{stamp()},, , , ,SOLVE_COMPLETE\n")
            fh.flush()
            break

        pids = solver_pids()
        alive = bool(pids)
        ck, step = checkpoint_state()
        event = ""
        if not alive:
            if missing_since is None:
                missing_since = time.time()
            elif time.time() - missing_since > 20:
                launch()
                restarts += 1
                missing_since = None
                event = f"RESUME_{restarts}"
        else:
            missing_since = None

        fh.write(f"{stamp()},{int(alive)},{ck:.5f},{step},{hist_t:.5f},{event}\n")
        fh.flush()
        time.sleep(60)

    fh.write(f"===== test end {stamp()} restarts={restarts} =====\n")
    fh.close()


if __name__ == "__main__":
    main()
