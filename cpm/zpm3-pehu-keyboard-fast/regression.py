#!/usr/bin/env python3
from pathlib import Path
import base64,configparser,json,shutil,sys,subprocess,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'archive-tools'));from test_mz800emu_boot import Emulator
sys.path.insert(0,str(ROOT/'cpm/suc-native'));from monitor_boot import reset_to_handover,enter_gide
sys.path.insert(0,str(ROOT/'cpm/gide/tools'));from media import SharpDSK,floppy,hard_volume
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/regression';out.mkdir(parents=True,exist_ok=True)
c=configparser.ConfigParser(interpolation=None);c.read(ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/interactive-0.1.0/mz700.ini')
shutil.copyfile(HERE/'build/gide-zpm3-pehu-keyboard-fast.img',out/'disk.img');c['GIDE']['hdd0_filepath']=str(out/'disk.img')
c['DEBUGGER']['auto_save_breakpoints']='0'
for p in out.glob('*.bpt'):p.unlink()
build=json.loads((HERE/'build/build.json').read_text());ceiling=build['resident_bdos_base']-1024
(out/'probe.asm').write_text(f'TPA_CEILING: EQU {ceiling}\n'+(HERE/'probe.asm').read_text())
subprocess.run([sys.executable,str(ROOT/'cpm/gide/third_party/pyz80.py'),'--obj='+str(out/'probe.com'),str(out/'probe.asm')],check=True,stdout=subprocess.DEVNULL)
image=bytearray((out/'disk.img').read_bytes())
for start in [0,8388608]:
 part=image[start:start+8388608];vv=hard_volume(part)
 for index,_ in vv.matching('GIDETST.BIN'):part[vv.offset+index*32]=0xe5
 image[start:start+8388608]=part
part=image[:8*1024*1024];v=hard_volume(part);v.write('PEHUTEST.COM',(out/'probe.com').read_bytes());image[:8*1024*1024]=part;(out/'disk.img').write_bytes(image)
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
checks=[]
try:
 reset_to_handover(call);enter_gide(call);run(500);assert 'C0>' in screen(),screen();checks.append('Sharp monitor F boot and retained load map')
 enter('PEHUTEST',1500)
 result=mem(0x6000,9);print('probe',result.hex(),screen()[-500:],flush=True)
 assert result[:2]==b'\x31\x00',result.hex()
 assert int.from_bytes(result[2:4],'little')==ceiling+6,result.hex()
 assert result[4:8]==bytes([79,0,24,0]),result.hex()
 assert result[8]==1,result.hex()
 assert mem(0x6010,17)==bytes.fromhex('8000051f01ff07ff01f000008000000203'),mem(0x6010,17).hex()
 checks.extend(['BDOS12=0031',f'{(ceiling-256)/1024}KiB application TPA','80x25 SCB','C/D sequential I/O with application stack7000, FCB8A00 and eight DMA placements spanning page/bank/VRAM/MMIO boundaries'])
 data=(out/'disk.img').read_bytes()
 for idx in range(2):
  v=hard_volume(bytearray(data[idx*8*1024*1024:(idx+1)*8*1024*1024]));expected=b''.join(bytes(((17*n+i+3+idx)&255) for i in range(128)) for n in range(8));assert v.read('PEHUTST.BIN')==expected
 checks.append('Independent host verification of every byte on both drives')
 for cmd in ['DIR C: [NOPAGE]','DIR D: [NOPAGE]','DIR [FULL,NOPAGE]','SHOW','VERS3','MC4']:
  enter(cmd);assert 'C0>' in screen(),(cmd,screen())
 assert mem(0x8000,2)==b'\x31\x00'
 checks.append('DIR, DIR[FULL], SHOW, VERS3, multi-record selection and repeated warm boots')
 enter('PIP');enter('D:=C:PEHUTST.BIN');enter('');enter('VERS3');assert mem(0x8000,2)==b'\x31\x00'
 data=(out/'disk.img').read_bytes();cvol=hard_volume(bytearray(data[:8*1024*1024]));dvol=hard_volume(bytearray(data[8*1024*1024:16*1024*1024]));assert dvol.read('PEHUTST.BIN')==cvol.read('PEHUTST.BIN')
 checks.append('Newer PIP interactive copy and blank Return exit; host-verified copy')
 for drive in 'CD':
  # Existing baseline executables exercise600 records and BDOS44 on real CCP.
  for verify in (False,True):
   rid=next(x['id'] for x in call('regions_list')['regions'] if x['kind']=='memext_ram' and x['sub_id']==0x18)
   call('region_write',{'region_id':rid,'offset':2,'data_b64':'AA=='})
   enter('C:TEST'+drive+(' V' if verify else ''),2000)
   for attempt in range(120):
    if mem(0x8002,1)!=b'\x00':break
    run(250)
   assert mem(0x8002,1)==b'\x01',(drive,verify,mem(0x8002,1).hex(),screen())
   run(500)
  raw=(out/'disk.img').read_bytes();start=(ord(drive)-67)*8*1024*1024;v=hard_volume(bytearray(raw[start:start+8*1024*1024]));expected=b''.join(bytes((n&255,n>>8))+bytes(((n&255)+(n>>8)+i)&255 for i in range(2,128)) for n in range(600));assert v.read('GIDETST.BIN')==expected
 checks.append('600-record C/D write/read and repeat verification through baseline TESTC/TESTD; host checked all153600bytes')
 call('screenshot_save_to_file',{'path':str(out/'ready.png'),'scale':'2'});(out/'screen.txt').write_text(screen()+'\n')
 (out/'result.json').write_text(json.dumps(dict(passed=True,checks=checks,probe=result.hex(),tpa_bytes=ceiling-256),indent=2)+'\n');print('PASS',checks)
finally:e.close()
