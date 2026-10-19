#!/usr/bin/env python3
from pathlib import Path
import base64,configparser,json,shutil,sys,subprocess,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'archive-tools'));from test_mz800emu_boot import Emulator
sys.path.insert(0,str(ROOT/'cpm/suc-native'));from monitor_boot import reset_to_handover,enter_gide
sys.path.insert(0,str(ROOT/'cpm/gide/tools'));from media import SharpDSK,floppy,hard_volume
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/user-areas';out.mkdir(parents=True,exist_ok=True)
c=configparser.ConfigParser(interpolation=None);c.read(ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/interactive-0.1.0/mz700.ini')
shutil.copyfile(HERE/'build/gide-zpm3-pehu-keyboard-fast.img',out/'disk.img');c['GIDE']['hdd0_filepath']=str(out/'disk.img')
c['DEBUGGER']['auto_save_breakpoints']='0'
c['GIDE']['hdd0_readonly']='1'
for p in out.glob('*.bpt'):p.unlink()
build=json.loads((HERE/'build/build.json').read_text());ceiling=build['resident_bdos_base']-1024
(out/'probe.asm').write_text(f'TPA_CEILING: EQU {ceiling}\n'+(HERE/'probe.asm').read_text())
subprocess.run([sys.executable,str(ROOT/'cpm/gide/third_party/pyz80.py'),'--obj='+str(out/'probe.com'),str(out/'probe.asm')],check=True,stdout=subprocess.DEVNULL)
image=bytearray((out/'disk.img').read_bytes());part=image[:8*1024*1024];v=hard_volume(part);v.write('PEHUTEST.COM',(out/'probe.com').read_bytes());image[:8*1024*1024]=part;(out/'disk.img').write_bytes(image)
with (out/'input.ini').open('w') as f:c.write(f)
original=floppy(SharpDSK((ROOT/'cpm/gide/reference/CPM7004.dsk').read_bytes()).logical()).read('PCPM.SYS');table=original[0xF3D6-0xC600:0xF4D6-0xC600];decode={table[x]:chr(x) for x in reversed(range(32,127))};decode[0]=' '
e=Emulator(ROOT/'emulators/Working/mz800emu/build-mac/build-mz700emu-pal/mz700emu-pal',out,['--home-dir',str(ROOT/'emulators/Working/mz800emu'),'--config',str(out/'input.ini')])
def call(c,d=None):
 r=e.call(c,d);assert r.get('success'),r;return r.get('data',{})
def mem(a,n):
 data=bytearray()
 while n:
  physical=a+(0x10000 if 0x2000<=a<0xc000 else 0)
  amount=min(n,4096-(a&4095))
  rid=next(x['id'] for x in call('regions_list')['regions'] if x['kind']=='memext_ram' and x['sub_id']==physical//4096)
  data+=base64.b64decode(call('region_read',{'region_id':rid,'offset':physical&4095,'length':amount})['data_b64'])
  a+=amount;n-=amount
 return bytes(data)

def screen():
 rid=next(x['id'] for x in call('regions_list')['regions'] if x['kind']=='vram_700_char')
 v=base64.b64decode(call('region_read',{'region_id':rid,'offset':0,'length':2048})['data_b64'])
 return '\n'.join(''.join(decode.get(v[(((i>>1)+(i&1))&1023)|((i&1)<<10)],'?') for i in range(row*80,(row+1)*80)).rstrip() for row in range(25)).rstrip()
def run(n):
 while n:k=min(n,1000);call('run',{'frames':k});n-=k
def enter(text,frames=500):
 call('input_send_keys',{'text':text,'frame_per_key':30});run(20);call('input_send_key',{'key':'RETURN','frames':30});run(frames)
before=hashlib.sha256((out/'disk.img').read_bytes()).hexdigest()
checks=[]
try:
 reset_to_handover(call);enter_gide(call);run(1300)
 for area in ['C1','C15','D1','D15','C0']:
  enter(area+':');assert area+'>' in screen(),(area,screen())
  for command in ['DIR [NOPAGE]','TPA','RTC']:
   enter(command,900)
   text=screen();(out/'latest.txt').write_text(text+'\n')
   assert 'PEHU BIOS: CCP load error' not in text,(area,command,text)
   assert text.splitlines()[-1].rstrip(' ?').endswith(area+'>'),(area,command,text)
   if command=='TPA':assert int.from_bytes(mem(0x8002,2),'little')==60672
   checks.append(dict(area=area,command=command))
 call('set_register',{'reg':'PC','value':0});run(1300);enter('TPA')
 assert 'C0>' in screen() and int.from_bytes(mem(0x8002,2),'little')==60672
 assert hashlib.sha256((out/'disk.img').read_bytes()).hexdigest()==before
 (out/'screen.txt').write_text(screen()+'\n');call('screenshot_save_to_file',{'path':str(out/'ready.png'),'scale':'2'})
 (out/'result.json').write_text(json.dumps(dict(passed=True,checks=checks,boot_user=0,warm_command_user_preserved=True,c0_lookup_from_other_users=True,readonly_image_unchanged=True,tpa_bytes=60672),indent=2)+'\n')
 print('PASS user areas C1/C15/D1/D15/C0: DIR,TPA,RTC preserve user and reload CCP from C0')
finally:e.close()
