#!/bin/bash
# 只看脚本怎么解析第 4 参，不启动编译
f=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3/SNM970_A15_build.sh
echo "===== head / 参数 ====="
grep -n -E 'inc|full|BUILD_MODE|compile_mode|\$4|qssi_only' "$f" | head -60
echo "===== build_qssi 是否无条件 ====="
grep -n -A8 'build_qssi\|main\|case' "$f" | head -80
