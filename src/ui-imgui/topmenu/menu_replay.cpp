/**
 * @file menu_replay.cpp
 * @brief Nabídka Replay (záznam a přehrání vstupů), souborové dialogy,
 *        oznámení výsledku a indikátor REC / PLAY v obraze.
 *
 * GUI jen posílá požadavky do modulu záznamu (replay.h) a čte jeho stav;
 * záznam i přehrávání řídí emu vlákno. Výsledek požadavku (chyba startu)
 * a konec záznamu / přehrávání (uloženo, konec, rozjetí) se ohlásí
 * notifikací.
 *
 * Volá jen UI vlákno.
 */

#include "main.h"
#include <stdio.h>
#include <string.h>
#include <string>
#include <glib.h>

#include "libs/imgui/imgui.h"
#include "libs/igfd/ImGuiFileDialog.h"
#include "ui-imgui/filechooser/imgui_filechooser.h"
#include "ui-imgui/bootstrap/myimgui.h"

#include "i18n.h"

#include "emulator/replay.h"
#include "snapshot/snapshot.h"
#include "topmenu.h"

extern "C" void snapshot_notification_show_ex(const char *message, bool is_error, const char *error_title);

/** @brief Požadavek z nabídky: otevřít dialog záznamu (uložit jako). */
static bool s_record_dialog_request = false;
/** @brief Požadavek z nabídky: otevřít dialog přehrání. */
static bool s_play_dialog_request = false;
/** @brief Otevřený dialog: 0 = žádný, 1 = záznam, 2 = přehrání. */
static int s_dialog_open = 0;
/** @brief Číslo požadavku, na jehož výsledek se čeká (0 = žádný). */
static uint32_t s_pending_seq = 0;
/** @brief Naposledy ohlášený výsledek (výsledek + snímek + text = otisk). */
static char s_last_outcome_key[REPLAY_STATUS_TEXT_MAX + 64] = "";


void imgui_menu_replay(void)
{
    if (!ImGui::BeginMenu(_L("Replay")))
    {
        return;
    };
    st_REPLAY_STATUS st;
    replay_get_status(&st);
    bool off = (st.mode == REPLAY_MODE_OFF);

    if (ImGui::MenuItem(_L("Record Inputs..."), NULL, false, off))
    {
        s_record_dialog_request = true;
    };
    ImGui::SetItemTooltip("%s", _("Record keyboard, joystick, resets and debugger writes from a start snapshot, "
                                  "to repeat the run exactly later."));
    if (ImGui::MenuItem(_L("Play Replay..."), NULL, false, off))
    {
        s_play_dialog_request = true;
    };
    if (ImGui::MenuItem(_L("Stop Replay"), NULL, false, !off))
    {
        s_pending_seq = replay_request_stop();
    };

    ImGui::Separator();
    if (st.mode == REPLAY_MODE_RECORDING)
    {
        ImGui::TextDisabled(_("Recording: frame %u, %u events"), st.frame, st.events);
    }
    else if (st.mode == REPLAY_MODE_PLAYING)
    {
        ImGui::TextDisabled(_("Playing: frame %u / %u"), st.frame, st.frames);
        if (st.deviated)
        {
            ImGui::TextDisabled(_("Deviated: %s"), st.deviation);
        };
    }
    else if (st.outcome != REPLAY_OUTCOME_NONE)
    {
        ImGui::TextDisabled(_("Last: %s"), st.outcome_message);
    }
    else
    {
        ImGui::TextDisabled("%s", _("No replay"));
    };
    ImGui::EndMenu();
}


/** @brief Otevře souborový dialog záznamu (record = true) nebo přehrání. */
static void replay_open_dialog(bool record)
{
    IGFD::FileDialogConfig config;
    config.path = g_snapshot_settings.default_directory;
    config.countSelectionMax = 1;
    config.flags = ImGuiFileDialogFlags_Modal |
                   ImGuiFileDialogFlags_DontShowHiddenFiles |
                   ImGuiFileDialogFlags_ShowDevicesButton |
                   ImGuiFileDialogFlags_CaseInsensitiveExtentionFiltering;
    if (record)
    {
        config.flags |= ImGuiFileDialogFlags_ConfirmOverwrite;
    }
    else
    {
        config.flags |= ImGuiFileDialogFlags_ReadOnlyFileNameField;
    };
    imgui_filechooser_prepare_config(BASEUI_FCHOOSER_CAT_SNAPSHOT, config);
    ImGuiFileDialog::Instance()->OpenDialog(record ? "ReplayRecordDialog" : "ReplayPlayDialog",
                                            record ? _("Record Inputs") : _("Play Replay"), ".mzr", config);
    s_dialog_open = record ? 1 : 2;
}


/** @brief Ohlásí chybu vyřízeného požadavku a nový výsledek záznamu / přehrávání. */
static void replay_notify(void)
{
    st_REPLAY_STATUS st;
    replay_get_status(&st);

    if (s_pending_seq && st.request_done >= s_pending_seq)
    {
        if (!st.request_ok)
        {
            char msg[REPLAY_STATUS_TEXT_MAX + 64];
            g_snprintf(msg, sizeof(msg), "%s: %s", _("Replay failed"), st.request_message);
            snapshot_notification_show_ex(msg, true, _("Replay Error"));
        };
        s_pending_seq = 0;
    };

    if (st.outcome == REPLAY_OUTCOME_NONE || st.mode != REPLAY_MODE_OFF) return;
    char key[sizeof(s_last_outcome_key)];
    g_snprintf(key, sizeof(key), "%d:%u:%s", (int)st.outcome, st.outcome_frame, st.outcome_message);
    if (strcmp(key, s_last_outcome_key) == 0) return;
    g_strlcpy(s_last_outcome_key, key, sizeof(s_last_outcome_key));

    char msg[REPLAY_STATUS_TEXT_MAX + 64];
    switch (st.outcome)
    {
        case REPLAY_OUTCOME_RECORDED:
            g_snprintf(msg, sizeof(msg), "%s: %s", _("Replay recorded"), st.outcome_message);
            snapshot_notification_show_ex(msg, false, NULL);
            break;
        case REPLAY_OUTCOME_ENDED:
            g_snprintf(msg, sizeof(msg), "%s: %s", _("Replay ended"), st.outcome_message);
            snapshot_notification_show_ex(msg, false, NULL);
            break;
        case REPLAY_OUTCOME_DESYNC:
            g_snprintf(msg, sizeof(msg), _("Replay differs from the recording at frame %u (%s)"),
                       st.outcome_frame, st.desync_parts);
            snapshot_notification_show_ex(msg, true, _("Replay Desync"));
            break;
        case REPLAY_OUTCOME_ERROR:
            g_snprintf(msg, sizeof(msg), "%s: %s", _("Replay failed"), st.outcome_message);
            snapshot_notification_show_ex(msg, true, _("Replay Error"));
            break;
        case REPLAY_OUTCOME_STOPPED:
        default:
            break;
    };
}


void imgui_replay_dialogs(void)
{
    if (s_record_dialog_request)
    {
        s_record_dialog_request = false;
        replay_open_dialog(true);
    };
    if (s_play_dialog_request)
    {
        s_play_dialog_request = false;
        replay_open_dialog(false);
    };

    if (s_dialog_open)
    {
        const char *key = (s_dialog_open == 1) ? "ReplayRecordDialog" : "ReplayPlayDialog";
        ImGui::SetNextWindowSize(ImVec2(900, 600), ImGuiCond_FirstUseEver);
        if (ImGuiFileDialog::Instance()->Display(key))
        {
            if (ImGuiFileDialog::Instance()->IsOk())
            {
                std::string path = ImGuiFileDialog::Instance()->GetFilePathName();
                s_pending_seq = (s_dialog_open == 1) ? replay_request_record(path.c_str(), 0, NULL)
                                                     : replay_request_play(path.c_str(), false);
            };
            ImGuiFileDialog::Instance()->Close();
            s_dialog_open = 0;
        };
    };

    replay_notify();
}


void imgui_replay_overlay(void)
{
    st_REPLAY_STATUS st;
    replay_get_status(&st);
    if (st.mode == REPLAY_MODE_OFF) return;

    char text[128];
    if (st.mode == REPLAY_MODE_RECORDING)
    {
        g_snprintf(text, sizeof(text), _("REPLAY REC %u"), st.frame);
    }
    else
    {
        g_snprintf(text, sizeof(text), _("REPLAY PLAY %u / %u%s"), st.frame, st.frames,
                   st.deviated ? _(" (deviated)") : "");
    };

    /* Levý dolní roh obrazu (horní rohy patří videu, sérii snímků a zvuku). */
    ImVec2 img_min = ImGui::GetItemRectMin();
    ImVec2 img_max = ImGui::GetItemRectMax();
    ImDrawList *dl = ImGui::GetForegroundDrawList();
    const float pad = 6.0f;
    const float margin = 10.0f;
    ImVec2 ts = ImGui::CalcTextSize(text);
    float r = ts.y * 0.4f;
    float w = pad + 2.0f * r + pad + ts.x + pad;
    float h = ts.y + 2.0f * pad;
    ImVec2 box_min(img_min.x + margin, img_max.y - margin - h);
    ImVec2 box_max(img_min.x + margin + w, img_max.y - margin);
    dl->AddRectFilled(box_min, box_max, IM_COL32(0, 0, 0, 160), 4.0f);
    ImVec2 c(box_min.x + pad + r, box_min.y + h * 0.5f);
    if (st.mode == REPLAY_MODE_RECORDING)
    {
        /* Červený kruh = záznam. */
        dl->AddCircleFilled(c, r, IM_COL32(230, 40, 40, 255));
    }
    else
    {
        /* Trojúhelník = přehrávání (oranžový při odchýlení). */
        ImU32 col = st.deviated ? IM_COL32(240, 170, 40, 255) : IM_COL32(120, 230, 120, 255);
        dl->AddTriangleFilled(ImVec2(c.x - r, c.y - r), ImVec2(c.x - r, c.y + r), ImVec2(c.x + r, c.y), col);
    };
    dl->AddText(ImVec2(c.x + r + pad, box_min.y + pad), IM_COL32(255, 255, 255, 255), text);
}
