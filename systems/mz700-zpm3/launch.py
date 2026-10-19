#!/usr/bin/env python3
"""Launch a writable local copy of a preserved MZ-700 ZP/M GIDE image."""
import argparse
import configparser
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def prepare(image, work, automatic=False, readonly=False):
    manifest = json.loads((HERE / 'manifest.json').read_text())['files']
    selected = [f'images/{image}.img', 'roms/stock-monitor-font.bin',
                'roms/boot-f000.bin', 'roms/boot-e800.bin']
    for name in selected:
        data = (HERE / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest[name]['sha256']:
            raise ValueError(f'Preservation checksum mismatch: {name}')
    work.mkdir(parents=True, exist_ok=True)
    disk = work / 'gide.img'
    if not disk.exists():
        # Exclusive creation prevents concurrent first launches overwriting a disk.
        with disk.open('xb') as dst, (HERE / selected[0]).open('rb') as src:
            shutil.copyfileobj(src, dst)
    cfg = configparser.ConfigParser(interpolation=None)
    cfg['VIDEO_MZ700'] = {'suc80_enabled': '1'}
    cfg['ROM'] = {
        'rom_type': 'USER_DEFINED', 'user_defined_allinone': '1',
        'user_defined_allinone_filepath': str(HERE / 'roms/stock-monitor-font.bin'),
        'boot_rom_mode': 'E800' if automatic else 'F000',
        'boot_rom_f000_filepath': str(HERE / 'roms/boot-f000.bin'),
        'boot_rom_e800_filepath': str(HERE / 'roms/boot-e800.bin'),
    }
    cfg['MEMEXT'] = {'connected': '1', 'type': 'PEHU', 'filling_on_init': 'NULL'}
    cfg['GIDE'] = {'enabled': '1', 'base': '0xa0', 'hdd0_filepath': str(disk),
                   'hdd0_readonly': str(int(readonly)), 'hdd1_filepath': '',
                   'hdd1_readonly': '1'}
    cfg['BREAKPOINTS'] = {'auto_save': '0', 'auto_load': '0'}
    cfg['DEBUGGER'] = {'auto_save_breakpoints': '0'}
    config = work / 'mz700.ini'
    with config.open('w') as dst:
        cfg.write(dst)
    return config


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--image', choices=['sharp-applications', 'keyboard-fast-factory'],
                    default='sharp-applications')
    ap.add_argument('--emulator', type=Path,
                    default=ROOT / 'build-mac/build-mz700emu-pal/mz700emu-pal')
    ap.add_argument('--work-dir', type=Path)
    ap.add_argument('--automatic', action='store_true', help='Use E800 automatic boot')
    ap.add_argument('--read-only', action='store_true')
    ap.add_argument('--prepare-only', action='store_true')
    args = ap.parse_args()
    work = (args.work_dir or ROOT / '.local/mz700-zpm3' / args.image).resolve()
    config = prepare(args.image, work, args.automatic, args.read_only)
    print(f'Working image: {work / "gide.img"}', flush=True)
    print('Press F, then Return at the Sharp monitor.' if not args.automatic
          else 'Automatic E800 boot selected.', flush=True)
    if args.prepare_only:
        return 0
    return subprocess.run([str(args.emulator.resolve()), '--home-dir', str(ROOT),
        '--cfg-dir', str(work), '--work-dir', str(work), '--config', str(config),
        '--no-first-run-windows']).returncode


if __name__ == '__main__':
    raise SystemExit(main())
