#!/usr/bin/env python3
"""Compare PEHU BIOS console entry points with preserved original SUC oracle."""
from pathlib import Path
import sys,configparser,base64,json,subprocess,datetime,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'archive-tools'));from test_mz800emu_boot import Emulator
sys.path.insert(0,str(ROOT/'cpm/suc-native'));from monitor_boot import reset_to_handover,enter_gide
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/rtc';out.mkdir(parents=True,exist_ok=True)
build=json.loads((HERE/'build/build.json').read_text());sym=build['symbols'];common=build['common_base']
c=configparser.ConfigParser(interpolation=None);c.read(ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/interactive-0.1.0/mz700.ini');c['GIDE']['hdd0_filepath']=str(HERE/'build/gide-zpm3-pehu-keyboard-fast.img');c['GIDE']['hdd0_readonly']='1';c['DEBUGGER']['auto_save_breakpoints']='0'
for p in out.glob('*.bpt'):p.unlink()
with (out/'input.ini').open('w') as f:c.write(f)
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
checks=[];epoch=datetime.date(1977,12,31);scb=common-256+0x58

def ports(dt):
 text='LD BC,0x0FA5\nLD A,6\nOUT (C),A\nLD BC,0x0DA5\nLD A,5\nOUT (C),A\n'
 for i,v in enumerate([dt.second,dt.minute,dt.hour,dt.day,dt.month,dt.year%100]):
  for n,d in [(2*i,v%10),(2*i+1,v//10)]:text+=f'LD BC,{(n<<8)|0xa5}\nLD A,{d}\nOUT (C),A\n'
 return text+'LD BC,0x0DA5\nLD A,4\nOUT (C),A\n'
def harness(code,tag,bank=1,iff=0):
 assemble_run(f"DI\nLD SP,0x1e00\nLD A,{bank}\nCALL {build['common_symbols']['selmem']}\n"+code+'\nLD A,1\nLD (0x1c20),A\nHALT\nJR $-1\n',tag)
def capture_time(iff):
 return f"LD BC,0\nLD DE,0x5678\nLD HL,0x1234\nLD IX,0x9ABC\nLD IY,0xDEF0\nSCF\n{('EI' if iff else 'DI')}\nCALL {common+78}\nLD (0x1c00),HL\nLD (0x1c02),DE\nLD (0x1c04),IX\nLD (0x1c06),IY\nLD A,I\nPUSH AF\nPOP BC\nLD (0x1c08),BC\nDI\n"
try:
 reset_to_handover(call);enter_gide(call);run(700)
 scb=int.from_bytes(physical(sym['rtc_time']+6,2,False),'little');assert common-256<=scb<common,hex(scb)
 print('Runtime SCB date:',hex(scb),flush=True)
 today=datetime.datetime.now();bootday=int.from_bytes(physical(scb,2,True),'little')
 assert abs(bootday-(today.date()-epoch).days)<=1,bootday
 helper=physical(0x3b,19,True);low=physical(0x50,12,True);fcb=physical(0x5c,36,True)
 fixtures=[datetime.datetime(y,m,d,23,34,45) for y,m,d in [(1978,1,1),(1979,12,31),(1980,2,29),(1999,12,31),(2000,1,1),(2000,2,29),(2023,2,28),(2024,2,29),(2026,10,19),(2076,2,29),(2077,12,31)]]
 for i,dt in enumerate(fixtures):
  harness(ports(dt),'fixture-'+str(i))
  expected=(dt.date()-epoch).days.to_bytes(2,'little')+bytes(int(f'{v:02d}',16) for v in [dt.hour,dt.minute,dt.second])
  for bank in [0,1]:
   for iff in [0,1]:
    write(scb,b'\xff'*5,True)
    harness(capture_time(iff),f'read-{i}-{bank}-{iff}',bank,iff)
    if physical(scb,5,True)!=expected:
     dump=''
     for reg in range(16):dump+=f'LD BC,{(reg<<8)|0xa5}\nIN A,(C)\nLD ({0x1d00+reg}),A\n'
     harness(dump,'failure-registers')
     raise AssertionError((dt,bank,iff,physical(scb,5,True).hex(),expected.hex(),physical(sym['rtc_calendar'],6,False).hex(),physical(0x1d00,16,True).hex()))
    r=physical(0x1c00,10,True);assert r[:8]==bytes.fromhex('34127856bc9af0de'),r.hex()
    assert bool(r[8]&4)==bool(iff),r.hex()
    assert physical(build['common_symbols']['current_bank'],1,True)==bytes([bank])
  # SET must programme the device: poison SCB afterwards then GET and compare.
  write(0x9000,expected[:4],True)
  harness('LD DE,0x9000\nLD C,104\nCALL 5\nLD BC,0x0FA5\nLD A,6\nOUT (C),A\n','set-'+str(i))
  write(scb,b'\xff'*5,True)
  harness('LD DE,0x9100\nLD C,105\nCALL 5\n','get-'+str(i))
  assert physical(0x9100,4,True)==expected[:4],(dt,physical(0x9100,4,True).hex())
  assert physical(0x3b,19,True)==helper and physical(0x50,12,True)==low and physical(0x5c,36,True)==fcb
  checks.append(dt.isoformat())
 for hour in [0,12,23]:
  dt=datetime.datetime(2026,10,19,hour,34,0)
  harness(ports(dt)+'LD BC,0x0FA5\nLD A,2\nOUT (C),A\n','12h-'+str(hour))
  harness('LD DE,0x9100\nLD C,105\nCALL 5\n','12h-get-'+str(hour))
  assert physical(0x9102,1,True)==bytes([int(f'{hour:02d}',16)])
 harness('LD BC,0x0FA5\nLD A,4\nOUT (C),A\nLD DE,0x9100\nLD C,105\nCALL 5\n','running')
 before=physical(scb,5,True);changed=False
 for i in range(10):
  time.sleep(.2);harness('LD DE,0x9100\nLD C,105\nCALL 5\n','advance-'+str(i))
  if physical(scb,5,True)!=before:changed=True;break
 assert changed,'RTC failed to advance'
 (out/'result.json').write_text(json.dumps(dict(passed=True,calendar_fixtures=len(fixtures),direct_bank_iff_cases=44,carry_set_entry=True,bdos_set_get=True,read_from_board_every_call=True,cold_boot_seeds_scb=True,normalises_12h=True,running_clock_advances=True,low_helper_and_fcb_unchanged=True,tpa_bytes=build['zccp_tpa_bytes']),indent=2)+'\n')
 print('PASS RTC:11 calendar fixtures,44 bank/IFF read cases, BDOS104/105,12h conversion and live advancement')
finally:e.close()
