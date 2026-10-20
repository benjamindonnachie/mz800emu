/* HAL Laboratory PCG-700. SPDX-License-Identifier: GPL-3.0-or-later
 * Register and source audit: docs/en/devices/hal-pcg700.md.
 */
#include "pcg700.h"
#include <string.h>
pcg700_t g_pcg700;

static uint8_t reverse_bits(uint8_t v)
{
    v = (uint8_t)((v >> 4) | (v << 4));
    v = (uint8_t)(((v & 0xcc) >> 2) | ((v & 0x33) << 2));
    return (uint8_t)(((v & 0xaa) >> 1) | ((v & 0x55) << 1));
}

void pcg700_reset(pcg700_t *pcg)
{
    pcg->data = pcg->addr_low = 0;
    pcg->control = PCG700_SSW;
}

void pcg700_power_on(pcg700_t *pcg)
{
    memset(pcg, 0, sizeof(*pcg));
    pcg->hsw = 1;
    pcg700_reset(pcg);
}

bool pcg700_active(const pcg700_t *pcg)
{
    return pcg->fitted && pcg->hsw &&
        !(pcg->control & PCG700_SSW);
}

bool pcg700_write(pcg700_t *pcg, uint16_t addr, uint8_t value, const uint8_t *cgrom)
{
    if (!pcg->fitted) return false;
    if (addr == 0xe010) { pcg->data = value; return false; }
    if (addr == 0xe011) { pcg->addr_low = value; return false; }
    if (addr != 0xe012) return false;

    bool was_active = pcg700_active(pcg);
    uint8_t previous = pcg->control;
    pcg->control = value & 0x3f;
    bool changed = was_active != pcg700_active(pcg);
    /* One write per rising strobe, using address/COPY from this write.
     * A subsequent low strobe rearms it, including a literal zero write.
     * HSW and SSW bypass the display, not the programming interface. */
    if (!(previous & PCG700_STROBE) && (value & PCG700_STROBE)) {
        unsigned offset = ((value & 7u) << 8) | pcg->addr_low;
        unsigned rom_addr = ((offset & 0x400u) << 1) | 0x400u | (offset & 0x3ffu);
        uint8_t data = (value & PCG700_COPY) ? reverse_bits(cgrom[rom_addr]) : pcg->data;
        changed |= pcg700_active(pcg) && pcg->ram[offset] != data;
        pcg->ram[offset] = data;
    }
    return changed;
}

uint8_t pcg700_pattern(const pcg700_t *pcg, unsigned cg_addr, const uint8_t *cgrom)
{
    cg_addr &= 0xfff;
    if (pcg700_active(pcg) && (cg_addr & 0x400)) {
        unsigned offset = ((cg_addr & 0x800u) >> 1) | (cg_addr & 0x3ffu);
        return reverse_bits(pcg->ram[offset]);
    }
    return cgrom[cg_addr];
}
