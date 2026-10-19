"""Small explicit CP/M image editor for this build's two documented formats.

Retains all CPC DSK track/sector metadata. This BIOS format uses side0
tracks0..39 then side1 tracks39..1. Side1 track0 is the separate boot track.
Mapping verified against F7F3 (79-logical_track on side1) and format flag78h.
"""
from pathlib import Path
import math

class SharpDSK:
    def __init__(self,data):
        self.data=bytearray(data)
        assert self.data[:8]==b'EXTENDED' and tuple(self.data[0x30:0x32])==(40,2)
        self.sectors={};at=256
        for i in range(80):
            size=self.data[0x34+i]*256;t=self.data[at:at+size];pos=at+256
            assert t[:10]==b'Track-Info' and t[0x15] in (8,16)
            cyl,head=t[0x10:0x12]
            for s in range(t[0x15]):
                d=t[0x18+8*s:0x20+8*s]
                n=int.from_bytes(d[6:8],'little') or (128<<d[3])
                assert n in (256,512) and 1<=d[2]<=t[0x15]
                self.sectors[cyl,head,d[2]]=(pos,n)
                pos+=n
            at+=size
        assert len(self.sectors)==648 and at==len(self.data)
    @staticmethod
    def track_order():
        return [(c,0) for c in range(40)]+[(c,1) for c in range(39,0,-1)]
    def logical(self):
        return bytearray(b''.join(self.data[at:at+n]
             for c,h in self.track_order()
             for key,(at,n) in sorted(self.sectors.items()) if key[:2]==(c,h)))
    def set_logical(self,data):
        assert len(data)==79*4096
        pos=0
        for c,h in self.track_order():
            for key,(at,n) in sorted(self.sectors.items()):
                if key[:2]==(c,h):
                    self.data[at:at+n]=data[pos:pos+n];pos+=n
        assert pos==len(data)

class Volume:
    def __init__(self,data,blocksize,blocks,entries,offset=0,exm=1):
        self.data=data;self.blocksize=blocksize;self.blocks=blocks
        self.entries=entries;self.offset=offset;self.exm=exm
        self.ptrsize=1 if blocks<=256 else 2
        assert offset+blocks*blocksize<=len(data)
    def directory(self):
        for i in range(self.entries):
            start=self.offset+i*32
            yield i,bytes(self.data[start:start+32])
    @staticmethod
    def name(entry):
        return bytes(x&127 for x in entry[1:9]).decode('ascii').rstrip()+'.'+bytes(x&127 for x in entry[9:12]).decode('ascii').rstrip()
    def matching(self,name,user=0):
        return [(i,e) for i,e in self.directory() if e[0]==user and self.name(e)==name.upper()]
    def pointers(self,e):
        return [int.from_bytes(e[p:p+self.ptrsize],'little') for p in range(16,32,self.ptrsize) if any(e[p:p+self.ptrsize])]
    def read(self,name,user=0):
        entries=self.matching(name,user)
        if not entries:raise FileNotFoundError(name)
        output=bytearray()
        for _,e in sorted(entries,key=lambda x:((x[1][14]<<5)|(x[1][12]&31))):
            ex=(e[14]<<5)|(e[12]&31)
            records=(ex&self.exm)*128+e[15]
            raw=b''.join(self.data[self.offset+b*self.blocksize:self.offset+(b+1)*self.blocksize] for b in self.pointers(e))
            assert len(raw)>=records*128
            output.extend(raw[:records*128])
        return bytes(output)
    def write(self,name,data,user=0):
        stem,ext=name.upper().split('.')
        assert 1<=len(stem)<=8 and len(ext)<=3 and 0<=user<16
        key=(stem.ljust(8)+ext.ljust(3)).encode('ascii')
        existing=self.matching(name,user)
        for i,_ in existing:self.data[self.offset+i*32]=0xe5
        used=set(range(math.ceil(self.entries*32/self.blocksize)))
        empty=[]
        for i,e in self.directory():
            if e[0]==0xe5:empty.append(i)
            elif e[0]<16:used.update(self.pointers(e))
        free=[i for i in range(self.blocks) if i not in used]
        capacity=(16//self.ptrsize)*self.blocksize
        chunks=[data[i:i+capacity] for i in range(0,len(data),capacity)] or [b'']
        need=sum(math.ceil(len(c)/self.blocksize) for c in chunks)
        if need>len(free) or len(chunks)>len(empty):raise ValueError('Volume full')
        for extent,chunk in enumerate(chunks):
            count=math.ceil(len(chunk)/128);e=bytearray(32);e[0]=user;e[1:12]=key
            ex=extent*(self.exm+1)+((count-1)//128 if count else 0)
            e[12]=ex&31;e[14]=ex>>5;e[15]=count%128 or (128 if count else 0)
            for j,start in enumerate(range(0,len(chunk),self.blocksize)):
                block=free.pop(0);e[16+j*self.ptrsize:16+(j+1)*self.ptrsize]=block.to_bytes(self.ptrsize,'little')
                payload=chunk[start:start+self.blocksize].ljust(self.blocksize,b'\x1a')
                at=self.offset+block*self.blocksize;self.data[at:at+self.blocksize]=payload
            i=empty.pop(0);at=self.offset+i*32;self.data[at:at+32]=e
        assert self.read(name,user)[:len(data)]==data

def floppy(data):return Volume(data,2048,156,64,offset=4096)
def hard_volume(data):
    assert len(data)==8*1024*1024
    return Volume(data,4096,2048,512)
