/**
 * @file   replay_format.h
 * @brief  Formát záznamu vstupů `.mzr`: datový model, zápis a čtení.
 *
 * Záznam je ZIP archiv (přes snapshot_io, stejně jako snapshot `.mzs`)
 * se čtyřmi soubory:
 *
 * | Soubor | Obsah |
 * |--------|-------|
 * | `manifest.json` | formát, verze, platforma, délka, interval hashů, varování |
 * | `start.mzs`     | startovní snapshot (kompletní, vždy s RAMdiskem) |
 * | `inputs.jsonl`  | události (jeden řádek = jedna událost), poslední řádek `end` |
 * | `hashes.csv`    | periodické hashe částí stavu |
 *
 * Čas události je číslo snímku `f` od startu záznamu (f = 0 je okamžik
 * startu) a poloha `at` v rámci snímku:
 *
 * | `at` | Kde se událost provede |
 * |------|------------------------|
 * | `b`  | v bodě hranice snímku záznamu (B_f), před hashem |
 * | `d`  | v drainu fronty dbgapi snímku f (zásah debuggeru za běhu) |
 * | `p`  | v pauze na hranici snímku f, po událostech `b` (pořadí záznamu) |
 *
 * Modul je jen datový: nečte ani nemění stav emulátoru, takže ho jde
 * testovat samostatně. Stav stroje do záznamu přenáší replay.c.
 *
 * Vlákna: funkce nejsou vázané na vlákno; jeden st_REPLAY_DATA nesmí
 * používat dvě vlákna současně.
 */

#ifndef REPLAY_FORMAT_H
#define REPLAY_FORMAT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <glib.h>

#ifdef __cplusplus
extern "C"
{
#endif

/** @brief Identifikátor formátu v `manifest.json` (`format`). */
#define REPLAY_FORMAT_ID "mz800emu-replay"

/** @brief Verze formátu v `manifest.json` (`version`); jiná verze se odmítne. */
#define REPLAY_FORMAT_VERSION 1

/** @brief Počet sloupců klávesnicové matice 8255 v události `kbd`. */
#define REPLAY_KBD_COLS 10

/** @brief Počet portů joysticku v události `joy` (port 0 a 1). */
#define REPLAY_JOY_PORTS 2

/** @brief Výchozí interval hashů ve snímcích (50 = 1 s na PAL). */
#define REPLAY_DEFAULT_HASH_INTERVAL 50

/** @brief Délka hex zápisu SHA-256 bez koncové nuly. */
#define REPLAY_HASH_HEX_LEN 64

    /**
     * @brief Druh události záznamu.
     */
    typedef enum en_REPLAY_EV_KIND
    {
        REPLAY_EV_KBD = 0,  /**< `kbd`: výsledná klávesová matice (10 bajtů, 0 = stisknuto). */
        REPLAY_EV_JOY,      /**< `joy`: stav joysticku na portu `p` (bity jako `g_joy.dev[].state`). */
        REPLAY_EV_AUTOTYPE, /**< `autotype`: start vkládání textu (text a časy stisku). */
        REPLAY_EV_RESET,    /**< `reset`: reset stroje. */
        REPLAY_EV_DBG,      /**< `dbg`: zásah debuggeru (jméno příkazu a argumenty). */
        REPLAY_EV_COUNT     /**< Počet druhů (není druh). */
    } en_REPLAY_EV_KIND;

    /**
     * @brief Poloha události v rámci snímku (viz tabulka v hlavičce souboru).
     */
    typedef enum en_REPLAY_EV_AT
    {
        REPLAY_AT_BOUNDARY = 0, /**< `b`: bod hranice snímku záznamu. */
        REPLAY_AT_DRAIN,        /**< `d`: drain fronty dbgapi za běhu. */
        REPLAY_AT_PAUSE,        /**< `p`: pauza na hranici snímku. */
        REPLAY_AT_COUNT         /**< Počet poloh (není poloha). */
    } en_REPLAY_EV_AT;

    /**
     * @brief Jedna událost záznamu.
     *
     * Platné jsou jen členy odpovídající druhu `kind`, ostatní jsou nulové.
     *
     * @invariant Řetězce (`text`, `cmd`, `args_json`) vlastní struktura
     *            v st_REPLAY_DATA (kopie z replay_data_add_event()),
     *            uvolní je replay_data_free().
     */
    typedef struct st_REPLAY_EVENT
    {
        uint32_t frame;            /**< Snímek od startu záznamu. */
        en_REPLAY_EV_KIND kind;    /**< Druh události. */
        en_REPLAY_EV_AT at;        /**< Poloha v rámci snímku. */
        uint8_t kbd[REPLAY_KBD_COLS]; /**< `kbd`: matice po sloupcích 0-9. */
        uint8_t joy_port;          /**< `joy`: port 0 nebo 1. */
        uint8_t joy_state;         /**< `joy`: stav (0FFh = nic). */
        char *text;                /**< `autotype`: text v kódování okna autotype (UTF-8). */
        uint32_t kd_ms;            /**< `autotype`: doba stisku v ms. */
        uint32_t ku_ms;            /**< `autotype`: doba uvolnění v ms. */
        char *cmd;                 /**< `dbg`: jméno příkazu (`mem_write`, `set_reg`, ...). */
        char *args_json;           /**< `dbg`: argumenty jako JSON objekt (text). */
    } st_REPLAY_EVENT;

    /**
     * @brief Části stavu v řádku hashů (pořadí sloupců `hashes.csv`).
     */
    typedef enum en_REPLAY_HASH_PART
    {
        REPLAY_HASH_CPU = 0, /**< `cpu`: registry a skrytý stav Z80. */
        REPLAY_HASH_RAM,     /**< `ram`: vnitřní RAM 64 KB. */
        REPLAY_HASH_MEMEXT,  /**< `memext`: RAM MemExt (jen připojený). */
        REPLAY_HASH_VRAM,    /**< `vram`: VRAM platformy. */
        REPLAY_HASH_PCG,     /**< `pcg`: PCG (jen MZ-1500). */
        REPLAY_HASH_PART_COUNT /**< Počet částí (není část). */
    } en_REPLAY_HASH_PART;

    /**
     * @brief Řádek `hashes.csv`: hashe částí stavu na hranici snímku.
     *
     * @invariant `part[i]` je buď 64 hex znaků malými písmeny, nebo prázdný
     *            řetězec (část na platformě nebo v sestavě chybí).
     */
    typedef struct st_REPLAY_HASH_ROW
    {
        uint32_t frame;  /**< Snímek od startu záznamu. */
        uint64_t ticks;  /**< Takty GDG (`gdg_get_total_ticks()`) v tom bodě. */
        char part[REPLAY_HASH_PART_COUNT][REPLAY_HASH_HEX_LEN + 1]; /**< Hex hashe částí. */
    } st_REPLAY_HASH_ROW;

    /**
     * @brief Celý záznam v paměti.
     *
     * @invariant `events` je seřazené podle `frame` neklesajícím pořadím
     *            (v rámci snímku v pořadí provedení); `hashes` rostoucím
     *            `frame`; žádná událost ani hash nemá `frame` > `frames`.
     * @invariant Všechny ukazatele vlastní struktura (replay_data_free()).
     */
    typedef struct st_REPLAY_DATA
    {
        char *emulator_version;   /**< Verze emulátoru, který záznam pořídil. */
        char *platform;           /**< Platforma (`mz700`, `mz800`, `mz1500`). */
        uint32_t screen_ticks;    /**< Takty GDG na snímek (VIDEO_SCREEN_TICKS); musí sedět při přehrání. */
        char *created;            /**< Čas pořízení ISO 8601 (místní čas). */
        char *description;        /**< Popis od uživatele (může být NULL). */
        uint32_t frames;          /**< Délka záznamu ve snímcích (= snímek konce). */
        uint32_t hash_interval;   /**< Interval hashů ve snímcích (aspoň 1). */
        uint32_t rerecord_count;  /**< Počet přepisů (v1 vždy 0). */
        bool has_debugger_events; /**< Záznam obsahuje události `dbg` (přehrání jen s debuggerem). */
        bool final_hash;          /**< Poslední řádek hashů (snímek `frames`) je stav na konci záznamu, po událostech `p` posledního snímku; jinak je to obyčejný periodický řádek. */
        GPtrArray *warnings;      /**< Varování záznamu (char *, bez duplicit). */
        uint8_t *start_snapshot;  /**< Data `start.mzs` (g_malloc). */
        size_t start_snapshot_size; /**< Velikost `start_snapshot` v bajtech. */
        GArray *events;           /**< Události (st_REPLAY_EVENT). */
        GArray *hashes;           /**< Řádky hashů (st_REPLAY_HASH_ROW). */
    } st_REPLAY_DATA;

    /**
     * @brief Textové jméno druhu události (`kbd`, `joy`, ...).
     * @return Statický řetězec; mimo rozsah "unknown".
     */
    const char *replay_ev_kind_name(en_REPLAY_EV_KIND kind);

    /**
     * @brief Textové jméno polohy (`b`, `d`, `p`).
     * @return Statický řetězec; mimo rozsah "?".
     */
    const char *replay_ev_at_name(en_REPLAY_EV_AT at);

    /**
     * @brief Jméno části hashe (`cpu`, `ram`, `memext`, `vram`, `pcg`).
     * @return Statický řetězec; mimo rozsah "unknown".
     */
    const char *replay_hash_part_name(en_REPLAY_HASH_PART part);

    /**
     * @brief Nový prázdný záznam (bez snapshotu, bez událostí).
     *
     * @return Záznam s `hash_interval` = REPLAY_DEFAULT_HASH_INTERVAL;
     *         uvolnit replay_data_free(). Alokace přes GLib (při nedostatku
     *         paměti proces skončí jako u všech g_malloc).
     */
    st_REPLAY_DATA *replay_data_new(void);

    /**
     * @brief Uvolní záznam včetně všech řetězců a dat snapshotu.
     * @param d Záznam nebo NULL (nic se nestane).
     */
    void replay_data_free(st_REPLAY_DATA *d);

    /**
     * @brief Připojí událost na konec záznamu (hluboká kopie řetězců).
     *
     * @param d  Záznam.
     * @param ev Událost; řetězce zůstávají volajícímu.
     * @post U `dbg` se nastaví `d->has_debugger_events`.
     * @pre `ev->frame` není menší než `frame` poslední události (pořadí
     *      kontroluje až replay_data_read(); zápis ho nekontroluje).
     */
    void replay_data_add_event(st_REPLAY_DATA *d, const st_REPLAY_EVENT *ev);

    /**
     * @brief Připojí řádek hashů na konec záznamu (kopie).
     */
    void replay_data_add_hash(st_REPLAY_DATA *d, const st_REPLAY_HASH_ROW *row);

    /**
     * @brief Přidá varování, pokud tam ještě není (porovnání textu).
     */
    void replay_data_add_warning(st_REPLAY_DATA *d, const char *warning);

    /**
     * @brief Převede události na text `inputs.jsonl` včetně řádku `end`.
     *
     * @return Nový řetězec (g_free); řádky končí `\n`.
     */
    char *replay_data_inputs_to_jsonl(const st_REPLAY_DATA *d);

    /**
     * @brief Načte události z textu `inputs.jsonl` (nahradí dosavadní).
     *
     * Kontroluje: každý řádek je JSON objekt se známým druhem a polohou,
     * `f` neklesá, poslední neprázdný řádek je `end`, žádná událost není
     * za `end`. Délku (`frames`) nastaví ze snímku řádku `end`.
     *
     * @param d    Záznam (události se nahradí).
     * @param text Text souboru (UTF-8).
     * @param[out] err Při chybě nový text chyby anglicky s číslem řádku (g_free); smí být NULL.
     * @return true = načteno; false = chyba, události záznamu jsou pak prázdné.
     */
    bool replay_data_inputs_from_jsonl(st_REPLAY_DATA *d, const char *text, char **err);

    /**
     * @brief Uloží záznam do souboru `.mzr` (atomicky přes `<path>.tmp`).
     *
     * @param d    Záznam se snapshotem (`start_snapshot` != NULL).
     * @param path Cílová cesta.
     * @param[out] err Při chybě nový text chyby anglicky (g_free); smí být NULL.
     * @return true = uloženo; false = chyba (cílový soubor se nezměnil).
     */
    bool replay_data_write(const st_REPLAY_DATA *d, const char *path, char **err);

    /**
     * @brief Načte záznam ze souboru `.mzr`.
     *
     * Kontroluje formát a verzi manifestu, přítomnost všech souborů,
     * pořadí událostí a hashů (viz replay_data_inputs_from_jsonl()).
     * Platformu a délku snímku nekontroluje (to dělá přehrávač proti
     * běžícímu emulátoru).
     *
     * @param path Cesta k souboru.
     * @param[out] err Při chybě nový text chyby anglicky (g_free); smí být NULL.
     * @return Nový záznam (replay_data_free()), nebo NULL při chybě.
     */
    st_REPLAY_DATA *replay_data_read(const char *path, char **err);

#ifdef __cplusplus
}
#endif

#endif /* REPLAY_FORMAT_H */
