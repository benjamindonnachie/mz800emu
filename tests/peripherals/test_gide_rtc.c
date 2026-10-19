/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "hw-generic/gide/gide.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>

/* This target substitutes time() in the portable core, without a guest hook. */
static time_t host_now=1792368000;
time_t gide_test_time(time_t *result) { if(result)*result=host_now; return host_now; }
static unsigned port(unsigned n) { return (n<<8)|0xa5; }
static void wr(unsigned n,unsigned value) { gide_write(port(n),value); }
static unsigned rd(unsigned n) { return gide_read(port(n)); }
static time_t epoch(int year,int month,int day,int hour,int minute,int second) {
    struct tm t={0};t.tm_year=year-1900;t.tm_mon=month-1;t.tm_mday=day;
    t.tm_hour=hour;t.tm_min=minute;t.tm_sec=second;t.tm_isdst=-1;
    return mktime(&t);
}
static void set(int year,int month,int day,int hour,int minute,int second) {
    unsigned v[]={second,minute,hour,day,month,(unsigned)year%100};
    wr(15,6);wr(13,1);
    for(unsigned i=0;i<6;i++) {wr(i*2,v[i]%10);wr(i*2+1,v[i]/10);}
    wr(12,3);wr(13,0);
    assert(g_gide.rtc_epoch==epoch(year,month,day,hour,minute,second));
}
static void expect(int year,int month,int day,int hour,int minute,int second) {
    unsigned v[]={second,minute,hour,day,month,(unsigned)year%100};
    wr(13,1);
    for(unsigned i=0;i<6;i++) {assert(rd(i*2)==v[i]%10);assert(rd(i*2+1)==v[i]/10);}
    wr(13,0);
}
int main(void) {
    setenv("TZ","UTC",1);tzset();gide_rtc_init();assert(gide_set_base(0xa0));gide_set_enabled(true);
    int years[]={1978,1980,1999,2000,2024,2026,2077};
    for(unsigned i=0;i<sizeof(years)/sizeof(*years);i++) {
        set(years[i],3,1,23,34,45);expect(years[i],3,1,23,34,45);
        assert(rd(12)==3);assert(rd(13)==2); /* BUSY forced high without HOLD. */
    }
    struct {int y,m,d,ny,nm,nd;} roll[]={
        {1999,12,31,2000,1,1},{2000,2,28,2000,2,29},
        {2024,2,28,2024,2,29},{2024,2,29,2024,3,1},{2023,2,28,2023,3,1}};
    for(unsigned i=0;i<sizeof(roll)/sizeof(*roll);i++) {
        set(roll[i].y,roll[i].m,roll[i].d,23,59,59);wr(15,4);
        host_now++;gide_rtc_refresh();expect(roll[i].ny,roll[i].nm,roll[i].nd,0,0,0);
    }
    set(2026,10,19,12,34,45);wr(15,4);wr(13,1);int64_t before=g_gide.rtc_epoch;
    host_now+=5;gide_rtc_refresh();assert(g_gide.rtc_epoch==before);assert(rd(13)==1);
    wr(13,0);assert(g_gide.rtc_epoch==before+1); /* One missed tick only. */
    wr(15,6);before=g_gide.rtc_epoch;host_now+=10;gide_reset();gide_rtc_refresh();
    assert(g_gide.rtc_epoch==before && rd(15)==6 && rd(13)==2);
    wr(13,1);wr(1,0xff);wr(3,0xff);wr(5,0xff);wr(7,0xff);wr(9,0xff);wr(12,0xff);
    assert(rd(1)==7 && rd(3)==7 && rd(5)==3 && rd(7)==3 && rd(9)==1 && rd(12)==7);
    /* Unsupported values are unpredictable; restore a valid complete calendar. */
    set(2026,10,19,23,34,45);wr(15,2); /* 12h representation, STOP retained. */
    assert(rd(4)==1 && rd(5)==5);wr(15,6);assert(rd(4)==3 && rd(5)==2);
    wr(13,8);expect(2026,10,19,23,35,0);
    g_gide.high=1;unsigned phase=g_gide.high; (void)gide_read(0xf0a5);assert(g_gide.high==phase);
    assert(gide_read(0xf0a5)==rd(0));
    puts("PASS RTC:1978..2077,century/leap/month rollover,HOLD/STOP/reset,masks,12/24h,ADJ,ATA phase");
    return 0;
}
