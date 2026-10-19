/**
 * @file test_replay_format.c
 * @brief Unit testy formátu záznamu vstupů `.mzr` (replay_format.c).
 *
 * Pokrývá: převod událostí na `inputs.jsonl` a zpět (všechny druhy
 * a polohy), kontroly čtení (pořadí snímků, chybějící `end`, událost za
 * `end`, neznámý druh, špatná matice), zápis a čtení celého souboru
 * včetně hashů a varování, odmítnutí cizího souboru a jiné verze.
 *
 * Licence: GPLv3
 */

#include "mztest.h"
#include <glib.h>
#include <glib/gstdio.h>
#include <string.h>

#include "emulator/replay_format.h"
#include "emulator/snapshot/snapshot_io.h"

/** @brief Dočasný adresář testu (g_dir_make_tmp), smaže tearDown(). */
static char *s_tmpdir = NULL;

void setUp(void)
{
    s_tmpdir = g_dir_make_tmp("replay_fmt_XXXXXX", NULL);
}

void tearDown(void)
{
    if (s_tmpdir)
    {
        GDir *dir = g_dir_open(s_tmpdir, 0, NULL);
        if (dir)
        {
            const char *name;
            while ((name = g_dir_read_name(dir)) != NULL)
            {
                char *p = g_build_filename(s_tmpdir, name, NULL);
                g_remove(p);
                g_free(p);
            };
            g_dir_close(dir);
        };
        g_rmdir(s_tmpdir);
        g_free(s_tmpdir);
        s_tmpdir = NULL;
    };
}


/** @brief Záznam se vzorovou událostí od každého druhu. */
static st_REPLAY_DATA *make_sample(void)
{
    st_REPLAY_DATA *d = replay_data_new();
    d->emulator_version = g_strdup("test");
    d->platform = g_strdup("mz800");
    d->screen_ticks = 354432;
    d->frames = 120;

    st_REPLAY_EVENT ev;
    memset(&ev, 0, sizeof(ev));
    ev.frame = 0;
    ev.kind = REPLAY_EV_KBD;
    ev.at = REPLAY_AT_BOUNDARY;
    memset(ev.kbd, 0xFF, sizeof(ev.kbd));
    ev.kbd[3] = 0xF7;
    replay_data_add_event(d, &ev);

    memset(&ev, 0, sizeof(ev));
    ev.frame = 10;
    ev.kind = REPLAY_EV_JOY;
    ev.joy_port = 1;
    ev.joy_state = 0xFE;
    replay_data_add_event(d, &ev);

    memset(&ev, 0, sizeof(ev));
    ev.frame = 20;
    ev.kind = REPLAY_EV_AUTOTYPE;
    ev.text = (char *)"LOAD \"x\"\n";
    ev.kd_ms = 20;
    ev.ku_ms = 30;
    replay_data_add_event(d, &ev);

    memset(&ev, 0, sizeof(ev));
    ev.frame = 20;
    ev.kind = REPLAY_EV_DBG;
    ev.at = REPLAY_AT_DRAIN;
    ev.cmd = (char *)"mem_write";
    ev.args_json = (char *)"{\"addr\":4660,\"data\":\"3e01\"}";
    replay_data_add_event(d, &ev);

    memset(&ev, 0, sizeof(ev));
    ev.frame = 50;
    ev.kind = REPLAY_EV_RESET;
    ev.at = REPLAY_AT_PAUSE;
    replay_data_add_event(d, &ev);
    return d;
}


/* Události projdou převodem na JSONL a zpět beze změny. */
void test_inputs_roundtrip(void)
{
    st_REPLAY_DATA *d = make_sample();
    TEST_ASSERT_TRUE(d->has_debugger_events);
    char *text = replay_data_inputs_to_jsonl(d);
    TEST_ASSERT_NOT_NULL(strstr(text, "{\"f\":120,\"k\":\"end\"}\n"));

    st_REPLAY_DATA *r = replay_data_new();
    char *err = NULL;
    TEST_ASSERT_TRUE_MESSAGE(replay_data_inputs_from_jsonl(r, text, &err), err ? err : "");
    TEST_ASSERT_EQUAL_UINT32(120, r->frames);
    TEST_ASSERT_EQUAL_UINT(d->events->len, r->events->len);
    TEST_ASSERT_TRUE(r->has_debugger_events);

    st_REPLAY_EVENT *e0 = &g_array_index(r->events, st_REPLAY_EVENT, 0);
    TEST_ASSERT_EQUAL_INT(REPLAY_EV_KBD, e0->kind);
    TEST_ASSERT_EQUAL_HEX8(0xF7, e0->kbd[3]);
    TEST_ASSERT_EQUAL_HEX8(0xFF, e0->kbd[9]);

    st_REPLAY_EVENT *e1 = &g_array_index(r->events, st_REPLAY_EVENT, 1);
    TEST_ASSERT_EQUAL_INT(REPLAY_EV_JOY, e1->kind);
    TEST_ASSERT_EQUAL_UINT8(1, e1->joy_port);
    TEST_ASSERT_EQUAL_HEX8(0xFE, e1->joy_state);

    st_REPLAY_EVENT *e2 = &g_array_index(r->events, st_REPLAY_EVENT, 2);
    TEST_ASSERT_EQUAL_STRING("LOAD \"x\"\n", e2->text);
    TEST_ASSERT_EQUAL_UINT32(30, e2->ku_ms);

    st_REPLAY_EVENT *e3 = &g_array_index(r->events, st_REPLAY_EVENT, 3);
    TEST_ASSERT_EQUAL_INT(REPLAY_AT_DRAIN, e3->at);
    TEST_ASSERT_EQUAL_STRING("mem_write", e3->cmd);
    TEST_ASSERT_NOT_NULL(strstr(e3->args_json, "\"addr\":4660"));

    st_REPLAY_EVENT *e4 = &g_array_index(r->events, st_REPLAY_EVENT, 4);
    TEST_ASSERT_EQUAL_INT(REPLAY_EV_RESET, e4->kind);
    TEST_ASSERT_EQUAL_INT(REPLAY_AT_PAUSE, e4->at);
    TEST_ASSERT_EQUAL_UINT32(50, e4->frame);

    g_free(err);
    g_free(text);
    replay_data_free(r);
    replay_data_free(d);
}


/** @brief true = text se načíst nepodaří a chyba obsahuje @p needle. */
static bool inputs_fail_with(const char *text, const char *needle)
{
    st_REPLAY_DATA *r = replay_data_new();
    char *err = NULL;
    bool ok = replay_data_inputs_from_jsonl(r, text, &err);
    bool match = !ok && err && strstr(err, needle) != NULL && r->events->len == 0;
    if (!match) TEST_MESSAGE(err ? err : "(no error)");
    g_free(err);
    replay_data_free(r);
    return match;
}


/* Čtení odmítne vadné soubory událostí s číslem řádku. */
void test_inputs_rejects_invalid(void)
{
    TEST_ASSERT_TRUE(inputs_fail_with("{\"f\":5,\"at\":\"b\",\"k\":\"reset\"}\n", "missing \"end\""));
    TEST_ASSERT_TRUE(inputs_fail_with("{\"f\":5,\"at\":\"b\",\"k\":\"reset\"}\n{\"f\":3,\"k\":\"end\"}\n",
                                      "line 2: frame 3 is before frame 5"));
    TEST_ASSERT_TRUE(inputs_fail_with("{\"f\":5,\"k\":\"end\"}\n{\"f\":6,\"at\":\"b\",\"k\":\"reset\"}\n",
                                      "line 2: event after"));
    TEST_ASSERT_TRUE(inputs_fail_with("{\"f\":1,\"at\":\"b\",\"k\":\"nope\"}\n{\"f\":2,\"k\":\"end\"}\n",
                                      "line 1: unknown event kind"));
    TEST_ASSERT_TRUE(inputs_fail_with("{\"f\":1,\"at\":\"b\",\"k\":\"kbd\",\"m\":[1,2]}\n{\"f\":2,\"k\":\"end\"}\n",
                                      "10 items"));
    TEST_ASSERT_TRUE(inputs_fail_with("{\"f\":1,\"at\":\"x\",\"k\":\"reset\"}\n{\"f\":2,\"k\":\"end\"}\n",
                                      "unknown \"at\""));
    TEST_ASSERT_TRUE(inputs_fail_with("{\"f\":1,\"at\":\"d\",\"k\":\"dbg\",\"cmd\":\"x\"}\n{\"f\":2,\"k\":\"end\"}\n",
                                      "\"args\""));
    TEST_ASSERT_TRUE(inputs_fail_with("not json\n", "line 1"));
}


/* Prázdné řádky a konec bez nového řádku nevadí. */
void test_inputs_tolerates_blank_lines(void)
{
    st_REPLAY_DATA *r = replay_data_new();
    char *err = NULL;
    TEST_ASSERT_TRUE(replay_data_inputs_from_jsonl(r, "\n\n{\"f\":2,\"at\":\"b\",\"k\":\"reset\"}\n\n{\"f\":7,\"k\":\"end\"}", &err));
    TEST_ASSERT_EQUAL_UINT(1, r->events->len);
    TEST_ASSERT_EQUAL_UINT32(7, r->frames);
    g_free(err);
    replay_data_free(r);
}


/* Celý soubor .mzr: manifest, snapshot, události, hashe a varování. */
void test_file_roundtrip(void)
{
    st_REPLAY_DATA *d = make_sample();
    uint8_t snap[300];
    for (int i = 0; i < 300; i++) snap[i] = (uint8_t)(i * 7);
    d->start_snapshot = g_memdup2(snap, sizeof(snap));
    d->start_snapshot_size = sizeof(snap);
    d->hash_interval = 25;
    d->description = g_strdup("popis");
    d->final_hash = true;
    replay_data_add_warning(d, "host joystick is not recorded");
    replay_data_add_warning(d, "host joystick is not recorded");

    st_REPLAY_HASH_ROW row;
    memset(&row, 0, sizeof(row));
    row.frame = 0;
    row.ticks = 12345678901ULL;
    memset(row.part[REPLAY_HASH_RAM], 'a', REPLAY_HASH_HEX_LEN);
    replay_data_add_hash(d, &row);
    row.frame = 100;
    memset(row.part[REPLAY_HASH_CPU], '0', REPLAY_HASH_HEX_LEN);
    replay_data_add_hash(d, &row);

    char *path = g_build_filename(s_tmpdir, "a.mzr", NULL);
    char *err = NULL;
    TEST_ASSERT_TRUE_MESSAGE(replay_data_write(d, path, &err), err ? err : "");

    st_REPLAY_DATA *r = replay_data_read(path, &err);
    TEST_ASSERT_NOT_NULL_MESSAGE(r, err ? err : "");
    TEST_ASSERT_EQUAL_STRING("mz800", r->platform);
    TEST_ASSERT_EQUAL_UINT32(354432, r->screen_ticks);
    TEST_ASSERT_EQUAL_UINT32(120, r->frames);
    TEST_ASSERT_EQUAL_UINT32(25, r->hash_interval);
    TEST_ASSERT_EQUAL_STRING("popis", r->description);
    TEST_ASSERT_TRUE(r->final_hash);
    TEST_ASSERT_TRUE(r->has_debugger_events);
    TEST_ASSERT_EQUAL_UINT(1, r->warnings->len);
    TEST_ASSERT_EQUAL_size_t(sizeof(snap), r->start_snapshot_size);
    TEST_ASSERT_EQUAL_MEMORY(snap, r->start_snapshot, sizeof(snap));
    TEST_ASSERT_EQUAL_UINT(5, r->events->len);
    TEST_ASSERT_EQUAL_UINT(2, r->hashes->len);
    st_REPLAY_HASH_ROW *h0 = &g_array_index(r->hashes, st_REPLAY_HASH_ROW, 0);
    TEST_ASSERT_EQUAL_UINT64(12345678901ULL, h0->ticks);
    TEST_ASSERT_EQUAL_size_t(REPLAY_HASH_HEX_LEN, strlen(h0->part[REPLAY_HASH_RAM]));
    TEST_ASSERT_EQUAL_STRING("", h0->part[REPLAY_HASH_CPU]);
    st_REPLAY_HASH_ROW *h1 = &g_array_index(r->hashes, st_REPLAY_HASH_ROW, 1);
    TEST_ASSERT_EQUAL_UINT32(100, h1->frame);
    TEST_ASSERT_EQUAL_CHAR('0', h1->part[REPLAY_HASH_CPU][0]);

    /* Dočasný soubor po atomickém zápisu nezůstal. */
    char *tmp = g_strdup_printf("%s.tmp", path);
    TEST_ASSERT_FALSE(g_file_test(tmp, G_FILE_TEST_EXISTS));

    g_free(tmp);
    g_free(err);
    g_free(path);
    replay_data_free(r);
    replay_data_free(d);
}


/* Zápis bez startovního snapshotu selže a nic nevytvoří. */
void test_write_requires_snapshot(void)
{
    st_REPLAY_DATA *d = make_sample();
    char *path = g_build_filename(s_tmpdir, "b.mzr", NULL);
    char *err = NULL;
    TEST_ASSERT_FALSE(replay_data_write(d, path, &err));
    TEST_ASSERT_NOT_NULL(err);
    TEST_ASSERT_FALSE(g_file_test(path, G_FILE_TEST_EXISTS));
    g_free(err);
    g_free(path);
    replay_data_free(d);
}


/** @brief Vytvoří ZIP s danými soubory (jméno, obsah; NULL ukončuje). */
static void write_zip(const char *path, const char *const *entries)
{
    snapshot_io_t *io = snapshot_io_open_write(path, 6);
    TEST_ASSERT_NOT_NULL(io);
    for (int i = 0; entries[i]; i += 2)
    {
        TEST_ASSERT_EQUAL_INT(SNAPSHOT_OK, snapshot_io_write_bin(io, entries[i], (const uint8_t *)entries[i + 1],
                                                                 strlen(entries[i + 1])));
    };
    snapshot_io_close(io);
}


/* Cizí ZIP, jiná verze a chybějící soubor se odmítnou. */
void test_read_rejects_foreign(void)
{
    char *path = g_build_filename(s_tmpdir, "c.mzr", NULL);
    char *err = NULL;

    const char *const no_manifest[] = { "start.mzs", "x", "inputs.jsonl", "{\"f\":0,\"k\":\"end\"}", "hashes.csv", "h", NULL };
    write_zip(path, no_manifest);
    TEST_ASSERT_NULL(replay_data_read(path, &err));
    TEST_ASSERT_NOT_NULL(strstr(err, "manifest.json"));

    const char *const other_version[] = { "manifest.json", "{\"format\":\"mz800emu-replay\",\"version\":99}",
                                          "start.mzs", "x", "inputs.jsonl", "{\"f\":0,\"k\":\"end\"}",
                                          "hashes.csv", "frame\n", NULL };
    write_zip(path, other_version);
    TEST_ASSERT_NULL(replay_data_read(path, &err));
    TEST_ASSERT_NOT_NULL(strstr(err, "unsupported version"));

    const char *const other_format[] = { "manifest.json", "{\"format\":\"something\",\"version\":1}",
                                         "start.mzs", "x", "inputs.jsonl", "{\"f\":0,\"k\":\"end\"}",
                                         "hashes.csv", "frame\n", NULL };
    write_zip(path, other_format);
    TEST_ASSERT_NULL(replay_data_read(path, &err));
    TEST_ASSERT_NOT_NULL(strstr(err, "not a mz800emu-replay"));

    const char *const hash_after_end[] = { "manifest.json", "{\"format\":\"mz800emu-replay\",\"version\":1}",
                                           "start.mzs", "x", "inputs.jsonl", "{\"f\":10,\"k\":\"end\"}",
                                           "hashes.csv", "frame,ticks,cpu,ram,memext,vram,pcg\n11,0,,,,,\n", NULL };
    write_zip(path, hash_after_end);
    TEST_ASSERT_NULL(replay_data_read(path, &err));
    TEST_ASSERT_NOT_NULL(strstr(err, "after the end"));

    g_free(err);
    g_free(path);
}


int main(int argc, char **argv)
{
    mztest_parse_args(argc, argv);
    mztest_init();

    UNITY_BEGIN();
    RUN_TEST(test_inputs_roundtrip);
    RUN_TEST(test_inputs_rejects_invalid);
    RUN_TEST(test_inputs_tolerates_blank_lines);
    RUN_TEST(test_file_roundtrip);
    RUN_TEST(test_write_requires_snapshot);
    RUN_TEST(test_read_rejects_foreign);
    int result = UNITY_END();
    mztest_teardown();
    return result;
}
