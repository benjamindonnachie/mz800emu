mz_add_test(ctc8253
    TYPE     EMU
    SOURCES  test_ctc8253.c
    LABELS   "emu;peripherals"
)

mz_add_test(pio8255
    TYPE     EMU
    SOURCES  test_pio8255.c
    LABELS   "emu;peripherals"
)

mz_add_test(psg
    TYPE     EMU
    SOURCES  test_psg.c
    LABELS   "emu;peripherals"
)

mz_add_test(unicard
    TYPE     EMU
    SOURCES  test_unicard.c
    LABELS   "emu;peripherals"
)

mz_add_test(wd279x
    TYPE     EMU
    SOURCES  test_wd279x.c
    LABELS   "emu;peripherals"
)

mz_add_test(gdg_mirror
    TYPE     EMU
    SOURCES  test_gdg_mirror.c
    LABELS   "emu;peripherals"
)

# HW scroll MZ-800: zápis registru uprostřed řádku nesmí přemapovat pixely,
# které paprsek už vykreslil; ladicí settery v jednotkách portu.
mz_add_test(hwscroll
    TYPE     EMU
    SOURCES  test_hwscroll.c
    LABELS   "emu;peripherals"
)

# Bootstrap --run-mzf (MZ-800 mód) nastavuje DMD cestou OUT CEh
# (GATE0 CTC0, latch MZ-700), ne přímým zápisem g_gdg.regDMD.
mz_add_test(mz800_bootstrap_dmd
    TYPE     EMU
    SOURCES  test_mz800_bootstrap_dmd.c
    LABELS   "emu;peripherals"
)

mz_add_test(printer
    TYPE     EMU
    SOURCES  test_printer.c
    LABELS   "emu;peripherals"
)

mz_add_test(mz1p16_emu
    TYPE     EMU
    SOURCES  test_mz1p16_emu.c
    LABELS   "emu;peripherals;mz1p16"
)

# Stav transportu CMT: invariant "bez pásky STOP", snapshot bez pásky,
# eject/stop bez pásky a přehrání nové pásky od začátku.
mz_add_test(cmt_state
    TYPE     EMU
    SOURCES  test_cmt_state.c
    LABELS   "emu;peripherals;cmt"
)

# Vlastní délky pulzů Virtual CMT a hlavičky CMTSPEED zařízení UniCMT v MZT.
mz_add_test(cmt_unicmt
    TYPE     EMU
    SOURCES  test_cmt_unicmt.c
    LABELS   "emu;peripherals;cmt"
)

# Portable GIDE core: no emulator/SDL stubs required.
add_executable(test_gide_core test_gide_core.c
    ${CMAKE_SOURCE_DIR}/src/emulator/hw-generic/gide/gide_core.c)
target_include_directories(test_gide_core PRIVATE ${CMAKE_SOURCE_DIR}/src/emulator)
# These are executable contracts, including in Release/RelWithDebInfo builds.
target_compile_options(test_gide_core PRIVATE -UNDEBUG)
add_test(NAME gide_core COMMAND test_gide_core)
set_tests_properties(gide_core PROPERTIES LABELS "peripherals;gide" TIMEOUT 30)
