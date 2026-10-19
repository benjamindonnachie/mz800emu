"""Native exhaustive scanner comparison and matched keyboard CPU timings."""
from pathlib import Path
import base64
import configparser
import csv
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'build-records/mz800emu/zpm3-pehu-keyboard-fast/keyboard-performance'
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT / 'archive-tools'), str(ROOT / 'cpm/suc-native')]
from test_mz800emu_boot import Emulator
from monitor_boot import reset_to_handover, enter_gide

variants = [
    ('baseline', HERE / 'reference/performance-baseline',
     HERE / 'reference/performance-baseline/profile.ini', 'gide-zpm3-pehu-screen-fast'),
    ('fast', HERE,
     ROOT / 'build-records/mz800emu/zpm3-pehu-keyboard-fast/interactive-0.1.0/mz700.ini',
     'gide-zpm3-pehu-keyboard-fast')]
results = []
contracts = {}

for variant, folder, profile, stem in variants:
    for repeat in range(1, 4):
        dest = OUT / f'{variant}-{repeat}'
        dest.mkdir(exist_ok=True)
        build = json.loads((folder / 'build/build.json').read_text())
        symbols = build['symbols']
        common = build['common_symbols']
        leaf = symbols['suc_blob'] + 105
        state = symbols['suc_state']
        config = configparser.ConfigParser(interpolation=None)
        config.read(profile)
        config['GIDE']['hdd0_filepath'] = str(folder / 'build' / (stem + '.img'))
        config['GIDE']['hdd0_readonly'] = '1'
        config['ROM']['user_defined_allinone_filepath'] = str(folder / 'build' / (stem + '-stock-rom.bin'))
        config['ROM']['boot_rom_f000_filepath'] = str(folder / 'build' / (stem + '-bootrom.bin'))
        config['ROM']['boot_rom_mode'] = 'F000'
        config['DEBUGGER']['auto_save_breakpoints'] = '0'
        for path in dest.glob('*.bpt'):
            path.unlink()
        with (dest / 'input.ini').open('w') as stream:
            config.write(stream)
        emulator = Emulator(ROOT / 'emulators/Working/mz800emu/build-mac/build-mz700emu-pal/mz700emu-pal',
                            dest, ['--home-dir', str(ROOT / 'emulators/Working/mz800emu'),
                                   '--config', str(dest / 'input.ini')])

        def call(command, data=None):
            result = emulator.call(command, data)
            assert result.get('success'), result
            return result.get('data', {})

        def physical(address, length):
            result = bytearray()
            while length:
                amount = min(length, 4096 - (address & 4095))
                region = next(r['id'] for r in call('regions_list')['regions']
                              if r['kind'] == 'memext_ram' and r['sub_id'] == address // 4096)
                result += base64.b64decode(call('region_read', {
                    'region_id': region, 'offset': address & 4095, 'length': amount})['data_b64'])
                address += amount
                length -= amount
            return bytes(result)

        def write(address, payload):
            while payload:
                amount = min(len(payload), 4096 - (address & 4095))
                region = next(r['id'] for r in call('regions_list')['regions']
                              if r['kind'] == 'memext_ram' and r['sub_id'] == address // 4096)
                call('region_write', {'region_id': region, 'offset': address & 4095,
                                     'data_b64': base64.b64encode(payload[:amount]).decode()})
                address += amount
                payload = payload[amount:]

        def assemble(text, name):
            path = dest / (name + '.asm')
            path.write_text(text)
            subprocess.run([sys.executable, str(ROOT / 'cpm/gide/third_party/pyz80.py'),
                            '--obj=' + str(path.with_suffix('.bin')),
                            '--mapfile=' + str(path.with_suffix('.map')), str(path)],
                           check=True, stdout=subprocess.DEVNULL)
            labels = {n: int(a, 16) for a, n in
                      (line.split('=', 1) for line in path.with_suffix('.map').read_text().splitlines())}
            return path.with_suffix('.bin').read_bytes(), labels

        prefix = f'''ORG 0x1000
 DI
 OUT (0xE1),A
 LD SP,0x1f00
 XOR A
 CALL {common['selmem']}
'''
        row = dict(variant=variant, repeat=repeat, tpa_bytes=build['zccp_tpa_bytes'], segments={})
        assert row['tpa_bytes'] == 60672
        try:
            reset_to_handover(call)
            enter_gide(call)
            call('run', {'frames': 700})
            for name, count, pending in [('raw_word_load', 10000, None),
                                         ('empty_const', 2000, False),
                                         ('pending_const', 2000, True)]:
                setup = prefix + f' CALL {symbols["keyboard_init"]}\n XOR A\n'
                setup += f' LD ({symbols["cursor_visible"]}),A\n LD ({symbols["cursor_drawn"]}),A\n'
                if pending:
                    setup += f' LD HL,0x0500\n LD ({state + 29}),HL\n'
                if pending is not None:
                    setup += f' LD A,1\n CALL {common["selmem"]}\n LD SP,0x7000\n'
                setup += f' LD BC,{count}\nstart:\n CALL {leaf if pending is None else build["common_base"] + 6}\n'
                if pending is not None:
                    setup += (' CP 255\n' if pending else ' OR A\n') + ' JP NZ,failed\n'
                source = setup + ''' DEC BC
 LD A,B
 OR C
 JP NZ,start
end:
 HALT
 JP end
failed:
 HALT
 JP failed
'''
                blob, labels = assemble(source, name)
                write(0x1000, blob)
                first = call('bp_add', {'addr': labels['start']})['id']
                call('set_register', {'reg': 'PC', 'value': 0x1000})
                call('run', {'frames': 20})
                assert call('get_registers')['PC'] == labels['start']
                call('bp_remove', {'id': first})
                stop = call('bp_add', {'addr': labels['end']})['id']
                start_cycles = call('get_raster_pos')['total_cycles']
                call('profiler_pc_start', {'reset': True})
                for _ in range(200):
                    call('run', {'frames': 100})
                    pc = call('get_registers')['PC']
                    assert pc != labels['failed'], (variant, name, 'unexpected keyboard status')
                    if pc == labels['end']:
                        break
                assert pc == labels['end'], (name, 'timeout')
                elapsed = (call('get_raster_pos')['total_cycles'] - start_cycles) & 0xffffffff
                call('profiler_pc_stop')
                call('profiler_pc_export', {'path': str(dest / (name + '.csv')), 'sort': 'addr'})
                leaf_profile = call('profiler_pc_get', {'from': leaf, 'to': leaf, 'limit': 1})
                invocations = sum(r['count'] for r in leaf_profile['rows'])
                assert invocations == count, (name, invocations, count)
                row['segments'][name] = dict(tstates=elapsed, invocations=invocations,
                                             tstates_per_invocation=elapsed / count)
                profile_rows = list(csv.DictReader((dest / (name + '.csv')).open()))
                body_cycles = sum(int(r['tstates']) for r in profile_rows
                                  if leaf <= int(r['pc'], 16) < leaf + 8)
                row['segments'][name].update(leaf_body_tstates=body_cycles,
                    leaf_body_tstates_per_invocation=body_cycles / count)
                call('bp_remove', {'id': stop})

            if repeat == 1:
                # Exercise all 65,536 words in the real emulated CPU. The
                # original DE and candidate DE may differ; compare A/F exactly.
                source = prefix + f'''high_value:
 LD B,0
 LD C,0
 LD HL,0x1400
loop:
 LD ({state + 29}),BC
 LD DE,0x5678
 CALL {leaf}
 LD (HL),A
 INC HL
 PUSH AF
 POP DE
 LD (HL),E
 INC HL
 INC C
 JR NZ,loop
 LD (0x1c00),BC
 LD (0x1c02),HL
 LD (0x1c04),SP
 LD A,1
 LD (0x1c20),A
 HALT
 JR $-1
'''
                blob, labels = assemble(source, 'all-words')
                write(0x1000, blob)
                pairs = bytearray()
                for high in range(256):
                    write(labels['high_value'] + 1, bytes([high]))
                    write(0x1c20, b'\0')
                    call('set_register', {'reg': 'PC', 'value': 0x1000})
                    call('run', {'frames': 2})
                    assert physical(0x1c20, 1) == b'\1', (variant, high, 'leaf timeout')
                    assert physical(0x1c00, 6) == bytes([0, high, 0, 0x16, 0, 0x1f])
                    output = physical(0x1400, 512)
                    assert output[::2] == bytes((low - high) & 255 for low in range(256))
                    pairs += output
                (dest / 'all-word-af.bin').write_bytes(pairs)
                contracts[variant] = pairs
                row['exhaustive_words'] = 65536
                row['af_sha256'] = hashlib.sha256(pairs).hexdigest()
            (dest / 'result.json').write_text(json.dumps(row, indent=2) + '\n')
            results.append(row)
            print(variant, repeat, row['segments'], flush=True)
        finally:
            emulator.close()

assert contracts['baseline'] == contracts['fast']
comparison = {}
for name in results[0]['segments']:
    numbers = {}
    for variant in ('baseline', 'fast'):
        values = {r['segments'][name]['tstates'] for r in results if r['variant'] == variant}
        assert len(values) == 1, (name, variant, values)
        numbers[variant] = values.pop()
    count = results[0]['segments'][name]['invocations']
    comparison[name] = dict(baseline_tstates=numbers['baseline'], fast_tstates=numbers['fast'],
        invocations=count, total_saved_tstates=numbers['baseline'] - numbers['fast'],
        saved_tstates_per_invocation=(numbers['baseline'] - numbers['fast']) / count,
        cycle_reduction_percent=100 * (1 - numbers['fast'] / numbers['baseline']))
    comparison[name]['leaf_body_tstates_per_invocation'] = {
        variant: next(r['segments'][name]['leaf_body_tstates_per_invocation']
                      for r in results if r['variant'] == variant)
        for variant in ('baseline', 'fast')}
summary = dict(passed=True, exhaustive_words=65536, exact_a_and_all_flags_equal=True,
    bc_hl_sp_preserved=True, leaf_de_change_allowed=True,
    leaf_cycle_saving=17, slot_bytes=8, comparison=comparison, results=results,
    method='Three fresh emulator processes per build. Breakpoint-delimited CPU cycles; leaf calls counted. Cursor disabled, no host keys during timing. Raw leaf and public CONST no-input/queued-input paths. Synthetic queued word0500h. Read-only disks. Not physical-hardware or host timings.')
(OUT / 'results.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(comparison, indent=2))
