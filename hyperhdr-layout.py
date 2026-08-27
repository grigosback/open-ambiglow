#!/usr/bin/env python3
"""Generate HyperHDR LED sampling regions for a Philips Evnia panel.

The Ambiglow strip is not a plain clockwise ring, and on models with a centre
bar that bar points out of the back of the panel rather than at any screen
edge, so it must not sample an edge. Geometry below is verified on a 34M2C8600:

    0 - 2    right edge, bottom -> up
    3 - 6    top edge, right corner -> toward centre
    7 - 10   top edge, centre -> left corner
    11 - 13  left edge, top -> bottom
    14 - 31  centre bar, vertical, top -> bottom
    32 - 45  bottom edge, left -> right

Writes straight into HyperHDR's SQLite settings (stop HyperHDR first), or
prints the JSON with --print.
"""
import argparse, json, os, sqlite3, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.expanduser("~/.config/HyperHDR/db/hyperhdr.db")
ZONE_ORDER = ["right", "rightup", "leftup", "left", "center", "bottom"]


def layout(model):
    with open(os.path.join(HERE, "models.json")) as f:
        models = json.load(f)
    if model not in models:
        sys.exit(f"unknown model {model!r}")
    return {k: v for k, v in models[model].items() if k in ZONE_ORDER}


def build(model, depth=0.10, centre_width=0.16, centre_bottom_first=False):
    z = layout(model)
    leds = []

    def add(hmin, hmax, vmin, vmax):
        leds.append({"hmin": round(max(0.0, hmin), 4), "hmax": round(min(1.0, hmax), 4),
                     "vmin": round(max(0.0, vmin), 4), "vmax": round(min(1.0, vmax), 4)})

    # right edge, bottom -> up
    n = z["right"]
    for i in range(n):
        add(1 - depth, 1, 1 - (i + 1) / n, 1 - i / n)

    # top edge, right half: right corner -> centre
    n = z["rightup"]
    for i in range(n):
        add(1 - (i + 1) * 0.5 / n, 1 - i * 0.5 / n, 0, depth)

    # top edge, left half: centre -> left corner
    n = z["leftup"]
    for i in range(n):
        add(0.5 - (i + 1) * 0.5 / n, 0.5 - i * 0.5 / n, 0, depth)

    # left edge, top -> bottom
    n = z["left"]
    for i in range(n):
        add(0, depth, i / n, (i + 1) / n)

    # centre bar: vertical band through the middle of the frame.
    # Verified on the 34M2C8600: the lowest index is the TOP of the bar.
    n = z.get("center", 0)
    if n:
        h0, h1 = 0.5 - centre_width / 2, 0.5 + centre_width / 2
        for i in range(n):
            if centre_bottom_first:
                add(h0, h1, 1 - (i + 1) / n, 1 - i / n)
            else:
                add(h0, h1, i / n, (i + 1) / n)

    # bottom edge, left -> right
    n = z.get("bottom", 0)
    for i in range(n):
        add(i / n, (i + 1) / n, 1 - depth, 1)

    return leds


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="34M2C8600")
    ap.add_argument("--depth", type=float, default=0.10,
                    help="how far into the frame edge LEDs sample (0-0.5)")
    ap.add_argument("--centre-width", type=float, default=0.16,
                    help="width of the band the centre bar samples")
    ap.add_argument("--centre-bottom-first", action="store_true",
                    help="invert the centre bar if it runs upside down on your panel")
    ap.add_argument("--print", dest="dump", action="store_true", help="print JSON, write nothing")
    ap.add_argument("--db", default=DB)
    a = ap.parse_args()

    leds = build(a.model, a.depth, a.centre_width, a.centre_bottom_first)
    print(f"{a.model}: {len(leds)} LED regions", file=sys.stderr)
    if a.dump:
        print(json.dumps(leds, indent=1))
        return

    if not os.path.exists(a.db):
        sys.exit(f"no HyperHDR database at {a.db}")
    c = sqlite3.connect(a.db)
    c.execute("UPDATE settings SET config=?, updated_at=? WHERE type='leds' AND hyperhdr_instance=0",
              (json.dumps(leds), time.strftime("%Y-%m-%dT%H:%M:%SZ")))
    c.commit()
    print(f"wrote {len(leds)} regions into {a.db} (restart HyperHDR)", file=sys.stderr)


if __name__ == "__main__":
    main()
