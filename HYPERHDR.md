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

The physical order is Philips', not a normal clockwise ring. For the 34M2C8600:

    index  0.. 2   left      (3)
    index  3.. 6   leftup    (4)
    index  7..24   center    (18)
    index 25..28   rightup   (4)
    index 29..31   right     (3)
    index 32..45   bottom    (14)

`leftup + center + rightup` together form the top edge. A sensible mapping is a clockwise
loop: up the left edge, across the top, down the right edge, then right-to-left along the
bottom. If your glow appears mirrored or rotated, reorder with the bridge's `--map` rather
than fighting HyperHDR's layout editor.

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
