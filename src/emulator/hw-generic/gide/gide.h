/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef MZ_GIDE_H
#define MZ_GIDE_H
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <time.h>
#ifdef __cplusplus
extern "C" {
#endif
/* The card latch is shared; ATA command/buffer state belongs to each drive. */
typedef struct {
    uint8_t count, sector, cyl_lo, cyl_hi, head, error, features, status, command;
    uint16_t pos, remaining, cylinders, heads, sectors;
    uint32_t lba;
    uint8_t buffer[512];
} gide_ata_state;
typedef struct {
    FILE *fp;
    uint32_t blocks;
    unsigned readonly;
    char *path;
    gide_ata_state ata;
} gide_drive;
typedef struct {
    unsigned enabled, base, selected, high;
    uint16_t latch;
    uint8_t control;
    gide_drive drive[2];
    uint8_t rtc[16];
    int64_t rtc_epoch, rtc_anchor, rtc_held_at;
    unsigned rtc_dirty, rtc_weekday_delta;
} gide_device;
extern gide_device g_gide;
void gide_init(void);
void gide_exit(void);
void gide_config_set_enabled(bool enabled);
bool gide_config_mount(unsigned drive, const char *path, bool readonly);
void gide_config_eject(unsigned drive);
void gide_reset(void);
bool gide_claims(uint16_t port);
uint8_t gide_read(uint16_t port);
void gide_write(uint16_t port, uint8_t value);
bool gide_mount(unsigned drive, const char *path, bool readonly);
void gide_eject(unsigned drive);
void gide_rtc_refresh(void);
void gide_rtc_init(void);
void gide_set_enabled(bool enabled);
bool gide_set_base(unsigned base);
bool gide_base_valid(unsigned base);
#ifdef __cplusplus
}
#endif
#endif
