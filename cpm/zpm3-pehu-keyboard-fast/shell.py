#!/usr/bin/env python3
"""Build declared ZCCP setup/drive patches from preserved original inputs."""
from pathlib import Path
import hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];BUILD=HERE/'build/shell';BUILD.mkdir(parents=True,exist_ok=True)
REF=HERE/'reference'
for name,digest in json.loads((REF/'zccp-provenance.json').read_text())['files'].items():assert hashlib.sha256((REF/name).read_bytes()).hexdigest()==digest,name
# Standard VT52 descriptor extracted from the pinned TCAP library. Our BIOS
# implements ESC H/J/Y/K. Retain zero entries for unsupported video modes.
lbr=(REF/'Z3TCAP.LBR').read_bytes()
entry=next(lbr[i:i+32] for i in range(0,3072,32) if lbr[i+1:i+12]==b'DEC52   Z3T')
at=int.from_bytes(entry[12:14],'little')*128;tcap=bytearray(lbr[at:at+128])
assert tcap[23:].startswith(b'\x1bH\x1bJ\0\x1bY%+ %+ \0\x1bK\0')
tcap[:16]=b'SHARP SUC 80x25 '.ljust(16,b' ')
# SUC physical cursor keys: up0B, down0A, right0C, left08.
tcap[16:20]=bytes([11,10,12,8]);tcap[20]=0
(BUILD/'TCAP.Z3T').write_bytes(tcap)
installer=bytearray((REF/'zccp0293/ZINSTAL.ZPM').read_bytes())
assert installer[3:10]==b'*MHZ*>\x12' and installer[10:18]==b'*MAXD*>\x10'
assert installer[0x268]==0
installer[0x268]=2 # Message buffer +2Fh: current drive C (zero-based)
installer[9]=4;installer[17]=4 # nominal MHz and highest drive D (one-based)
(BUILD/'ZINSTAL.ZPM').write_bytes(installer)
alias=bytearray((REF/'startup-alias.com').read_bytes())
assert alias[22:30]==b'Z3 ALIAS'
command=b'C0:SETPATH /C $$$$ C0 /Q;C0:LOADSEG TCAP.Z3T'
end=alias.index(0,30);assert len(command)<=end-30
alias[30:end]=command.ljust(end-30,b'\0')
(BUILD/'STARTZPM.COM').write_bytes(alias)
for src,dst in [('tpa.asm','TPA.COM'),('reset-drive.asm','reset-drive.bin'),('tpatest.asm','TPATEST.COM')]:
 subprocess.run([sys.executable,str(ROOT/'cpm/gide/third_party/pyz80.py'),'--obj='+str(BUILD/dst),str(HERE/src)],check=True)
zccp=bytearray((REF/'zccp0293/CCP.COM').read_bytes())
assert zccp[0x77c:0x785]==bytes.fromhex('3e0d327e0d4fc32c01')
zccp[0x77c:0x785]=bytes.fromhex('c30012000000000000')
zccp=zccp.ljust(0x1100,b'\0')+(BUILD/'reset-drive.bin').read_bytes()
(BUILD/'ZCCP.COM').write_bytes(zccp)

# Native ZPM3 must see the complete ZCCP file under the standard CCP name.
(BUILD/'CCP.COM').write_bytes(zccp)
