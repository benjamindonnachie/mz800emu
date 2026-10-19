#!/usr/bin/env python3
"""Compare PEHU BIOS console entry points with preserved original SUC oracle."""
from pathlib import Path
import sys,configparser,base64,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'archive-tools'));from test_mz800emu_boot import Emulator
sys.path.insert(0,str(ROOT/'cpm/suc-native'));from monitor_boot import reset_to_handover,enter_gide
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/terminal-contract';out.mkdir(parents=True,exist_ok=True)
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
sys.path.insert(0,str(ROOT/'cpm/gide/tools'));from media import SharpDSK,floppy
original=floppy(SharpDSK((ROOT/'cpm/gide/reference/CPM7004.dsk').read_bytes()).logical()).read('PCPM.SYS');table=original[0xF3D6-0xC600:0xF4D6-0xC600]
def cell(i):return (((i>>1)+(i&1))&1023)|((i&1)<<10)
def scroll(chars,attrs):
 for memory in [chars,attrs]:
  memory[0:960]=memory[40:1000];memory[1025:1985]=memory[1065:2025]
 for i in range(1920,2000):chars[cell(i)]=0
checks=[];max_video_stack=0;max_gate_stack=0
try:
 reset_to_handover(call);enter_gide(call);run(700)
 regions=call('regions_list')['regions'];charid=next(x['id'] for x in regions if x['kind']=='vram_700_char');attrid=next(x['id'] for x in regions if x['kind']=='vram_700_attr')
 # Inlined accesses execute inside these private-stack routines. Keep the
 # old helper breakpoints as well, to catch any remaining indirect caller.
 for name in ['video_write','video_read','video_copy','mmio_write','mmio_read',
              'draw_character','zero_run','cursor_tick','hide_cursor']:
  bid=call('bp_add',{'addr':sym[name]})['id']
  assert call('bp_update',{'id':bid,'fields':['expr'],'expr':'IFF1 || SP >= 0xC000'})['updated']
 cases=[]
 for pos in [0,1,2,3,79,80,81,1998,1999]:
  for kind in ['eol','eos']:cases.append((kind,pos))
 # Every first-row erase length exercises all short tails and16-byte edges.
 cases += [('eol',pos) for pos in range(80)]
 cases += [('clear',0),('scroll',1920)]
 for row in range(25):
  for col in [0,1,39,40,78]:cases.append(('draw',row*80+col))
 cases += [('draw',row*80+79) for row in [0,12,23,24]]
 for num,(kind,pos) in enumerate(cases):
  chars=bytearray((i*17+3)&255 for i in range(2048));attrs=bytearray((i*7+49)&255 for i in range(2048))
  call('region_write',{'region_id':charid,'offset':0,'data_b64':base64.b64encode(chars).decode()});call('region_write',{'region_id':attrid,'offset':0,'data_b64':base64.b64encode(attrs).decode()})
  write(sym['cursor_row'],bytes(9),False)
  row,col=divmod(pos,80);stream=b'\x1bY'+bytes([row+32,col+32])
  want_cursor=(row,col)
  if kind in ['eol','eos']:
   stream+=b'\x1b'+(b'K' if kind=='eol' else b'J')
   limit=(row+1)*80 if kind=='eol' else 2000
   for i in range(pos,limit):chars[cell(i)]=0
  elif kind=='clear':stream=b'\x1a';chars[:]=bytes(2048);want_cursor=(0,0)
  elif kind=='scroll':stream=b'\x1bY8 '+b'\n';scroll(chars,attrs);want_cursor=(24,0)
  else:
   stream+=b'A';chars[cell(pos)]=table[65]
   if col==79:
    if row==24:scroll(chars,attrs);want_cursor=(24,0)
    else:want_cursor=(row+1,0)
   else:want_cursor=(row,col+1)
  write(0x4000,stream,True)
  for lo,hi in [(sym['video_stack'],sym['video_stack_end']),(build['common_symbols']['gate_stack'],build['common_symbols']['gate_stack_end'])]:write(lo,b'\xa5'*(hi-lo),False)
  body=f"""DI
LD SP,0x1f00
LD A,1
CALL {build['common_symbols']['selmem']}
LD SP,0x7000
LD HL,0x4000
LD BC,{len(stream)}
again:
PUSH BC
PUSH HL
LD C,(HL)
EI
CALL {common+12}
POP HL
POP BC
INC HL
DEC BC
LD A,B
OR C
JR NZ,again
DI
LD A,1
LD (0x1c20),A
HALT
JR $-1
"""
  assemble_run(body,f'{num}-{kind}-{pos}')
  actual=base64.b64decode(call('region_read',{'region_id':charid,'offset':0,'length':2048})['data_b64']);actual_attrs=base64.b64decode(call('region_read',{'region_id':attrid,'offset':0,'length':2048})['data_b64'])
  assert actual==chars,(kind,pos,'characters',[(i,a,b) for i,(a,b) in enumerate(zip(actual,chars)) if a!=b][:5])
  assert actual_attrs==attrs,(kind,pos,'attributes')
  assert physical(sym['cursor_row'],2,False)==bytes(want_cursor),(kind,pos,'cursor',physical(sym['cursor_row'],2,False).hex(),want_cursor)
  for which,lo,hi in [('video',sym['video_stack'],sym['video_stack_end']),('gate',build['common_symbols']['gate_stack'],build['common_symbols']['gate_stack_end'])]:
   data=physical(lo,hi-lo,False);first=next((i for i,b in enumerate(data) if b!=0xa5),len(data));assert first>=16,(kind,pos,which,'stack margin',first)
   if which=='video':max_video_stack=max(max_video_stack,len(data)-first)
   else:max_gate_stack=max(max_gate_stack,len(data)-first)
  checks.append(dict(kind=kind,position=pos,passed=True))
 (out/'result.json').write_text(json.dumps(dict(passed=True,checks=checks,all_25_rows=True,odd_even_erase=True,full_character_and_attribute_vram_checked=True,mmio_interrupts_masked=True,video_stack_bytes_used=max_video_stack,gate_stack_bytes_used=max_gate_stack),indent=2)+'\n')
 print('PASS',len(checks),'terminal contracts: all rows, wrap/scroll, odd/even erasure, attributes and masked MMIO')
finally:e.close()
