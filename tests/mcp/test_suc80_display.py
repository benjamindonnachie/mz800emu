#!/usr/bin/env python3
"""Black-box PAL MZ-700 SUC display tests. No disk or external ROM required.

Run with MZ_EMU=/absolute/path/to/mz700emu-pal python3 test_suc80_display.py.
Checks actual CPU MMIO writes, rendered glyphs/attributes, banking, reset,
snapshot round-trips and old snapshots without the SUC latch.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import threading
import time
import zipfile

import emu_test_proc

REPO = Path(__file__).resolve().parents[2]


class Emu:
    def __init__(self, exe, folder, fitted, config_text=None):
        self.folder = folder
        folder.mkdir(exist_ok=True)
        ini = folder / 'emu.ini'
        ini.write_text(config_text if config_text is not None else
                       '[VIDEO_MZ700]\nsuc80_enabled=' + str(int(fitted)) + '\n')
        self.err = (folder / 'stderr.log').open('w')
        self.proc = subprocess.Popen(
            [str(exe), '--mcp-pipe', '--no-first-run-windows',
             '--home-dir', str(REPO), '--cfg-dir', str(folder),
             '--work-dir', str(folder), '--config', str(ini)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err,
            text=True, bufsize=1, cwd=folder,
            env=dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy'))
        self.messages = queue.Queue()
        self.seq = 0
        def read():
            for line in self.proc.stdout:
                self.messages.put(json.loads(line))
            self.messages.put(None)
        threading.Thread(target=read, daemon=True).start()
        self.call('pause')
        self.call('set_speed', {'mode': 'max'})
        self.call('reset')
        self.call('run', {'frames': 100})
        self.palette = self.call('get_frame_framebuffer_info')['palette']
        self.cpu(b'')

    def call(self, cmd, data=None):
        self.seq += 1
        req = dict(req_id=self.seq, cmd=cmd)
        if data is not None:
            req['data'] = data
        self.proc.stdin.write(json.dumps(req) + '\n')
        self.proc.stdin.flush()
        deadline = time.monotonic() + 15
        while True:
            r = self.messages.get(timeout=max(.01, deadline-time.monotonic()))
            if r is None:
                raise RuntimeError('Emulator exited; see ' + str(self.folder/'stderr.log'))
            if r.get('req_id') == self.seq:
                if not r.get('success'):
                    raise AssertionError(r)
                return r.get('data', {})

    def cpu(self, code):
        # Real CPU instructions, then DI and a stable JP loop (no guest ROM).
        end = 0x8000 + len(code) + 1
        program = code + b'\xf3\xc3' + end.to_bytes(2, 'little')
        self.call('mem_write', {'addr': 0x8000, 'data_hex': program.hex()})
        self.call('set_register', {'reg': 'PC', 'value': 0x8000})
        self.call('run', {'frames': 3})

    def mode(self, addr, value):
        self.cpu(bytes((0x3e, value, 0x32)) + addr.to_bytes(2, 'little'))

    def frame(self):
        d = self.call('get_frame_screenshot_raw')
        assert d['available'] and (d['width'], d['height']) == (704, 232), d
        return base64.b64decode(d['data_b64'])

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)
        self.err.close()


def font_bytes():
    p = REPO/'src/emulator/mzarch/mz700/memory/ROM/ROM_MZ700_EU_CGROM.c'
    s = p.read_text().split('{', 1)[1].split('}', 1)[0]
    return bytes(int(h, 16) for h in re.findall(r'0x([0-9a-fA-F]{2})\b', s))


def assert_canvas(emu, vram, columns):
    actual = emu.frame()
    font = font_bytes()
    palette = [bytes(((c >> 16) & 255, (c >> 8) & 255, c & 255, 255)) for c in emu.palette]
    colors = [0, 9, 10, 11, 12, 13, 14, 15]
    for row in range(25):
        for line in range(8):
            expected = bytearray()
            for col in range(columns):
                if columns == 40:
                    loc = row*40+col
                else:
                    # Hardware-sheet banks: first char D000, second D401.
                    loc = row*40+col//2+(0x401 if col % 2 else 0)
                attr = vram[0x800+loc]
                mask = font[((attr & 0x80) << 4) + 8*vram[loc] + line]
                fg, bg = palette[colors[(attr >> 4) & 7]], palette[colors[attr & 7]]
                for bit in range(8):
                    pixel = fg if mask & (1 << bit) else bg
                    expected.extend(pixel * (2 if columns == 40 else 1))
            start = ((16+row*8+line)*704+32)*4
            assert actual[start:start+2560] == expected, (columns, row, line)
    return hashlib.sha256(actual).hexdigest()


def main():
    emu_test_proc.install(deadline_s=90)
    exe = Path(os.environ.get('MZ_EMU', REPO/'build-mac/build-mz700emu-pal/mz700emu-pal')).resolve()
    if not exe.is_file():
        print('SKIP: set MZ_EMU to a PAL MZ-700 binary')
        return 77
    work = Path(os.environ.get('MZ_SUC_TEST_OUTPUT', tempfile.mkdtemp(prefix='mz700-suc80-'))).resolve()
    work.mkdir(exist_ok=True, parents=True)
    print('Evidence:', work)
    checks = []
    # Every address has a distinct deterministic glyph/attribute pattern,
    # covering both CGROM banks, independent colours and the last cell.
    vram = bytearray(((i*17+i//31) & 255) for i in range(4096))
    vram[0x400] = 255  # Unused leading byte of the odd-character bank.
    for fitted in (False, True):
        e = Emu(exe, work/('fitted' if fitted else 'stock'), fitted)
        try:
            e.call('mem_write', {'addr': 0xd000, 'data_hex': vram.hex()})
            e.call('run', {'frames': 3})
            base = assert_canvas(e, vram, 40)
            checks.append('Reset renders 40 columns, fitted=' + str(fitted))
            for addr, value in ((0xe00c, 0x50), (0xe00d, 0x10), (0xe00e, 0xff), (0xe00f, 0x91)):
                e.mode(addr, value)
                assert_canvas(e, vram, 80 if fitted else 40)
            checks.append('All four register addresses latch D4, or ignore writes when absent')
            if not fitted:
                continue
            e.call('screenshot_save_to_file', {'path': str(e.folder/'80-columns.png'), 'scale': '2'})
            snap = e.folder/'80-columns.mzs'
            e.call('snapshot_save', {'path': str(snap)})
            e.mode(0xe00c, 0x28)
            assert assert_canvas(e, vram, 40) == base
            e.mode(0xe00f, 0xef)  # D4 clear, despite other bits being set.
            assert_canvas(e, vram, 40)
            checks.append('40/80 mode is D4, not an exact 28h/50h byte match')
            e.call('snapshot_load', {'path': str(snap)})
            e.call('run', {'frames': 3})
            assert_canvas(e, vram, 80)
            checks.append('Snapshot restores the 80-column latch and both VRAM banks')
            # Writes to E00C with the upper region mapped as RAM must not latch.
            e.cpu(bytes.fromhex('d3e1'))
            e.mode(0xe00c, 0x28)
            e.cpu(bytes.fromhex('d3e3'))
            assert_canvas(e, vram, 80)
            checks.append('E1/E3 RAM banking qualifies display-register writes')
            # Adjacent undocumented registers and reads must not switch modes.
            e.mode(0xe00b, 0x28)
            e.mode(0xe010, 0x28)
            e.cpu(bytes.fromhex('3a0ce0'))
            assert_canvas(e, vram, 80)
            checks.append('Adjacent writes and register reads do not change mode')
            # Preserve unrelated machine state while removing new XML keys.
            legacy = e.folder/'legacy.mzs'
            with zipfile.ZipFile(snap) as src:
                members = {n: src.read(n) for n in src.namelist()}
            members['hw/gdg.xml'] = re.sub(
                rb'\s*<suc80_\w+[^>]*>.*?</suc80_\w+>', b'', members['hw/gdg.xml'])
            # mzs protects the payload with a hash in addition to ZIP CRCs.
            digest = hashlib.sha256()
            for name in sorted(members):
                if name != 'manifest.xml':
                    digest.update(members[name])
            members['manifest.xml'] = re.sub(
                rb'(<value type="string">)[0-9a-f]{64}(</value>)',
                lambda m: m[1]+digest.hexdigest().encode()+m[2], members['manifest.xml'])
            with zipfile.ZipFile(legacy, 'w') as dst:
                for name, data in members.items():
                    dst.writestr(name, data)
            e.call('snapshot_load', {'path': str(legacy)})
            e.call('run', {'frames': 3})
            assert_canvas(e, vram, 40)
            checks.append('Legacy snapshots default to 40 columns')
            e.mode(0xe00c, 0x50)
            e.call('reset')
            e.call('run', {'frames': 100})
            e.cpu(b'')
            # Reset may initialise some VRAM, so replace only the test pattern.
            e.call('mem_write', {'addr': 0xd000, 'data_hex': vram.hex()})
            e.call('run', {'frames': 3})
            assert_canvas(e, vram, 40)
            e.call('screenshot_save_to_file', {'path': str(e.folder/'40-columns.png'), 'scale': '2'})
            checks.append('Hardware reset clears the 80-column latch')
        finally:
            e.close()
    (work/'results.json').write_text(json.dumps({'passed': checks}, indent=2))
    for check in checks:
        print('PASS:', check)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
