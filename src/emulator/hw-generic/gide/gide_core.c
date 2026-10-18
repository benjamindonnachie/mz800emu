/* SPDX-License-Identifier: GPL-3.0-or-later
 * KC-Club/Tilmann Reh GIDE: functional PIO ATA disk and RTC72421 emulation.
 * Byte-phase logic follows GIDE1.PDS rev02, 26 September 1995.
 * No IDE8 dependency. Disk commands complete synchronously, without IRQ/DMA.
 */
#include "gide.h"
#include <stdlib.h>
#include <string.h>
#include <limits.h>

gide_device g_gide;
enum { ERR=1, DRQ=8, DSC=16, DRDY=64, BSY=128, ABRT=4, IDNF=16, UNC=64 };

static void rtc_write(unsigned n, uint8_t v);

static gide_drive *drive(void) { return &g_gide.drive[g_gide.selected]; }
static void fail(gide_drive *d, uint8_t error) {
    d->ata.error=error; d->ata.status=DRDY|DSC|ERR;
    d->ata.remaining=0; d->ata.command=0; d->ata.pos=0;
}
static void reset_drive(gide_drive *d, unsigned id) {
    memset(&d->ata, 0, sizeof(d->ata));
    d->ata.count=1; d->ata.sector=1; d->ata.head=0xa0|(id<<4);
    d->ata.error=1; d->ata.status=d->fp ? DRDY|DSC : 0;
    d->ata.heads=16; d->ata.sectors=63;
    unsigned c=d->blocks/(16*63);
    d->ata.cylinders=(uint16_t)(c ? (c>16383 ? 16383:c) : 1);
}
void gide_reset(void) {
    g_gide.selected=0; g_gide.high=0; g_gide.latch=0; g_gide.control=0;
    for (unsigned i=0;i<2;i++) reset_drive(&g_gide.drive[i],i);
    /* Host reset inhibits RTC CS1, clearing HOLD and RESET, not battery time. */
    rtc_write(13,0);
    rtc_write(15,g_gide.rtc[15]&~1);
    g_gide.rtc_anchor=(int64_t)time(NULL);
}
void gide_eject(unsigned id) {
    if (id>1) return;
    gide_drive *d=&g_gide.drive[id];
    if (d->fp) fclose(d->fp);
    free(d->path); d->path=NULL; d->fp=NULL; d->blocks=0;
    reset_drive(d,id); g_gide.high=0;
}
bool gide_mount(unsigned id, const char *path, bool readonly) {
    if (id>1 || !path || !*path) return false;
    /* Never create/truncate an image. Validate a replacement before ejecting. */
    FILE *fp=fopen(path,readonly ? "rb":"r+b");
    if (!fp) return false;
    if (fseeko(fp,0,SEEK_END)) { fclose(fp); return false; }
    off_t size=ftello(fp);
    if (size<512 || size%512 || (uint64_t)size/512>0x10000000u) {
        fclose(fp); return false;
    }
    char *name=strdup(path);
    if (!name) { fclose(fp); return false; }
    gide_eject(id);
    gide_drive *d=&g_gide.drive[id];
    d->fp=fp; d->path=name; d->readonly=readonly; d->blocks=(uint32_t)(size/512);
    reset_drive(d,id); return true;
}
bool gide_base_valid(unsigned base) {
    /* Supported MZ-700 blocks without native/implemented expansion conflicts.
     * Every physical jumper block exists, but collisions are not emulated. */
    return base==0x10 || base==0x20 || base==0x30 || base==0x40 ||
           base==0x80 || base==0x90 || base==0xa0 || base==0xb0 || base==0xc0;
}
bool gide_set_base(unsigned base) {
    if (!gide_base_valid(base)) return false;
    g_gide.base=base; g_gide.high=0; return true;
}
void gide_set_enabled(bool enabled) {
    g_gide.enabled=enabled; gide_reset();
}
bool gide_claims(uint16_t port) {
    return g_gide.enabled && (port&0xf0)==g_gide.base && (port&15)>=5;
}
static bool seek_sector(gide_drive *d) {
    return d->ata.lba<d->blocks && !fseeko(d->fp,(off_t)d->ata.lba*512,SEEK_SET);
}
static bool read_sector(gide_drive *d) {
    if (!seek_sector(d) || fread(d->ata.buffer,1,512,d->fp)!=512) {
        clearerr(d->fp); fail(d,UNC); return false;
    }
    d->ata.pos=0; d->ata.status=DRDY|DSC|DRQ; return true;
}
static bool address(gide_drive *d) {
    gide_ata_state *a=&d->ata;
    if (a->head&0x40)
        a->lba=((uint32_t)(a->head&15)<<24)|((uint32_t)a->cyl_hi<<16)|
                ((uint32_t)a->cyl_lo<<8)|a->sector;
    else {
        unsigned c=((unsigned)a->cyl_hi<<8)|a->cyl_lo, h=a->head&15;
        if (!a->sector || a->sector>a->sectors || h>=a->heads || c>=a->cylinders) {
            fail(d,IDNF); return false;
        }
        a->lba=(c*a->heads+h)*a->sectors+a->sector-1;
    }
    if (a->lba>=d->blocks || a->remaining>d->blocks-a->lba) {
        fail(d,IDNF); return false;
    }
    return true;
}
static void next_sector(gide_drive *d) {
    gide_ata_state *a=&d->ata;
    a->remaining--; a->count=(uint8_t)a->remaining; a->lba++;
    if (a->head&0x40) {
        a->sector=a->lba; a->cyl_lo=a->lba>>8; a->cyl_hi=a->lba>>16;
        a->head=(a->head&0xf0)|((a->lba>>24)&15);
    } else {
        unsigned track=a->lba/a->sectors, cyl=track/a->heads;
        a->sector=a->lba%a->sectors+1;
        a->head=(a->head&0xf0)|(track%a->heads);
        a->cyl_lo=cyl; a->cyl_hi=cyl>>8;
    }
    a->pos=0;
    if (!a->remaining) { a->status=DRDY|DSC; a->command=0; }
    else if (a->command==0x20 || a->command==0x21) read_sector(d);
}
static void word(gide_drive *d,unsigned n,unsigned v) {
    d->ata.buffer[2*n]=v; d->ata.buffer[2*n+1]=v>>8;
}
static void ata_string(gide_drive *d,unsigned n,unsigned len,const char *s) {
    for (unsigned i=0;i<len;i++) d->ata.buffer[n*2+(i^1)]=i<strlen(s) ? s[i]:' ';
}
static void command(gide_drive *d,uint8_t cmd) {
    gide_ata_state *a=&d->ata;
    a->error=0; a->pos=0; a->remaining=0; a->command=cmd;
    if (cmd==0x90) {
        for (unsigned i=0;i<2;i++) reset_drive(&g_gide.drive[i],i);
        g_gide.selected=0; return;
    }
    if (!d->fp) { a->status=0; a->command=0; return; }
    a->status=DRDY|DSC;
    switch (cmd) {
    case 0xec: /* IDENTIFY DEVICE, words are always little endian on ATA. */
        memset(a->buffer,0,512); word(d,0,0x40); word(d,1,a->cylinders);
        word(d,3,a->heads); word(d,6,a->sectors);
        ata_string(d,10,20,g_gide.selected ? "MZGIDE00000000000002":"MZGIDE00000000000001");
        ata_string(d,23,8,"1.0"); ata_string(d,27,40,"MZ800EMU KC-CLUB GIDE PIO DISK");
        word(d,47,0x8000); word(d,49,0x200); word(d,53,1);
        word(d,54,a->cylinders); word(d,55,a->heads); word(d,56,a->sectors);
        word(d,57,a->cylinders*a->heads*a->sectors);
        word(d,58,(a->cylinders*a->heads*a->sectors)>>16);
        word(d,60,d->blocks); word(d,61,d->blocks>>16);
        a->remaining=1; a->status|=DRQ; break;
    case 0x20: case 0x21: case 0x30: case 0x31:
        a->remaining=a->count ? a->count:256;
        if (!address(d)) break;
        if ((cmd==0x30 || cmd==0x31) && d->readonly) { fail(d,ABRT); break; }
        if (cmd==0x20 || cmd==0x21) read_sector(d);
        else { memset(a->buffer,0,512); a->status|=DRQ; }
        break;
    case 0x10: /* RECALIBRATE */ a->cyl_lo=a->cyl_hi=0; a->command=0; break;
    case 0x91: /* INITIALISE DEVICE PARAMETERS */
        if (!a->count) { fail(d,ABRT); break; }
        a->heads=(a->head&15)+1; a->sectors=a->count;
        { unsigned c=d->blocks/(a->heads*a->sectors);
          a->cylinders=c>65535 ? 65535 : (c ? c:1); }
        a->command=0; break;
    case 0xe7: /* FLUSH CACHE: no write-back cache is advertised. */
        if (fflush(d->fp)) fail(d,UNC); else a->command=0;
        break;
    case 0xef: /* Only default PIO transfer mode is implemented. */
        if (a->features!=3 || (a->count!=0 && a->count!=8)) fail(d,ABRT);
        else a->command=0;
        break;
    default: fail(d,ABRT); break;
    }
}
static uint16_t data_read(void) {
    gide_drive *d=drive(); gide_ata_state *a=&d->ata;
    if (!(a->status&DRQ) || (a->command!=0xec && a->command!=0x20 && a->command!=0x21)) return 0xffff;
    uint16_t v=a->buffer[a->pos]|((uint16_t)a->buffer[a->pos+1]<<8);
    a->pos+=2;
    if (a->pos==512) {
        if (a->command==0xec) { a->status=DRDY|DSC; a->remaining=0; a->command=0; a->pos=0; }
        else next_sector(d);
    }
    return v;
}
static void data_write(uint16_t v) {
    gide_drive *d=drive(); gide_ata_state *a=&d->ata;
    if (!(a->status&DRQ) || (a->command!=0x30 && a->command!=0x31)) return;
    a->buffer[a->pos++]=v; a->buffer[a->pos++]=v>>8;
    if (a->pos==512) {
        if (d->readonly || !seek_sector(d) || fwrite(a->buffer,1,512,d->fp)!=512 || fflush(d->fp)) {
            clearerr(d->fp); fail(d,UNC); return;
        }
        next_sector(d);
    }
}

/* RTC calendar follows host local time; offset/settings are process state.
 * Updates are atomic: BUSY=0 while held. STD.P and factory TEST not modelled. */
static bool rtc_stopped(void) { return (g_gide.rtc[13]&1) || (g_gide.rtc[15]&3); }
static void rtc_digits(void) {
    time_t t=(time_t)g_gide.rtc_epoch; struct tm tm;
    localtime_r(&t,&tm);
    unsigned vals[6]={(unsigned)tm.tm_sec,(unsigned)tm.tm_min,(unsigned)tm.tm_hour,
                     (unsigned)tm.tm_mday,(unsigned)tm.tm_mon+1,(unsigned)tm.tm_year%100};
    if (!(g_gide.rtc[15]&4)) vals[2]=tm.tm_hour%12 ? tm.tm_hour%12:12;
    for (unsigned i=0;i<6;i++) { g_gide.rtc[2*i]=vals[i]%10; g_gide.rtc[2*i+1]=vals[i]/10; }
    if (!(g_gide.rtc[15]&4) && tm.tm_hour>=12) g_gide.rtc[5]|=4;
    g_gide.rtc[12]=(tm.tm_wday+g_gide.rtc_weekday_delta)%7;
}
void gide_rtc_refresh(void) {
    int64_t now=(int64_t)time(NULL);
    if (!rtc_stopped() && !g_gide.rtc_dirty) {
        if (now>g_gide.rtc_anchor) g_gide.rtc_epoch+=now-g_gide.rtc_anchor;
        rtc_digits();
    }
    g_gide.rtc_anchor=now;
}
void gide_rtc_init(void) {
    memset(g_gide.rtc,0,16); g_gide.rtc[15]=4;
    g_gide.rtc_epoch=g_gide.rtc_anchor=(int64_t)time(NULL);
    g_gide.rtc_dirty=0; g_gide.rtc_weekday_delta=0; rtc_digits();
}
static void rtc_commit(void) {
    uint8_t *r=g_gide.rtc;
    struct tm tm={0}; tm.tm_sec=r[0]+10*r[1]; tm.tm_min=r[2]+10*r[3];
    tm.tm_hour=r[4]+10*(r[5]&3);
    if (!(r[15]&4)) tm.tm_hour=tm.tm_hour%12+((r[5]&4)?12:0);
    tm.tm_mday=r[6]+10*r[7]; tm.tm_mon=r[8]+10*r[9]-1;
    tm.tm_year=100+r[10]+10*r[11]; tm.tm_isdst=-1;
    time_t t=mktime(&tm);
    if (t!=(time_t)-1) {
        g_gide.rtc_epoch=(int64_t)t;
        g_gide.rtc_weekday_delta=(r[12]+7-tm.tm_wday)%7;
    }
    g_gide.rtc_dirty=0; g_gide.rtc_anchor=(int64_t)time(NULL);
}
static void rtc_write(unsigned n,uint8_t v) {
    gide_rtc_refresh(); v&=15;
    if (n<13) {
        g_gide.rtc[n]=v; g_gide.rtc_dirty=1;
        if (!rtc_stopped()) rtc_commit();
    } else if (n==13) {
        bool was=g_gide.rtc[13]&1;
        g_gide.rtc[13]=v&1; /* BUSY read-only, no wired STD.P interrupts. */
        if (!was && (v&1)) g_gide.rtc_held_at=(int64_t)time(NULL);
        if (was && !(v&1)) {
            if (g_gide.rtc_dirty) rtc_commit();
            else if (!(g_gide.rtc[15]&3) && (int64_t)time(NULL)>g_gide.rtc_held_at) g_gide.rtc_epoch++;
        }
        if (v&8) {
            if (g_gide.rtc_dirty) rtc_commit();
            time_t t=(time_t)g_gide.rtc_epoch; struct tm tm; localtime_r(&t,&tm);
            g_gide.rtc_epoch+=(tm.tm_sec>=30 ? 60:0)-tm.tm_sec; rtc_digits();
        }
    } else if (n==14) g_gide.rtc[n]=v;
    else {
        bool was=rtc_stopped(); g_gide.rtc[15]=v&7;
        if (was && !rtc_stopped() && g_gide.rtc_dirty) rtc_commit();
        if (!g_gide.rtc_dirty) rtc_digits();
    }
}
uint8_t gide_read(uint16_t port) {
    unsigned r=port&15; gide_drive *d=drive(); gide_ata_state *a=&d->ata;
    if (r==5) {
        gide_rtc_refresh(); unsigned n=(port>>8)&15;
        return n==13 ? (g_gide.rtc[13]|((g_gide.rtc[13]&1)?0:2)) : g_gide.rtc[n];
    }
    if (r==6) return (g_gide.control&4) ? BSY : a->status;
    if (r==7) return 0xc0 | (g_gide.selected ? 1:2) | ((~a->head&15)<<2);
    if (r==8) {
        if (!g_gide.high) g_gide.latch=(g_gide.control&4) ? 0xffff:data_read();
        uint8_t v=g_gide.latch>>(g_gide.high ? 8:0);
        g_gide.high^=1; return v;
    }
    if (r<9) return 0xff;
    g_gide.high=0; /* GAL: any task-file access resets LH, including STATUS. */
    if (!d->fp) return 0;
    switch (r) {
    case 9:return a->error; case 10:return a->count; case 11:return a->sector;
    case 12:return a->cyl_lo; case 13:return a->cyl_hi; case 14:return a->head;
    default:return (g_gide.control&4) ? BSY:a->status;
    }
}
void gide_write(uint16_t port,uint8_t v) {
    unsigned r=port&15; gide_drive *d=drive(); gide_ata_state *a=&d->ata;
    if (r==5) { rtc_write((port>>8)&15,v); return; }
    if (r==6) {
        bool reset=g_gide.control&4; g_gide.control=v&6;
        if (reset && !(v&4)) {
            for (unsigned i=0;i<2;i++) reset_drive(&g_gide.drive[i],i);
            g_gide.selected=0;
        }
        /* CS1 access does NOT clock/reset the physical card's LH latch. */
        return;
    }
    if (r==8) {
        if (!g_gide.high) g_gide.latch=(g_gide.latch&0xff00)|v;
        else {
            g_gide.latch=(g_gide.latch&255)|((uint16_t)v<<8);
            if (!(g_gide.control&4)) data_write(g_gide.latch);
        }
        g_gide.high^=1; return;
    }
    if (r<9) return;
    g_gide.high=0;
    if (g_gide.control&4) return;
    if (r==14) {
        g_gide.selected=(v>>4)&1;
        for (unsigned i=0;i<2;i++) g_gide.drive[i].ata.head=v;
        return;
    }
    if (r==15) { command(d,v); return; }
    /* ATA-3 section5.1: parameter writes reach both embedded controllers. */
    for (unsigned i=0;i<2;i++) {
        a=&g_gide.drive[i].ata;
        switch (r) {
        case 9:a->features=v; break; case 10:a->count=v; break; case 11:a->sector=v; break;
        case 12:a->cyl_lo=v; break; case 13:a->cyl_hi=v; break;
        }
    }
}
