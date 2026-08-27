# Driving Ambiglow from HyperHDR

HyperHDR has no driver for the monitor's ENE MCU, and adding one would mean writing a
C++ `DriverNet*`/`DriverSerial*` class and rebuilding HyperHDR. There is no need: its
**`udpraw`** output is a bare RGB byte stream, so a small bridge is enough.

    HyperHDR  --udpraw/UDP:5568-->  hyperhdr-bridge.py  --USB ctrl xfer-->  0xC450  -->  46 LEDs

Verified working: a synthetic 46-LED gradient sent to :5568 appeared byte-identical in the
source buffer and rendered to the framebuffer.

## HyperHDR configuration

LED hardware -> **udpraw**
  - host `127.0.0.1`, port `5568`
  - LED count **46**
  - RGB byte order

LED layout — the panel's physical order is Philips', not a normal clockwise ring:

    index  0.. 2   left      (3)
    index  3.. 6   leftup    (4)
    index  7..24   center    (18)
    index 25..28   rightup   (4)
    index 29..31   right     (3)
    index 32..45   bottom    (14)

Build the layout in HyperHDR however you like, then reorder with the bridge's `--map`
(46 comma-separated source indices) rather than fighting HyperHDR's layout editor.

## Running

    sudo ./hyperhdr-bridge.py --max-fps 60 --restore-on-exit

Install `99-evnia-ambiglow.rules` into `/etc/udev/rules.d/` to drop the sudo.

The bridge reconnects on its own when the monitor's USB hub powers down and comes back.

## Caveat: screen capture on Hyprland with HDR

HyperHDR's Linux capture goes through PipeWire / xdg-desktop-portal. If you run Hyprland
with a 10-bit HDR output, for example

    monitor=DP-3,3440x1440@175.00,0x0,1,bitdepth,10,cm,hdr,...

be aware that **screen capture is known to break under xdg-desktop-portal-hyprland with
`bitdepth 10` and with HDR enabled** (hyprwm/xdg-desktop-portal-hyprland issues #270 and
#313, open as of writing). That is the awkward part: HyperHDR may be unable to capture
the monitor in exactly the HDR mode where the firmware's white-lock makes this project
most useful.

Also: the PipeWire grabber only works when HyperHDR runs as a **user application inside
the session**, never as a system service.

Ways around it, roughly in order of how well they preserve the goal:

1. **HDMI/USB capture card** — HyperHDR's intended design. Capture the source before it
   reaches the display; sidesteps the compositor entirely and keeps HDR.
2. **Wait for the portal fix** — the bridge is unaffected and will work the day capture does.
3. **Drop to `bitdepth 8`** — capture works, but loses the HDR this was meant to fix.
4. **Skip HyperHDR** — feed the LEDs directly from any source (a script, desktop theme
   state, `ambiglow.py`). The monitor's own "Follow Video" already does ambilight in SDR;
   the direct path is most valuable precisely where its firmware falls back to white.
