from pathlib import Path
import configparser,shutil,sys,hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/interactive-0.1.0';out.mkdir(parents=True,exist_ok=True)
image=ROOT/'build-records/mz800emu/disks/gide-zpm3-pehu-keyboard-fast-0.1.0.img'
if not image.exists():shutil.copyfile(HERE/'build/gide-zpm3-pehu-keyboard-fast.img',image)
else:
 sys.path.insert(0,str(ROOT/'cpm/gide/tools'));from media import hard_volume
 original=image.read_bytes();data=bytearray(original);part=data[:8*1024*1024];v=hard_volume(part)
 files={(e[0],v.name(e)):v.read(v.name(e),e[0]) for _,e in v.directory() if e[0]<16}
 factory=(HERE/'build/gide-zpm3-pehu-keyboard-fast.img').read_bytes();fv=hard_volume(bytearray(factory[:8*1024*1024]))
 installed=['CPM3.SYS','RTC.COM','ZPMINFO.TXT','CCP.COM','ZCCP.COM','ZINSTAL.ZPM','STARTZPM.COM','TCAP.Z3T','TPA.COM','TPATEST.COM','LOADSEG.COM','RSXDIR.COM','DISKINFO.COM','SETPATH.COM','TCVIEW.COM']
 for name in installed:v.write(name,fv.read(name))
 # Restore README only if it is exactly the earlier, unpublished generated text.
 generated=b'PEHU banked CP/M3 test. System bank0, application bank1.\r\nOriginal SUC keyboard and banked VRAM console, C/D GIDE.\r\nKeep CPM3.SYS and CCP.COM. Original0.6.8 disk retained.\r\n'
 restore_readme=files.get((0,'README.TXT'),b'').rstrip(b'\x1a')==generated
 if restore_readme:v.write('README.TXT',fv.read('README.TXT'))
 for (user,name),payload in files.items():
  if (user!=0 or name not in installed) and not(restore_readme and user==0 and name=='README.TXT'):assert v.read(name,user)==payload
 data[:8*1024*1024]=part;data[16*1024*1024:]=factory[16*1024*1024:]
 assert data[8*1024*1024:16*1024*1024]==original[8*1024*1024:16*1024*1024]
 assert image.read_bytes()==original,'Working disk changed during migration'
 image.write_bytes(data)
 (out/'migration.json').write_text(json.dumps(dict(previous_sha256=hashlib.sha256(original).hexdigest(),updated_sha256=hashlib.sha256(data).hexdigest(),other_files_preserved=True,d_drive_unchanged=True,restored_original_readme=restore_readme),indent=2)+'\n')
c=configparser.ConfigParser(interpolation=None);c.read(ROOT/'build-records/mz800emu/cpm3-suc-native/interactive-0.6.8/mz700.ini')
c['MEMEXT']['connected']='1';c['MEMEXT']['type']='PEHU';c['MEMEXT']['filling_on_init']='NULL'
c['ROM']['user_defined_allinone_filepath']=str(HERE/'build/gide-zpm3-pehu-keyboard-fast-stock-rom.bin')
c['ROM']['boot_rom_f000_filepath']=str(HERE/'build/gide-zpm3-pehu-keyboard-fast-bootrom.bin')
c['ROM']['boot_rom_e800_filepath']=str(HERE/'build/gide-zpm3-pehu-keyboard-fast-e800.bin')
c['ROM']['boot_rom_mode']='F000';c['GIDE']['hdd0_filepath']=str(image)
with (out/'mz700.ini').open('w') as f:c.write(f)
launcher=ROOT/'emulators/Start MZ-700 ZPM3 ZCCP PEHU Keyboard Fast - TEST.command'
text=(ROOT/'emulators/Start MZ-700 ZPM3 ZCCP PEHU Screen Fast - TEST.command').read_text().replace('zpm3-pehu-screen-fast/interactive-0.1.0','zpm3-pehu-keyboard-fast/interactive-0.1.0')
launcher.write_text(text);launcher.chmod(0o755)
print(launcher)
