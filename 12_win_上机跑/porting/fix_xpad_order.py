#!/usr/bin/env python3
# Fix xpad.c: the xone hand-off guard must appear AFTER the local variable
# declarations, otherwise clang -Werror,-Wdeclaration-after-statement fails.
# Idempotent and safe: only rewrites when the bad ordering is present.
import sys

OLD = (
    "{\n"
    "\t/* hand Razer devices over to xone */\n"
    "\tif (xone_claim_needed(intf))\n"
    "\t\treturn -ENODEV;\n"
    "\n"
    "\tstruct usb_device *udev = interface_to_usbdev(intf);\n"
    "\tstruct usb_xpad *xpad;\n"
    "\tstruct usb_endpoint_descriptor *ep_irq_in, *ep_irq_out;\n"
    "\tint i, error;\n"
)

NEW = (
    "{\n"
    "\tstruct usb_device *udev = interface_to_usbdev(intf);\n"
    "\tstruct usb_xpad *xpad;\n"
    "\tstruct usb_endpoint_descriptor *ep_irq_in, *ep_irq_out;\n"
    "\tint i, error;\n"
    "\n"
    "\t/* hand Razer devices over to xone */\n"
    "\tif (xone_claim_needed(intf))\n"
    "\t\treturn -ENODEV;\n"
)

for path in sys.argv[1:]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        src = f.read()
    if NEW in src:
        print(f"ALREADY_FIXED {path}")
    elif OLD in src:
        src = src.replace(OLD, NEW, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        print(f"FIXED {path}")
    else:
        print(f"PATTERN_NOT_FOUND {path}")
        sys.exit(2)

print("ALL_DONE")
