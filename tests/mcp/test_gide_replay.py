#!/usr/bin/env python3
"""SUC replay round-trip and explicit exclusion of uncaptured GIDE media/RTC."""
import json
import os
from pathlib import Path
import tempfile

import emu_test_proc
from test_suc80_display import Emu

REPO = Path(__file__).resolve().parents[2]


def main():
    emu_test_proc.install(deadline_s=90)
    exe = Path(os.environ.get('MZ_EMU', REPO / 'build-mac/build-mz700emu-pal/mz700emu-pal')).resolve()
    if not exe.is_file():
        return 77
    work = Path(tempfile.mkdtemp(prefix='mz700-gide-replay-'))
    record = work / 'suc80.mzr'
    e = Emu(exe, work / 'suc80', True)
    try:
        e.mode(0xe00c, 0x50)
        started = e.call('replay_record_start', {'path': str(record), 'hash_interval': 10,
                                               'final_hash': True})
        assert started['mode'] == 'recording', started
        e.call('run', {'frames': 30})
        e.call('replay_record_stop')
        e.call('replay_play', {'path': str(record), 'pause_after_load': True})
        e.call('run', {'frames': 100})
        status = e.call('replay_status')
        assert status['outcome'] == 'ended' and not status['deviated'], status
    finally:
        e.close()
    blocked = work / 'blocked.mzr'
    e = Emu(exe, work / 'gide', True,
            '[VIDEO_MZ700]\nsuc80_enabled=1\n[GIDE]\nenabled=1\nbase=0xa0\n')
    try:
        for cmd, data in [('replay_record_start', {'path': str(blocked)}),
                          ('replay_play', {'path': str(record)})]:
            try:
                e.call(cmd, data)
            except AssertionError as error:
                assert 'GIDE is fitted' in str(error), error
            else:
                raise AssertionError(cmd + ' unexpectedly accepted fitted GIDE')
        assert not blocked.exists(), 'Rejected recording created a file'
        assert e.call('replay_status')['mode'] == 'off'
    finally:
        e.close()
    (work / 'result.json').write_text(json.dumps(dict(passed=True,
        suc80_replay=True, fitted_gide_record_rejected=True,
        fitted_gide_play_rejected=True, no_record_file_created=True), indent=2))
    print('PASS: SUC80 replay and fitted-GIDE record/play exclusion; evidence:', work)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
