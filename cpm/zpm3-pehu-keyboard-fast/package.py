#!/usr/bin/env python3
"""Preserve this trial and byte-compare a build from its source ZIP alone."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];BUILD=HERE/'build'
OUT=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/preservation/0.1.0';OUT.mkdir(parents=True,exist_ok=True)
inputs=[ROOT/x for x in [
 'cpm/cpm3-on2/reference/rmac.com','cpm/cpm3-on2/reference/scb.rel',
 'cpm/cpm3-on2/reference/utilities/gencpm.com','cpm/cpm3-on2/reference/utilities/ccp.com',
 'cpm/cpm3-on2/reference/upstream/cpm3src_unix.zip','cpm/cpm3-on2/toolchain/zxcc-0.5.7.tar.gz',
 'cpm/gide/third_party/pyz80.py','cpm/gide/tools/media.py','cpm/gide/reference/CPM7004.dsk',
 'cpm/suc-native/build.py','cpm/suc-native/monitor_boot.py','cpm/suc-native/build/cpmldr.com',
 'cpm/suc-native/build/cpmldr.sym','cpm/suc-native/build/cpm3.sys','cpm/suc-native/build/build.json',
 'build-records/mz800emu/roms/mz700-13a-eu-font-1e05.bin',
 'build-records/mz800emu/disks/gide-cpm3-suc-native-0.6.8.img',
 'build-records/mz800emu/cpm3-suc-native/interactive-0.6.8/mz700.ini',
 'emulators/Working/Start MZ-700 CP-M 3 - SUC Native.command',
 'emulators/Working/Start MZ-700 CP-M 3 PEHU Banked - TEST.command',
 'build-records/mz800emu/disks/gide-cpm3-pehu-banked-0.1.0.img',
 'build-records/mz800emu/cpm3-pehu-banked/interactive-0.1.0/mz700.ini',
 'cpm/pehu-banked/build/cpm3.sys','cpm/pehu-banked/build/bnkbios3.spr',
 'emulators/Start MZ-700 ZPM3 ZCCP PEHU Keyboard Fast - TEST.command',
 'emulators/Start MZ-700 ZPM3 ZCCP PEHU Screen Fast - TEST.command',
 'emulators/Working/Start MZ-700 ZPM3 ZCCP PEHU Move LDI - TEST.command',
 'emulators/Working/Start MZ-700 ZPM3 ZCCP PEHU Fast - TEST.command',
 'emulators/Working/Start MZ-700 ZPM3 ZCCP PEHU Direct - TEST.command',
 'emulators/Working/Start MZ-700 ZPM3 ZCCP PEHU Display LDI - TEST.command',
 'archive-tools/test_mz800emu_boot.py','build-records/mz800emu/cpm3-suc-native/keyboard/original/result.json']]
inputs+=sorted(p for p in HERE.rglob('*') if p.is_file() and 'build' not in p.relative_to(HERE).parts and '__pycache__' not in p.parts)
inputs+=list((HERE/'reference/performance-baseline/build').glob('*'))
def archive(path,files):
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(set(files)):z.write(p,p.relative_to(ROOT))
 with zipfile.ZipFile(path) as z:assert z.testzip() is None
source=OUT/'MZ700-ZPM3-PEHU-KEYBOARD-FAST-0.1.0-source.zip';archive(source,inputs)
rebuild=Path(tempfile.mkdtemp(prefix='mz-pehu-rebuild-',dir='/tmp'))
with zipfile.ZipFile(source) as z:z.extractall(rebuild)
for name in ['build.py','media.py']:
 cmd=[sys.executable,str(rebuild/'cpm/zpm3-pehu-keyboard-fast'/name)]
 if name=='build.py':cmd+=['--zxcc','/tmp/pehu-force-source-toolchain-not-present']
 p=subprocess.run(cmd,cwd=rebuild,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 (OUT/(name+'.rebuild.log')).write_bytes(p.stdout);assert p.returncode==0,p.stdout.decode(errors='replace')
outputs=['native-0.bin','common-0.bin','bnkbios3.spr','bnkbdos3.spr','resbdos3.spr','cpm3.sys','cpmldr.com','stage.bin','gide-zpm3-pehu-keyboard-fast-bootrom.bin','gide-zpm3-pehu-keyboard-fast-e800.bin','gide-zpm3-pehu-keyboard-fast-stock-rom.bin','GIDE-CPM3.MZF','gide-zpm3-pehu-keyboard-fast.img','RTC.COM','shell/CCP.COM','shell/ZCCP.COM','shell/ZINSTAL.ZPM','shell/STARTZPM.COM','shell/TCAP.Z3T','shell/TPA.COM','shell/TPATEST.COM','shell/reset-drive.bin']
comparison={}
for name in outputs:
 a=(BUILD/name).read_bytes();b=(rebuild/'cpm/zpm3-pehu-keyboard-fast/build'/name).read_bytes();assert a==b,name
 comparison[name]={'bytes':len(a),'sha256':hashlib.sha256(a).hexdigest(),'byte_identical':True}
(OUT/'clean-rebuild.json').write_text(json.dumps(dict(passed=True,source_zip_only=True,zxcc_built_from_source=True,outputs=comparison),indent=2)+'\n')
validation=json.loads((HERE/'VALIDATION.json').read_text());validation['source_package_rebuild']=json.loads((OUT/'clean-rebuild.json').read_text());(HERE/'VALIDATION.json').write_text(json.dumps(validation,indent=2)+'\n')
archive(source,inputs)
archive(OUT/'MZ700-ZPM3-PEHU-KEYBOARD-FAST-0.1.0-media.zip',[BUILD/n for n in outputs if (n.startswith('shell/') or n.endswith(('.img','.bin','.MZF','.COM'))) and not n.startswith(('native-','common-','stage'))])
evidence=[]
for folder in ['boot','regression','fresh-verify','keyboard','gateways','sector-boundaries','native-transfer','identity-history','rtc','rtc-command','zccp-shell','user-areas','copy-contract','terminal-contract']:
 evidence+=list((OUT.parents[1]/folder).glob('result.json'))
 evidence+=list((OUT.parents[1]/folder).glob('*.png'))
 evidence+=list((OUT.parents[1]/folder).glob('screen.txt'))
 evidence+=list((OUT.parents[1]/folder).glob('frames.json'))
evidence+=[p for p in (OUT.parents[1]/'applications').rglob('*') if p.is_file() and (p.name=='result.json' or p.suffix=='.png')]
evidence+=list((OUT.parents[1]/'benchmark').rglob('*.json'))+list((OUT.parents[1]/'benchmark').rglob('*.csv'))
evidence += [OUT.parents[1]/'media-preservation.json',OUT.parents[1]/'runtime-source.diff']
evidence += [OUT.parents[1]/'binary-change-audit.json']
evidence += [p for p in (OUT.parents[1]/'keyboard-performance').rglob('*') if p.is_file() and p.suffix in ('.json','.csv','.bin')]
archive(OUT/'MZ700-ZPM3-PEHU-KEYBOARD-FAST-0.1.0-evidence.zip',evidence+[HERE/'VALIDATION.json',OUT/'clean-rebuild.json',BUILD/'build.json',BUILD/'gencpm-transcript.txt'])
manifest={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in OUT.glob('*.zip')}
(OUT/'packages.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('PASS source-ZIP-only rebuild:',len(outputs),'byte-identical outputs; all ZIP CRCs pass')
