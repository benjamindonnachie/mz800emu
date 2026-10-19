"""Independent host byte verification of alternating random C/D writes."""
from pathlib import Path
import base64,configparser,hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'archive-tools'),str(ROOT/'cpm/gide/tools')]
from test_mz800emu_boot import Emulator
from media import hard_volume
sys.path.insert(0,str(ROOT/'cpm/suc-native'))
from monitor_boot import reset_to_handover,enter_gide
ACTIVE_CONFIG=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/interactive-0.1.0/mz700.ini'
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/sector-boundaries';out.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,str(ROOT/'cpm/gide/third_party/pyz80.py'),'--obj='+str(out/'SECTEST.COM'),str(HERE/'sector_test.asm')],check=True,stdout=subprocess.DEVNULL)
raw=bytearray((HERE/'build/gide-zpm3-pehu-keyboard-fast.img').read_bytes())
for i,byte in [(0,0x5a),(1,0xa5)]:
 part=raw[i*8388608:(i+1)*8388608];v=hard_volume(part);v.write('EDGE.DAT',bytes([byte])*600*128)
 if i==0:v.write('SECTEST.COM',(out/'SECTEST.COM').read_bytes())
 raw[i*8388608:(i+1)*8388608]=part
image=out/'disk.img';image.write_bytes(raw)
ini=configparser.ConfigParser(interpolation=None);ini.read(ACTIVE_CONFIG);ini['GIDE']['hdd0_filepath']=str(image)
ini['DEBUGGER']['auto_save_breakpoints']='0'
for p in out.glob('*.bpt'):p.unlink()
with (out/'input.ini').open('w') as f:ini.write(f)
e=Emulator(ROOT/'emulators/Working/mz800emu/build-mac/build-mz700emu-pal/mz700emu-pal',out,['--home-dir',str(ROOT/'emulators/Working/mz800emu'),'--config',str(out/'input.ini')])
def call(c,d=None):
 r=e.call(c,d);assert r.get('success'),r;return r.get('data',{})
def run(n):
 while n:k=min(n,1000);call('run',{'frames':k});n-=k
def mem(a,n):
 pa=a+(0x10000 if 0x2000<=a<0xc000 else 0);rid=next(x['id'] for x in call('regions_list')['regions'] if x['kind']=='memext_ram' and x['sub_id']==pa//4096)
 return base64.b64decode(call('region_read',{'region_id':rid,'offset':pa&4095,'length':n})['data_b64'])
try:
 reset_to_handover(call);enter_gide(call);run(3000)
 rid=next(x['id'] for x in call('regions_list')['regions'] if x['kind']=='memext_ram' and x['sub_id']==0x18);call('region_write',{'region_id':rid,'offset':4,'data_b64':'AA=='})
 call('input_send_keys',{'text':'SECTEST','frame_per_key':30});run(10);call('input_send_key',{'key':'RETURN','frames':30});run(4000)
 assert mem(0x8004,1)==b'\xa5',(mem(0x8004,2).hex(),call('get_registers'),mem(0x6ff0,16).hex())
 call('screenshot_save_to_file',{'path':str(out/'result.png'),'scale':'2'})
finally:e.close()
indices=[0,1,3,4,31,32,127,128,255,256,511,512,599]
after=image.read_bytes()
for i,old,new in [(0,0x5a,0x3c),(1,0xa5,0xc3)]:
 expected=bytearray(bytes([old])*600*128)
 for n in indices:expected[n*128:(n+1)*128]=bytes([new])*128
 assert hard_volume(bytearray(after[i*8388608:(i+1)*8388608])).read('EDGE.DAT')==expected
(out/'result.json').write_text(json.dumps(dict(passed=True,checks=['BDOS44 four-record read to unaligned DMA40FF','Alternating C/D random read/write without intermediate close','Record indices '+str(indices),'Close and BDOS48 flush','Warmboot after test','Host checks every byte, including untouched quarters and other sectors','Emulator exits before host persistence verification']),indent=2)+'\n')
print('PASS sector boundaries, multi-record DMA and cross-drive dirty-buffer ownership')
