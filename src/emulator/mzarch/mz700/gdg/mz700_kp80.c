/* SPDX-License-Identifier: GPL-3.0-or-later
 * K&P programming interface on SUC VRAM/scanout, not a second video card.
 * Reference: B. Krueger-Knauber, sharpmz/mz-700/80zkup.htm + KuP80Z.Lib.
 */
#include <string.h>
#include "mz700_kp80.h"
#include "mz700_gdg.h"
#include "mz700_framebuffer.h"
#include "hw-generic/memory/memory.h"
#include "mzarch/mzarch.h"

void kp80_reset(void)
{
    g_gdg.kp80_index = 0;
    g_gdg.kp80_address = 0;
    memset(g_gdg.kp80_registers, 0, sizeof(g_gdg.kp80_registers));
}

void kp80_set_interface(unsigned enabled)
{
    g_gdg.suc80_kp_interface = !!enabled;
    if (enabled) g_gdg.suc80_enabled = 1;
    kp80_reset();
    g_gdg.suc80_mode80 = 0;
    g_framebuffer.screen_changes = SCRSTS_THIS_IS_CHANGED;
}

int kp80_claims(uint16_t port)
{
    return g_gdg.suc80_enabled && g_gdg.suc80_kp_interface &&
           (port & 0xfcu) == 0x70u;
}

static unsigned register_pair(unsigned reg)
{
    return ((g_gdg.kp80_registers[reg] << 8) |
            g_gdg.kp80_registers[reg + 1]) & 0x3fffu;
}

unsigned kp80_display_start(void) { return register_pair(12) & 0x7ffu; }

uint8_t kp80_read(uint16_t port)
{
    switch (port & 3u) {
    case 0: /* A VRAM read does not advance the transparent address. */
        return g_memory.VRAM[suc80_vram_offset(g_gdg.kp80_address)];
    case 2: /* Functional, immediately ready; blanking follows the SUC raster. */
        return 0x80u | (GDG_TEST_VBLN ? 0x20u : 0);
    case 3:
        return (uint8_t)g_gdg.kp80_registers[g_gdg.kp80_index];
    default:
        return 0xff;
    }
}

void kp80_write(uint16_t port, uint8_t value)
{
    static const uint8_t masks[20] = {
        0xff,0xff,0xff,0xff,0x7f,0x1f,0x7f,0x7f,0xff,0x1f,
        0x7f,0x1f,0x3f,0xff,0x3f,0xff,0,0,0x3f,0xff
    };
    switch (port & 3u) {
    case 1: {
        unsigned offset = suc80_vram_offset(g_gdg.kp80_address);
        /* Raw byte goes into actual SUC character RAM, with monochrome colour. */
        g_memory.VRAM[offset] = value;
        g_memory.VRAM[offset + 0x800] = 0x70;
        g_gdg.kp80_address = (g_gdg.kp80_address + 1) & 0x3fff;
        g_gdg.kp80_registers[18] = g_gdg.kp80_address >> 8;
        g_gdg.kp80_registers[19] = g_gdg.kp80_address & 0xff;
        g_framebuffer.screen_changes = SCRSTS_THIS_IS_CHANGED;
        break;
    }
    case 2:
        g_gdg.kp80_index = value & 31;
        if (g_gdg.kp80_index == 31)
            g_gdg.kp80_address = register_pair(18);
        break;
    case 3: {
        unsigned reg = g_gdg.kp80_index;
        if (reg >= 20 || reg == 16 || reg == 17) break;
        g_gdg.kp80_registers[reg] = value & masks[reg];
        if (reg == 1) g_gdg.suc80_mode80 = (value == 80);
        g_framebuffer.screen_changes = SCRSTS_THIS_IS_CHANGED;
        break;
    }
    default:
        break;
    }
}

unsigned kp80_cursor_mask(unsigned address, unsigned line)
{
    unsigned r10 = g_gdg.kp80_registers[10];
    unsigned mode = (r10 >> 5) & 3u;
    unsigned height = (g_gdg.kp80_registers[9] & 31u) + 1;
    unsigned first = r10 & 31u, last = g_gdg.kp80_registers[11] & 31u;
    if (mode == 1 || address != (register_pair(14) & 0x7ffu)) return 0;
    if (mode >= 2 && (g_mzarch_main.cursor_timer & (mode == 2 ? 16u : 32u))) return 0;
    /* Retain the eight-line SUC character cell, scaling the CRTC cursor range. */
    unsigned source_line = line * height / 8;
    return first <= source_line && source_line <= last ? 0xffu : 0;
}

uint8_t kp80_display_code(uint8_t value)
{
    /* Printable ASCII mapped to the existing European Sharp 8x8 font.
     * K&P's control-code graphics and German substitutions are not its ROM. */
    static const uint8_t punctuation[32] = {
        0,0x61,0x62,0x63,0x64,0x65,0x66,0x67,
        0x68,0x69,0x6b,0x6a,0x2f,0x2a,0x2e,0x2d,
        0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,
        0x28,0x29,0x4f,0x2c,0x51,0x2b,0x57,0x49
    };
    value &= 0x7f;
    if (value >= ' ' && value <= '?') return punctuation[value - ' '];
    if (value == '@') return 0x55;
    if (value >= 'A' && value <= 'Z') return value - 'A' + 1;
    if (value >= 'a' && value <= 'z') return value - 'a' + 0x81;
    switch (value) {
    case '[': return 0x52; case '\\': return 0x59; case ']': return 0x54;
    case '^': return 0x50; case '_': return 0x3c; case '`': return 0x55;
    case '{': return 0x52; case '|': return 0x59; case '}': return 0x54;
    case '~': return 0x50; default: return 0;
    }
}
