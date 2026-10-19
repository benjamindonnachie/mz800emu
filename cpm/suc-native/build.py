#!/usr/bin/env python3
"""Build full-64KiB non-banked CP/M3 with native Sharp/GIDE/port console BIOS."""
from pathlib import Path
import argparse,hashlib,json,os,pty,re,select,shutil,subprocess,sys,tarfile,tempfile,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];BUILD=HERE/'build';BUILD.mkdir(exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('--zxcc',type=Path);args=ap.parse_args()
ref=ROOT/'cpm/cpm3-on2/reference'
asmpath=ROOT/'cpm/gide/third_party/pyz80.py'
def run(argv,cwd=BUILD,log=None):
 p=subprocess.run([str(x) for x in argv],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 if p.returncode:raise RuntimeError(p.stdout.decode(errors="replace"))
 if log:log.write(p.stdout);log.flush()
 if any(str(x).endswith('rmac.com') for x in argv):assert not re.search(rb'(?m)^[A-Z?] {2,}',p.stdout),p.stdout.decode(errors='replace')
 return p.stdout
head='''        JP driver_init
        JP null
        JP console_status
        JP console_input
        JP console_output
        JP null
        JP null
        JP eof
        JP disk_home
        JP select
        JP set_track
        JP set_sector
        JP set_dma
        JP read
        JP write
        JP yes
        JP sector_translate
        JP install_helper
null:   RET
eof:    LD A,26
        RET
yes:    LD A,0xFF
        RET
sector_translate:
        LD H,B
        LD L,C
        RET
driver_init:
        CALL keyboard_init
        CALL console_init
        RET
'''
body=head+'\n'.join((HERE/n).read_text() for n in ['banking.asm','keyboard.asm','suc-keyboard.asm','console.asm','disk.asm'])
bins=[];maps=[]
for origin in [0,256]:
 src=BUILD/f'native-{origin}.asm';src.write_text(f'ORG {origin}\n'+body)
 run([sys.executable,asmpath,'--obj='+str(BUILD/f'native-{origin}.bin'),'--mapfile='+str(BUILD/f'native-{origin}.map'),src])
 bins.append((BUILD/f'native-{origin}.bin').read_bytes())
 maps.append({n:int(a,16) for a,n in (s.split('=',1) for s in (BUILD/f'native-{origin}.map').read_text().splitlines())})
# Prove that the relocated original code differs only at declared operands
# and omitted lower-ROM switching instructions. Tables/macros are pinned too.
sys.path.insert(0,str(ROOT/'cpm/gide/tools'))
from media import SharpDSK,floppy
system=floppy(SharpDSK((ROOT/'cpm/gide/reference/CPM7004.dsk').read_bytes()).logical()).read('PCPM.SYS')
provenance=json.loads((HERE/'keyboard-provenance.json').read_text())
assert hashlib.sha256(system).hexdigest()==provenance['original_sys_sha256']
patches=json.loads((HERE/'keyboard-relocations.json').read_text())
expected=bytearray(system[patches['base']-0xC600:patches['end']-0xC600])
for r in patches['relocations']:
 at=r['offset'];assert int.from_bytes(expected[at:at+2],'little')==r['original']
 name,_,add=r['expression'].partition('+');value=maps[0][name]+(int(add) if add else 0)
 expected[at:at+2]=value.to_bytes(2,'little')
for r in patches['nop_patches']:
 at=r['offset'];assert expected[at:at+r['bytes']]==bytes.fromhex(r['original']);expected[at:at+r['bytes']]=bytes(r['bytes'])
assert bins[0][maps[0]['suc_blob']:maps[0]['suc_blob']+len(expected)]==expected
assert bins[0][maps[0]['suc_macros']:maps[0]['suc_macros']+256]==system[0xDF00-0xC600:0xE000-0xC600]
assert bins[0][maps[0]['suc_special_macros']:maps[0]['suc_special_macros']+128]==system[0xE000-0xC600:0xE080-0xC600]

a,b=bins;assert len(a)==len(b)
relocs=[i-1 for i,(x,y) in enumerate(zip(a,b)) if x!=y]
assert len(set(relocs))==len(relocs)
for i in relocs:assert i>=0 and b[i]==a[i] and b[i+1]==(a[i+1]+1)&255
# Emit real relocatable RMAC words rather than treating machine-code bytes as
# absolute. Assembling a third origin proves the relocation map independently.
third=BUILD/'native-check.asm';third.write_text('ORG 32768\n'+body)
run([sys.executable,asmpath,'--obj='+str(BUILD/'native-check.bin'),third])
check=bytearray(a)
for i in relocs:check[i:i+2]=((int.from_bytes(a[i:i+2],'little')+32768)&65535).to_bytes(2,'little')
assert check==(BUILD/'native-check.bin').read_bytes()
lines=['\tcseg','\tpublic\tdriver','driver:'];i=0
while i<len(a):
 if i in relocs:
  lines.append(f'\tdw\tdriver+0{int.from_bytes(a[i:i+2],"little"):04x}h');i+=2
 else:
  end=min(i+16,len(a));end=min([j for j in relocs if i<j<end] or [end])
  lines.append('\tdb\t'+','.join(f'0{x:02x}h' for x in a[i:end]));i=end
native='\n'.join(lines)+'\n'
with (BUILD/'build.log').open('wb') as log:
 zxcc=args.zxcc
 if zxcc is None:
  tools=Path(tempfile.mkdtemp(prefix='mz-full-ram-zxcc-',dir='/tmp'))
  with tarfile.open(ROOT/'cpm/cpm3-on2/toolchain/zxcc-0.5.7.tar.gz') as t:
   assert all(not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in t.getmembers());t.extractall(tools,filter='data')
  src=tools/'zxcc-0.5.7';prefix=tools/'installed'
  for cmd in [['./configure','--prefix='+str(prefix)],['make','-j4'],['make','install']]:run(cmd,src,log)
  zxcc=prefix/'bin/zxcc'
 for n in ['rmac.com','link.com','scb.rel','bdos3.spr','cpmldr.rel','gencpm.com','ccp.com']:
  shutil.copyfile(ref/('utilities/'+n if n in ('ccp.com','bdos3.spr','gencpm.com','cpmldr.rel') else n),BUILD/n)
 for n in ['gbios.asm','ldrbios.asm']:
  s=(ref/n).read_text().replace('drives\tequ\t5','drives\tequ\t4')
  # Native driver exposes the original17 BIOS signatures for the period bridge.
  s=s.replace('bios+','driver+')
  s=re.sub(r'(?m)^(\w+)\tequ\tdriver\+(\w+)\s*$',r'\1:\n\tjmp\tdriver+\2',s)
  if n=='gbios.asm':
   # Adopt CPMLDR's cursor before CCP overwrites the transient loader.
   # Both drivers share VRAM, but have distinct resident state addresses.
   assert maps[0]['console_end']-maps[0]['cursor_row']==9
   handover=(f'\nboot:\n\tcall\tdriver+0{maps[0]["keyboard_init"]:04x}h\n'
             f'\tlxi\th,driver+0{maps[0]["cursor_row"]:04x}h\n'
             '\tlxi\td,LOADERCONSOLE\n\tlxi\tb,9\n\tcall\tmove\n')
   s=s.replace('\nboot:\n',handover)
  s=s.replace('wboot:\n','wboot:\n\tcall\tdriver+51\n')
  if n=='gbios.asm':
   s=s.replace('\tmvi\tm,1','\tmvi\tm,3').replace(';drive a:',';C: CCP.COM')
   s=s.replace('\tmvi\tb,36','\tmvi\tc,44\n\tlxi\td,1\n\tcall\tbdos\n\tmvi\tb,36')
   s=s.replace('\tcpi\tdrives','\tcpi\t2\n\trc\n\tcpi\tdrives')
  else:s=s.replace('\tcall\tdriver+slds80','\tmvi\tc,2\n\tcall\tdriver+slds80')
  s,nopen=re.subn(r'\tora\ta\n\tjnz\toperr[^\n]*','\tcpi\t255\n\tjz\toperr',s);assert nopen==1
  s=s.replace('\nmove:\n','\nmove:\n\tmov\ta,b\n\tora\tc\n\trz\nmovebyte:\n').replace('\tjnz\tmove\n','\tjnz\tmovebyte\n')
  s=s.replace('\tjmp\txmove','\tjmp\ttime').replace('\tjmp\tuserf','\tjmp\txmove\n\tjmp\tuserf')
  s,nres=re.subn(r'\tjmp\twboot[^\n]*\n\tjmp\twboot[^\n]*','\tjmp\treserved\n\tjmp\treserved',s);assert nres==1
  s=s.replace('devini:\n','time:\nreserved:\ndevini:\n')
  s=s.replace('\tdseg\n',native+'\tdseg\n')
  (BUILD/n).write_bytes(s.replace('\n','\r\n').encode())
 for argv in [['rmac.com','-ldrbios'],['link.com','-cpmldr,scb,ldrbios']]:run([zxcc,*argv],log=log)
 loader_symbols=(BUILD/'cpmldr.sym').read_text()
 loader_driver=int(re.search(r'(?i)([0-9a-f]{4})\s+DRIVER',loader_symbols)[1],16)
 loader_console=loader_driver+maps[0]['cursor_row']
 resident=(BUILD/'gbios.asm').read_text().replace('LOADERCONSOLE',f'0{loader_console:04x}h')
 (BUILD/'gbios.asm').write_bytes(resident.replace('\n','\r\n').encode())
 for argv in [['rmac.com','-gbios'],['link.com','-bios3[os]=gbios,scb']]:run([zxcc,*argv],log=log)
 (BUILD/'gencpm.dat').unlink(missing_ok=True)
 master,slave=pty.openpty();p=subprocess.Popen([str(zxcc),'gencpm.com'],cwd=BUILD,stdin=slave,stdout=slave,stderr=slave);os.close(slave)
 # GENCPM defaults to hexadecimal. Display counts require the decimal # prefix.
 answers=[('Create a new GENCPM.DAT','Y'),('Display Load Map','Y'),('Number of console columns','#80'),('Number of lines','#25'),('Backspace echoes','N'),('Rubout echoes','N'),('Initial default drive','C'),('Top page of memory','FF'),('Bank switched memory','N'),('Double allocation vectors','N'),('Accept new system definition','Y')]
 captured=bytearray();pending='';index=0;end=time.monotonic()+30
 try:
  while True:
   if time.monotonic()>end:raise TimeoutError('GENCPM')
   ready,_,_=select.select([master],[],[],.2)
   if ready:
    try:data=os.read(master,65536)
    except OSError:
     if p.poll() is not None:break
     raise
    if not data:break
    captured.extend(data);pending+=data.decode(errors='replace')
    if index<len(answers) and answers[index][0] in pending and '?' in pending:
     os.write(master,(answers[index][1]+'\n').encode());index+=1;pending=''
   elif p.poll() is not None:break
  assert p.wait()==0 and index==len(answers),captured.decode(errors='replace')
 finally:
  os.close(master)
  if p.poll() is None:p.kill();p.wait()
 log.write(captured);assert b'SYSTEM GENERATION DONE' in captured
 (BUILD/'gencpm-transcript.txt').write_bytes(captured)
# Find the linked native block from its jump-table and entry bytes, not a
# presumed load address. GENCPM relocates BIOS3.SPR into the final image.
sysfile=(BUILD/'cpm3.sys').read_bytes()
loadmap=re.findall(rb'(BIOS3|BDOS3)\s+SPR\s+([0-9A-F]+)H\s+([0-9A-F]+)H',captured)
layout={n.decode():dict(base=int(x,16),bytes=int(y,16)) for n,x,y in loadmap}
assert set(layout)=={'BIOS3','BDOS3'}
# Parse RMAC listing's driver label offset (relative CSEG); map against
# loaded high BIOS in tests, while all test symbol addresses come from here.
symbols=(BUILD/'bios3.sym').read_text(errors='replace')
m=re.search(r'(?i)([0-9a-f]{4})\s+DRIVER',symbols)
assert m,'driver public symbol missing in LINK symbols'
driver_base=layout['BIOS3']['base']+int(m[1],16)
report=dict(version='0.6.8-suc-native',memory_bytes=65536,top_page='FF',layout=layout,driver_base=driver_base,driver_bytes=len(a),relocation_words=len(relocs),symbols={n:driver_base+x for n,x in maps[0].items()},helper=dict(read='003B',write='0041',copy='0047',bytes=19),program_ceiling=layout['BDOS3']['base']-0x300,tpa_bytes=layout['BDOS3']['base']-0x400,loader_prefix_bytes=0x300)
report['console']=dict(columns=80,lines=25,scb_width=79,scb_page_length=24,gencpm_input='explicit decimal #80/#25')
report['cursor']=dict(glyph=0xef,timer_address=0xe002,timer_bit=6,visible_when=0,state_bytes=9,service='CONOUT and CONST/CONIN polling',attributes_preserved=True)
(BUILD/'build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
