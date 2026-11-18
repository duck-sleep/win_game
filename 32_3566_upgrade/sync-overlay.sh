#!/bin/sh
set -e
K=/home/rk/k11c
SRC=$K/k11c-br-staging
DST=$K/k11c-br-overlay
rm -rf "$DST"
cp -a "$SRC" "$DST"
# text only; binaries (k11c-gw, fakevo, yuv, gray) are left untouched
find "$DST" -type f \( -name '*.sh' -o -name '*.service' -o -name '*.conf' -o -name '*.py' \
  -o -name '*.html' -o -name 'authorized_keys' -o -name 'k11c-release' \) -exec sed -i 's/\r$//' {} +
tr -d '\r' < $K/links.txt > $K/links.lf
tr -d '\r' < $K/users.txt > $K/k11c-br-users.txt
find "$DST" -type d -exec chmod 755 {} +
find "$DST" -type f -exec chmod 644 {} +
for f in "$DST"/usr/local/sbin/*.sh "$DST"/opt/k11c-kvm/k11c-gw "$DST"/opt/k11c-kvm/k11c-cloud "$DST"/opt/k11c-kvm/vo/fakevo; do
  [ -f "$f" ] && chmod 755 "$f"
done
if [ -f "$DST/etc/wpa_supplicant/wpa_supplicant-nl80211-wlan0.conf" ]; then
  chmod 600 "$DST/etc/wpa_supplicant/wpa_supplicant-nl80211-wlan0.conf"
fi
find "$DST" -type d -name .ssh -exec chmod 700 {} +
find "$DST" -path '*/.ssh/authorized_keys' -exec chmod 600 {} +
while read -r link target; do
  [ -n "$link" ] || continue
  mkdir -p "$(dirname "$DST/$link")"
  ln -sfn "$target" "$DST/$link"
done < $K/links.lf
find "$DST" -type l -exec ls -l {} +
md5sum "$DST/usr/local/sbin/k11c-gadget.sh"
