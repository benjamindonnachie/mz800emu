"""Reproduce a disk boot through mz800emu's native JSONL control interface."""
import argparse
import json
import os
import pathlib
import queue
import subprocess
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Emulator:
    def __init__(self, binary, folder, extra=()):
        self.folder = pathlib.Path(folder).resolve()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.log = (self.folder / 'protocol.jsonl').open('w')
        self.err = (self.folder / 'stderr.log').open('w')
        self.q = queue.Queue()
        self.seq = 0
        self.argv = [str(pathlib.Path(binary).resolve()), '--mcp-pipe',
                     '--no-first-run-windows', '--home-dir', str(ROOT / 'emulators/mz800emu'),
                     '--cfg-dir', str(self.folder), '--work-dir', str(self.folder), *extra]
        env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        self.p = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=self.err, text=True, bufsize=1, cwd=self.folder, env=env)
        (self.folder / 'launch.json').write_text(json.dumps(self.argv, indent=2))
        def reader():
            for line in self.p.stdout:
                self.log.write(line)
                self.log.flush()
                self.q.put(json.loads(line))
            self.q.put({'eof': True})
        threading.Thread(target=reader, daemon=True).start()

    def call(self, cmd, data=None, timeout=45):
        self.seq += 1
        req = dict(req_id=self.seq, cmd=cmd)
        if data is not None:
            req['data'] = data
        self.log.write(json.dumps({'request': req}) + '\n')
        self.log.flush()
        self.p.stdin.write(json.dumps(req) + '\n')
        self.p.stdin.flush()
        end = time.monotonic() + timeout
        while True:
            r = self.q.get(timeout=max(.01, end-time.monotonic()))
            if r.get('eof'):
                raise RuntimeError('Emulator exited: ' + str(self.p.poll()))
            if r.get('req_id') == self.seq:
                return r

    def close(self):
        self.p.stdin.close()
        try:
            self.p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.p.terminate()
            self.p.wait(timeout=5)
        self.err.close()
        self.log.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--image', required=True)
    ap.add_argument('--binary', default=str(ROOT / 'emulators/mz800emu/build-mac/build-mz700emu-pal/mz700emu-pal'))
    ap.add_argument('--boot', default='JF000\r')
    ap.add_argument('--frames', type=int, default=1000)
    ap.add_argument('--hd-patch', default='off')
    ap.add_argument('--config')
    ap.add_argument('--command', default='DIR')
    ap.add_argument('--probe-bdos', action='store_true')
    args = ap.parse_args()
    out = ROOT / 'build-records/mz800emu/runs' / args.name
    out.mkdir(parents=True, exist_ok=True)
    config = out / 'boot-input.ini'
    text = pathlib.Path(args.config).read_text() if args.config else ''
    text += '\n[FDC]\nconnected = 1\nhd_patch = ' + ('1' if args.hd_patch == 'on' else '0') + '\nbus_xlate = invert\nwd279x_fdd0_readonly = 1\nwd279x_fdd0_storage_mode = discard\n'
    config.write_text(text)
    extra = ['--config', str(config)]
    emu = Emulator(args.binary, out, extra)
    results = []
    def call(cmd, data=None):
        r = emu.call(cmd, data)
        results.append(dict(command=cmd, arguments=data, response=r))
        print(cmd, json.dumps(r)[:1200], flush=True)
        return r
    try:
        call('pause')
        call('set_speed', {'mode': 'max'})
        call('media_insert', {'slot': 'fdc0_fd0', 'path': str(pathlib.Path(args.image).resolve()), 'ro': True})
        call('reset')
        call('run', {'frames': 150})
        call('screenshot_save_to_file', {'path': str(out / 'monitor.png'), 'scale': '2'})
        call('input_send_keys', {'text': args.boot.rstrip('\r\n'), 'encoding': 'ascii', 'frame_per_key': 5})
        call('run', {'frames': 10})
        call('input_send_key', {'key': 'RETURN', 'frames': 30})
        call('run', {'frames': args.frames})
        call('get_registers')
        call('mem_read', {'addr': 0, 'len': 256})
        call('mem_read', {'addr': 0xf000, 'len': 128})
        call('mem_read', {'addr': 0xd000, 'len': 1000})
        call('media_state')
        call('screenshot_save_to_file', {'path': str(out / 'boot.png'), 'scale': '2'})
        if args.command:
            call('input_send_keys', {'text': args.command, 'encoding': 'ascii', 'frame_per_key': 5})
            call('run', {'frames': 10})
            call('input_send_key', {'key': 'RETURN', 'frames': 30})
            call('run', {'frames': 500})
            call('get_registers')
            call('screenshot_save_to_file', {'path': str(out / 'directory.png'), 'scale': '2'})
        if args.probe_bdos:
            snapshot = out / 'cpm-directory.mzs'
            call('snapshot_save', {'path': str(snapshot), 'description': 'MZ-700 P-CP/M after DIR; SUC 80-column output is incomplete in the standard display'})
            # Scratch RAM: LD C,12; CALL 0005; LD (8100),HL; HALT.
            # Restoring the snapshot afterwards removes the probe and its state.
            call('mem_write', {'addr': 0x8000, 'data_hex': '0E0CCD050022008176'})
            call('set_register', {'reg': 'SP', 'value': 0x9000})
            call('set_register', {'reg': 'PC', 'value': 0x8000})
            call('run', {'frames': 10})
            call('get_registers')
            call('mem_read', {'addr': 0x8100, 'len': 2})
            call('snapshot_load', {'path': str(snapshot)})
    finally:
        emu.close()
        (out / 'results.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
