#!/usr/bin/env python3
"""Application-level regressions, including cold processes and host byte checks."""
from pathlib import Path
import hashlib,json,re,sys
from apps_session import Session,ROOT,hard_volume
OUT=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/applications'
case=sys.argv[1];evidence={};s=None
def volume(image):return hard_volume(bytearray(Path(image).read_bytes()[8388608:16777216]))
def result():
    evidence['passed']=True;(OUT/('test-'+case)/'result.json').write_text(json.dumps(evidence,indent=2)+'\n');print(case,'PASS',flush=True)
def compiler_prepare(image):
    raw=bytearray(image.read_bytes());part=raw[8388608:16777216];v=hard_volume(part)
    for i,e in v.directory():
        if e[0]==2 and v.name(e) in ['HELLO.COM','HELLO.CRL','IOCHECK.COM','IOCHECK.CRL','IOTEST.DAT']:part[v.offset+i*32]=0xe5
    raw[8388608:16777216]=part;image.write_bytes(raw)
try:
    s=Session('test-'+case,compiler_prepare if case=='compiler' else None)
    if case=='utilities':
        assert 'SuperCalc' in s.command('APPS')
        assert re.search(r'\n20\d\d-\d\d-\d\d \d\d:\d\d:\d\d\n',s.command('DATE'))
        assert 'Space:' in s.command('SHOW D:')
        assert s.screen().endswith('C0>')
        s.command('PIP D:APPSCP.TXT=C:APPS.TXT[V]',5000)
        assert 'file copy program' in s.command('HELP PIP [NOPAGE]')
        s.key('RETURN');s.run();assert s.screen().endswith('C0>')
        s.command('DUMP D:SHARP.TXT');assert '0000' in s.screen()
        s.screenshot('utilities');image=s.image;s.close();s=None
        assert volume(image).read('APPSCP.TXT')==(ROOT/'build-records/mz800emu/zpm3-pehu-fast-apps/payload/C/0/APPS.TXT').read_bytes().ljust((len((ROOT/'build-records/mz800emu/zpm3-pehu-fast-apps/payload/C/0/APPS.TXT').read_bytes())+127)//128*128,b'\x1a')
        evidence.update(clock='DATE alias queried live RTC',pip_verified=True,help=True,dump=True)
    elif case=='basic':
        s.command('D4:');assert 'BASIC-80 Rev. 5.21' in s.command('MBASIC')
        assert '\n 42' in s.command('PRINT 6*7');assert s.command('SYSTEM').endswith('D4>')
        s.command('C0:');assert '60672 bytes' in s.command('TPA')
        evidence.update(microsoft_basic='5.21',arithmetic=True,exit=True,tpa_bytes=60672)
    elif case=='compiler':
        s.command('D:');s.command('D2:')
        s.command('TPA')
        assert int.from_bytes(s.mem(0x8002,2),'little')==60672
        for source in ['HELLO','IOCHECK']:
            assert s.command('CC '+source+'.C',6000).endswith('D2>')
            assert s.command('CLINK '+source,6000).endswith('D2>')
        assert 'BDS C on Sharp MZ-700: PASS' in s.command('HELLO')
        assert 'IOCHECK PASS: 81920 bytes verified' in s.command('IOCHECK',20000)
        s.screenshot('native-compiler')
        text=s.command('SUBMIT BUILD',25000)
        assert 'IOCHECK PASS: 81920 bytes verified' in text and text.endswith('D2>')
        # The prompt retains a reclaimable loader prefix. Measure inside
        # the next transient, after the loader has reclaimed its workspace.
        s.command('TPA')
        entry=int.from_bytes(s.mem(0x8000,2),'little')
        assert entry==0xee00 and int.from_bytes(s.mem(0x8002,2),'little')==60672
        s.screenshot('submit');image=s.image;s.close();s=None
        data=volume(image).read('IOTEST.DAT',2)
        assert data==bytes((i+j)&255 for i in range(80) for j in range(1024))
        for name in ['HELLO.COM','HELLO.CRL','IOCHECK.COM','IOCHECK.CRL']:assert len(volume(image).read(name,2))>0
        s=Session('test-compiler-cold',source=image)
        s.command('TPA');assert int.from_bytes(s.mem(0x8002,2),'little')==60672
        evidence.update(native_compile_link_run=True,batch_compile_link_run=True,io_bytes=len(data),io_sha256=hashlib.sha256(data).hexdigest(),transient_bdos_entry_after_submit=f'{entry:04X}',application_tpa_after_submit=60672,cold_application_tpa=60672)
    elif case=='wordstar':
        s.command('D:');assert 'Sharp MZ-700' in s.command('WS SHARP.TXT')
        s.text('VERIFIED EDIT ');s.ctrl('K');s.text('X');s.run(4000);assert s.capture('save and exit').endswith('D0>')
        image=s.image;s.close();s=None
        saved=volume(image).read('SHARP.TXT');assert b'verified edit ' in bytes(x&127 for x in saved).lower()
        s=Session('test-wordstar-cold',source=image);s.command('D:');assert 'verified edit' in s.command('WS SHARP.TXT').lower();s.screenshot('reopened')
        s.ctrl('K');s.text('X');s.run(3000);assert s.capture('cold exit').endswith('D0>')
        evidence.update(edit_save_cold_reopen=True,document_sha256=hashlib.sha256(saved).hexdigest())
    elif case=='database':
        for command in ['D:','D1:','DBASE','','DO DEMO']:s.command(command,3000)
        assert re.search(r'\n\s*100\n',s.screen()),'Demo total not displayed'
        for command in ['CREATE VERIFY','NAME,C,20','SCORE,N,6,0','','N','USE VERIFY','APPEND BLANK','REPLACE NAME WITH "SHARP", SCORE WITH 42','APPEND BLANK','REPLACE NAME WITH "GIDE", SCORE WITH 58','INDEX ON NAME TO VERIFY','GO TOP','? NAME','SUM SCORE']:s.command(command,3000)
        assert 'gide' in s.screen().lower() and re.search(r'\n\s*100\n',s.screen())
        assert s.command('QUIT').endswith('D1>');image=s.image;s.close();s=None
        assert len(volume(image).read('VERIFY.DBF',1))>0 and len(volume(image).read('VERIFY.NDX',1))>0
        s=Session('test-database-cold',source=image)
        for command in ['D:','D1:','DBASE','','USE VERIFY INDEX VERIFY','LIST','SUM SCORE']:s.command(command,3000)
        assert 'sharp' in s.screen().lower() and 'gide' in s.screen().lower() and re.search(r'\n\s*100\n',s.screen())
        s.screenshot('reopened-index');assert s.command('QUIT').endswith('D1>')
        evidence.update(create_append_update_index_sum_cold_reopen=True,records=2,total=100)
    elif case=='spreadsheet':
        for command in ['D:','D3:','SC2',''] :s.command(command)
        for command in ['=A1','42','=A2','58','=A3','SUM(A1:A2)']:s.command(command)
        assert re.search(r'\n\s*3\|\s+100',s.screen())
        s.text('/S');s.run(500);s.command('LIVE');s.text('A');s.run(2000)
        s.command('/Q');assert s.command('Y').endswith('D3>');image=s.image;s.close();s=None
        data=volume(image).read('LIVE.CAL',3);assert data.startswith(b'SuperCalc')
        s=Session('test-spreadsheet-cold',source=image)
        for command in ['D:','D3:','SC2','']:s.command(command)
        s.text('/L');s.command('LIVE');s.text('A');s.run(2000)
        assert re.search(r'\n\s*3\|\s+100',s.capture('cold loaded sheet'))
        s.command('=A1');s.command('142');assert re.search(r'\n\s*3\|\s+200',s.screen())
        s.screenshot('recalculated');s.command('/Q');assert s.command('Y').endswith('D3>')
        evidence.update(formula=True,save_cold_reopen=True,initial_sum=100,recalculated_sum=200,sheet_sha256=hashlib.sha256(data).hexdigest())
    else:raise ValueError(case)
    result()
finally:
    if s:s.close()
