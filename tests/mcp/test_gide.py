#!/usr/bin/env python3
"""Native Z80 GIDE tests with disposable raw images, never archival media."""
import base64
import json
import os
from pathlib import Path
import tempfile
import zipfile
import hashlib
import re
from test_suc80_display import Emu, REPO
import emu_test_proc


def out(port,value):
    return bytes((0x3e,value,0xd3,port))


def task(base,lba,count=1,slave=False,cmd=0x20):
    return b''.join(out(base+r,v) for r,v in (
        (14,0xe0|(0x10 if slave else 0)|((lba>>24)&15)),
        (10,count),(11,lba&255),(12,(lba>>8)&255),(13,(lba>>16)&255),(15,cmd)))


def read_data(e,base,n=512):
    # INIR decrements B, so full I/O high-address lines vary on every byte.
    assert n%256==0
    code=b'\xf3\x21\x00\x90'+bytes((0x0e,base+8))
    code+=(b'\x06\x00\xed\xb2')*(n//256)
    e.cpu(code)
    return base64.b64decode(e.call('mem_read',{'addr':0x9000,'len':n})['data_b64'])


def write_data(e,base,data):
    assert len(data)%256==0
    e.call('mem_write',{'addr':0x9000,'data_hex':data.hex()})
    e.cpu(b'\xf3\x21\x00\x90'+bytes((0x0e,base+8))+(b'\x06\x00\xed\xb3')*(len(data)//256))


def inp(e,port):
    e.cpu(b'\xf3\x01'+port.to_bytes(2,'little')+b'\xed\x78\x32\x00\xb0')
    return base64.b64decode(e.call('mem_read',{'addr':0xb000,'len':1})['data_b64'])[0]


def rtc_out(e,base,reg,value):
    e.cpu(b'\xf3\x01'+((reg<<8)|(base+5)).to_bytes(2,'little')+bytes((0x3e,value,0xed,0x79)))


def snapshot_variant(src,dst,change):
    with zipfile.ZipFile(src) as z:
        files={n:z.read(n) for n in z.namelist()}
    change(files)
    digest=hashlib.sha256()
    for name in sorted(files):
        if name!='manifest.xml':digest.update(files[name])
    files['manifest.xml']=re.sub(rb'(<value type="string">)[0-9a-f]{64}(</value>)',
        lambda m:m[1]+digest.hexdigest().encode()+m[2],files['manifest.xml'])
    with zipfile.ZipFile(dst,'w') as z:
        for name,data in files.items():z.writestr(name,data)


def main():
    emu_test_proc.install(deadline_s=180)
    exe=Path(os.environ.get('MZ_EMU',REPO/'build-mac/build-mz700emu-pal/mz700emu-pal')).resolve()
    work=Path(os.environ.get('MZ_GIDE_TEST_OUTPUT',tempfile.mkdtemp(prefix='mz700-gide-'))).resolve()
    work.mkdir(parents=True,exist_ok=True)
    master=work/'master.img'; slave=work/'slave.img'
    pattern=bytes((i*37+i//512*13)&255 for i in range(512*2048))
    master.write_bytes(pattern); slave.write_bytes(bytes(x^0xa5 for x in pattern))
    original_slave=hashlib.sha256(slave.read_bytes()).hexdigest()
    ini=f'[GIDE]\nenabled=1\nbase=0xa0\nhdd0_filepath={master}\nhdd0_readonly=0\nhdd1_filepath={slave}\nhdd1_readonly=1\n'
    checks=[]; e=Emu(exe,work/'enabled',True,ini); b=0xa0
    try:
        e.cpu(task(b,0,cmd=0xec))
        assert inp(e,b+6)&0x48==0x48
        ident=read_data(e,b)
        assert int.from_bytes(ident[120:124],'little')==2048
        assert ident[99]&2==2
        assert ident[54:94][0:2]==b'ZM'
        assert inp(e,b+15)==0x50
        checks.append('IDENTIFY capacity, model, LBA capability and DRQ completion')
        for lba,n in ((0,1),(17,2),(2047,1)):
            e.cpu(task(b,lba,n))
            assert read_data(e,b,512*n)==pattern[512*lba:512*(lba+n)]
            assert inp(e,b+15)==0x50
        checks.append('Real Z80 INIR reads sector zero, multiple sectors and final sector')
        e.cpu(task(b,3,slave=True))
        assert read_data(e,b)==bytes(x^0xa5 for x in pattern[1536:2048])
        e.cpu(task(b,3,slave=True,cmd=0x30))
        assert inp(e,b+15)&1 and inp(e,b+9)==4
        assert hashlib.sha256(slave.read_bytes()).hexdigest()==original_slave
        e.cpu(out(b+14,0xe0)+out(b+10,1)+out(b+11,7)+out(b+12,0)+out(b+13,0)+out(b+14,0xf0)+out(b+15,0x20))
        assert read_data(e,b)==bytes(x^0xa5 for x in pattern[7*512:8*512])
        checks.append('ATA parameter writes broadcast before late master/slave selection')
        checks.append('Slave selection and read-only write rejection leave image unchanged')
        new=bytes((255-i*11)&255 for i in range(1024))
        e.cpu(task(b,37,2,cmd=0x30)); write_data(e,b,new)
        assert inp(e,b+15)==0x50
        data=master.read_bytes()
        assert data[:37*512]==pattern[:37*512] and data[39*512:]==pattern[39*512:]
        assert data[37*512:39*512]==new
        e.cpu(task(b,37,2)); assert read_data(e,b,1024)==new
        checks.append('Real Z80 OTIR multi-sector write persists exactly the addressed bytes')
        for lba,count in ((2048,1),(2047,2),(0xfffffff,1)):
            before=hashlib.sha256(master.read_bytes()).hexdigest()
            e.cpu(task(b,lba,count,cmd=0x30))
            assert inp(e,b+15)&1 and inp(e,b+9)==16
            assert hashlib.sha256(master.read_bytes()).hexdigest()==before
        checks.append('Out-of-range transfers fail with IDNF without growing or changing image')
        e.cpu(task(b,0,0)); assert read_data(e,b,512*1)==pattern[:512]
        assert inp(e,b+10)==255
        e.cpu(out(b+15,0xff)); assert inp(e,b+9)==4
        checks.append('Zero sector count means 256; unsupported command returns ABRT')
        # CHS C=0,H=1,S=1 corresponds to LBA63 with default16/63 translation.
        e.cpu(b''.join(out(b+r,v) for r,v in ((14,0xa1),(10,1),(11,1),(12,0),(13,0),(15,0x20))))
        assert read_data(e,b)==pattern[63*512:64*512]
        e.cpu(out(b+11,0)+out(b+15,0x20)); assert inp(e,b+9)==16
        # Reprogramme CHS to 4 heads, 16 sectors, then C=1,H=2,S=3 => LBA98.
        e.cpu(out(b+14,0xa3)+out(b+10,16)+out(b+15,0x91))
        assert inp(e,b+15)==0x50
        e.cpu(b''.join(out(b+r,v) for r,v in ((14,0xa2),(10,1),(11,3),(12,1),(13,0),(15,0x20))))
        assert read_data(e,b)==pattern[98*512:99*512]
        checks.append('One-based CHS and INITIALISE DEVICE PARAMETERS translation')
        # RTC high address lines and high aliases; STOP permits deterministic values.
        rtc_out(e,b,15,6); rtc_out(e,b,13,1)
        digits=[5,4,4,3,3,2,8,1,0,1,6,2,0]  # 2026-10-18 23:34:45, Sunday
        for reg,value in enumerate(digits): rtc_out(e,b,reg,value|0xa0)
        for reg,value in enumerate(digits): assert inp(e,(reg<<8)|(b+5))==value
        assert inp(e,0xf0a5)==5
        assert inp(e,0x0da5)==1
        rtc_out(e,b,13,0); assert inp(e,0x0da5)==2
        rtc_out(e,b,13,8)  # nearest minute 23:35:00
        assert [inp(e,(i<<8)|(b+5)) for i in range(6)]==[0,0,5,3,3,2]
        rtc_out(e,b,15,2)  # 12h +STOP: 11:35 PM
        assert inp(e,0x04a5)==1 and inp(e,0x05a5)==5
        rtc_out(e,b,15,6)
        checks.append('RTC full 16-bit decoding, nibble writes, HOLD/BUSY, STOP, 12/24h and ADJ')
        # Low read latches a whole word. ALT STATUS and RTC leave phase alone.
        e.cpu(task(b,0)); assert inp(e,b+8)==pattern[0]
        inp(e,b+6); inp(e,0x00a5)
        assert inp(e,b+8)==pattern[1]
        assert inp(e,b+8)==pattern[2]
        inp(e,b+9)  # ERROR resets GAL phase, discarding the latched high byte3.
        assert inp(e,b+8)==pattern[4]
        snap=e.folder/'mid-read.mzs'; e.call('snapshot_save',{'path':str(snap)})
        assert inp(e,b+8)==pattern[5]
        e.cpu(out(b+15,0xff)); e.call('snapshot_load',{'path':str(snap)})
        assert inp(e,b+8)==pattern[5] and inp(e,b+8)==pattern[6]
        checks.append('Shared byte latch: task registers reset phase; RTC/alternate status preserve it; snapshot restores mid-word read')
        # Save between low/high WRITE bytes, restore buffer and byte latch.
        e.cpu(task(b,101,cmd=0x30)); e.cpu(out(b+8,0x12))
        snap=e.folder/'mid-write.mzs'; e.call('snapshot_save',{'path':str(snap)})
        e.cpu(out(b+8,0x34)); e.call('snapshot_load',{'path':str(snap)})
        e.cpu(out(b+8,0x56))
        e.call('mem_write',{'addr':0x9000,'data_hex':(b'\x78\x9a'*255).hex()})
        e.cpu(b'\xf3\x21\x00\x90'+bytes((0x0e,b+8))+b'\x06\xff\xed\xb3'*2)
        assert master.read_bytes()[101*512:102*512]==b'\x12\x56'+b'\x78\x9a'*255
        checks.append('Snapshot restores partial WRITE buffer and byte latch without duplicate disk writes')
        # Hardware reset and SRST abort partial transfers; reset never writes disk.
        before=master.read_bytes()
        e.cpu(task(b,102,cmd=0x30)); write_data_short=out(b+8,1)+out(b+8,2)
        e.cpu(write_data_short+out(b+6,4)); assert inp(e,b+6)==0x80
        e.cpu(out(b+6,0)); assert inp(e,b+15)==0x50 and inp(e,b+11)==1
        assert master.read_bytes()==before
        e.cpu(task(b,103,cmd=0x30)+out(b+8,1)); e.call('reset'); e.call('run',{'frames':100})
        assert inp(e,b+15)==0x50 and master.read_bytes()==before
        assert inp(e,0x0fa5)==6  # host reset leaves battery-backed STOP/time intact
        checks.append('SRST and host reset abort partial writes, restore ATA signature and preserve RTC')
        snap=e.folder/'baseline.mzs';e.call('snapshot_save',{'path':str(snap)})
        for kind in ('bad-position','wrong-media','legacy'):
            dest=e.folder/(kind+'.mzs')
            def change(files):
                if kind=='legacy':
                    files.pop('devices/gide.xml');files.pop('devices/gide.bin')
                elif kind=='bad-position':
                    files['devices/gide.xml']=re.sub(rb'(<pos[^>]*>)[0-9]+',rb'\g<1>511',files['devices/gide.xml'],count=1)
                else:
                    files['devices/gide.xml']=files['devices/gide.xml'].replace(b'master.img',b'other.img')
            snapshot_variant(snap,dest,change)
            if kind=='legacy':
                e.cpu(task(b,0));assert inp(e,b+8)==pattern[0]
                e.call('snapshot_load',{'path':str(dest)})
                assert inp(e,b+15)==0x50 and inp(e,b+11)==1
            else:
                try:e.call('snapshot_load',{'path':str(dest)})
                except AssertionError:pass
                else:raise AssertionError('Invalid GIDE snapshot was accepted: '+kind)
        checks.append('Legacy snapshots reset GIDE; malformed positions and different media are rejected')
    finally:
        e.close()
    # Fresh processes test optional decoding, alternate base, absent drives and bad images.
    for label,config,base in (
        ('absent','[GIDE]\nenabled=1\nbase=0x90\n',0x90),
        ('disabled',ini.replace('enabled=1','enabled=0'),0xa0),
        ('collision',ini.replace('base=0xa0','base=0xe0'),0xa0)):
        e=Emu(exe,work/label,False,config)
        try:
            if label=='absent':
                assert inp(e,base+15)==0
                e.cpu(out(base+15,0xec)); assert inp(e,base+15)==0
                assert inp(e,base+8)==255
                rtc_out(e,base,15,6); assert inp(e,0x0f95)==6
            else:
                # Unconnected IN returns the preceding opcode DBUS latch (ED/78),
                # compare another unconnected port rather than assuming FF.
                assert inp(e,base+15)==inp(e,0x4f)
        finally: e.close()
    checks.append('Optional card decoding, alternate base, absent devices and bank-port conflict rejection')
    assert hashlib.sha256(slave.read_bytes()).hexdigest()==original_slave
    (work/'results.json').write_text(json.dumps({'passed':checks},indent=2))
    for check in checks: print('PASS:',check)
    print('Evidence:',work)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
