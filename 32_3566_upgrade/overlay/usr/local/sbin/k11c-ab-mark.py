#!/usr/bin/python3
# Mark the booted A/B slot successful in misc, at the Android AVB offset.
# Without this, U-Boot gives each slot 7 tries and then stops booting it.
import binascii
import os
import time

OFF = 2048
PATH = "/dev/block/by-name/misc"
MAGIC = b"\0AB0"


def crc32(data):
    return binascii.crc32(data) & 0xFFFFFFFF


def valid(blob):
    if len(blob) != 32 or blob[0:4] != MAGIC:
        return False
    stored = int.from_bytes(blob[28:32], "big")
    return stored == crc32(blob[:28])


def fresh():
    blob = bytearray(32)
    blob[0:4] = MAGIC
    blob[4] = 1  # version major
    blob[5] = 0  # version minor
    blob[8] = 15  # slot A priority
    blob[9] = 7
    blob[12] = 14  # slot B priority
    blob[13] = 7
    return blob


def main():
    for _ in range(50):
        if os.path.exists(PATH):
            break
        time.sleep(0.1)
    else:
        return
    with open(PATH, "rb") as handle:
        handle.seek(OFF)
        blob = bytearray(handle.read(32))
    if not valid(blob):
        blob = fresh()
    # The slot U-Boot just chose is the one with the higher priority.
    slot = 0 if blob[8] >= blob[12] else 1
    base = 8 + 4 * slot
    blob[base + 1] = 0  # tries_remaining cleared once successful
    blob[base + 2] = 1  # successful_boot
    blob[28:32] = crc32(blob[:28]).to_bytes(4, "big")
    with open(PATH, "r+b") as handle:
        handle.seek(OFF)
        handle.write(blob)
        handle.flush()
        os.fsync(handle.fileno())


if __name__ == "__main__":
    main()
