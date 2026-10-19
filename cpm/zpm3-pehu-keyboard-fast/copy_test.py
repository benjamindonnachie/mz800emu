#!/usr/bin/env python3
"""Compare PEHU BIOS console entry points with preserved original SUC oracle."""
from pathlib import Path
import sys,configparser,base64,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'archive-tools'));from test_mz800emu_boot import Emulator
sys.path.insert(0,str(ROOT/'cpm/suc-native'));from monitor_boot import reset_to_handover,enter_gide
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/copy-contract';out.mkdir(parents=True,exist_ok=True)
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
checks=[];max_stack=0
cases=[]
for size in [0,1,15,16,17,31,32,33,63,64,65,127,128,129,511,512,513,4096,8191,8192,8193]:
 cases.extend([(0,1,0x2fc0,0x7fc0,size),(1,0,0x7fc0,0x2fc0,size)])
cases += [(0,0,0x3000,0x4000,512),(1,1,0x3000,0x4000,512),(0,1,0x1fc0,0x3fc0,512),(1,0,0x3fc0,0x1fc0,512),(0,1,0x5000,0xcfc0,512),(1,0,0xcfc0,0x5000,512),(0,1,0xd000,0xd001,512),(1,0,0xd001,0xd000,512),(0,1,0x1c80,0x1c81,512),(0,1,0x1fc0,0x1fc1,128),(1,0,0x1fc1,0x1fc0,128),(1,1,0x4000,0x4001,512),(0,1,0x4000,0x4001,512)]
cases += [(0,1,0x2000,0x6000,16384),(1,0,0x6000,0x2000,16384),(0,1,0x3fff,0x5fff,8193),(1,0,0x5fff,0x3fff,8193),(0,1,0x1fff,0x3fff,8193),(1,0,0x3fff,0x1fff,8193),(0,1,0xd000,0xe000,512)]
def address(a,bank):return a+(0x10000 if bank and 0x2000<=a<0xc000 else 0)
try:
 reset_to_handover(call);enter_gide(call);run(700)
 for i,(sb,db,src,dst,count) in enumerate(cases):
  for iff in [0,1]:
   write(dst,bytes([0xcc])*max(1,count),bool(db));write(src,bytes((j*17+43)&255 for j in range(max(1,count))),bool(sb))
   model={address(src+j,sb):x for j,x in enumerate(physical(src,max(1,count),bool(sb)))}
   model.update({address(dst+j,db):x for j,x in enumerate(physical(dst,max(1,count),bool(db)))})
   for j in range(count):model[address(dst+j,db)]=model[address(src+j,sb)]
   stack=build['common_symbols']['gate_stack'];stack_end=build['common_symbols']['gate_stack_end'];write(stack,b'\xa5'*(stack_end-stack),False)
   caller_sp=0xd000 if (sb==1 and src<=0x7000 and src+count>0x6ff0) or (db==1 and dst<=0x7000 and dst+count>0x6ff0) else 0x7000
   body=f"""DI
LD SP,0x1f00
LD A,1
CALL {build['common_symbols']['selmem']}
LD SP,{caller_sp}
LD IX,0x1357
LD IY,0x2468
LD B,{db}
LD C,{sb}
CALL {common+87}
LD HL,{dst}
LD DE,{src}
LD BC,{count}
{('EI' if iff else 'DI')}
CALL {common+75}
LD (0x1c00),HL
LD (0x1c02),DE
LD (0x1c04),BC
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
   assemble_run(body,f'copy-{i}-{iff}')
   result=physical(0x1c00,14,True)
   assert result[:6]==(dst+count).to_bytes(2,'little')+(src+count).to_bytes(2,'little')+b'\0\0',(i,iff,result.hex())
   assert result[6:12]==bytes.fromhex('57136824')+caller_sp.to_bytes(2,'little'),(i,result.hex())
   assert bool(result[12]&4)==bool(iff),(i,result.hex())
   assert physical(dst,max(1,count),bool(db))==bytes(model[address(dst+j,db)] for j in range(max(1,count))),(i,sb,db,src,dst,count)
   assert physical(build['common_symbols']['current_bank'],1,True)==b'\x01'
   for window in [0x2000,0x4000]:assert base64.b64decode(call('mem_read',{'addr':window,'len':16})['data_b64'])==physical(window,16,True),(i,'alias mapping not restored',window)
   watermark=physical(stack,stack_end-stack,False);first=next((j for j,x in enumerate(watermark) if x!=0xa5),len(watermark));assert first>=16,(i,first)
   max_stack=max(max_stack,len(watermark)-first)
   checks.append(dict(source_bank=sb,dest_bank=db,source=src,dest=dst,bytes=count,iff=iff,passed=True))
 (out/'result.json').write_text(json.dumps(dict(passed=True,checks=checks,banked_caller_stack='7000',forward_overlap_reference=True,gate_stack_max_observed=max_stack,gate_stack_allocated=stack_end-stack,tpa_bytes=60672),indent=2)+'\n')
 print('PASS',len(checks),'copy contracts, overlap/boundaries, banked caller stack, IFF, registers; max stack',max_stack)
finally:e.close()
