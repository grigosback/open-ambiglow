#!/usr/bin/env python3
"""ENE EC register access over USB for Philips Evnia monitors.

The Ambiglow LEDs are driven by an ENE 6K7732 MCU inside the monitor, which
appears on the monitor's USB upstream as 0cf2:a201. Its interface 0 is
vendor-specific with no endpoints and no kernel driver bound, so registers are
read and written with plain USB control transfers.

Protocol (recovered from EneEc.dll shipped with Evnia Precision Center):

    write: bmRequestType=0x40, bRequest=0x80, wValue=addr>>16, wIndex=addr&0xFFFF
    read : bmRequestType=0xC0, bRequest=0x81, wValue=addr>>16, wIndex=addr&0xFFFF

Transfers larger than 4096 bytes are split; the device auto-increments internally.
"""
import usb.core

VID, PID = 0x0CF2, 0xA201

RT_WRITE, REQ_WRITE = 0x40, 0x80
RT_READ, REQ_READ = 0xC0, 0x81
MAX_CHUNK = 0x1000

# Register map (see PROTOCOL.md)
ADDR_CHIP_ID = 0x4000   # reads 77 30
ADDR_PALETTE = 0xB0B4   # 13-entry colour wheel
ADDR_SOURCE  = 0xC450   # 46 RGB triplets - host writable, this is the control point
ADDR_FB1     = 0xB8BC   # rendered framebuffer (effect engine owns it)
ADDR_FB2     = 0xBE5C   # second rendered framebuffer


class DeviceNotFound(Exception):
    pass


def open_dev():
    """Find the ENE MCU. Raises DeviceNotFound if the monitor's USB is down."""
    d = usb.core.find(idVendor=VID, idProduct=PID)
    if d is None:
        raise DeviceNotFound(
            f"ENE {VID:04x}:{PID:04x} not found - is the monitor's USB upstream "
            "connected to this machine? DisplayPort alone is not enough."
        )
    return d


def read_regs(dev, addr, length, timeout=2000):
    """Read `length` bytes starting at EC address `addr`."""
    out = bytearray()
    while length > 0:
        n = min(length, MAX_CHUNK)
        out += dev.ctrl_transfer(RT_READ, REQ_READ,
                                 (addr >> 16) & 0xFFFF, addr & 0xFFFF, n, timeout)
        length -= n
    return bytes(out)


def write_regs(dev, addr, data, timeout=2000):
    """Write `data` to EC address `addr`. Returns bytes written."""
    data = bytes(data)
    total = 0
    for i in range(0, len(data), MAX_CHUNK):
        chunk = data[i:i + MAX_CHUNK]
        total += dev.ctrl_transfer(RT_WRITE, REQ_WRITE,
                                   (addr >> 16) & 0xFFFF, addr & 0xFFFF, chunk, timeout)
    return total


def chip_id(dev):
    return read_regs(dev, ADDR_CHIP_ID, 2).hex()


if __name__ == "__main__":
    d = open_dev()
    print(f"ENE MCU {VID:04x}:{PID:04x}  chip id 0x{chip_id(d)}")
    print(f"source buffer @0x{ADDR_SOURCE:04X}: {read_regs(d, ADDR_SOURCE, 12).hex(' ')} ...")
