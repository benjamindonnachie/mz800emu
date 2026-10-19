/**
 * @file test_replay_input.c
 * @brief Unit testy cesty vstupů záznamu (replay.c) bez GUI a bez hlavní smyčky.
 *
 * Hlavní smyčku simuluje test: pauzu nastaví přímo (`g_emulator.paused`),
 * konec snímku = zvýšení `g_gdg.total_elapsed.screens` a volání
 * replay_on_frame_boundary(), paused smyčku volání replay_on_paused().
 *
 * Pokrývá:
 *   - mimo záznam zapisuje sken klávesnice a okno VKBD hned (jako dřív),
 *   - při záznamu čeká matice z UI ("čekající matice") a reset na hranici
 *     snímku a teprve tam se převezme a zapíše do záznamu,
 *   - uložený soubor obsahuje události ve správných snímcích a polohách,
 *   - při přehrávání se živý vstup zahodí, záznam se přehraje bez rozjetí
 *     (shodný závěrečný hash) a skončí s výsledkem `ended`,
 *   - start záznamu při běžícím autotype se odmítne.
 *
 * Licence: GPLv3
 */

#include "mztest.h"
#include <glib.h>
#include <glib/gstdio.h>
#include <string.h>

#include "emulator/replay.h"
#include "emulator/replay_format.h"
#include "emulator/emulator.h"
#include "hw-generic/pio8255/pio8255.h"
#include "hw-generic/gdg/gdg.h"

/** @brief Dočasný adresář testu. */
static char *s_tmpdir = NULL;

void setUp(void)
{
    if (!s_tmpdir) s_tmpdir = g_dir_make_tmp("replay_in_XXXXXX", NULL);
    g_emulator.paused = true;
}

void tearDown(void)
{
}


/** @brief Cesta souboru v dočasném adresáři (g_free). */
static char *tmp_path(const char *name)
{
    return g_build_filename(s_tmpdir, name, NULL);
}


/** @brief Konec snímku v simulované hlavní smyčce. */
static void next_frame(void)
{
    g_gdg.total_elapsed.screens++;
    replay_on_frame_boundary();
}


/** @brief Matice se všemi klávesami uvolněnými kromě (col, value). */
static void idle_matrix(uint8_t *m, int col, uint8_t value)
{
    memset(m, 0xFF, 10);
    if (col >= 0) m[col] = value;
}


/* Mimo záznam: sken klávesnice a VKBD zapisují hned. */
void test_off_mode_writes_immediately(void)
{
    uint8_t m[10];
    idle_matrix(m, 3, 0xF7);
    replay_host_keyboard_submit(m, -1, 0xFF);
    TEST_ASSERT_EQUAL_HEX8(0xF7, g_pio8255.keyboard_matrix[3]);
    TEST_ASSERT_EQUAL_HEX8(0xFF, g_pio8255.keyboard_matrix[4]);

    pio8255_vkbd_matrix_reset();
    replay_host_vkbd_set(2, 1, true);
    TEST_ASSERT_EQUAL_HEX8(0xFD, g_pio8255.vkbd_matrix[2]);
    replay_host_vkbd_set(2, 1, false);
    TEST_ASSERT_EQUAL_HEX8(0xFF, g_pio8255.vkbd_matrix[2]);

    TEST_ASSERT_FALSE(replay_divert_reset_request());

    idle_matrix(m, -1, 0);
    replay_host_keyboard_submit(m, -1, 0xFF);
}


/* Záznam: vstupy z UI a reset čekají na hranici snímku. */
void test_recording_takes_inputs_at_frame_boundary(void)
{
    char *path = tmp_path("in.mzr");
    pio8255_vkbd_matrix_reset();
    pio8255_keyboard_matrix_reset();

    uint32_t seq = replay_request_record(path, 5, "unit test");
    replay_on_paused();
    st_REPLAY_STATUS st;
    replay_get_status(&st);
    TEST_ASSERT_EQUAL_UINT32(seq, st.request_done);
    TEST_ASSERT_TRUE_MESSAGE(st.request_ok, st.request_message);
    TEST_ASSERT_EQUAL_INT(REPLAY_MODE_RECORDING, st.mode);
    TEST_ASSERT_TRUE(replay_is_active());

    /* Vstup z UI se do matice nezapíše hned. */
    uint8_t m[10];
    idle_matrix(m, 4, 0x7F);
    replay_host_keyboard_submit(m, -1, 0xFF);
    replay_host_vkbd_set(1, 0, true);
    TEST_ASSERT_EQUAL_HEX8(0xFF, g_pio8255.keyboard_matrix[4]);
    TEST_ASSERT_EQUAL_HEX8(0xFF, g_pio8255.vkbd_matrix[1]);
    TEST_ASSERT_TRUE(replay_divert_reset_request());

    /* Hranice snímku: reset, převzetí matice (VKBD okna se promítne do
     * keyboard_matrix), vzorek. */
    next_frame();
    TEST_ASSERT_EQUAL_HEX8(0x7F, g_pio8255.keyboard_matrix[4]);
    TEST_ASSERT_EQUAL_HEX8(0xFE, g_pio8255.keyboard_matrix[1]);
    TEST_ASSERT_EQUAL_UINT32(1, replay_current_frame());

    /* V pauze na hranici snímku: konec se závěrečným hashem. */
    TEST_ASSERT_TRUE(replay_paused_at_boundary());
    seq = replay_request_stop();
    replay_on_paused();
    replay_get_status(&st);
    TEST_ASSERT_TRUE_MESSAGE(st.request_ok, st.request_message);
    TEST_ASSERT_EQUAL_INT(REPLAY_MODE_OFF, st.mode);
    TEST_ASSERT_EQUAL_INT(REPLAY_OUTCOME_RECORDED, st.outcome);

    char *err = NULL;
    st_REPLAY_DATA *d = replay_data_read(path, &err);
    TEST_ASSERT_NOT_NULL_MESSAGE(d, err ? err : "");
    TEST_ASSERT_EQUAL_UINT32(1, d->frames);
    TEST_ASSERT_TRUE(d->final_hash);
    TEST_ASSERT_EQUAL_UINT32(5, d->hash_interval);
    TEST_ASSERT_EQUAL_STRING("unit test", d->description);
    /* f = 0: matice + 2 joysticky; f = 1: reset, matice. */
    TEST_ASSERT_EQUAL_UINT(5, d->events->len);
    st_REPLAY_EVENT *e0 = &g_array_index(d->events, st_REPLAY_EVENT, 0);
    TEST_ASSERT_EQUAL_INT(REPLAY_EV_KBD, e0->kind);
    TEST_ASSERT_EQUAL_UINT32(0, e0->frame);
    st_REPLAY_EVENT *e3 = &g_array_index(d->events, st_REPLAY_EVENT, 3);
    TEST_ASSERT_EQUAL_INT(REPLAY_EV_RESET, e3->kind);
    TEST_ASSERT_EQUAL_UINT32(1, e3->frame);
    TEST_ASSERT_EQUAL_INT(REPLAY_AT_BOUNDARY, e3->at);
    st_REPLAY_EVENT *e4 = &g_array_index(d->events, st_REPLAY_EVENT, 4);
    TEST_ASSERT_EQUAL_INT(REPLAY_EV_KBD, e4->kind);
    TEST_ASSERT_EQUAL_HEX8(0x7F, e4->kbd[4]);
    TEST_ASSERT_EQUAL_HEX8(0xFE, e4->kbd[1]);
    /* Hash f = 0 a závěrečný f = 1. */
    TEST_ASSERT_EQUAL_UINT(2, d->hashes->len);
    TEST_ASSERT_EQUAL_UINT32(1, g_array_index(d->hashes, st_REPLAY_HASH_ROW, 1).frame);
    replay_data_free(d);
    g_free(err);

    /* Po konci záznamu jde vstup zase rovnou. */
    idle_matrix(m, -1, 0);
    replay_host_keyboard_submit(m, -1, 0xFF);
    TEST_ASSERT_EQUAL_HEX8(0xFF, g_pio8255.keyboard_matrix[4]);
    g_free(path);
}


/* Přehrávání: živý vstup se zahodí, záznam doběhne bez rozjetí. */
void test_playback_ignores_live_input_and_ends(void)
{
    char *path = tmp_path("in.mzr");
    uint32_t seq = replay_request_play(path, true);
    replay_on_paused();
    st_REPLAY_STATUS st;
    replay_get_status(&st);
    TEST_ASSERT_EQUAL_UINT32(seq, st.request_done);
    TEST_ASSERT_TRUE_MESSAGE(st.request_ok, st.request_message);
    TEST_ASSERT_EQUAL_INT(REPLAY_MODE_PLAYING, st.mode);
    TEST_ASSERT_EQUAL_UINT32(1, st.frames);

    uint8_t m[10];
    idle_matrix(m, 6, 0x00);
    replay_host_keyboard_submit(m, -1, 0xFF);
    replay_host_vkbd_set(7, 3, true);
    TEST_ASSERT_EQUAL_HEX8(0xFF, g_pio8255.keyboard_matrix[6]);
    TEST_ASSERT_EQUAL_HEX8(0xFF, g_pio8255.vkbd_matrix[7]);

    next_frame();
    replay_get_status(&st);
    TEST_ASSERT_EQUAL_INT(REPLAY_MODE_OFF, st.mode);
    TEST_ASSERT_EQUAL_INT_MESSAGE(REPLAY_OUTCOME_ENDED, st.outcome, st.outcome_message);
    TEST_ASSERT_EQUAL_UINT32(1, st.outcome_frame);
    TEST_ASSERT_FALSE(st.deviated);
    TEST_ASSERT_EQUAL_HEX8(0x7F, g_pio8255.keyboard_matrix[4]);
    TEST_ASSERT_EQUAL_INT(EMU_PAUSE_REASON_REPLAY_END, g_emulator.pause_reason);
    g_free(path);
}


/* Start záznamu při běžícím autotype se odmítne. */
void test_record_refused_while_autotype_runs(void)
{
    static char text[] = "A";
    char *path = tmp_path("no.mzr");
    pio8255_set_autotype(text);
    uint32_t seq = replay_request_record(path, 0, NULL);
    replay_on_paused();
    st_REPLAY_STATUS st;
    replay_get_status(&st);
    TEST_ASSERT_EQUAL_UINT32(seq, st.request_done);
    TEST_ASSERT_FALSE(st.request_ok);
    TEST_ASSERT_NOT_NULL(strstr(st.request_message, "autotype"));
    TEST_ASSERT_EQUAL_INT(REPLAY_MODE_OFF, st.mode);
    TEST_ASSERT_FALSE(g_file_test(path, G_FILE_TEST_EXISTS));
    pio8255_set_autotype(NULL);
    g_free(path);
}


int main(int argc, char **argv)
{
    mztest_parse_args(argc, argv);
    mztest_init();
    replay_init();

    UNITY_BEGIN();
    RUN_TEST(test_off_mode_writes_immediately);
    RUN_TEST(test_recording_takes_inputs_at_frame_boundary);
    RUN_TEST(test_playback_ignores_live_input_and_ends);
    RUN_TEST(test_record_refused_while_autotype_runs);
    int result = UNITY_END();

    char *p = tmp_path("in.mzr");
    g_remove(p);
    g_free(p);
    g_rmdir(s_tmpdir);
    g_free(s_tmpdir);
    mztest_teardown();
    return result;
}
