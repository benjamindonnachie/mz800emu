/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef MZ700_KP80_H
#define MZ700_KP80_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
void kp80_reset(void);
void kp80_set_interface(unsigned enabled);
int kp80_claims(uint16_t port);
uint8_t kp80_read(uint16_t port);
void kp80_write(uint16_t port, uint8_t value);
unsigned kp80_display_start(void);
unsigned kp80_cursor_mask(unsigned address, unsigned line);
uint8_t kp80_display_code(uint8_t value);
/* Full 2048-byte bijection, including odd-cell wrap to unused D400h. */
static inline unsigned suc80_vram_offset(unsigned address)
{
    unsigned odd = address & 1u;
    return (((address >> 1) + odd) & 0x3ffu) | (odd << 10);
}
#ifdef __cplusplus
}
#endif
#endif
