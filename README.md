# open-ambiglow

Control the Ambiglow LEDs on Philips Evnia monitors from Linux.

Philips ships **Evnia Precision Center** for Windows only, and its Ambiglow effects are
firmware-driven — in HDR the glow tends to lock to white regardless of what is on screen.
This project talks to the LED controller directly, so you get per-LED colour control from
any OS that can do USB.

```bash
./ambiglow.py --solid 00FF00          # everything green
./ambiglow.py --rainbow               # hue sweep across the strip
./ambiglow.py --zone bottom FF0000 --zone center 0000FF
./ambiglow.py --off
./ambiglow.py --get                   # read current colours
```

## How it works

Ambiglow is **not** a DDC/CI feature. The monitor advertises manufacturer-specific VCP
codes (`E0`, `F2`, `ED`, …) and they accept writes, but silently discard them — readback
never changes. That is a dead end.

The LEDs are driven by an **ENE 6K7732** MCU *inside the monitor*, which appears on the
monitor's USB upstream as `0cf2:a201`. Its interface 0 is vendor-specific with zero
endpoints and no kernel driver bound, so libusb can claim it without detaching anything.
Registers are read and written with plain USB control transfers:

| field | value |
|---|---|
| `bmRequestType` | `0x40` write / `0xC0` read |
| `bRequest` | `0x80` write / `0x81` read |
| `wValue` | `addr >> 16` |
| `wIndex` | `addr & 0xFFFF` |

Writing 46 RGB triplets to **`0xC450`** sets every LED. The monitor's own effect engine
renders that buffer, so the write sticks — unlike writing the framebuffer directly, which
the engine overwrites within 50 ms.

Full derivation, register map and disassembly notes: **[PROTOCOL.md](PROTOCOL.md)**.

Works on Linux and Windows. The device is WCID, so Windows binds WinUSB to it
automatically — no Zadig, no INF. See **[WINDOWS.md](WINDOWS.md)**.

## Requirements

- Python 3 and `pyusb` (`pip install pyusb`; on Windows also `libusb-package`)
- The monitor's **USB upstream cable connected to this machine**. DisplayPort alone is not
  enough — the MCU lives on the monitor's USB hub, and it disappears when that hub powers
  down.
- `ddcutil` (optional) for model auto-detection

## Install

```bash
git clone https://github.com/grigosback/open-ambiglow
cd open-ambiglow
pip install -r requirements.txt          # or: sudo pacman -S python-pyusb

sudo groupadd -r ambiglow
sudo usermod -aG ambiglow "$USER"
sudo cp udev/99-evnia-ambiglow.rules /etc/udev/rules.d/
sudo udevadm control --reload
sudo udevadm trigger --action=add --subsystem-match=usb --attr-match=idVendor=0cf2
```

Then **log out and back in** so your session picks up the new group. Until then you need
`sudo` for every call.

The rule sets `TAG+="uaccess"` as well, which grants the active seat user access on many
setups — but that depends on logind tagging the device, which does not always happen for
devices behind a hub, hence the group.

## HyperHDR

You can drive these LEDs from [HyperHDR](https://github.com/awawa-dev/HyperHDR) for real
ambient lighting. HyperHDR has no driver for this MCU, but its `udpraw` output is a bare
RGB byte stream, so a small bridge is enough:

```bash
./hyperhdr-bridge.py --restore-on-exit
```

Then in HyperHDR: **LED hardware → udpraw**, `127.0.0.1:5568`, 46 LEDs.

Verified end to end on Arch + Hyprland at ~48 fps, including PipeWire capture of a 10-bit
HDR output. Install notes, config, and LED layout: **[HYPERHDR.md](HYPERHDR.md)**.

## Supported models

`models.json` carries LED layouts for 19 Evnia models. Only the **34M2C8600** has been
tested on real hardware — the rest are transcribed from the layout table shipped with
Precision Center and should work, but reports are welcome.

**The buffer order is the field order in Philips' layout table**, not left-to-right:

```
right 3 | rightup 4 | leftup 4 | left 3 | center 18 | bottom 14
```

Verified physical geometry on a 34M2C8600 — the strip is one continuous path, and the
centre section is a **vertical bar** on the back panel, not part of the top edge:

```
 0 - 2    right edge, bottom -> up
 3 - 6    top edge, right corner -> toward centre
 7 - 10   top edge, centre -> left corner
11 - 13   left edge, top -> bottom
14 - 31   centre bar, vertical, bottom -> top
32 - 45   bottom edge, left -> right
```

Check your own panel with `./ambiglow.py --identify` (each zone a distinct colour),
`--led N RRGGBB` (one LED at a time), or `--walk` (steps through all of them).

## Status and limitations

- ✅ per-LED colour control, verified on a 34M2C8600
- ✅ read access to the whole EC address space
- ❓ the mode selector (`effect_sel_SWMode` in Philips' code) has not been located; not
  needed for colour control, but it would let you stop the built-in effects cleanly
- ❓ brightness register not identified
- ❓ untested whether the firmware's HDR white-lock overrides `0xC450`
- ✅ HyperHDR integration working (PipeWire capture -> udpraw -> bridge -> LEDs)

## Notes

This was worked out by static analysis of Philips' own `EneEc.dll` plus differential
dumps of the MCU's memory. No Philips binaries are redistributed here. `models.json`
contains LED counts transcribed from their data file — facts, not their file.

Not affiliated with or endorsed by Philips, TPV, or MMD.

## Licence

MIT — see [LICENSE](LICENSE).
