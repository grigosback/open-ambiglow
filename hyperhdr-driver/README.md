# Native HyperHDR driver

A HyperHDR LED driver that talks to the monitor directly, so no bridge process is needed.
It appears in **LED hardware** as **`ambiglow`**, under the USB/Serial group.

Built and verified against HyperHDR master on Arch Linux, driving a 34M2C8600.

## Why this exists

The `udpraw` bridge in the repo root works fine, but it means a second process, a systemd
unit, and USB permissions arranged separately from HyperHDR. This moves all of that inside
HyperHDR.

## Design

libusb is **loaded at runtime** with `dlopen` / `LoadLibrary`, not linked at build time.
That mirrors what HyperHDR already does for libftdi in `ProviderSpiLibFtdi`, and means:

- no new build dependency, and no CMake changes at all
- works on Windows via `libusb-1.0.dll`, where HyperHDR does not link libusb
- `libusb-1.0` is already declared in HyperHDR's runtime package dependencies

Driver files live in `led-drivers/other/`, which CMake globs automatically.

## Applying it

```bash
git clone --recursive https://github.com/awawa-dev/HyperHDR
cd HyperHDR
git apply /path/to/0001-ambiglow-led-driver.patch
cmake -B build -S . -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
sudo cmake --install build --prefix /usr/local
sudo mkdir -p /usr/local/share/hyperhdr/web
sudo cp build/lib/web_resources.rcc /usr/local/share/hyperhdr/web/
```

The web resources step is needed because `cmake --install` does not place
`web_resources.rcc`, and without it the web UI will not start.

On a 12700K the whole build takes well under a minute.

## Configuration

**LED hardware -> ambiglow**, LED count to match your panel (46 on the 34M2C8600).
Everything else is optional and expert-level: `vendorId` (0x0CF2), `productId` (0xA201),
`address` (0xC450), `interface` (0).

Generate the LED layout with `../hyperhdr-layout.py` exactly as with the bridge.

The monitor's OSD must still be set to **Static Mode** — the driver logs a reminder when
it starts.

## Upstream

Not submitted yet. Worth opening an issue first: HyperHDR removed its Hyperion-inherited
USB drivers (the `rawhid`, `lightpack` and `paintpack` schemas are still registered but
their sources are gone), so it is worth asking whether a USB driver is wanted before
sending a PR.
