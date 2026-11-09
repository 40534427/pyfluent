#!/bin/bash
# Watch solver; when it exits, run finalize.
echo "[$(date '+%F %T')] watcher start"
while ps aux | grep -q "[r]un_parachute"; do sleep 60; done
echo "[$(date '+%F %T')] solver exited, finalizing"
sleep 10
bash /workspace/run_300ms/finalize300.sh
