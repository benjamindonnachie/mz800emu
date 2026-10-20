#!/usr/bin/env python3
"""HAL PCG-700: real Z80 MMIO, pixel output, banking and snapshots.

MZ_EMU selects a PAL or NTSC MZ-700 executable. All files use a disposable directory.
"""
import base64
import json
import os
from pathlib import Path
import tempfile
import zipfile

from test_suc80_display import Emu, REPO, font_bytes
from test_gide import snapshot_variant
import emu_test_proc


def store(addr, value):
    return bytes((0x3e, value, 0x32)) + addr.to_bytes(2, 'little')


def upload(e, data, copy=False):
    """Z80 loop copies 2048 bytes to PCG using full E010/E011/E012 writes."""
    assert len(data) == 2048
    e.call('mem_write', {'addr': 0x9000, 'data_hex': data.hex()})
    code = bytearray.fromhex('f3 210090 110000 010008')  # DI; HL=9000; DE=0; BC=800
    loop = len(code)
    code += bytes.fromhex('7e 3210e0 7b 3211e0 7a')
    code += bytes((0xf6, 0x30 if copy else 0x10))  # OR strobe + optional COPY
    code += bytes.fromhex('3212e0 af 3212e0 23 13 0b 78 b1 20')
    code += bytes(((loop - (len(code) + 1)) & 255,))
    e.cpu(store(0xe012, 8) + code)
    e.call('run', {'frames': 12})


def vram_pattern():
    # Both character sets, all 256 codes, all eight rows and multiple colours.
    return bytearray((i * 17 + i // 31) & 255 for i in range(4096))


def assert_display(e, vram, ram=None, columns=40):
    actual = e.frame()
    font = font_bytes()
    palette = [bytes(((c >> 16) & 255, (c >> 8) & 255, c & 255, 255)) for c in e.palette]
    colours = [0, 9, 10, 11, 12, 13, 14, 15]
    for y in range(200):
        expected = bytearray()
        for x in range(columns):
            loc = y // 8 * 40 + (x if columns == 40 else x // 2 + (0x401 if x & 1 else 0))
            char, attr = vram[loc], vram[0x800 + loc]
            bank = attr >> 7
            if ram is not None and char >= 128:
                mask = ram[bank * 1024 + (char - 128) * 8 + y % 8]
                bits = range(7, -1, -1)  # Hardware patterns are MSB on the left.
            else:
                mask = font[bank * 2048 + char * 8 + y % 8]
                bits = range(8)  # Repository CGROM arrays are already reversed.
            for bit in bits:
                pixel = palette[colours[(attr >> 4) & 7 if mask & (1 << bit) else attr & 7]]
                expected.extend(pixel * (2 if columns == 40 else 1))
        start = ((16 + y) * 704 + 32) * 4
        assert actual[start:start + 2560] == expected, ('pixels', columns, y)


def saved_pcg(e, path):
    e.call('snapshot_save', {'path': str(path)})
    with zipfile.ZipFile(path) as z:
        return z.read('hw/pcg700.bin')


def main():
    emu_test_proc.install(deadline_s=180)
    exe = Path(os.environ.get('MZ_EMU', REPO/'build-mac/build-mz700emu-pal/mz700emu-pal')).resolve()
    if not exe.is_file():
        print('SKIP: set MZ_EMU to a MZ-700 executable')
        return 77
    work = Path(os.environ.get('MZ_PCG_TEST_OUTPUT', tempfile.mkdtemp(prefix='mz700-pcg-'))).resolve()
    work.mkdir(parents=True, exist_ok=True)
    print('Evidence:', work)
    checks = []
    vram = vram_pattern()
    ram = bytes((i * 37 + i // 29) & 255 for i in range(2048))
    for fitted in (False, True):
        e = Emu(exe, work/('fitted' if fitted else 'absent'), False,
                f'[PCG700]\nfitted={int(fitted)}\nhsw=1\n[VIDEO_MZ700]\nsuc80_enabled=1\n')
        try:
            e.call('mem_write', {'addr': 0xd000, 'data_hex': vram.hex()})
            e.call('run', {'frames': 3})
            assert_display(e, vram)
            upload(e, ram)
            assert_display(e, vram, ram if fitted else None)
            checks.append('Both banks, all 2048 pattern bytes and MSB-left pixels, fitted=' + str(fitted))
            if not fitted:
                state = saved_pcg(e, e.folder/'absent.mzs')
                assert state[2:] == b'\x00\x00\x08' + bytes(2048)
                continue
            snapshot = e.folder/'programmed.mzs'
            state = saved_pcg(e, snapshot)
            assert state[5:] == ram
            # Bits 6/7 do not alter control; SSW bypass does not erase RAM.
            e.mode(0xe012, 0xc8)
            assert_display(e, vram)
            e.mode(0xe012, 0xc0)
            assert_display(e, vram, ram)
            checks.append('Software bypass and unused control bits')
            # Strobe must be released before another transfer. Use bank 1,
            # offset 3FF to catch addressing mistakes at the end of RAM.
            e.mode(0xe011, 0xff)
            e.mode(0xe010, 0x96)
            e.mode(0xe012, 0x17)
            e.mode(0xe010, 0x69)
            e.mode(0xe012, 0x17)
            test_ram = bytearray(ram); test_ram[2047] = 0x96
            assert_display(e, vram, test_ram)
            state = saved_pcg(e, e.folder/'strobe-high.mzs')
            assert state[4] == 0x17 and state[-1] == 0x96
            e.mode(0xe012, 0)
            e.mode(0xe012, 0x17)
            test_ram[-1] = 0x69
            assert_display(e, vram, test_ram)
            e.call('snapshot_load', {'path': str(e.folder/'strobe-high.mzs')})
            e.mode(0xe012, 0x17)
            assert saved_pcg(e, e.folder/'strobe-restored.mzs') == state
            checks.append('One transfer per strobe and snapshot preservation of a high strobe')
            # Upper RAM must receive writes without the PCG responding.
            e.cpu(bytes.fromhex('d3e1'))
            e.cpu(store(0xe010, 0xaa) + store(0xe011, 0x55) + store(0xe012, 0))
            assert saved_pcg(e, e.folder/'banked.mzs') == state
            e.call('mem_write', {'addr': 0xe010, 'data_hex': 'aa5500'})
            assert saved_pcg(e, e.folder/'banked-debugger.mzs') == state
            data = e.call('mem_read', {'addr': 0xe010, 'len': 3})
            assert base64.b64decode(data['data_b64']) == bytes((0xaa, 0x55, 0))
            e.cpu(bytes.fromhex('d3e3'))
            checks.append('E1 upper RAM masks every PCG register; E3 restores access')
            # OUT(C),A with full I/O address E012 is not a memory write.
            e.cpu(bytes.fromhex('0112e0 3e00 ed79 3a12e0') + store(0xe013, 0))
            assert saved_pcg(e, e.folder/'unrelated.mzs') == state
            checks.append('Reads, adjacent MMIO and Z80 I/O writes do not programme PCG')
            # ROM copy must ignore E010 data, cover both banks and use the
            # original CGROM even after all its upper characters were changed.
            upload(e, bytes(2048), copy=True)
            assert_display(e, vram)
            font = font_bytes()
            reverse = lambda x: int(f'{x:08b}'[::-1], 2)
            original = bytes(reverse(x) for x in font[1024:2048] + font[3072:4096])
            assert saved_pcg(e, e.folder/'rom-copy.mzs')[5:] == original
            checks.append('ROM copy restores both complete banks from immutable CGROM')
            e.call('snapshot_load', {'path': str(snapshot)})
            e.call('run', {'frames': 3})
            assert_display(e, vram, ram)
            e.mode(0xe00c, 0x50)
            assert_display(e, vram, ram, 80)
            e.call('screenshot_save_to_file', {'path': str(e.folder/'pcg-80-columns.png'), 'scale': '2'})
            checks.append('Snapshot restores RAM/control, with PCG output in SUC 80 columns')
            # Loading a legacy snapshot must not retain the live PCG state.
            legacy = e.folder/'legacy.mzs'
            snapshot_variant(snapshot, legacy, lambda members: members.pop('hw/pcg700.bin'))
            e.call('snapshot_load', {'path': str(legacy)})
            e.call('run', {'frames': 3})
            assert_display(e, vram)
            assert saved_pcg(e, e.folder/'legacy-loaded.mzs')[0] == 0
            checks.append('Legacy snapshots load with the card absent')
            # Reset bypasses the display while preserving character RAM.
            e.call('snapshot_load', {'path': str(snapshot)})
            e.call('reset')
            e.call('run', {'frames': 100})
            e.cpu(b'')
            state = saved_pcg(e, e.folder/'reset.mzs')
            assert state[:5] == b'\x01\x01\x00\x00\x08' and state[5:] == ram
            e.call('mem_write', {'addr': 0xd000, 'data_hex': vram.hex()})
            e.call('run', {'frames': 3})
            assert_display(e, vram)
            e.mode(0xe012, 0)
            assert_display(e, vram, ram)
            e.call('screenshot_save_to_file', {'path': str(e.folder/'pcg-40-columns.png'), 'scale': '2'})
            checks.append('Soft reset preserves RAM and starts in CGROM bypass')
        finally:
            e.close()
    # Hardware display switch does not prevent programming the card.
    e = Emu(exe, work/'hsw-off', False, '[PCG700]\nfitted=1\nhsw=0\n')
    try:
        e.call('mem_write', {'addr': 0xd000, 'data_hex': vram.hex()})
        upload(e, ram)
        assert_display(e, vram)
        state = saved_pcg(e, e.folder/'hsw-off.mzs')
        assert state[:2] == bytes((1, 0)) and state[5:] == ram
        checks.append('HSW bypass uses CGROM while programming remains available')
    finally:
        e.close()
    (work/'results.json').write_text(json.dumps({'passed': checks}, indent=2))
    for check in checks:
        print('PASS:', check)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
