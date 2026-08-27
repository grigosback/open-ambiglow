#!/usr/bin/env python3
"""Bridge HyperHDR's udpraw output to Philips Evnia Ambiglow LEDs.

HyperHDR's 'udpraw' LED device sends a bare RGB byte stream (no header) over UDP.
This listens for it and writes the frames into the monitor's LED buffer.

    HyperHDR --udpraw/UDP--> this bridge --USB control transfer--> Ambiglow

In HyperHDR: LED hardware -> udpraw, host 127.0.0.1, port 5568, and set the LED
count to match your panel (46 for the 34M2C8600). See HYPERHDR.md.
"""
import argparse
import json
import os
import socket
import sys
import time

import eneec
from eneec import read_regs, write_regs, DeviceNotFound, ADDR_SOURCE

HERE = os.path.dirname(os.path.abspath(__file__))
ZONE_ORDER = ["left", "leftup", "center", "rightup", "right", "bottom"]


def led_count(model):
    with open(os.path.join(HERE, "models.json")) as f:
        models = json.load(f)
    if model not in models:
        raise SystemExit(f"unknown model {model!r}")
    return sum(v for k, v in models[model].items() if k in ZONE_ORDER)


def connect(quiet=False):
    """Open the MCU, retrying - the monitor's USB hub powers down on its own."""
    warned = False
    while True:
        try:
            return eneec.open_dev()
        except DeviceNotFound:
            if not warned and not quiet:
                print("waiting for the monitor's USB upstream...", flush=True)
                warned = True
            time.sleep(3.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5568, help="HyperHDR udpraw default")
    ap.add_argument("--model", default="34M2C8600")
    ap.add_argument("--max-fps", type=float, default=60.0,
                    help="cap USB writes; 0 disables the cap")
    ap.add_argument("--map", metavar="IDX,...",
                    help="reorder HyperHDR's LED order into the panel's physical order")
    ap.add_argument("--restore-on-exit", action="store_true",
                    help="put back whatever was showing when the bridge started")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    nled = led_count(a.model)
    nbyte = nled * 3

    order = None
    if a.map:
        order = [int(x) for x in a.map.split(",")]
        if sorted(order) != list(range(nled)):
            raise SystemExit(f"--map must be a permutation of 0..{nled - 1}")

    d = connect(a.quiet)
    saved = read_regs(d, ADDR_SOURCE, nbyte) if a.restore_on_exit else None

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((a.bind, a.port))
    s.settimeout(0.5)
    if not a.quiet:
        print(f"listening on {a.bind}:{a.port} -> {a.model}, {nled} LEDs", flush=True)

    min_dt = 1.0 / a.max_fps if a.max_fps > 0 else 0.0
    last = 0.0
    pending = None
    frames, t0 = 0, time.time()

    try:
        while True:
            try:
                pkt, _ = s.recvfrom(65535)
                if len(pkt) >= nbyte:
                    pending = pkt[:nbyte]
            except socket.timeout:
                pass

            now = time.time()
            if pending is not None and now - last >= min_dt:
                buf = pending
                if order:
                    buf = b"".join(buf[i * 3:i * 3 + 3] for i in order)
                try:
                    write_regs(d, ADDR_SOURCE, buf)
                except Exception:
                    if not a.quiet:
                        print("USB write failed, reconnecting", flush=True)
                    d = connect(a.quiet)
                    continue
                last, pending = now, None
                frames += 1
                if not a.quiet and now - t0 >= 10.0:
                    print(f"  {frames / (now - t0):5.1f} fps", flush=True)
                    frames, t0 = 0, now
    except KeyboardInterrupt:
        if not a.quiet:
            print("\nstopping", flush=True)
    finally:
        if saved is not None:
            try:
                write_regs(d, ADDR_SOURCE, saved)
            except Exception:
                pass


if __name__ == "__main__":
    main()
