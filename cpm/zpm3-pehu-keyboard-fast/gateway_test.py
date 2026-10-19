#!/usr/bin/env python3
"""Compare PEHU BIOS console entry points with preserved original SUC oracle."""
from pathlib import Path
import sys,configparser,base64,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'archive-tools'));from test_mz800emu_boot import Emulator
sys.path.insert(0,str(ROOT/'cpm/suc-native'));from monitor_boot import reset_to_handover,enter_gide
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/gateways';out.mkdir(parents=True,exist_ok=True)
build=json.loads((HERE/'build/build.json').read_text());sym=build['symbols'];common=build['common_base']
c=configparser.ConfigParser(interpolation=None);c.read(ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/interactive-0.1.0/mz700.ini');c['GIDE']['hdd0_filepath']=str(HERE/'build/gide-zpm3-pehu-keyboard-fast.img');c['GIDE']['hdd0_readonly']='1';c['DEBUGGER']['auto_save_breakpoints']='0'
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
checks=[]
try:
 reset_to_handover(call);enter_gide(call);run(500)
 for stack in [0x1e00,0x7000,build['resident_bdos_base']-1024-16]:
  for iff in [0,1]:
   body=f"""DI
LD SP,0x1f00
LD A,1
CALL {build['common_symbols']['selmem']}
LD SP,{stack}
LD BC,0x1234
LD DE,0x5678
LD HL,0x9abc
LD IX,0x1357
LD IY,0x2468
{('EI' if iff else 'DI')}
CALL {common+6}
LD (0x1c00),BC
LD (0x1c02),DE
LD (0x1c04),HL
LD (0x1c06),IX
LD (0x1c08),IY
LD (0x1c0a),SP
LD A,I
PUSH AF
POP BC
LD (0x1c0c),BC
DI
LD A,1
LD (0x1c20),A
HALT
JR $-1
"""
   assemble_run(body,f'callback-{stack:x}-{iff}');data=physical(0x1c00,14,True)
   assert data[:10]==bytes.fromhex('34127856bc9a57136824'),data.hex()
   assert int.from_bytes(data[10:12],'little')==stack,data.hex()
   assert bool(data[12]&4)==bool(iff),data.hex()
   assert physical(build['common_symbols']['current_bank'],1,True)==b'\x01',(stack,iff,physical(build['common_symbols']['current_bank'],1,True).hex(),call('get_registers'))
   checks.append(dict(test='callback',stack=stack,iff=iff,passed=True))
 # Private masked mapper preserves AF/BC/DE/HL and SP, leaves IFF disabled,
 # and restores all actual pages even if current_bank already matches A.
 for initial_bank in [0,1]:
  for requested_bank in [0,1]:
   for flags in [0,1,0x44,0xD7]:
    body=f"""LD SP,0x1f00
LD A,{initial_bank}
CALL {build['common_symbols']['selmem']}
LD BC,0x20e7
LD A,16
OUT (C),A
LD B,0x40
INC A
OUT (C),A
LD HL,{requested_bank*256+flags}
PUSH HL
POP AF
LD BC,0x1234
LD DE,0x5678
LD HL,0x9abc
CALL {build['common_symbols']['bank_force_masked']}
LD (0x1c06),HL
PUSH AF
POP HL
LD (0x1c00),HL
LD (0x1c02),BC
LD (0x1c04),DE
LD (0x1c08),SP
LD A,I
PUSH AF
POP BC
LD (0x1c0a),BC
LD A,1
LD (0x1c20),A
HALT
JR $-1
"""
    assemble_run(body,f'masked-{initial_bank}-{requested_bank}-{flags}')
    data=physical(0x1c00,12,False)
    assert data[:10]==bytes([flags,requested_bank])+bytes.fromhex('34127856bc9a001f'),data.hex()
    assert not(data[10]&4),data.hex()
    assert physical(build['common_symbols']['current_bank'],1,False)==bytes([requested_bank])
    for window in range(0x2000,0xc000,0x2000):
     assert base64.b64decode(call('mem_read',{'addr':window,'len':16})['data_b64'])==physical(window,16,bool(requested_bank)),('masked mapping',initial_bank,requested_bank,window)
    checks.append(dict(test='private_masked_mapper',initial_bank=initial_bank,requested_bank=requested_bank,flags=flags,passed=True))
 for source_bank,dest_bank,src,dst,count in [(0,1,0x2fc0,0x7fc0,256),(1,0,0x7fc0,0x2fc0,256),(0,1,0x1fc0,0xbfc0,128),(1,0,0xbfc0,0x1fc0,128),(0,1,0x5000,0xcfc0,128),(0,1,0x5000,0x6000,0)]:
  pattern=bytes((i*17+43)&255 for i in range(count));write(src,pattern,bool(source_bank));before=physical(dst,max(1,count),bool(dest_bank))
  body=f"""DI
LD SP,0x1e00
LD A,1
CALL {build['common_symbols']['selmem']}
LD B,{dest_bank}
LD C,{source_bank}
CALL {common+87}
LD HL,{dst}
LD DE,{src}
LD BC,{count}
CALL {common+75}
LD (0x1c00),HL
LD (0x1c02),DE
LD (0x1c04),BC
LD A,1
LD (0x1c20),A
HALT
JR $-1
"""
  assemble_run(body,f'move-{len(checks)}');result=physical(0x1c00,6,True)
  assert result==(dst+count).to_bytes(2,'little')+(src+count).to_bytes(2,'little')+b'\x00\x00',result.hex()
  assert physical(dst,max(1,count),bool(dest_bank))==(pattern if count else before)
  assert physical(build['common_symbols']['current_bank'],1,True)==b'\x01',(stack,iff,physical(build['common_symbols']['current_bank'],1,True).hex(),call('get_registers'))
  checks.append(dict(test='xmove',source_bank=source_bank,destination_bank=dest_bank,source=src,destination=dst,bytes=count,passed=True))
 (out/'result.json').write_text(json.dumps(dict(passed=True,checks=checks),indent=2)+'\n');print('PASS',len(checks),'gateway and cross-bank cases')
finally:e.close()
