#!/bin/sh
# usage: k11c-upgrade.sh <http://.../update.img | local path> [md5]
# The image must land where recovery can read it: /userdata, /mnt/sdcard, /mnt/udisk
set -e
SRC="$1"
MD5="$2"
[ -n "$SRC" ] || { echo "usage: $0 <url|path> [md5]"; exit 2; }
case "$SRC" in
  http://*|https://*)
    IMG=/userdata/update.img
    rm -f "$IMG" "$IMG.part"
    wget -O "$IMG.part" "$SRC"
    mv "$IMG.part" "$IMG"
    ;;
  /userdata/*|/mnt/sdcard/*|/mnt/udisk/*)
    IMG="$SRC"
    ;;
  *)
    echo "path must be under /userdata, /mnt/sdcard or /mnt/udisk"
    exit 2
    ;;
esac
[ -f "$IMG" ] || { echo "no $IMG"; exit 1; }
if [ -n "$MD5" ]; then
  echo "$MD5  $IMG" | md5sum -c -
fi
sync
echo "upgrade from $IMG, current: $(cat /etc/k11c-release)"
exec /usr/bin/update ota "$IMG"
