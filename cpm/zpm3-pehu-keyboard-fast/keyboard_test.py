#!/usr/bin/env python3
"""Compare PEHU BIOS console entry points with preserved original SUC oracle."""
from pathlib import Path
import sys,configparser,base64,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'archive-tools'));from test_mz800emu_boot import Emulator
sys.path.insert(0,str(ROOT/'cpm/suc-native'));from monitor_boot import reset_to_handover,enter_gide
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/keyboard';out.mkdir(parents=True,exist_ok=True)
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
cases=[]
def record(name,action):
 before=int.from_bytes(physical(0x5ff0,2,True),'little');action();run(20);after=int.from_bytes(physical(0x5ff0,2,True),'little')
 cases.append(dict(name=name,bytes=physical(0x5000+before,after-before,True).hex(),alpha=physical(sym['suc_state']+27,1,False).hex(),macro_page=physical(sym['suc_state']+26,1,False).hex()))
try:
 reset_to_handover(call);enter_gide(call);run(500)
 # Ensure the application view is selected before entering the harness: use
 # the BIOS public bank selector via a tiny shared-low trampoline.
 app=build['common_symbols']['selmem'];tramp=bytes([0xf3,0xd3,0xe1,0x31,0,0x10,0x3e,1,0xcd,app&255,app>>8,0xc3,0,0x40])
 write(0x1f00,tramp,True);write(0x4000,(out/'harness.bin').read_bytes(),True);call('set_register',{'reg':'PC','value':0x1f00});run(100)
 record('ordinary_shift_punctuation',lambda:text('Az09;=/?'))
 record('ALPHA_then_letters',lambda:(key('ALPHA'),text('Az')))
 record('ALPHA_restore_then_letters',lambda:(key('ALPHA'),text('Az')))
 record('GRAPH',lambda:key('GRAPH'))
 record('BREAK',lambda:key('BREAK'))
 record('control_A',lambda:(call('input_press_key',{'key':'CTRL'}),text('A'),call('input_release_key',{'key':'CTRL'})))
 record('backspace_and_cursor',lambda:[key(k) for k in ['BACKSPACE','LEFT','RIGHT','UP','DOWN']])
 for page in range(4):
  for n in range(1,5):record(f'page{page}_F{n}',lambda n=n:key('F'+str(n)))
  record(f'page{page}_F5_next',lambda:key('F5'))
 write(sym['suc_macros'],bytes.fromhex('0358590d'),False)
 record('custom_F1_XY_Return',lambda:key('F1'))
 original=json.loads((ROOT/'build-records/mz800emu/cpm3-suc-native/keyboard/original/result.json').read_text())
 assert cases==original,(call('get_registers'),physical(build['common_symbols']['current_bank'],1,True).hex(),physical(0x5ff0,2,True).hex(),[(a,b) for a,b in zip(cases,original) if a!=b])
 (out/'result.json').write_text(json.dumps(dict(passed=True,equivalent_cases=len(cases),cases=cases),indent=2)+'\n');print('PASS',len(cases),'original SUC keyboard cases through banked BIOS gateways')
finally:e.close()
