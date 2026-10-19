#!/usr/bin/env python3
"""Construct independent boot ROM/factory ATA image, preserving prior disks."""
from pathlib import Path
import hashlib,json,re,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];BUILD=HERE/'build'
sys.path.insert(0,str(ROOT/'cpm/gide/tools'));from media import hard_volume
loader=(BUILD/'cpmldr.com').read_bytes();padded=loader.ljust((len(loader)+511)//512*512,b'\0')
driver=int(re.search(r'(?i)([0-9a-f]{4})\s+DRIVER',(BUILD/'cpmldr.sym').read_text())[1],16)
(BUILD/'stage.asm').write_text(f'LOADER_DRIVER: EQU {driver}\nLOADER_LBA: EQU 32769\nLOADER_SECTORS: EQU {len(padded)//512}\nLOADER_SUM: EQU {sum(padded)&65535}\n'+(HERE/'bootstrap.asm').read_text())
def asm(src,dst):subprocess.run([sys.executable,str(ROOT/'cpm/gide/third_party/pyz80.py'),'--obj='+str(BUILD/dst),str(BUILD/src)],cwd=BUILD,check=True)
asm('stage.asm','stage.bin');stage=(BUILD/'stage.bin').read_bytes();assert len(stage)<4096
original=(ROOT/'build-records/mz800emu/roms/mz700-13a-eu-font-1e05.bin').read_bytes()
# Preserve the entire monitor and character ROM. The monitor's JF000
# command enters a separate upper boot ROM; nothing patches low ROM.
(BUILD/'reset.asm').write_text(f'ORG 0xF000\nNOP\nDI\nLD HL,0xF100\nLD DE,0x8000\nLD BC,{len(stage)}\nLDIR\nJP 0x8000\n');asm('reset.asm','reset.bin')
boot_rom=bytearray(b'\xff'*4096);reset=(BUILD/'reset.bin').read_bytes()
assert len(reset)<=256 and len(stage)<=3840
boot_rom[:len(reset)]=reset;boot_rom[256:256+len(stage)]=stage
manual_rom=bytearray(original[:8192]+b'\xff'*4096+boot_rom)
(BUILD/'gide-zpm3-pehu-keyboard-fast-manual-rom.bin').write_bytes(manual_rom)
# Address-specific automatic image is optional; it is not the default.
(BUILD/'autostart.asm').write_text(f'ORG 0xE800\nNOP\nDI\nLD HL,0xE900\nLD DE,0x8000\nLD BC,{len(stage)}\nLDIR\nJP 0x8000\n');asm('autostart.asm','autostart.bin')
auto_rom=bytearray(b'\xff'*2048);entry=(BUILD/'autostart.bin').read_bytes()
assert len(entry)<=256 and len(stage)<=1792
auto_rom[:len(entry)]=entry;auto_rom[256:256+len(stage)]=stage
(BUILD/'gide-zpm3-pehu-keyboard-fast-e800.bin').write_bytes(auto_rom)
(BUILD/'gide-zpm3-pehu-keyboard-fast-stock-rom.bin').write_bytes(original[:8192]+b'\xff'*8192)
# No ROM atE800: leave the stock monitor waiting for its normal commands.
rom=manual_rom[:]
assert rom[:8192]==original[:8192]
(BUILD/'gide-zpm3-pehu-keyboard-fast-bootrom.bin').write_bytes(boot_rom)
# Standard Sharp tape container, machine-code type, load/execute at8000.
header=bytearray(128);header[0]=1;header[1:18]=b'GIDE CPM3'+b'\r'*8
header[18:20]=len(stage).to_bytes(2,'little')
header[20:22]=(0x8000).to_bytes(2,'little');header[22:24]=(0x8000).to_bytes(2,'little')
(BUILD/'GIDE-CPM3.MZF').write_bytes(header+stage)
(BUILD/'gide-zpm3-pehu-keyboard-fast-rom.bin').write_bytes(rom)
base=(HERE/'reference/current-fast.img').read_bytes()
assert hashlib.sha256(base).hexdigest()==json.loads((HERE/'reference/current-fast.json').read_text())['sha256']
image=bytearray(base[:16*1024*1024]);part=image[:8*1024*1024];v=hard_volume(part)
v.write('CPM3.SYS',(BUILD/'cpm3.sys').read_bytes())
# Retain installed ZCCP and application contents from the current Fast baseline.
v.write('RTC.COM',(BUILD/'RTC.COM').read_bytes())
v.write('ZPMINFO.TXT',b'PEHU banked ZPM3 N10, native512 sectors. Bank0 system, bank1 application.\r\nOriginal SUC keyboard and banked VRAM console, C/D GIDE.\r\nKeep CPM3.SYS and CCP.COM. Original0.6.8 disk retained.\r\n')
for name in ['AUTOTOG.COM','CLRHIST.COM','SETZ3.COM']:
 if not v.matching(name):v.write(name,(HERE/'reference/zpm3n10'/name).read_bytes())
# Independent shell installation; the old CCP remains in the baseline snapshot.
shell={'CCP.COM':BUILD/'shell/CCP.COM','ZCCP.COM':BUILD/'shell/ZCCP.COM','ZINSTAL.ZPM':BUILD/'shell/ZINSTAL.ZPM','STARTZPM.COM':BUILD/'shell/STARTZPM.COM','TCAP.Z3T':BUILD/'shell/TCAP.Z3T','TPA.COM':BUILD/'shell/TPA.COM','TPATEST.COM':BUILD/'shell/TPATEST.COM'}
for n in ['LOADSEG.COM','RSXDIR.COM','DISKINFO.COM']:shell[n]=HERE/'reference/zccp0293'/n
for n in ['SETPATH.COM','TCVIEW.COM']:shell[n]=HERE/'reference'/n
for n,p in shell.items():v.write(n,p.read_bytes())
image[:8*1024*1024]=part;header=bytearray(512);header[:8]=b'GIDEZPM!';image+=header+padded
(BUILD/'gide-zpm3-pehu-keyboard-fast.img').write_bytes(image)
report=json.loads((BUILD/'build.json').read_text());report['boot']=dict(header='GIDEZPM!',loader_lba=32769,loader_bytes=len(loader),sectors=len(padded)//512,checksum=sum(padded)&65535,monitor_unchanged=True,monitor_entry=0,boot_rom_entry=0xF000,separate_boot_rom_required=True,automatic_boot=False,ram_loader_entry=0x8000,boot_command='F',sharp_display_initialisation=True)
report['files']={n:dict(bytes=(BUILD/n).stat().st_size,sha256=hashlib.sha256((BUILD/n).read_bytes()).hexdigest()) for n in ['cpmldr.com','cpm3.sys','bnkbios3.spr','gide-zpm3-pehu-keyboard-fast-rom.bin','gide-zpm3-pehu-keyboard-fast.img','stage.bin','gide-zpm3-pehu-keyboard-fast-bootrom.bin','GIDE-CPM3.MZF','gide-zpm3-pehu-keyboard-fast-manual-rom.bin','gide-zpm3-pehu-keyboard-fast-stock-rom.bin','gide-zpm3-pehu-keyboard-fast-e800.bin']}
(BUILD/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['boot']))
