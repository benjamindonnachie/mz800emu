#!/usr/bin/env python3
from pathlib import Path
import base64,configparser,json,shutil,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'archive-tools'));from test_mz800emu_boot import Emulator
sys.path.insert(0,str(ROOT/'cpm/suc-native'));from monitor_boot import reset_to_handover,enter_gide
sys.path.insert(0,str(ROOT/'cpm/gide/tools'));from media import SharpDSK,floppy
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/smoke';out.mkdir(parents=True,exist_ok=True)
c=configparser.ConfigParser(interpolation=None);c.read(ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/interactive-0.1.0/mz700.ini')
shutil.copyfile(HERE/'build/gide-zpm3-pehu-keyboard-fast.img',out/'disk.img');c['GIDE']['hdd0_filepath']=str(out/'disk.img')
c['DEBUGGER']['auto_save_breakpoints']='0'
for p in out.glob('*.bpt'):p.unlink()
with (out/'input.ini').open('w') as f:c.write(f)
original=floppy(SharpDSK((ROOT/'cpm/gide/reference/CPM7004.dsk').read_bytes()).logical()).read('PCPM.SYS');table=original[0xF3D6-0xC600:0xF4D6-0xC600];decode={table[x]:chr(x) for x in reversed(range(32,127))};decode[0]=' '
e=Emulator(ROOT/'emulators/Working/mz800emu/build-mac/build-mz700emu-pal/mz700emu-pal',out,['--home-dir',str(ROOT/'emulators/Working/mz800emu'),'--config',str(out/'input.ini')])
def call(c,d=None):
 r=e.call(c,d);assert r.get('success'),r;return r.get('data',{})
def mem(a,n):return base64.b64decode(call('mem_read',{'addr':a,'len':n})['data_b64'])
def screen():
 rid=next(x['id'] for x in call('regions_list')['regions'] if x['kind']=='vram_700_char')
 v=base64.b64decode(call('region_read',{'region_id':rid,'offset':0,'length':2048})['data_b64'])
 return '\n'.join(''.join(decode.get(v[(((i>>1)+(i&1))&1023)|((i&1)<<10)],'?') for i in range(row*80,(row+1)*80)).rstrip() for row in range(25)).rstrip()
try:
 reset_to_handover(call);enter_gide(call)
 for i in range(10):
  call('run',{'frames':100});s=screen();print(i,call('get_registers')['PC'],s[-500:],flush=True)
  if 'C0>' in s:break
 (out/'screen.txt').write_text(s+'\n');call('screenshot_save_to_file',{'path':str(out/'boot.png'),'scale':'2'})
 (out/'registers.json').write_text(json.dumps(call('get_registers'),indent=2)+'\n')
 call('snapshot_save',{'path':str(out/'boot.mzs')})
 print('vectors',mem(0,8).hex())
 assert 'C0>' in s,s
finally:e.close()
