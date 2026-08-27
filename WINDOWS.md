# Windows

Everything here works on Windows, and the driver situation is the easy case.

> Written from the protocol and the device's own descriptors, but **not tested on
> Windows** — the reverse engineering and all hardware verification were done on Linux.
> Corrections welcome.

## No driver hacking needed

The MCU is a **WCID device**: it advertises Microsoft OS descriptors asking for WinUSB.

    string descriptor 0xEE : "MSFT100", vendor code 0x87
    compatible ID          : WINUSB

So Windows binds `winusb.sys` to interface 0 by itself the first time the monitor's USB
upstream is plugged in. **Do not run Zadig** — there is nothing to replace, and forcing
libusb-win32 or libusbK would only break Philips' own software.

libusb's Windows backend is WinUSB, so `pyusb` talks to the device with no changes.

## Setup

1. Connect the monitor's **USB upstream cable** to the PC. DisplayPort alone is not
   enough — the MCU lives on the monitor's internal hub.

2. Install Python 3 (python.org or `winget install Python.Python.3.12`), then:

   ```
   pip install pyusb libusb-package
   ```

   `libusb-package` ships `libusb-1.0.dll`, which pyusb needs and Windows does not
   provide. Alternatively drop a `libusb-1.0.dll` next to the scripts.

3. Check it:

   ```
   python eneec.py
   ```

   Expect `chip id 0x7730`. If you get `No backend available`, libusb isn't being found.
   If you get access errors, close Evnia Precision Center (see below).

4. Drive the LEDs:

   ```
   python ambiglow.py --solid 00FF00
   python ambiglow.py --identify
   ```

## Conflicts with Evnia Precision Center

Precision Center uses the same WinUSB interface through its own `EneEc.dll`. Two processes
cannot hold that handle at once, so **close Precision Center** (including its tray icon)
before using these tools. They are alternatives to each other, not companions.

You do not need Precision Center installed for any of this — Windows binds WinUSB from the
device's own descriptors.

## HyperHDR on Windows

Install from the [releases page](https://github.com/awawa-dev/HyperHDR/releases) — take
the `.exe` installer. Windows capture uses DXGI / Windows Graphics Capture and handles HDR
sources, so none of the Wayland portal caveats apply.

Configure exactly as on Linux: **LED hardware -> udpraw**, `127.0.0.1`, port `5568`, LED
count to match your panel, colour order RGB. Then generate the sampling regions:

```
python hyperhdr-layout.py --model 34M2C8600
```

It finds the database under `%LOCALAPPDATA%\HyperHDR\db\hyperhdr.db` (or `~/.hyperhdr` if
that exists). Stop HyperHDR before running it, and pass `--db` if auto-detection misses.

Then run the bridge:

```
python hyperhdr-bridge.py --restore-on-exit
```

## Starting it automatically

HyperHDR's installer offers to start at logon; enable that.

For the bridge, Task Scheduler is the reliable route — create a task that runs at logon:

```
schtasks /create /tn "Ambiglow bridge" /tr "pythonw C:\path\to\hyperhdr-bridge.py --restore-on-exit --quiet" /sc onlogon /rl limited
```

`pythonw` rather than `python` keeps a console window from appearing. No admin rights are
needed — WinUSB access does not require elevation once the driver is bound.

A shortcut to the same command in `shell:startup` works too, and is easier to undo.

## Notes

- The MCU disappears when the monitor's USB hub powers down, which it does independently
  of the panel. The bridge retries, so it recovers on its own.
- If you dual-boot, the monitor's USB upstream can only be attached to one machine at a
  time; whichever has it is the one that can drive the LEDs.
