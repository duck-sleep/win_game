#!/bin/bash
set -u
VEN=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3
cd "$VEN" || { echo NO_VEN; exit 1; }

echo "===== tmux ====="
tmux ls 2>/dev/null || echo no_tmux

echo "===== build.log tail ====="
if [ -f build.log ]; then
  ls -l build.log
  echo "----- last 80 -----"
  tail -n 80 build.log
else
  echo NO_build.log
fi

echo "===== build_log ERROR ====="
ls -lt build_log/*ERROR* 2>/dev/null | head -10
ls -lt build_log/*.txt 2>/dev/null | head -15

echo "===== grep fail in build.log ====="
if [ -f build.log ]; then
  grep -n -E 'error:|FAILED|ninja: error|err_exit|Killed|ERROR|FAILED:' build.log | tail -40
fi
