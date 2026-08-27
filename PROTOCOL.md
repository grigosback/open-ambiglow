# Philips Evnia Ambiglow — control protocol

Recovered 2026-08-27 by static analysis of Evnia Precision Center 1.11.0
(md5 2196caee09afbc569f7faa6b8eb2ff3a), specifically `resources/bin/lib/ENE/EneEc.dll`.

## Hardware

Ambiglow is NOT on DDC/CI. DDC manufacturer codes (E0, F2, ED, ...) accept writes
at the protocol level but silently ignore them — readback never changes.

The LEDs are driven by an **ENE 6K7732** MCU inside the monitor, reachable over the
monitor's USB upstream:

    usb 0cf2:a201  "ENE 6K7732"
      interface 0 : vendor-specific, 0 endpoints, no kernel driver  <-- control channel
      interface 1 : HID, vendor usage page 0xFF72, report ID 0xEC   <-- not the command path

Because interface 0 has no kernel driver bound, libusb can claim it without detaching
anything.

## EC register access (from EneEc.dll)

`Ec_ReadRegs` @ 0x100039c0 and `Ec_WriteRegs` @ 0x10003a90 build a WinUSB setup packet:

    mov WORD PTR [esp+0x18], 0x81c0   ; read : bmRequestType=0xC0, bRequest=0x81
    mov WORD PTR [esp+0x18], 0x8040   ; write: bmRequestType=0x40, bRequest=0x80

Full setup packet:

| field         | value                    |
|---------------|--------------------------|
| bmRequestType | 0x40 write / 0xC0 read   |
| bRequest      | 0x80 write / 0x81 read   |
| wValue        | (addr >> 16) & 0xFFFF    |
| wIndex        | addr & 0xFFFF            |
| wLength       | chunk length, max 0x1000 |

Transfers >4096 bytes are split into 0x1000 chunks; the address is NOT incremented
between chunks (the EC auto-increments internally).

`Ec_Init` reads address 0x0100 (per the "Failed to ReadRegs(0x0100)" error string).

Exports: DelayUs, Ec_ErrorString, Ec_Exit, Ec_GetChipId, Ec_GetPID, Ec_GetRevId,
Ec_GetVID, Ec_Init, Ec_ReadRegs, Ec_ResetAndStop, Ec_Run, Ec_WriteRegs.

## LED layout — 34M2C8600 (from PCenter_AmbiglowInfo.json)

    Left 3 | LeftUp 4 | Center 18 | RightUp 4 | Right 3 | Bottom 14   = 46 LEDs
    WriteType: 1

## Modes (names from Zeasn.USB.ENE.Lib.dll metadata)

    LEDOFF, StaticMode, StaticModeRainbow, ColorShift, ColorShiftRainbow,
    ColorWave, ColorWaveRainbow, ColorBreathing, ColorBreathingRainbow
    Brightness: Bright / Brighter / Brightest

Related symbols: CUSBENE6K7732, ENE_0x7730, ECBUS_WINUSB, ENELightStaticTable,
ENELightNumbersData, SetLedGroupAll, SetLed_group, GetLightColors, ParameterLedSync.

## Register map (found by diffing dumps across an OSD change)

| address | size | meaning |
|---------|------|---------|
| `0x4000` | 2 | chip id, reads `77 30` (matches the `ENE_0x7730` symbol) |
| `0xB080` | 39 | copy of the HID report descriptor |
| `0xB0B4` | ~39 | 13-entry colour palette (hue wheel), matches DDC `E2A01A(00..0D)` |
| `0xB100` | ~192 | sine ramp x3 — the breathing animation table |
| **`0xC450`** | **138** | **source colour buffer, 46 RGB triplets — HOST WRITABLE** |
| `0xB8BC` | 138 | rendered framebuffer, 46 RGB triplets (effect engine owns it) |
| `0xBE5C` | 138 | second rendered framebuffer (double buffer) |

### Controlling the LEDs

Write 138 bytes (46 RGB triplets) to **`0xC450`**. The value sticks, and the effect
engine renders it into `0xB8BC`/`0xBE5C` within ~50 ms.

Do NOT write `0xB8BC` directly — the effect engine overwrites it within 50 ms.
Writes there are accepted and verifiable on immediate readback, then lost.

LED order is the zone order from `PCenter_AmbiglowInfo.json`:
`left 3, leftup 4, center 18, rightup 4, right 3, bottom 14`.

The engine applies a slight scale on render (`0xFF` source -> `0xFE` rendered), and
LEDs at index 14..31 render at roughly 39% (`0x63` vs `0xFE`) — a fixed per-LED
brightness map in firmware, not something we set.

`0xB22D` is NOT a mode register — it reads back values different from those written;
the apparent hit in the first diff was coincidental. The real mode selector has not
been located, and has not been needed: writing `0xC450` works regardless of mode.

## Still unknown

- The mode selector (`effect_sel_SWMode` in the obfuscated assembly) and brightness
  register. Not required for direct colour control.
- Whether the HDR white-lock overrides `0xC450` writes.
