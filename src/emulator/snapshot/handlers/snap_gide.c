/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "snapshot/snapshot_mgr.h"
#if MZARCH == 700
#include "snapshot/snapshot_xml.h"
#include "snapshot/snapshot_config.h"
#include "hw-generic/gide/gide.h"
#include <glib.h>
#include <string.h>
#define ATA_FIELDS(X) X(count) X(sector) X(cyl_lo) X(cyl_hi) X(head) X(error) X(features) \
 X(status) X(command) X(pos) X(remaining) X(cylinders) X(heads) X(sectors) X(lba)
#define CARD_FIELDS(X) X(enabled) X(base) X(selected) X(high) X(latch) X(control) X(rtc_dirty) X(rtc_weekday_delta)
static en_SNAPSHOT_RESULT save_gide(st_SNAPSHOT_CONTEXT *ctx) {
    gide_rtc_refresh();
    snapshot_xml_writer_t *w=snapshot_xml_writer_new(); snapshot_xml_write_header(w);
    snapshot_xml_open_element(w,"gide");
#define SAVE_CARD(k) snapshot_xml_write_uint(w,#k,g_gide.k);
    CARD_FIELDS(SAVE_CARD)
#undef SAVE_CARD
    snapshot_xml_write_uint64(w,"rtc_epoch",g_gide.rtc_epoch);
    snapshot_xml_write_uint64(w,"rtc_held_at",g_gide.rtc_held_at);
    uint8_t payload[1040];
    for (unsigned i=0;i<2;i++) {
        char name[16]; g_snprintf(name,sizeof(name),"drive%u",i);
        snapshot_xml_open_element(w,name);
        gide_drive *d=&g_gide.drive[i];
        snapshot_xml_write_string(w,"path",d->path ? d->path:"");
        snapshot_xml_write_uint(w,"blocks",d->blocks);
        snapshot_xml_write_uint(w,"readonly",d->readonly);
#define SAVE_ATA(k) snapshot_xml_write_uint(w,#k,d->ata.k);
        ATA_FIELDS(SAVE_ATA)
#undef SAVE_ATA
        snapshot_xml_close_element(w);
        memcpy(payload+512*i,d->ata.buffer,512);
    }
    memcpy(payload+1024,g_gide.rtc,16);
    snapshot_xml_close_element(w);
    char *xml=snapshot_xml_writer_finish(w);
    en_SNAPSHOT_RESULT res=snapshot_io_write_xml(ctx->io,"devices/gide.xml",xml);
    g_free(xml);
    return res==SNAPSHOT_OK ? snapshot_io_write_bin(ctx->io,"devices/gide.bin",payload,sizeof(payload)):res;
}
static en_SNAPSHOT_RESULT load_gide(st_SNAPSHOT_CONTEXT *ctx) {
    if (!snapshot_io_entry_exists(ctx->io,"devices/gide.xml")) { gide_reset(); return SNAPSHOT_OK; }
    char *xml=NULL;
    en_SNAPSHOT_RESULT res=snapshot_io_read_xml(ctx->io,"devices/gide.xml",&xml);
    if (res!=SNAPSHOT_OK) return res;
    snapshot_xml_reader_t *r=snapshot_xml_reader_new(xml); g_free(xml);
    if (!r) return SNAPSHOT_ERR_XML_PARSE;
    gide_device next=g_gide; bool valid=snapshot_xml_enter_element(r,"gide");
    unsigned v; uint64_t v64;
#define LOAD_CARD(k) if (snapshot_xml_read_uint(r,#k,&v)) { next.k=v; if ((uint64_t)next.k!=v) valid=false; } else valid=false;
    CARD_FIELDS(LOAD_CARD)
#undef LOAD_CARD
    if (snapshot_xml_read_uint64(r,"rtc_epoch",&v64)) next.rtc_epoch=(int64_t)v64; else valid=false;
    if (snapshot_xml_read_uint64(r,"rtc_held_at",&v64)) next.rtc_held_at=(int64_t)v64; else valid=false;
    for (unsigned i=0;i<2;i++) {
        char name[16]; g_snprintf(name,sizeof(name),"drive%u",i);
        if (!snapshot_xml_enter_element(r,name)) { valid=false; break; }
        gide_drive *d=&next.drive[i]; char *path=NULL; unsigned blocks=0,ro=0;
        /* GMarkup represents an empty string element without a text node. */
        snapshot_xml_read_string(r,"path",&path);
        if (!path) path=g_strdup("");
        if (!snapshot_xml_read_uint(r,"blocks",&blocks)) valid=false;
        if (!snapshot_xml_read_uint(r,"readonly",&ro)) valid=false;
        if (g_strcmp0(path,d->path ? d->path:"") || blocks!=d->blocks || ro!=d->readonly) {
            g_free(path); snapshot_xml_reader_free(r);
            SNAP_ERR("gide","Snapshot requires the same image paths, sizes and write protection");
            return SNAPSHOT_ERR_EXTERNAL_REF;
        }
        g_free(path);
#define LOAD_ATA(k) if (snapshot_xml_read_uint(r,#k,&v)) { \
    d->ata.k=v; if ((uint64_t)d->ata.k!=v) valid=false; } else valid=false;
        ATA_FIELDS(LOAD_ATA)
#undef LOAD_ATA
        if (d->ata.pos>510 || (d->ata.pos&1) || d->ata.remaining>256 ||
            !d->ata.heads || d->ata.heads>16 || !d->ata.sectors || d->ata.sectors>255 ||
            d->ata.lba>0x10000000u) valid=false;
        if ((d->ata.status&8) && (!d->fp || !d->ata.remaining ||
            (d->ata.command!=0x20 && d->ata.command!=0x21 && d->ata.command!=0x30 &&
             d->ata.command!=0x31 && d->ata.command!=0xec))) valid=false;
        snapshot_xml_leave_element(r);
    }
    snapshot_xml_reader_free(r);
    if (!valid || next.selected>1 || next.high>1 || next.enabled>1 ||
        !gide_base_valid(next.base) || next.rtc_dirty>1 || next.rtc_weekday_delta>6 || next.rtc_epoch<0 || next.rtc_epoch>4102444799LL)
        return SNAPSHOT_ERR_CORRUPTED;
    uint8_t payload[1040];
    res=snapshot_io_read_bin_into(ctx->io,"devices/gide.bin",payload,sizeof(payload));
    if (res!=SNAPSHOT_OK) return res;
    for (unsigned i=0;i<16;i++) if (payload[1024+i]>15) return SNAPSHOT_ERR_CORRUPTED;
    for (unsigned i=0;i<2;i++) memcpy(next.drive[i].ata.buffer,payload+512*i,512);
    memcpy(next.rtc,payload+1024,16);
    snapshot_config_pin_ini_value("GIDE","enabled",g_gide.enabled);
    snapshot_config_pin_ini_value("GIDE","base",g_gide.base);
    /* Wall-clock time elapsed while saved is intentionally not added. */
    next.rtc_held_at=(int64_t)time(NULL); next.rtc_anchor=next.rtc_held_at;
    g_gide=next; return SNAPSHOT_OK;
}
void snap_gide_register(void) {
    snapshot_register_component("gide",SNAPSHOT_PRIORITY_DEVICE,save_gide,load_gide,false);
}
#endif
