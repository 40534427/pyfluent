#!/usr/bin/env python3
"""One-click PyInstaller build script for T5J make_kfile.exe.

Run it from the project root (the folder containing this file):

    py -3 build_exe.py

If py launcher is not on PATH:

    python build_exe.py        # or with full path
    C:\\Users\\40534\\AppData\\Local\\Programs\\Python\\Python314\\python.exe build_exe.py

Prerequisites:
    - Python 3.10+ (real install, NOT Microsoft Store stub)
    - pip install pyinstaller  (script does this automatically if missing)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys


def find_python() -> str:
    """Best-effort locate a real python executable.

    This runs AFTER __main__ was invoked by some python, so sys.executable
    is ALREADY a real python (otherwise we'd never get here).  We just print
    it for visibility.
    """
    return sys.executable


def run(cmd: list[str], **kw) -> int:
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, **kw)
    return r.returncode


def main() -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(root, "src")
    tpl = os.path.join(src_dir, "paramk", "_template.pkb.gz")
    gen = os.path.join(src_dir, "paramk", "generator.py")

    py = find_python()
    print("=" * 60)
    print(f"  T5J make_kfile.exe  Build")
    print(f"  python = {py}")
    print("=" * 60)

    # --- sanity checks ----------------------------------------------------
    if not os.path.exists(gen):
        print(f"[ERROR] generator.py not found: {gen}")
        return 1
    if not os.path.exists(tpl):
        print(f"[ERROR] template not found: {tpl}")
        return 1

    # --- ensure pyinstaller ----------------------------------------------
    print("\n[1/3] Checking pyinstaller ...")
    try:
        import PyInstaller  # noqa: F401
        print("  Already installed.")
    except ImportError:
        print("  Installing via pip ...")
        rc = run([py, "-m", "pip", "install", "--upgrade", "pip"])
        if rc:
            print("[ERROR] pip failed (network?)")
            return 1
        rc = run([py, "-m", "pip", "install", "pyinstaller"])
        if rc:
            print("[ERROR] pyinstaller install failed")
            return 1

    # --- build -----------------------------------------------------------
    print(f"\n[2/3] Building make_kfile.exe  (cwd={src_dir}) ...")
    work_dir = os.path.join(src_dir, "build")
    spec_dir = os.path.join(src_dir, "build")
    dist_dir = os.path.join(root)
    # PyInstaller --add-data separator: ';' on Windows, ':' on Linux.
    # CRITICAL: must use an ABSOLUTE source path -- PyInstaller resolves
    # relative paths against the work/spec dir, not cwd.
    sep = ";" if sys.platform.startswith("win") else ":"
    tpl_abs = os.path.abspath(tpl)
    add_data = f"{tpl_abs}{sep}paramk"

    cmd = [
        py, "-m", "PyInstaller",
        "--onefile",
        "--name", "make_kfile",
        "--add-data", add_data,
        "--distpath", dist_dir,
        "--workpath", work_dir,
        "--specpath", spec_dir,
        "--noconfirm",
        "--clean",
        gen,
    ]
    rc = run(cmd, cwd=src_dir)
    if rc:
        print("[ERROR] PyInstaller failed. See output above.")
        return 1

    # --- clean up ---------------------------------------------------------
    print("\n[3/3] Cleaning ...")
    try:
        if os.path.isdir(work_dir):
            shutil.rmtree(work_dir)
        spec_file = os.path.join(src_dir, "make_kfile.spec")
        if os.path.isfile(spec_file):
            os.remove(spec_file)
    except OSError as e:
        print(f"  (clean skipped: {e})")

    exe_name = "make_kfile.exe" if sys.platform.startswith("win") else "make_kfile"
    exe_path = os.path.join(root, exe_name)
    if not os.path.isfile(exe_path):
        print(f"\n[ERROR] {exe_name} was NOT produced!")
        print("  Check the PyInstaller output above for errors.")
        return 1

    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print("\n" + "=" * 60)
    print("  DONE !")
    print(f"  {exe_name}  →  {exe_path}")
    print(f"  Size: {size_mb:.1f} MB")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
