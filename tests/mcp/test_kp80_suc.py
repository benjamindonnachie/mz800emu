#!/usr/bin/env python3
"""K&P port protocol, with native CPU and the actual shared SUC framebuffer."""
import base64,json,os,re,tempfile,zipfile
from pathlib import Path
from test_suc80_display import Emu,REPO,font_bytes,assert_canvas
import emu_test_proc

def out(port,value):return bytes((0x3e,value,0xd3,port))
def reg(index,value):return out(0x72,index)+out(0x73,value)
def pair(index,value):return reg(index,value>>8)+reg(index+1,value&255)
def ptr(value):return pair(18,value)+out(0x72,31)
def offset(i):return (((i>>1)+(i&1))&1023)|((i&1)<<10)
def mem(e,a,n):return base64.b64decode(e.call('mem_read',{'addr':a,'len':n})['data_b64'])
def vram(e,name='state'):
 p=e.folder/(name+'.mzs');e.call('snapshot_save',{'path':str(p)})
 with zipfile.ZipFile(p) as z:return z.read('memory/vram.bin')
def readport(port,dest):return bytes((0xdb,port,0x32))+dest.to_bytes(2,'little')
def init():
 values=bytes.fromhex('7f50640c1e02191c7809600900000000')
 return b''.join(reg(i,v) for i,v in enumerate(values))+reg(10,0x20)
def pixel_check(e,raw,start=0,cursor=None):
 frame=e.frame();font=font_bytes();palette=[bytes(((c>>16)&255,(c>>8)&255,c&255,255)) for c in e.palette];colors=[0,9,10,11,12,13,14,15]
 for row in range(25):
  for line in range(8):
   expected=bytearray()
   for col in range(80):
    i=(start+row*80+col)&2047;o=offset(i);c=raw[o]&127
    # Independently known native-font positions, fixture deliberately A-Z/digits/space.
    code=(c-64 if 65<=c<=90 else c-16 if 48<=c<=57 else 0)
    attr=raw[2048+o];mask=font[(((attr<<4)&2048)|(code*8))+line]
    if cursor is not None and i==cursor:mask=255
    fg=palette[colors[(attr>>4)&7]];bg=palette[colors[attr&7]]
    for bit in range(8):expected.extend(fg if mask&(1<<bit) else bg)
   at=((16+row*8+line)*704+32)*4
   assert frame[at:at+640*4]==expected,(row,line)

def main():
 emu_test_proc.install(deadline_s=120)
 exe=Path(os.environ.get('MZ_EMU',REPO/'build-mac/build-mz700emu-pal/mz700emu-pal')).resolve()
 if not exe.is_file():return 77
 work=Path(os.environ.get('MZ_KP_TEST_OUTPUT',tempfile.mkdtemp(prefix='mz700-kp80-'))).resolve();work.mkdir(parents=True,exist_ok=True)
 checks=[]
 # Existing installations do not claim K&P ports or change existing SUC pixels.
 e=Emu(exe,work/'native',True)
 try:
  raw=bytearray((i*17+i//31)&255 for i in range(4096));e.call('mem_write',{'addr':0xd000,'data_hex':raw.hex()})
  e.cpu(init()+ptr(0)+out(0x71,65));assert vram(e)==raw
  e.mode(0xe00c,0x50);assert_canvas(e,raw,80)
  checks.append('Default SUC interface leaves K&P ports unclaimed and native scanout unchanged')
 finally:e.close()
 # A remembered interface is not permission to fit a disabled expansion.
 e=Emu(exe,work/'disabled-kp',False,'[VIDEO_MZ700]\nsuc80_enabled=0\nsuc80_kp_interface=1\n')
 try:
  raw=bytearray(4096);raw[2048:]=bytes([0x70])*2048
  e.call('mem_write',{'addr':0xd000,'data_hex':raw.hex()})
  e.cpu(init()+ptr(0)+out(0x71,65))
  assert vram(e)==raw
  assert_canvas(e,raw,40)
  checks.append('Explicitly disabled SUC remains absent with a remembered K&P interface')
 finally:e.close()
 e=Emu(exe,work/'kp',True,'[VIDEO_MZ700]\nsuc80_enabled=1\nsuc80_kp_interface=1\n')
 try:
  raw=bytearray(4096);raw[2048:]=bytes([0x70])*2048
  e.call('mem_write',{'addr':0xd000,'data_hex':raw.hex()})
  e.call('run',{'frames':3})
  assert_canvas(e,raw,40)
  e.cpu(init())
  # Raw2048-byte fixture, including48 cells beyond the visible2000.
  data=bytes(b'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '[i%37] for i in range(2048))
  e.call('mem_write',{'addr':0x4000,'data_hex':data.hex()})
  # OUTI loops through high I/O addresses, exercising low-byte-only port decode.
  e.cpu(ptr(0)+bytes.fromhex('2100401171000e71')+b'\x06\x00\xed\xb3'*8)
  raw=vram(e,'full-pattern')
  for i,c in enumerate(data):assert raw[offset(i)]==c,(i,offset(i))
  assert raw[2048:]==bytes([0x70])*2048
  pixel_check(e,raw)
  checks.append('All2048 raw characters use SUC D000/D401/D001/D402 mapping; cell2047 wraps D400 without touching attributes')
  # Read twice: no advancement. Incremented address after previous2048 writes
  # is0800 (aliases VRAM0), and direct memory editing is immediately visible.
  e.cpu(ptr(1)+readport(0x70,0x7000)+readport(0x70,0x7001))
  assert mem(e,0x7000,2)==b'BB'
  e.cpu(bytes.fromhex('3e5a3201d4'))
  e.cpu(readport(0x70,0x7002));assert mem(e,0x7002,1)==b'Z'
  checks.append('Read port neither increments nor caches: direct SUC VRAM edits are immediately read')
  # Register staging and R31 latch: R18/19 alone must not change live pointer.
  e.cpu(ptr(3)+pair(18,9)+out(0x71,65))
  assert vram(e)[offset(3)]==65
  # Writes updateR18/19: re-stage9 then latch and write.
  e.cpu(ptr(9)+out(0x71,66));assert vram(e)[offset(9)]==66
  e.cpu(ptr(0x3fff)+out(0x71,67)+out(0x71,68))
  raw=vram(e);assert raw[offset(2047)]==67 and raw[offset(0)]==68
  # Port access is independent of CPU's memory banking, and preserves hiddenRAM.
  e.cpu(bytes.fromhex('d3e13e993200d0')+ptr(0)+out(0x71,69))
  assert mem(e,0xd000,1)==b'\x99'
  e.cpu(bytes.fromhex('d3e3'));raw=vram(e);assert raw[0]==69
  checks.append('StagedR18/19/R31, auto increment,14bit wrap and bank-independent VRAM writes')
  for start in (80,2040,0):
   e.cpu(pair(12,start));pixel_check(e,raw,start)
  checks.append('Display-start scrolling wraps over all2048 cells using shared physical VRAM')
  e.cpu(pair(14,0)+reg(9,9)+reg(10,0)+reg(11,9));pixel_check(e,raw,cursor=0)
  e.cpu(reg(10,0x20));pixel_check(e,raw)
  checks.append('Hardware cursor steady/off overlays shared SUC pixels without modifying VRAM')
  # Stable frame hashes show both blink phases with no subsequent writes.
  e.cpu(reg(10,0x40));frames=set()
  for _ in range(40):
   e.call('run',{'frames':1});frames.add(e.frame())
  assert len(frames)==2,len(frames)
  e.cpu(reg(10,0x20));pixel_check(e,raw)
  checks.append('Cursor16-frame blink refreshes without guest VRAM writes')
  e.cpu(ptr(1500)+pair(12,2040)+pair(14,1700)+reg(10,0x20))
  snap=e.folder/'restore.mzs';e.call('snapshot_save',{'path':str(snap)})
  e.cpu(ptr(0)+pair(12,0));e.call('snapshot_load',{'path':str(snap)});e.cpu(out(0x71,65))
  restored=vram(e);assert restored[offset(1500)]==65
  pixel_check(e,restored,2040)
  checks.append('Snapshot restores interface, staged registers, live pointer, scrolling and sharedVRAM')
  e.call('screenshot_save_to_file',{'path':str(e.folder/'scrolled.png'),'scale':'2'})
  e.call('reset');e.call('run',{'frames':100});e.cpu(b'')
  e.call('mem_write',{'addr':0xd000,'data_hex':raw.hex()});e.call('run',{'frames':3});assert_canvas(e,raw,40)
  checks.append('Reset retains configured interface but clearsCRTC/pointer/mode to stock40 columns')
 finally:e.close()
 # Author's preserved unmodified MZF body, when supplied by the workspace.
 sample=REPO.parents[1]/'sources/kp80/library/KuPTest.MZF'
 if sample.is_file():
  e=Emu(exe,work/'author-demo',True,'[VIDEO_MZ700]\nsuc80_enabled=1\nsuc80_kp_interface=1\n')
  try:
   blob=sample.read_bytes();size=int.from_bytes(blob[18:20],'little');load=int.from_bytes(blob[20:22],'little');entry=int.from_bytes(blob[22:24],'little')
   e.call('mem_write',{'addr':load,'data_hex':blob[128:128+size].hex()});e.call('set_register',{'reg':'PC','value':entry});e.call('run',{'frames':100})
   raw=vram(e);assert bytes(raw[offset(3*80+5+i)] for i in range(3))==b'BKK'
   assert bytes(raw[offset(8*80+i)] for i in range(128))==bytes(range(128))
   e.call('screenshot_save_to_file',{'path':str(e.folder/'original-author-demo.png'),'scale':'2'})
   checks.append('Original BKK MZF executes unmodified, drawsBKK at5,3 and writes all128 testcodes')
  finally:e.close()
 result=dict(passed=True,checks=checks);(work/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
