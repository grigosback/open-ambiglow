# Driving Ambiglow from HyperHDR

HyperHDR has no driver for the monitor's ENE MCU, and adding one would mean writing a C++
driver class and rebuilding it. There is no need: HyperHDR's **`udpraw`** output is a bare
RGB byte stream, so a small bridge is enough.

    HyperHDR --udpraw/UDP:5568--> hyperhdr-bridge.py --USB ctrl xfer--> 0xC450 --> LEDs

Verified working end to end on Arch + Hyprland: PipeWire screen capture -> HyperHDR ->
bridge -> LEDs, at ~48 fps.

## Installing HyperHDR on Arch

Upstream ships a native Arch package on its releases page. **Take a v22 build or newer.**
The v21.0.0.0 package bundles its own `libssl.so.3` and fails to start against Arch's
OpenSSL 3.5:

    libssl.so.3: version `OPENSSL_3.5.0' not found (required by libngtcp2_crypto_ossl.so.0)

```bash
curl -LO https://github.com/awawa-dev/HyperHDR/releases/download/v22.0.0.0beta2/HyperHDR-22.0.0beta2-1-x86_64.pkg.tar.zst
sudo pacman -U HyperHDR-22.0.0beta2-1-x86_64.pkg.tar.zst
```

The AUR also has `hyperhdr-git`, which builds against system libraries and avoids the
bundled-library problem entirely, at the cost of a long Qt build.

## Configuring HyperHDR

Web UI on <http://localhost:8090>.

**LED hardware -> udpraw**, host `127.0.0.1`, port `5568`, LED count to match your panel
(46 on the 34M2C8600), colour order RGB.

Config changes over the JSON API need an auth token, so scripted setup is easiest by
editing `~/.config/HyperHDR/db/hyperhdr.db` (SQLite, `settings` table, JSON in `config`)
with HyperHDR stopped. The keys that matter are `device` and `leds` for instance 0, plus
`systemControl.systemInstanceEnable` to feed the screen grabber into it.

## LED layout

The buffer order is Philips' field order, and the centre section is a vertical bar on the
back panel rather than part of the top edge. Verified on a 34M2C8600:

     0 - 2    right edge, bottom -> up
     3 - 6    top edge, right corner -> toward centre
     7 - 10   top edge, centre -> left corner
    11 - 13   left edge, top -> bottom
    14 - 31   centre bar, vertical, bottom -> top
    32 - 45   bottom edge, left -> right

`hyperhdr-layout.py` generates matching sampling regions and writes them straight into
HyperHDR's settings:

```bash
systemctl --user stop hyperhdr
./hyperhdr-layout.py --model 34M2C8600
systemctl --user start hyperhdr
```

`--depth` controls how far into the frame the edge LEDs sample; `--centre-width` sets the
width of the central band the vertical bar samples. `--print` dumps the JSON instead of
writing.

To check the geometry on your own panel: `ambiglow.py --identify` lights each zone a
distinct colour, `--led N RRGGBB` lights one LED, `--walk` steps through all of them.

## Running

```bash
./hyperhdr-bridge.py --restore-on-exit
```

`systemd/ambiglow-bridge.service` is a user unit for it:

```bash
cp systemd/ambiglow-bridge.service ~/.config/systemd/user/
systemctl --user enable --now ambiglow-bridge.service
```

HyperHDR itself must run as a **user application inside the session** — its PipeWire
grabber cannot get screen access from a system service. A `systemd --user` unit is fine.

## Screen capture on Wayland

This works. On Hyprland 0.56.2 with a 10-bit HDR output

    monitor=DP-3,3440x1440@175.00,0x0,1,bitdepth,10,cm,hdr,...

HyperHDR's grabber reports `Pipewire: Using DmaBuf frame type. The hardware acceleration
is ENABLED` and captures correctly.

Older reports of capture breaking under `bitdepth 10` or with HDR enabled
(hyprwm/xdg-desktop-portal-hyprland #270, #313) no longer applied in this test. If you are
on an older Hyprland or portal and capture comes up black, those issues are the place to
look.
