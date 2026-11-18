#!/bin/sh
# The ext4 image is smaller than the partition. /dev/root is not a device node
# on this Buildroot, so grow the partition named by root=PARTUUID= in cmdline.
grep -qx /bin/bash /etc/shells || echo /bin/bash >> /etc/shells
uuid=$(cat /proc/cmdline | tr ' ' '\n' | sed -n 's/^root=PARTUUID=//p')
if [ -n "$uuid" ] && [ -e "/dev/disk/by-partuuid/$uuid" ]; then
	resize2fs "/dev/disk/by-partuuid/$uuid"
fi
for name in userdata oem; do
	dev=/dev/block/by-name/$name
	if [ -e "$dev" ]; then
		resize2fs "$dev"
	fi
done
