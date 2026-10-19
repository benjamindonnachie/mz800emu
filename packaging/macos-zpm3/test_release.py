#!/usr/bin/env python3
"""Extract a release ZIP, verify signatures and boot through its native launcher."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'archive-tools'))
from test_mz800emu_boot import Emulator


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    fresh = Path(tempfile.mkdtemp(prefix='mz700-extracted-release-', dir='/private/tmp'))
    subprocess.run(['ditto', '-x', '-k', str(args.archive.resolve()), str(fresh)], check=True)
    app = next(fresh.glob('*/*.app'))
    launcher = app / 'Contents/MacOS/MZ700-ZPM3'
    resources = app / 'Contents/Resources'
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    stock = (resources / 'system/roms/stock-monitor-font.bin').read_bytes()
    asm = (ROOT / 'cpm/zpm3-pehu-keyboard-fast/suc-keyboard.asm').read_text().split('suc_F3D6:', 1)[1]
    table = bytes(int(x, 16) for x in re.findall(r'0x([0-9A-Fa-f]{2})', asm)[:256])
    assert len(table) == 256
    decode = {table[x]: chr(x) for x in reversed(range(32, 127))}; decode[0] = ' '
    original_path = os.environ.get('PATH')
    os.environ['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'
    os.environ['DYLD_PRINT_LIBRARIES'] = '1'
    results = []
    try:
        for name, options in [('sharp-manual', []), ('factory-manual', ['--factory']),
                              ('sharp-automatic', ['--automatic'])]:
            work = fresh / name; evidence = output / name; evidence.mkdir()
            e = Emulator(launcher, work, [*options, '--read-only'])
            def call(cmd, data=None):
                reply = e.call(cmd, data)
                assert reply.get('success'), reply
                return reply.get('data', {})
            def screen():
                region = next(x['id'] for x in call('regions_list')['regions'] if x['kind'] == 'vram_700_char')
                data = base64.b64decode(call('region_read', {'region_id': region, 'offset': 0, 'length': 2048})['data_b64'])
                return '\n'.join(''.join(decode.get(data[(((i >> 1) + (i & 1)) & 1023) | ((i & 1) << 10)], '?')
                    for i in range(row * 80, (row + 1) * 80)).rstrip() for row in range(25)).rstrip()
            def command(text):
                call('input_send_keys', {'text': text, 'frame_per_key': 30})
                call('input_send_key', {'key': 'RETURN', 'frames': 30})
                call('run', {'frames': 150})
                return screen()
            try:
                call('pause'); call('set_speed', {'mode': 'max'}); call('reset')
                assert call('get_registers')['PC'] == 0
                assert base64.b64decode(call('mem_read', {'addr': 0, 'len': 4096})['data_b64']) == stock[:4096]
                automatic = '--automatic' in options
                bid = call('bp_add', {'addr': 0xe800})['id'] if automatic else None
                call('run', {'frames': 1000})
                if automatic:
                    assert call('get_registers')['PC'] == 0xe800
                    call('bp_remove', {'id': bid})
                else:
                    assert call('get_registers')['PC'] < 0x1000
                    call('input_send_keys', {'text': 'F', 'frame_per_key': 30})
                    call('run', {'frames': 10})
                    call('input_send_key', {'key': 'RETURN', 'frames': 30})
                call('run', {'frames': 400})
                text = screen()
                assert 'C0>' in text and 'ZPM3 N10 / ZCCP' in text, text
                assert 'BIOS3' in text and '60K TPA' in text, text
                text = command('TPA'); assert '60672' in text, text
                text = command('RTC'); assert 'C0>' in text and 'error' not in text.lower(), text
                (evidence / 'screen.txt').write_text(text + '\n')
                call('screenshot_save_to_file', {'path': str(evidence / 'ready.png'), 'scale': '2'})
                assert (work / 'mz700.ini').read_text().count(str(resources)) >= 3
            finally:
                e.close()
            loaded = (work / 'stderr.log').read_text()
            assert '/opt/homebrew/' not in loaded, loaded[-4000:]
            assert '/Contents/Frameworks/' in loaded, 'No bundled dyld libraries recorded'
            (evidence / 'dyld.log').write_text(loaded)
            source_name = 'keyboard-fast-factory' if '--factory' in options else 'sharp-applications'
            preserved = resources / 'system/images' / (source_name + '.img')
            disk = work / 'gide.img'
            digest = hashlib.sha256(preserved.read_bytes()).hexdigest()
            assert hashlib.sha256(disk.read_bytes()).hexdigest() == digest
            # Existing-copy preservation must also hold after a real host edit.
            with disk.open('ab') as dst:
                dst.write(b'release-launcher-preservation-test')
            edited = hashlib.sha256(disk.read_bytes()).hexdigest()
            subprocess.run([str(launcher), '--prepare-only', '--work-dir', str(work), *options],
                           check=True, stdout=subprocess.PIPE)
            assert hashlib.sha256(disk.read_bytes()).hexdigest() == edited
            results.append(dict(profile=name, native_launcher=True, boot=True, tpa_bytes=60672,
                rtc_command=True, no_homebrew_loaded=True, pristine_disk_unchanged=True,
                edited_working_copy_preserved=True, rom_reset_zero=True))
    finally:
        if original_path is None:
            os.environ.pop('PATH', None)
        else:
            os.environ['PATH'] = original_path
        os.environ.pop('DYLD_PRINT_LIBRARIES', None)
    report = dict(passed=True, archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        extracted_app_signature_verified=True, extracted_directory=str(fresh), profiles=results)
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
