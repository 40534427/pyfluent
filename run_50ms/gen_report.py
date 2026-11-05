#!/usr/bin/env python3
"""Generate calculation report post-hoc on existing successful T5E 50ms results."""
import sys
sys.path.insert(0, '/workspace/ale_parachute')
from aleparachute.report import generate_report

outdir = '/workspace/T5E_R05_y1ext04_pleak01_50ms/results'
print(f"generating report from {outdir} ...")
path = generate_report(outdir)
print(f"[report] -> {path}")
