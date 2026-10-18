/* SPDX-License-Identifier: GPL-3.0-or-later
 * Standalone contract tests; also run under Address/UndefinedBehaviourSanitizer.
 */
#include "hw-generic/gide/gide.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void task(uint32_t lba, unsigned count, uint8_t cmd) {
    gide_write(0xae,0xe0|((lba>>24)&15));
    gide_write(0xaa,count); gide_write(0xab,lba);
    gide_write(0xac,lba>>8); gide_write(0xad,lba>>16); gide_write(0xaf,cmd);
}
static unsigned pattern(unsigned byte) { return (byte*37+byte/512*13)&255; }
int main(void) {
    char path[]="/tmp/mz-gide-core-XXXXXX";
    int fd=mkstemp(path); assert(fd>=0);
    FILE *fp=fdopen(fd,"wb"); assert(fp);
    for (unsigned i=0;i<1024*512;i++) assert(fputc(pattern(i),fp)!=EOF);
    assert(!fclose(fp));
    assert(gide_mount(0,path,false));
    gide_rtc_init(); gide_set_base(0xa0); gide_set_enabled(true);
    assert(gide_claims(0xaaa8)); assert(!gide_claims(0xa4));
    assert(!gide_set_base(0xe0)); assert(!gide_set_base(0xa1));
    task(0,0,0x20);
    for (unsigned sector=0;sector<256;sector++) {
        assert(gide_read(0xa6)==0x58);
        for (unsigned i=0;i<512;i++) assert(gide_read(0xa8)==pattern(sector*512+i));
        assert(gide_read(0xaa)==(uint8_t)(255-sector));
    }
    assert(gide_read(0xaf)==0x50);
    task(1023,2,0x30); assert(gide_read(0xa9)==16);
    task(0,1,0x20); (void)gide_read(0xa8); assert(g_gide.high==1);
    gide_write(0xa6,4); assert(gide_read(0xa6)==0x80); assert(g_gide.high==1);
    /* Even a data access during ATA reset still clocks the external GAL. */
    assert(gide_read(0xa8)==g_gide.latch>>8);
    gide_write(0xa6,0); assert(g_gide.high==0); /* CS1 does not clock GAL LH. */
    assert(gide_read(0xaf)==0x50); assert(g_gide.high==0);
    FILE *original=g_gide.drive[0].fp;
    assert(!gide_mount(0,"/no/such/mz-gide-image",false));
    assert(g_gide.drive[0].fp==original);
    assert(gide_mount(0,path,true)); task(1,1,0x30); assert(gide_read(0xa9)==4);
    /* RTC counts host seconds; HOLD retains at most one missed increment. */
    gide_write(0x0fa5,4); gide_rtc_refresh();
    int64_t epoch=g_gide.rtc_epoch;
    g_gide.rtc_anchor-=3; gide_rtc_refresh(); assert(g_gide.rtc_epoch==epoch+3);
    gide_write(0x0da5,1); epoch=g_gide.rtc_epoch;
    g_gide.rtc_anchor-=3; g_gide.rtc_held_at-=3; gide_rtc_refresh();
    assert(g_gide.rtc_epoch==epoch); assert(gide_read(0x0da5)==1);
    gide_write(0x0da5,0); assert(g_gide.rtc_epoch==epoch+1);
    gide_write(0x0fa5,6); epoch=g_gide.rtc_epoch;
    g_gide.rtc_anchor-=3; gide_rtc_refresh(); assert(g_gide.rtc_epoch==epoch);
    /* Bounded arbitrary ATA register traffic. All writes remain on temp media. */
    assert(gide_mount(0,path,false)); gide_reset();
    uint32_t seed=1234567;
    for (unsigned i=0;i<200000;i++) {
        seed=seed*1664525u+1013904223u;
        unsigned port=0xa6+(seed%10);
        if (seed&0x8000) gide_write(port,seed>>24); else (void)gide_read(port);
    }
    gide_eject(0); assert(!g_gide.drive[0].fp);
    assert(!unlink(path));
    puts("PASS: 256-sector transfer, bounds, GAL phase, read-only mount, RTC progression and 200000 arbitrary ATA accesses");
    return 0;
}
