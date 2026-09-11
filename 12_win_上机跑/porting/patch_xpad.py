#!/usr/bin/env python3
# Patch xpad.c so Razer (0x1532) is claimed by xone, not xpad.
# Idempotent: safe to run multiple times.
import sys, re

path = sys.argv[1]
with open(path, "r", encoding="utf-8", errors="replace") as f:
    src = f.read()

if "xone_claim_needed" in src:
    print("ALREADY_PATCHED")
    sys.exit(0)

# 1) Insert helper function right before xpad_probe definition.
helper = (
    "\n/* Razer Wolverine V3 Pro (0x1532:0x0a3f) is handled by the xone driver. */\n"
    "static bool xone_claim_needed(struct usb_interface *intf)\n"
    "{\n"
    "\tstruct usb_device *udev = interface_to_usbdev(intf);\n"
    "\treturn le16_to_cpu(udev->descriptor.idVendor) == 0x1532;\n"
    "}\n\n"
)

m = re.search(r"^static int xpad_probe\(struct usb_interface \*intf", src, re.M)
if not m:
    print("ERROR: xpad_probe not found")
    sys.exit(2)

idx = m.start()
src = src[:idx] + helper + src[idx:]

# 2) Insert the early-return at the very top of xpad_probe body (after its opening brace).
# Find the helper's xpad_probe now and its first '{'.
pm = re.search(r"^static int xpad_probe\(struct usb_interface \*intf[^\n]*\n\{", src, re.M)
if not pm:
    print("ERROR: xpad_probe body brace not found")
    sys.exit(3)
brace_end = pm.end()
guard = (
    "\n\t/* hand Razer devices over to xone */\n"
    "\tif (xone_claim_needed(intf))\n"
    "\t\treturn -ENODEV;\n"
)
src = src[:brace_end] + guard + src[brace_end:]

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

print("PATCH_OK")
