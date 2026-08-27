#!/usr/bin/env python3
"""Control Philips Evnia Ambiglow LEDs from Linux.

Writes the per-LED source colour buffer inside the monitor's ENE MCU. The
monitor's own effect engine renders it, so writes stick without having to fight
it. See PROTOCOL.md for how this was worked out.
"""
import argparse
import colorsys
import json
import os
import sys
import time

from eneec import open_dev, read_regs, write_regs, DeviceNotFound, ADDR_SOURCE, ADDR_FB1

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL = "34M2C8600"
ZONE_ORDER = ["left", "leftup", "center", "rightup", "right", "bottom"]


def load_models():
    with open(os.path.join(HERE, "models.json")) as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def detect_model(models):
    """Ask ddcutil for the connected Philips model, if it is available."""
    import subprocess
    try:
        out = subprocess.run(["ddcutil", "detect"], capture_output=True, text=True,
                             timeout=30).stdout
    except Exception:
        return None
    for name in models:
        if name in out:
            return name
    return None


def zone_slices(layout):
    out, i = {}, 0
    for name in ZONE_ORDER:
        n = layout.get(name, 0)
        if n:
            out[name] = (i, i + n)
            i += n
    return out, i


def parse_hex(s):
    s = s.lstrip("#")
    if len(s) != 6:
        raise SystemExit(f"bad colour {s!r} - expected RRGGBB")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def main():
    models = load_models()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--solid", metavar="RRGGBB", help="set every LED to one colour")
    g.add_argument("--rainbow", action="store_true", help="hue sweep across the strip")
    g.add_argument("--zone", nargs=2, action="append", metavar=("ZONE", "RRGGBB"),
                   help="colour one zone; repeatable")
    g.add_argument("--off", action="store_true", help="all LEDs off")
    g.add_argument("--get", action="store_true", help="print current colours by zone")
    ap.add_argument("--model", choices=sorted(models), help="override model detection")
    ap.add_argument("--hold", type=float, metavar="SEC",
                    help="revert to the previous colours after SEC seconds")
    a = ap.parse_args()

    model = a.model or detect_model(models) or DEFAULT_MODEL
    layout = models[model]
    zones, nled = zone_slices(layout)
    nbyte = nled * 3

    try:
        d = open_dev()
    except DeviceNotFound as e:
        raise SystemExit(str(e))

    before_raw = read_regs(d, ADDR_SOURCE, nbyte)
    before = [tuple(before_raw[i:i + 3]) for i in range(0, nbyte, 3)]

    if a.get:
        print(f"{model}: {nled} LEDs")
        for name, (s, e) in zones.items():
            print(f"  {name:<8} " + " ".join("%02x%02x%02x" % c for c in before[s:e]))
        return

    if a.solid:
        leds = [parse_hex(a.solid)] * nled
    elif a.off:
        leds = [(0, 0, 0)] * nled
    elif a.rainbow:
        leds = [tuple(int(v * 255) for v in colorsys.hsv_to_rgb(i / nled, 1, 1))
                for i in range(nled)]
    else:
        leds = list(before)
        for zone, col in a.zone:
            if zone not in zones:
                raise SystemExit(f"unknown zone {zone!r} for {model}; have {list(zones)}")
            s, e = zones[zone]
            leds[s:e] = [parse_hex(col)] * (e - s)

    write_regs(d, ADDR_SOURCE, bytes(b for rgb in leds for b in rgb))
    print(f"{model}: set {nled} LEDs")

    if a.hold:
        time.sleep(a.hold)
        write_regs(d, ADDR_SOURCE, before_raw)
        print("restored")


if __name__ == "__main__":
    main()
