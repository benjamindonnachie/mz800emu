/**
 * @file   state_hash.h
 * @brief  Sdílený hash SHA-256 částí stavu stroje (paměť, VRAM, obraz).
 *
 * Jedna definice "co patří do hashe" pro všechny, kdo porovnávají stav
 * dvou běhů: `result.json` automatizace (automation.c), později čtení
 * paměti přes MCP a detekce rozjetí při přehrávání záznamu. Funguje i
 * v buildu bez debuggeru (nepotřebuje regiony debuggeru, čte přímo
 * fyzické paměti).
 *
 * | Část (en_STATE_HASH_PART) | Obsah | Platformy |
 * |---------------------------|-------|-----------|
 * | `ram`    | vnitřní RAM 64 KB (`g_memory.RAM`), bez ohledu na mapování | všechny |
 * | `memext` | RAM MemExt 512 KB (`g_memext.RAM`), jen s připojeným MemExt | všechny |
 * | `vram`   | MZ-800: 4 plány po 8 KB (`VRAM` + `EXVRAM`, 32 KB); MZ-700 a MZ-1500: znaková + atributová VRAM 4 KB | všechny |
 * | `pcg`    | 3 banky PCG po 8 KB (`g_memory.PCG`) | MZ-1500 |
 * | `screen` | framebuffer INDEX8 celého displeje (`g_framebuffer.pixels`, VIDEO_DISPLAY_WIDTH x VIDEO_DISPLAY_HEIGHT bajtů, indexy palety, ne RGB) | všechny |
 *
 * Hash je SHA-256 bajtů v pořadí uložení, výstup 64 hex znaků malými
 * písmeny. Hash obrazu je obsah framebufferu v okamžiku volání: na hranici
 * snímku celý dokončený snímek, uprostřed snímku řádky nad paprskem už
 * z nového snímku (stejný obraz jako screenshot v tu chvíli).
 *
 * Vlákna: funkce čtou paměť emulátoru bez zámku, volat jen z emu vlákna
 * (nebo když emu vlákno stojí v pauze).
 */

#ifndef STATE_HASH_H
#define STATE_HASH_H

#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C"
{
#endif

    /** @brief Délka hex zápisu SHA-256 bez koncové nuly. */
#define STATE_HASH_HEX_LEN 64

    /**
     * @brief Části stavu, které umí state_hash_part() hashovat.
     *
     * Pořadí je zároveň pořadí v `result.json` (state_hash_part_name()).
     */
    typedef enum en_STATE_HASH_PART
    {
        STATE_HASH_RAM = 0, /**< Vnitřní RAM 64 KB. */
        STATE_HASH_MEMEXT,  /**< RAM MemExt (jen připojený MemExt). */
        STATE_HASH_VRAM,    /**< VRAM platformy (MZ-800 všechny 4 plány). */
        STATE_HASH_PCG,     /**< PCG (jen MZ-1500). */
        STATE_HASH_SCREEN,  /**< Framebuffer INDEX8 celého displeje. */
        STATE_HASH_PART_COUNT /**< Počet částí (není to část). */
    } en_STATE_HASH_PART;

    /**
     * @brief SHA-256 bloku bajtů jako hex řetězec.
     *
     * @param data Data (může být NULL jen při @p len == 0).
     * @param len  Počet bajtů.
     * @param[out] out_hex Buffer aspoň STATE_HASH_HEX_LEN + 1 znaků; po
     *             návratu 64 hex znaků malými písmeny a nula.
     */
    void state_hash_buffer(const void *data, size_t len, char *out_hex);

    /**
     * @brief Jméno části pro výstupy (`ram`, `memext`, `vram`, `pcg`, `screen`).
     *
     * @param part Část; mimo rozsah vrátí "unknown".
     * @return Statický řetězec, neuvolňovat.
     */
    const char *state_hash_part_name(en_STATE_HASH_PART part);

    /**
     * @brief Hash jedné části stavu.
     *
     * @param part Část podle tabulky v hlavičce souboru.
     * @param[out] out_hex Buffer aspoň STATE_HASH_HEX_LEN + 1 znaků.
     * @return true = hash vypočten; false = část na této platformě nebo
     *         v této sestavě není (PCG mimo MZ-1500, MemExt odpojený,
     *         framebuffer ještě nevznikl), @p out_hex se pak nemění.
     * @pre Volá se z emu vlákna nebo při stojícím emu vlákně.
     */
    bool state_hash_part(en_STATE_HASH_PART part, char *out_hex);

#ifdef __cplusplus
}
#endif

#endif /* STATE_HASH_H */
