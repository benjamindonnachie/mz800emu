#ifndef IMGUI_CMT_H
#define IMGUI_CMT_H

#ifdef __cplusplus
extern "C"
{
#endif

    void imgui_cmt(bool *p_open);
    void imgui_cmt_fix_mzfsize_popup(bool *p_open);
    void imgui_cmt_fix_mzfsize_popup_activate(const char *filename, int valid_size, int file_size);
    void imgui_cmt_tape_index_window(bool *p_open);
    void imgui_cmt_tape_update_filelist(void);

    /**
     * @brief Začátek zákazu ovládání kazety během záznamu / přehrávání vstupů.
     *
     * Okna kazety volají cmt_play() / cmt_stop() přímo z UI vlákna, mimo
     * záznam vstupů (replay.h), který je nezopakuje. Při běžícím záznamu nebo
     * přehrávání vypíše vysvětlení a zahájí ImGui::BeginDisabled().
     *
     * @return true = zákaz platí, volající musí zavolat imgui_cmt_replay_lock_end(true).
     * @pre UI vlákno, uvnitř ImGui::Begin() okna.
     */
    bool imgui_cmt_replay_lock_begin(void);

    /**
     * @brief Konec zákazu z imgui_cmt_replay_lock_begin() (před ImGui::End()).
     * @param locked Návratová hodnota imgui_cmt_replay_lock_begin().
     */
    void imgui_cmt_replay_lock_end(bool locked);

#ifdef __cplusplus
}
#endif

#endif /* IMGUI_CMT_H */
