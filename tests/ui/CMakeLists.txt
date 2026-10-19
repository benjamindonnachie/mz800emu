# UI testy - smoke test infrastruktury (SDL3 + ImGui + OpenGL inicializace).
# Hodnota nízká (testuje vendored knihovny), ale rychlé a užitečné při ImGui
# upgrade - detekuje rozbitý backend.

mz_add_test(ui-smoke
    TYPE     UI
    SOURCES  test_ui_smoke.cpp
    LIBS     mzlib_imgui mzlib_igfd mzlib_imwidgets
    LABELS   "ui"
)

# Memory Browser V0 hex MVP - membrowser mutant
add_subdirectory(membrowser)

# Funkční testy UI logiky - video záznam (menu, dialog nastavení, REC indikátor,
# notifikace událostí, okno dálkového ovládání a tabulka zkratek), okno Replay
# Control (zkratky, vykreslení bez záznamu, při záznamu, rewindu a přehrávání)
# a okna Screenshot Control a Audio Capture Control (zkratky, vykreslení).
# Linkuje UI zdroje přímo; notifikace stubuje test.
mz_add_test(ui-functional
    TYPE     UI
    SOURCES  test_ui_functional.cpp
             ${CMAKE_SOURCE_DIR}/src/ui-imgui/videorec/videorec_menu.cpp
             ${CMAKE_SOURCE_DIR}/src/ui-imgui/videorec/videorec_setup_dialog.cpp
             ${CMAKE_SOURCE_DIR}/src/ui-imgui/videorec/videorec_remote_window.cpp
             ${CMAKE_SOURCE_DIR}/src/ui-imgui/topmenu/menu_replay.cpp
             ${CMAKE_SOURCE_DIR}/src/ui-imgui/topmenu/replay_window.cpp
             ${CMAKE_SOURCE_DIR}/src/ui-imgui/screenshot/screenshot_ui.cpp
             ${CMAKE_SOURCE_DIR}/src/ui-imgui/audiocap/audio_capture_ui.cpp
             ${CMAKE_SOURCE_DIR}/src/ui-imgui/filechooser/igfd_ToggleButton.cpp
    LIBS     mzlib_imgui mzlib_igfd mzlib_imwidgets
    LABELS   "ui;videorec"
)
