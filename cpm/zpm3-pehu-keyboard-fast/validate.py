"""Run native regressions sequentially, preserving evidence and failures."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'build-records/mz800emu/zpm3-pehu-keyboard-fast'
SUITES = [
    ('boot', 'boot_test.py'), ('regression', 'regression.py'),
    ('fresh-verify', 'fresh_verify.py'), ('keyboard', 'keyboard_test.py'),
    ('gateways', 'gateway_test.py'), ('sector-boundaries', 'sector_test.py'),
    ('native-transfer', 'native_transfer_test.py'),
    ('identity-history', 'identity_test.py'), ('rtc', 'rtc_test.py'),
    ('rtc-command', 'rtc_command_test.py'), ('zccp-shell', 'shell_test.py'),
    ('user-areas', 'user_area_test.py'), ('copy-contract', 'copy_test.py'),
    ('terminal-contract', 'terminal_test.py')]
logs = OUT / 'suite-logs'
logs.mkdir(parents=True, exist_ok=True)
results = {'system_suites': {}, 'application_suites': {}}

def run(name, script, args=()):
    path = logs / (name + '.log')
    print('RUN', name, flush=True)
    with path.open('w') as stream:
        process = subprocess.run([sys.executable, str(HERE / script), *args],
                                 stdout=stream, stderr=subprocess.STDOUT)
    if process.returncode:
        text = path.read_text()[-8000:]
        bugpath = ROOT / '.wolf/buglog.json'
        bugs = json.loads(bugpath.read_text())
        number = max(int(b['id'].split('-')[-1]) for b in bugs['bugs']) + 1
        now = datetime.datetime.now().astimezone().isoformat()
        bugs['bugs'].append(dict(id=f'bug-{number:03d}', timestamp=now,
            error_message=text, file=str(path.relative_to(ROOT)),
            root_cause='Native trial regression failed; investigation pending.',
            fix='Pending investigation; trial has not been validated.',
            tags=['keyboard-fast', 'regression', name], related_bugs=[],
            occurrences=1, last_seen=now))
        bugpath.write_text(json.dumps(bugs, indent=2) + '\n')
        print(text, flush=True)
        raise SystemExit(process.returncode)
    print('PASS', name, flush=True)

for name, script in SUITES:
    run(name, script)
    result = json.loads((OUT / name / 'result.json').read_text())
    assert result['passed'], name
    results['system_suites'][name] = result
for name in ('basic', 'utilities', 'wordstar', 'compiler', 'database', 'spreadsheet'):
    run('application-' + name, 'apps_test.py', [name])
    result = json.loads((OUT / 'applications' / ('test-' + name) / 'result.json').read_text())
    assert result['passed'], name
    results['application_suites'][name] = result

baseline = json.loads((HERE / 'baseline.json').read_text())
assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
           for name, digest in baseline.items())
build = json.loads((HERE / 'build/build.json').read_text())
assert build['zccp_tpa_bytes'] == 60672
assert build['common_raw_bytes'] <= 2048 and build['native_bytes'] <= 6656
assert build['common_base'] == 0xF800 and build['resident_bdos_base'] == 0xF200
results.update(passed=True, version=build['version'], tpa_bytes=60672,
               common_bytes=build['common_raw_bytes'], native_bytes=build['native_bytes'],
               preserved_baseline_files=len(baseline), baseline_files_unchanged=True,
               status='Native regressions passed; see PERFORMANCE.json for separate timings.')
(HERE / 'VALIDATION.json').write_text(json.dumps(results, indent=2) + '\n')
print('PASS: 14 system + 6 application suites; baseline unchanged; TPA60672.', flush=True)
