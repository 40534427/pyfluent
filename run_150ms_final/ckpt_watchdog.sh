#!/bin/bash
# Commit the evolving checkpoint/history every 20 min so a sandbox rollback
# can never lose more than one interval of compute.
cd /workspace
while true; do
  sleep 1200
  if grep -q "ALL DONE" /workspace/run_150ms_final/run.log 2>/dev/null; then
    git -c user.name="40534427" -c user.email="40534427@users.noreply.github.com" add run_150ms_final/results 2>/dev/null
    git -c user.name="40534427" -c user.email="40534427@users.noreply.github.com" commit -q -m "chore: final 150ms results" 2>/dev/null
    echo "watchdog: final commit done, exiting"
    break
  fi
  git -c user.name="40534427" -c user.email="40534427@users.noreply.github.com" add run_150ms_final/results/checkpoint.npz run_150ms_final/results/history.csv 2>/dev/null
  git -c user.name="40534427" -c user.email="40534427@users.noreply.github.com" commit -q -m "chore: 150ms progress checkpoint $(date -u +%H:%M)" 2>/dev/null
done
