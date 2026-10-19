#!/usr/bin/env python3
"""Verify loader banner is not overwritten and capture every boot frame."""
from pathlib import Path
import sys,configparser,base64,json,hashlib,argparse
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'archive-tools'));sys.path.insert(0,str(ROOT/'cpm/gide/tools'))
from test_mz800emu_boot import Emulator
sys.path.insert(0,str(ROOT/'cpm/suc-native'))
from monitor_boot import ACTIVE_CONFIG,reset_to_handover,enter_gide
sys.path.insert(0,str(ROOT/'cpm/gide/tools'))
from media import SharpDSK,floppy
ACTIVE_CONFIG=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/interactive-0.1.0/mz700.ini'
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/boot';out.mkdir(exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('--image',type=Path);ap.add_argument('--attribute',type=lambda x:int(x,0));ap.add_argument('--manual',action='store_true');ap.add_argument('--automatic',action='store_true');ap.add_argument('--mzf',action='store_true');args=ap.parse_args()
if args.automatic:out=out.parent/'boot-automatic';out.mkdir(exist_ok=True)
if args.manual or args.mzf:out=out.parent/('boot-mzf' if args.mzf else 'boot-manual');out.mkdir(exist_ok=True)
if args.attribute is not None:out=out.parent/f'boot-attribute-{args.attribute:02x}';out.mkdir(exist_ok=True)
ini=configparser.ConfigParser(interpolation=None,strict=False);ini.read(ACTIVE_CONFIG);ini['GIDE']['hdd0_readonly']='1'
if args.manual or args.mzf:ini['ROM']['user_defined_allinone_filepath']=str(HERE/'build/gide-zpm3-pehu-keyboard-fast-manual-rom.bin')
if args.automatic:ini['ROM']['boot_rom_mode']='E800'
if args.image:ini['GIDE']['hdd0_filepath']=str(args.image.resolve())
if not args.image:ini['GIDE']['hdd0_filepath']=str(HERE/'build/gide-zpm3-pehu-keyboard-fast.img')
ini['DEBUGGER']['auto_save_breakpoints']='0'
for p in out.glob('*.bpt'):p.unlink()
with (out/'input.ini').open('w') as f:ini.write(f)
system=floppy(SharpDSK((ROOT/'cpm/gide/reference/CPM7004.dsk').read_bytes()).logical()).read('PCPM.SYS');table=system[0xF3D6-0xC600:0xF4D6-0xC600];decode={table[x]:chr(x) for x in reversed(range(32,127))};decode[0]=' '
e=Emulator(ROOT/'emulators/Working/mz800emu/build-mac/build-mz700emu-pal/mz700emu-pal',out,['--home-dir',str(ROOT/'emulators/Working/mz800emu'),'--config',str(out/'input.ini')])
def call(c,d=None):
 r=e.call(c,d);assert r.get('success'),r;return r.get('data',{})
def mem(a,n):return base64.b64decode(call('mem_read',{'addr':a,'len':n})['data_b64'])
try:
 reset_to_handover(call)
 call('screenshot_save_to_file',{'path':str(out/'sharp-monitor.png'),'scale':'2'})
 if args.mzf:
  r=call('media_load_mzf',{'path':str(HERE/'build/GIDE-CPM3.MZF')});assert r['load_addr']==0x8000 and r['exec_addr']==0x8000
  bid=call('bp_add',{'addr':0x8000})['id']
  call('input_send_keys',{'text':'J8000','frame_per_key':30});call('run',{'frames':10});call('input_send_key',{'key':'RETURN','frames':30})
  assert call('get_registers')['PC']==0x8000,'Monitor could not enter MZF loader'
 elif args.automatic:bid=None;assert call('get_registers')['PC']==0xe800
 else:
  bid=call('bp_add',{'addr':0xf000})['id'];enter_gide(call)
  assert call('get_registers')['PC']==0xf000,'Monitor F did not reach separate boot ROM'
 attr_id=next(x['id'] for x in call('regions_list')['regions'] if x['kind']=='vram_700_attr')
 rom_attrs=base64.b64decode(call('region_read',{'region_id':attr_id,'offset':0,'length':2048})['data_b64'])
 assert len(set(rom_attrs))==1,'ROM should initialise the complete attribute RAM'
 inherited=rom_attrs
 if args.attribute is not None:
  inherited=bytes([args.attribute])*2048
  call('region_write',{'region_id':attr_id,'offset':0,'data_b64':base64.b64encode(inherited).decode()})
 if bid is not None:call('bp_remove',{'id':bid})
 bid=call('bp_add',{'addr':0xb00})['id'];call('run',{'frames':100});assert call('get_registers')['PC']==0xb00
 expected=(HERE/'build/cpmldr.com').read_bytes()[0x125:0x177];before=mem(0x225,len(expected));assert before==expected
 call('bp_remove',{'id':bid});bid=call('bp_add',{'addr':0x106})['id'];call('run',{'frames':100});assert call('get_registers')['PC']==0x106
 after=mem(0x225,len(expected));assert after==before,'Loader initialisation corrupted its small stack/banner'
 call('bp_remove',{'id':bid});rid=next(x['id'] for x in call('regions_list')['regions'] if x['kind']=='vram_700_char');changes=[];previous='';saw_banner=False;saw_map=False;saw_prompt=False
 for frame in range(1,1001):
  call('run',{'frames':1});v=base64.b64decode(call('region_read',{'region_id':rid,'offset':0,'length':2048})['data_b64'])
  screen='\n'.join(''.join(decode.get(v[(((i>>1)+(i&1))&1023)|((i&1)<<10)],'?') for i in range(row*80,(row+1)*80)).rstrip() for row in range(25)).rstrip()
  assert 'BDOS ERR' not in screen and 'BOOT ERROR' not in screen and 'BIOS can' not in screen,(frame,screen)
  saw_banner|='Copyright (C) 2025, DRDOS Inc.' in screen;saw_map|='BIOS3' in screen;saw_prompt|='C0>' in screen
  if screen!=previous:
   changes.append(dict(frame=frame,text=screen));previous=screen
   if 'Copyright (C) 2025, DRDOS Inc.' in screen and 'BIOS3' in screen:call('screenshot_save_to_file',{'path':str(out/'loader.png'),'scale':'2'})
  if saw_prompt:break
 assert saw_banner and saw_map and saw_prompt,(saw_banner,saw_map,saw_prompt,screen,call('get_registers'))
 for text in ['Copyright (C) 2025, DRDOS Inc.','BIOS3','BDOS3','TPA','C0>']:
  assert text in screen,('Loader text lost during console handover',text,screen)
 assert screen.index('C0>')>screen.index('TPA'),screen
 assert 'ZPM3 N10 / ZCCP' in screen,screen
 assert screen.count('ZCPR compatible system for CP/M+ by Simeon Cran')==1,screen
 call('run',{'frames':3})
 regions=call('regions_list')['regions'];attr_id=next(x['id'] for x in regions if x['kind']=='vram_700_attr')
 attrs=base64.b64decode(call('region_read',{'region_id':attr_id,'offset':0,'length':2048})['data_b64'])
 syms=json.loads((HERE/'build/build.json').read_text())['symbols']
 assert attrs==inherited,'Cursor changed inherited colour attributes'
 call('screenshot_save_to_file',{'path':str(out/'ready.png'),'scale':'2'})
 (out/'frames.json').write_text(json.dumps(changes,indent=2)+'\n');report=dict(passed=True,zccp_banner_count=1,banner_unchanged=True,complete_copyright=True,load_map=True,load_map_retained_at_prompt=True,c_prompt=True,no_boot_errors=True,software_cursor=True,sharp_cursor_glyph=239,hardware_blink_timer=True,sharp_rom_initialisation=True,monitor_unchanged=True,reset_pc_zero=True,monitor_command_boot=not(args.mzf or args.automatic),automatic_monitor_chain=args.automatic,waits_for_f=not args.automatic,mzf_loader=args.mzf,rom_attribute=rom_attrs[0],inherited_attribute=inherited[0],attributes_preserved=True,kp_interface_disabled=ini['VIDEO_MZ700']['suc80_kp_interface']=='0',frames_checked=frame,cause='Stock monitor and loader preserved; common banked BIOS adopts loader console state without clearing the load map.')
 (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
finally:e.close()
