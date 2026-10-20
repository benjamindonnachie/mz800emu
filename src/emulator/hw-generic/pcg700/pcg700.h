/* HAL Laboratory PCG-700. SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef PCG700_H
#define PCG700_H
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define PCG700_RAM_SIZE 0x800
#define PCG700_SSW 0x08
#define PCG700_STROBE 0x10
#define PCG700_COPY 0x20

typedef struct {
    unsigned fitted, hsw;
    uint8_t ram[PCG700_RAM_SIZE]; /* Physical, MSB-left pattern bytes. */
    uint8_t data, addr_low, control;
} pcg700_t;
extern pcg700_t g_pcg700;
/* Power-on is deterministic; soft reset retains character RAM and switches. */
void pcg700_power_on(pcg700_t *pcg);
void pcg700_reset(pcg700_t *pcg);
bool pcg700_active(const pcg700_t *pcg);
/* Returns whether the display may have changed. CGROM is emulator LSB-left. */
bool pcg700_write(pcg700_t *pcg, uint16_t addr, uint8_t value, const uint8_t *cgrom);
uint8_t pcg700_pattern(const pcg700_t *pcg, unsigned cg_addr, const uint8_t *cgrom);
#ifdef __cplusplus
}
#endif
#endif
