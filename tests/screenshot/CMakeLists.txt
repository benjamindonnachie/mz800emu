# tests/screenshot/CMakeLists.txt
# Standalone test čistého jádra screenshotu (oblast, měřítko, ořez) pro
# geometrie všech platforem, bez emu core.

mz_add_test(screenshot
    TYPE     STANDALONE
    SOURCES  test_screenshot.c ${CMAKE_SOURCE_DIR}/src/emulator/screenshot/screenshot.c
    LIBS     mz::glib
    LABELS   "standalone;screenshot"
)
