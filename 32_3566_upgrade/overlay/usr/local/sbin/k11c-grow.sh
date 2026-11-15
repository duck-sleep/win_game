#!/bin/sh
# Grow the ext4 that was baked small, and let dropbear accept root's shell.
grep -qx /bin/bash /etc/shells || echo /bin/bash >> /etc/shells
resize2fs /dev/root
for name in userdata oem; do
	dev=/dev/block/by-name/$name
	if [ -e "$dev" ]; then
		resize2fs "$dev"
	fi
done
