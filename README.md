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

## Requirements

- Python 3 and `pyusb` (`pip install pyusb`)
- The monitor's **USB upstream cable connected to this machine**. DisplayPort alone is not
  enough — the MCU lives on the monitor's USB hub, and it disappears when that hub powers
  down.
- `ddcutil` (optional) for model auto-detection

## Install

```bash
git clone https://github.com/grigosback/open-ambiglow
cd open-ambiglow
pip install -r requirements.txt
sudo cp udev/99-evnia-ambiglow.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
```

Without the udev rule you need `sudo` for every call.

## HyperHDR

You can drive these LEDs from [HyperHDR](https://github.com/awawa-dev/HyperHDR) for real
ambient lighting. HyperHDR has no driver for this MCU, but its `udpraw` output is a bare
RGB byte stream, so a small bridge is enough:

```bash
./hyperhdr-bridge.py --restore-on-exit
```

Then in HyperHDR: **LED hardware → udpraw**, `127.0.0.1:5568`, 46 LEDs.

Setup details and an important caveat about screen capture under Wayland with HDR:
**[HYPERHDR.md](HYPERHDR.md)**.

## Supported models

`models.json` carries LED layouts for 19 Evnia models. Only the **34M2C8600** has been
tested on real hardware — the rest are transcribed from the layout table shipped with
Precision Center and should work, but reports are welcome.

For the 34M2C8600 the 46 LEDs are ordered:

```
left 3 | leftup 4 | center 18 | rightup 4 | right 3 | bottom 14
```

## Status and limitations

- ✅ per-LED colour control, verified on a 34M2C8600
- ✅ read access to the whole EC address space
- ❓ the mode selector (`effect_sel_SWMode` in Philips' code) has not been located; not
  needed for colour control, but it would let you stop the built-in effects cleanly
- ❓ brightness register not identified
- ❓ untested whether the firmware's HDR white-lock overrides `0xC450`

## Notes

This was worked out by static analysis of Philips' own `EneEc.dll` plus differential
dumps of the MCU's memory. No Philips binaries are redistributed here. `models.json`
contains LED counts transcribed from their data file — facts, not their file.

Not affiliated with or endorsed by Philips, TPV, or MMD.

## Licence

MIT — see [LICENSE](LICENSE).
