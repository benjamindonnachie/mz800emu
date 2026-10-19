#!/usr/bin/env python3
"""Independent PEHU banked CP/M3, using unoptimised SUC Native driver."""
from pathlib import Path
import argparse,base64,hashlib,json,os,pickle,pty,re,select,shutil,subprocess,sys,time,tarfile,tempfile
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]; BUILD=HERE/'build';BUILD.mkdir(exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('--zxcc',type=Path,default=Path('/tmp/mz-cpm3-zxcc/bin/zxcc'));args=ap.parse_args();zxcc=args.zxcc
REF=ROOT/'cpm/cpm3-on2/reference';PYZ=ROOT/'cpm/gide/third_party/pyz80.py'
if not zxcc.exists():
 tools=Path(tempfile.mkdtemp(prefix='mz-pehu-zxcc-',dir='/tmp'))
 with tarfile.open(ROOT/'cpm/cpm3-on2/toolchain/zxcc-0.5.7.tar.gz') as archive:
  assert all(not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in archive.getmembers())
  archive.extractall(tools,filter='data')
 source=tools/'zxcc-0.5.7';prefix=tools/'installed'
 for command in [['./configure','--prefix='+str(prefix)],['make','-j4'],['make','install']]:
  result=subprocess.run(command,cwd=source,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  assert result.returncode==0,result.stdout.decode(errors='replace')
 zxcc=prefix/'bin/zxcc'

def run(cmd):
 p=subprocess.run(list(map(str,cmd)),cwd=BUILD,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 (BUILD/'build.log').open('ab').write(p.stdout)
 assert p.returncode==0 and not re.search(rb'\[[^\r\n]*\?',p.stdout),p.stdout.decode(errors='replace')
 if any(str(x).endswith('rmac.com') for x in cmd): assert not re.search(rb'(?m)^[A-Z?] {2,}',p.stdout),p.stdout.decode(errors='replace')
 return p.stdout
(BUILD/'build.log').write_bytes(b'')
provenance=json.loads((HERE/'upstream-dri/provenance.json').read_text())
for name,digest in provenance['files'].items():assert hashlib.sha256((HERE/'upstream-dri'/name).read_bytes()).hexdigest()==digest,name
for name in ['cpm/suc-native/build/cpmldr.com','cpm/suc-native/build/cpmldr.sym','cpm/suc-native/build.py','cpm/suc-native/build/build.json']:
 expected=json.loads((HERE/'loader-inputs.json').read_text())[name];assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
for n in ['rmac.com','scb.rel']:
 shutil.copyfile(REF/n,BUILD/n)
shutil.copyfile(HERE/'upstream-dri/drlink.com',BUILD/'link.com')
for n in ['gencpm.com','ccp.com']:shutil.copyfile(REF/'utilities'/n,BUILD/n)
for n in ['cpmldr.com','cpmldr.sym']:shutil.copyfile(ROOT/'cpm/suc-native/build'/n,BUILD/n)
# Native512 driver; common ATA transfers honour the selected DMA bank.
# Head is extracted as a string literal without executing original build.py.
import ast
parsed=ast.parse((ROOT/'cpm/suc-native/build.py').read_text())
head=next(ast.literal_eval(n.value) for n in parsed.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='head' for t in n.targets))
disk=(HERE/'disk.asm').read_text()
body=head+'\n'.join((HERE/n).read_text() for n in ['banking.asm','keyboard.asm','suc-keyboard.asm','console.asm','rtc.asm','startup.asm','direct-move.asm'])+'\n'+disk
body='COMMON_MOVE_PENDING: EQU 0xD1D1\nCOMMON_MOVE_SOURCE: EQU 0xD2D2\nCOMMON_MOVE_DEST: EQU 0xD3D3\nCOMMON_CALLER_BANK: EQU 0xD4D4\nSCB_DATE: EQU 0xDADA\nCOMMON_TO_DMA: EQU 0xD5D5\nCOMMON_FROM_DMA: EQU 0xD6D6\n'+body

def assemble(text,tag):
 blobs=[];symbols=[]
 for origin in (0,256,32768):
  src=BUILD/f'{tag}-{origin}.asm';src.write_text(f'ORG {origin}\n'+text)
  run([sys.executable,PYZ,'--obj='+str(src.with_suffix('.bin')),'--exportfile='+str(src.with_suffix('.symbols')),src])
  blobs.append(src.with_suffix('.bin').read_bytes());symbols.append(pickle.loads(src.with_suffix('.symbols').read_bytes()))
 a,b,c=blobs;assert len(a)==len(b)==len(c)
 relocs={i-1 for i,(x,y) in enumerate(zip(a,b)) if x!=y}
 expected=bytearray(a)
 for i in relocs:expected[i:i+2]=((int.from_bytes(a[i:i+2],'little')+32768)&65535).to_bytes(2,'little')
 assert expected==c
 return a,relocs,symbols[0]
a,ar,am=assemble(body,'native')
sys.path.insert(0,str(ROOT/'cpm/gide/tools'))
from media import SharpDSK,floppy
system=floppy(SharpDSK((ROOT/'cpm/gide/reference/CPM7004.dsk').read_bytes()).logical()).read('PCPM.SYS')
provenance=json.loads((HERE/'keyboard-provenance.json').read_text())
assert hashlib.sha256(system).hexdigest()==provenance['original_sys_sha256']
patches=json.loads((HERE/'keyboard-relocations.json').read_text())
expected=bytearray(system[patches['base']-0xC600:patches['end']-0xC600])
for r in patches['relocations']:
 at=r['offset'];assert int.from_bytes(expected[at:at+2],'little')==r['original']
 name,_,add=r['expression'].partition('+');value=am[name]+(int(add) if add else 0)
 expected[at:at+2]=value.to_bytes(2,'little')
for r in patches['nop_patches']:
 at=r['offset'];assert expected[at:at+r['bytes']]==bytes.fromhex(r['original']);expected[at:at+r['bytes']]=bytes(r['bytes'])
for r in patches.get('instruction_patches',[]):
 at=r['offset'];before=bytes.fromhex(r['original']);after=bytes.fromhex(r['replacement'])
 assert len(before)==len(after)
 assert expected[at:at+len(before)]==before
 expected[at:at+len(before)]=after
assert a[am['suc_blob']:am['suc_blob']+len(expected)]==expected
assert a[am['suc_macros']:am['suc_macros']+256]==system[0xDF00-0xC600:0xE000-0xC600]
assert a[am['suc_special_macros']:am['suc_special_macros']+128]==system[0xE000-0xC600:0xE080-0xC600]

external={'T_SELECT':'select','T_CONST':'console_status','T_CONIN':'console_input','T_CONOUT':'console_output','T_HOME':'disk_home','T_TRACK':'set_track','T_SECTOR':'set_sector','T_DMA':'set_dma','T_READ':'read','T_WRITE':'write','T_KEYINIT':'keyboard_init','T_CURSOR':'cursor_row','T_HELPER':'install_helper','T_TIME':'rtc_time','T_STARTUP':'startup_banner','T_MOVE':'direct_move'}
markers={n:0xA500+am[v] for n,v in external.items()}
loader_driver=int(re.search(r'(?i)([0-9a-f]{4})\s+DRIVER',(BUILD/'cpmldr.sym').read_text())[1],16)
loader_reference=json.loads((ROOT/'cpm/suc-native/build/build.json').read_text())
loader_cursor=loader_driver+loader_reference['symbols']['cursor_row']-loader_reference['driver_base']
common='\n'.join(f'{n}: EQU {v}' for n,v in markers.items())+f'\nLOADER_CONSOLE: EQU {loader_cursor}\nSCB_MXTPA: EQU 0xFE62\n'+(HERE/'common.asm').read_text()
c,cr,cm=assemble(common,'common')
assert len(c)<=2048,('Common BIOS would reduce TPA',len(c))

def emit(data,relocs,base,fixes,fix_locations):
 lines=[base+':'];i=0
 while i<len(data):
  word=int.from_bytes(data[i:i+2],'little')
  if i in fix_locations:
   assert word in fixes
   lines.append('\tdw\t'+fixes[word]);i+=2
  elif i in relocs:lines.append(f'\tdw\t{base}+0{word:04x}h');i+=2
  else:lines.append(f'\tdb\t0{data[i]:02x}h');i+=1
 return '\n'.join(lines)+'\n'
# Common references into the banked segment and vice versa remain LINK relocations.
cf={markers[n]:'driver+0%04xh'%am[v] for n,v in external.items()};cf[0xFE62]='@mxtpa'
af={0xD1D1:'cbbase+0%04xh'%cm['move_pending'],0xD2D2:'cbbase+0%04xh'%cm['move_source'],0xD3D3:'cbbase+0%04xh'%cm['move_dest'],0xD4D4:'cbbase+0%04xh'%cm['gate_saved_bank'],0xDADA:'@date',0xD7D7:'cbbase+0%04xh'%cm['public_dpb'],0xD8D8:'cbbase+0%04xh'%cm['public_alv_c'],0xD9D9:'cbbase+0%04xh'%cm['public_alv_d'],0xD5D5:'cbbase+0%04xh'%cm['to_dma'],0xD6D6:'cbbase+0%04xh'%cm['from_dma']}
# Marker values can occur accidentally in opcodes or data. Prove reference
# locations by changing the source EQU values and assembling a second time.
# In this build T_TIME happens to be B0EDh, exactly the bytes ED B0 (LDIR).
# Never infer a reference from matching those bytes alone.
def external_locations(source,blob,fixes,tag):
 def change(match):
  value=int(match[2],0)
  return match[1]+str(value^0xFFFF) if value in fixes else match[0]
 altered=re.sub(r'(?im)^(\w+:\s*EQU\s+)(0x[0-9a-f]+|[0-9]+)\s*$',change,source)
 other,_,_=assemble(altered,tag+'-external-check')
 assert len(blob)==len(other)
 changed={i for i,(x,y) in enumerate(zip(blob,other)) if x!=y};locations=set()
 while changed:
  at=min(changed)
  assert at+1 in changed,(tag,at,'not a whole external word')
  word=int.from_bytes(blob[at:at+2],'little')
  assert word in fixes and int.from_bytes(other[at:at+2],'little')==word^0xFFFF,(tag,at,word)
  locations.add(at);changed.remove(at);changed.remove(at+1)
 return locations
cl=external_locations(common,c,cf,'common');al=external_locations(body,a,af,'native')
s='\textrn\t@mxtpa,@date\n\tpublic\tcbbase,driver\n\tcseg\n'+emit(c,cr,'cbbase',cf,cl)+'\tdseg\n'+emit(a,ar,'driver',af,al)+'\tend\n'
(BUILD/'bios.asm').write_bytes(s.replace('\n','\r\n').encode())
# Preserve the supplied N10 machine code and relocation maps verbatim.
pinned=json.loads((HERE/'reference/provenance.json').read_text())['files']
for name in ['RESBDOS3.SPR','BNKBDOS3.SPR']:
 raw=(HERE/'reference/zpm3n10'/name).read_bytes()
 assert hashlib.sha256(raw).hexdigest()==pinned[name]['sha256'],name
 assert raw[256:262]==b'SIMEON',name
 shutil.copyfile(HERE/'reference/zpm3n10'/name,BUILD/name.lower())
run([zxcc,'rmac.com','-bios']);run([zxcc,'link.com','-bnkbios3[os,b]=bios,scb'])
(BUILD/'gencpm.dat').unlink(missing_ok=True)
master,slave=pty.openpty();p=subprocess.Popen([str(zxcc),'gencpm.com'],cwd=BUILD,stdin=slave,stdout=slave,stderr=slave);os.close(slave)
answers=[('Create a new GENCPM.DAT','Y'),('Display Load Map','Y'),('Number of console columns','#80'),('Number of lines','#25'),('Backspace echoes','N'),('Rubout echoes','N'),('Initial default drive','C'),('Top page of memory','FF'),('Bank switched memory','Y'),('Common memory base page','C0'),('Long error messages','Y'),('Accept new system definition','Y')]
captured=bytearray();pending='';idx=0;end=time.monotonic()+20
try:
 while True:
  if time.monotonic()>end:raise TimeoutError('GENCPM waiting: '+pending)
  ready,_,_=__import__('select').select([master],[],[],.1)
  if ready:
   try:data=os.read(master,65536)
   except OSError:
    if p.poll() is not None:break
    raise
   if not data:break
   captured.extend(data);pending+=data.decode(errors='replace')
   if idx<len(answers) and answers[idx][0] in pending and '?' in pending:
    os.write(master,(answers[idx][1]+'\n').encode());idx+=1;pending=''
  elif p.poll() is not None:break
 assert p.wait()==0 and idx==len(answers),captured.decode(errors='replace')
finally:
 (BUILD/'gencpm-transcript.txt').write_bytes(captured);os.close(master)
 if p.poll() is None:p.kill();p.wait()
assert b'SYSTEM GENERATION DONE' in captured
symbols=(BUILD/'bnkbios3.sym').read_text();linked={n:int(x,16) for x,n in re.findall(r'([0-9A-F]{4})\s+(CBBASE|DRIVER)',symbols,re.I)}
report={'version':'0.1.0-zpm3-pehu-keyboard-fast','common_raw_bytes':len(c),'native_bytes':len(a),'native_offsets':am,'common_offsets':cm,'linked':linked,'loader_driver':loader_driver,'common_boundary':0xC000,'system_bank':0,'application_bank':1,'shared_low_bytes':8192}
(BUILD/'build.json').write_text(json.dumps(report,indent=2)+'\n')
layout=[dict(module=n.decode(),base=int(x,16),bytes=int(y,16)) for n,x,y in re.findall(rb'(BNKBIOS3|RESBDOS3|BNKBDOS3)\s+SPR\s+([0-9A-F]+)H\s+([0-9A-F]+)H',captured)]
report['layout']=layout
report['physical_sector_bytes']=512
report['dpb']={'spt':128,'psh':2,'phm':3}
report['private_bios_deblocking']=False
report['bdos_buffers']={'directory_per_drive':512,'data_per_drive':512,'bank':0}
report['rtc']={'chip':'RTC72421','ports':'nA5','service_bank':0,'calendar_window':'1978..2077','read_from_board_every_call':True,'cold_boot_seeds_scb':True,'no_extra_low_ram':True,'no_extra_rom_gateway':True,'time_vector_offset':78,'caller_registers_preserved':['BC','DE','HL'],'caller_bank_iff_preserved':True}
report['common_base']=layout[0]['base'];report['driver_base']=layout[1]['base']
report['symbols']={n:report['driver_base']+v for n,v in am.items() if v<len(a)}
report['symbols'].update({n:report['common_base']+cm[v] for n,v in [('dpb','public_dpb'),('allocation_c','public_alv_c'),('allocation_d','public_alv_d')]})
report['common_symbols']={n:report['common_base']+v for n,v in cm.items()}
assert layout[0]['base']==0xF800 and layout[2]['base']==0xF200,layout
report['zccp_tpa_bytes']=60672
assert report['driver_base']>=0x6000, 'Native copy code must remain outside alias windows'
report['speed']={'direct_page_copy':True,'move_unroll_bytes':16,'ata_unroll_bytes':16,'video_unroll_bytes':16,'alias_windows':[0x2000,0x4000],'max_chunk_bytes':8192,'gate_stack_bytes':80,'redundant_mapping_skipped':True,'overlap_forward_semantics_retained':True}
report['speed'].update(screen_access_inlined=True,row_offset_lookup=True,private_masked_mapper=True,masked_mapper_saved_tstates_per_call=52)
report['speed'].update(keyboard_direct_word_load=True,keyboard_word_load_saved_tstates=17,keyboard_slot_bytes=8)
report['external_fixups']={'method':'source EQU perturbation, two-byte delta proof','common':len(cl),'native':len(al),'common_marker_byte_collisions_ignored':[i for i in range(len(c)-1) if int.from_bytes(c[i:i+2],'little') in cf and i not in cl]}
report['zccp_net_tpa_cost_bytes']=1024
report['zccp_startup']='Complete C-drive-patched ZCCP as CCP.COM; automatic ZINSTAL once'
report['resident_bdos_base']=layout[2]['base'];report['normal_application_tpa_bytes']=layout[2]['base']-0x100
(BUILD/'build.json').write_text(json.dumps(report,indent=2)+'\n')
print(captured.decode(errors='replace'));print(report['linked'])

run([sys.executable,PYZ,'--obj='+str(BUILD/'RTC.COM'),HERE/'rtc_command.asm'])

run([sys.executable,HERE/'shell.py'])
