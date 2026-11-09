#!/bin/bash
# Periodically gzip+commit checkpoint & history so a sandbox reset can't lose them.
cd /workspace || exit 1
while true; do
  sleep 1200
  if ! ps aux | grep -q "[r]un_parachute"; then
    # final backup then exit
    :
  fi
  mkdir -p run_300ms/backup
  [ -f run_300ms/results/checkpoint.npz ] && gzip -kc run_300ms/results/checkpoint.npz > run_300ms/backup/checkpoint.npz.gz 2>/dev/null
  [ -f run_300ms/results/history.csv ] && cp run_300ms/results/history.csv run_300ms/backup/history.csv 2>/dev/null
  [ -f run_300ms/results/line_force.csv ] && cp run_300ms/results/line_force.csv run_300ms/backup/line_force.csv 2>/dev/null
  git add run_300ms/backup/ >/dev/null 2>&1
  git -c user.name="trae-agent" -c user.email="agent@local" commit -qm "ckpt backup $(date '+%H:%M')" >/dev/null 2>&1
  ps aux | grep -q "[r]un_parachute" || exit 0
done
