#!/bin/bash
# 在 Windows 上请用 scp；此脚本给 VM 上手工覆盖用。
set -e
DST=/home/laide/Desktop/10_code/LA.QSSI.15.0/vendor/meig/HapticX
cp -n "$DST/HapticX.apk" "$DST/HapticX.apk.0.1.0.bak" || true
cp -f HapticX.apk "$DST/HapticX.apk"
cp -f privapp-permissions_hapticx.xml "$DST/"
cp -f default-permissions-com.meig.hapticx.xml "$DST/"
ls -l "$DST"
