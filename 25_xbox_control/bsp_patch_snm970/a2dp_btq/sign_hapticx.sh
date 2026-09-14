#!/bin/bash
set -e
JAVA=/home/laide/Desktop/10_code/LA.QSSI.15.0-irix/prebuilts/jdk/jdk21/linux-x86/bin/java
KEY=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3-irix/build/make/target/product/security
JAR=/home/laide/Desktop/10_code/LA.QSSI.15.0-irix/prebuilts/sdk/tools/lib/signapk.jar
LIB=/home/laide/Desktop/10_code/LA.QSSI.15.0-irix/prebuilts/sdk/tools/linux/lib64
export LD_LIBRARY_PATH="$LIB:${LD_LIBRARY_PATH:-}"
IN=${1:-/tmp/hapticx-in.apk}
OUT=${2:-/tmp/hapticx-signed.apk}
"$JAVA" -Djava.library.path="$LIB" -jar "$JAR" "$KEY/platform.x509.pem" "$KEY/platform.pk8" "$IN" "$OUT"
ls -l "$OUT"
echo SIGN_OK
