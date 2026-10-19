#!/usr/bin/env python3
"""Compare PEHU BIOS console entry points with preserved original SUC oracle."""
from pathlib import Path
import sys,configparser,base64,json,subprocess,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'archive-tools'));from test_mz800emu_boot import Emulator
sys.path.insert(0,str(ROOT/'cpm/suc-native'));from monitor_boot import reset_to_handover,enter_gide
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/native-transfer';out.mkdir(parents=True,exist_ok=True)
build=json.loads((HERE/'build/build.json').read_text());sym=build['symbols'];common=build['common_base']
c=configparser.ConfigParser(interpolation=None);c.read(ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/interactive-0.1.0/mz700.ini');shutil.copyfile(HERE/'build/gide-zpm3-pehu-keyboard-fast.img',out/'disk.img');c['GIDE']['hdd0_filepath']=str(out/'disk.img');c['GIDE']['hdd0_readonly']='0';c['DEBUGGER']['auto_save_breakpoints']='0'
for p in out.glob('*.bpt'):p.unlink()
with (out/'input.ini').open('w') as f:c.write(f)
source=f'''ORG 0x4000
DI
LD SP,0x7000
LD HL,0x5000
LD (pointer),HL
LD HL,0
LD (0x5FF0),HL
loop:
CALL {common+6}
OR A
JR Z,loop
CALL {common+9}
LD HL,(pointer)
LD (HL),A
INC HL
LD (pointer),HL
LD HL,(0x5FF0)
INC HL
LD (0x5FF0),HL
JR loop
pointer: DW 0
'''
(out/'harness.asm').write_text(source)
subprocess.run([sys.executable,str(ROOT/'cpm/gide/third_party/pyz80.py'),'--obj='+str(out/'harness.bin'),str(out/'harness.asm')],check=True,stdout=subprocess.DEVNULL)
e=Emulator(ROOT/'emulators/Working/mz800emu/build-mac/build-mz700emu-pal/mz700emu-pal',out,['--home-dir',str(ROOT/'emulators/Working/mz800emu'),'--config',str(out/'input.ini')])
def call(c,d=None):
 r=e.call(c,d);assert r.get('success'),r;return r.get('data',{})
def run(n):call('run',{'frames':n})
def physical(a,n,app):
 data=bytearray()
 while n:
  pa=a+(0x10000 if app and 0x2000<=a<0xc000 else 0);k=min(n,4096-(a&4095))
  rid=next(x['id'] for x in call('regions_list')['regions'] if x['kind']=='memext_ram' and x['sub_id']==pa//4096)
  data+=base64.b64decode(call('region_read',{'region_id':rid,'offset':pa&4095,'length':k})['data_b64']);a+=k;n-=k
 return bytes(data)
def write(a,data,app):
 while data:
  pa=a+(0x10000 if app and 0x2000<=a<0xc000 else 0);k=min(len(data),4096-(a&4095));rid=next(x['id'] for x in call('regions_list')['regions'] if x['kind']=='memext_ram' and x['sub_id']==pa//4096)
  call('region_write',{'region_id':rid,'offset':pa&4095,'data_b64':base64.b64encode(data[:k]).decode()});a+=k;data=data[k:]
def key(k):call('input_send_key',{'key':k,'frames':15});run(15)
def text(t):call('input_send_keys',{'text':t,'frame_per_key':15});run(15)
def assemble_run(body,tag):
 source=out/(tag+'.asm');source.write_text('ORG 0x1000\nDI\nOUT (0xE1),A\n'+body)
 subprocess.run([sys.executable,str(ROOT/'cpm/gide/third_party/pyz80.py'),'--obj='+str(source.with_suffix('.bin')),str(source)],check=True,stdout=subprocess.DEVNULL)
 write(0x1000,source.with_suffix('.bin').read_bytes(),True);write(0x1c20,b'\x00',True);call('set_register',{'reg':'PC','value':0x1000});run(30);assert physical(0x1c20,1,True)==b'\x01',(tag,call('get_registers'))
before=(out/'disk.img').read_bytes();pattern=bytes((i*29+7)&255 for i in range(512))
try:
 reset_to_handover(call);enter_gide(call);run(500)
 write(0x3fc0,pattern,True)
 no_read=call('bp_add',{'addr':sym['ata_read']})['id']
 body=f"""DI
LD SP,0x1e00
LD A,1
CALL {build['common_symbols']['selmem']}
LD C,2
LD E,0
CALL {common+27}
LD BC,511
CALL {common+30}
LD BC,31
CALL {common+33}
LD BC,0x3fc0
CALL {common+36}
LD A,1
CALL {common+84}
LD C,0
CALL {common+42}
LD (0x1c21),A
LD A,1
LD (0x1c20),A
HALT
JR $-1
"""
 assemble_run(body,'write512');assert physical(0x1c21,1,True)==b'\x00';call('bp_remove',{'id':no_read})
 for bank,target in [(1,0xbfc0),(0,0x4fc0)]:
  write(target,b'\x00'*512,bool(bank))
  body=f"""DI
LD SP,0x1e00
LD A,1
CALL {build['common_symbols']['selmem']}
LD BC,{target}
CALL {common+36}
LD A,{bank}
CALL {common+84}
CALL {common+39}
LD (0x1c21),A
LD A,1
LD (0x1c20),A
HALT
JR $-1
"""
  assemble_run(body,f'read512-bank{bank}');assert physical(0x1c21,1,True)==b'\x00';assert physical(target,512,bool(bank))==pattern
  assert physical(build['common_symbols']['current_bank'],1,True)==b'\x01'
finally:e.close()
after=(out/'disk.img').read_bytes();at=16383*512
assert after[at:at+512]==pattern
assert after[:at]==before[:at] and after[at+512:]==before[at+512:]
(out/'result.json').write_text(json.dumps(dict(passed=True,physical_sector_bytes=512,write_read_before_write=False,read_entry_breakpoint_not_hit_during_write=True,app_dma_write='3FC0-41BF',app_dma_read='BFC0-C1BF',system_dma_read='4FC0-51BF',all_other_sectors_unchanged=True,dma_bank_restored=True),indent=2)+'\n')
print('PASS direct512-byte ATA transfers in both DMA banks, no read-before-write, all other sectors unchanged')
