"""Pipe emulator and snapshot helpers for the HAL PCG-700 tests."""
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
    def __init__(self, exe, folder, config_text):
        self.folder = folder
        folder.mkdir(exist_ok=True)
        ini = folder / 'emu.ini'
        ini.write_text(config_text)
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


def snapshot_variant(src,dst,change):
    with zipfile.ZipFile(src) as z:
        files={n:z.read(n) for n in z.namelist()}
    change(files)
    digest=hashlib.sha256()
    for name in sorted(files):
        if name!='manifest.xml':digest.update(files[name])
    files['manifest.xml']=re.sub(rb'(<value type="string">)[0-9a-f]{64}(</value>)',
        lambda m:m[1]+digest.hexdigest().encode()+m[2],files['manifest.xml'])
    with zipfile.ZipFile(dst,'w') as z:
        for name,data in files.items():z.writestr(name,data)
