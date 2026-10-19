"""Live application test support, using a disposable GIDE image."""
from pathlib import Path
import base64,configparser,json,shutil,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'archive-tools'),str(ROOT/'cpm/gide/tools'),str(ROOT/'cpm/rtc')]
from test_mz800emu_boot import Emulator
from monitor_boot import ACTIVE_CONFIG,reset_to_handover,enter_gide
from media import SharpDSK,floppy,hard_volume
class Session:
    def __init__(self,name,prepare=None,source=None):
        self.out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/applications'/name;self.out.mkdir(parents=True,exist_ok=True)
        self.image=self.out/'disk.img';shutil.copyfile(source or ROOT/'cpm/zpm3-pehu-keyboard-fast/build/gide-zpm3-pehu-keyboard-fast.img',self.image)
        if prepare:prepare(self.image)
        ini=configparser.ConfigParser(interpolation=None);ini.read(ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/interactive-0.1.0/mz700.ini')
        ini['ROM']['boot_rom_mode']='F000';ini['GIDE']['hdd0_filepath']=str(self.image);ini['GIDE']['hdd0_readonly']='0'
        with (self.out/'input.ini').open('w') as f:ini.write(f)
        self.s=json.loads((ROOT/'cpm/zpm3-pehu-keyboard-fast/build/build.json').read_text())['symbols'];self.results=[]
        system=floppy(SharpDSK((ROOT/'cpm/gide/reference/CPM7004.dsk').read_bytes()).logical()).read('PCPM.SYS')
        table=system[0xF3D6-0xC600:0xF4D6-0xC600];self.decode={table[x]:chr(x) for x in reversed(range(32,127))};self.decode[0]=' '
        emuhome=ROOT/'emulators/Working/mz800emu'
        if not emuhome.exists():emuhome=ROOT/'emulators/mz800emu'
        self.e=Emulator(emuhome/'build-mac/build-mz700emu-pal/mz700emu-pal',self.out,['--home-dir',str(emuhome),'--config',str(self.out/'input.ini')])
        reset_to_handover(self.call);enter_gide(self.call);self.run(3000)
    def call(self,c,d=None):
        r=self.e.call(c,d);assert r.get('success'),r;return r.get('data',{})
    def run(self,n=1500):
        while n:k=min(n,1000);self.call('run',{'frames':k});n-=k
    def mem(self,a,n,app=True):
        result=bytearray()
        regions=self.call('regions_list')['regions']
        while n:
            pa=a+(0x10000 if app and 0x2000<=a<0xc000 else 0);k=min(n,4096-(a&4095))
            rid=next(x['id'] for x in regions if x['kind']=='memext_ram' and x['sub_id']==pa//4096)
            result+=base64.b64decode(self.call('region_read',{'region_id':rid,'offset':pa&4095,'length':k})['data_b64']);a+=k;n-=k
        return bytes(result)
    def text(self,t):self.call('input_send_keys',{'text':t,'frame_per_key':30});self.run(10)
    def key(self,k):self.call('input_send_key',{'key':k,'frames':30});self.run(15)
    def ctrl(self,k):
        self.call('input_press_key',{'key':'CTRL'});self.text(k);self.call('input_release_key',{'key':'CTRL'});self.run(20)
    def command(self,t,frames=1500):self.text(t);self.key('RETURN');self.run(frames);return self.capture(t)
    def screen(self):
        rid=next(x['id'] for x in self.call('regions_list')['regions'] if x['kind']=='vram_700_char')
        raw=bytearray(base64.b64decode(self.call('region_read',{'region_id':rid,'offset':0,'length':2048})['data_b64']))
        if self.mem(self.s['cursor_drawn'],1,False)==b'\x01':raw[int.from_bytes(self.mem(self.s['cursor_address'],2,False),'little')-0xd000]=self.mem(self.s['cursor_saved_character'],1,False)[0]
        return '\n'.join(''.join(self.decode.get(raw[(((i>>1)+(i&1))&1023)|((i&1)<<10)],'?') for i in range(r*80,(r+1)*80)).rstrip() for r in range(25)).rstrip()
    def capture(self,label):
        text=self.screen();self.results.append(dict(action=label,screen=text));print(label,repr(text[-1700:]),flush=True)
        (self.out/'screens.json').write_text(json.dumps(self.results,indent=2)+'\n');return text
    def screenshot(self,name):self.call('screenshot_save_to_file',{'path':str(self.out/(name+'.png')),'scale':'2'})
    def close(self):self.e.close()
if __name__=='__main__':
    s=Session(sys.argv[1])
    try:
        for command in sys.argv[2:]:s.command(command)
        s.screenshot('screen')
    finally:s.close()
