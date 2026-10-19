# Záznam a přehrání vstupů (replay).

# Formát .mzr: inputs.jsonl, hashes.csv, manifest a zápis/čtení souboru.
mz_add_test(replay-format
    TYPE     EMU
    SOURCES  test_replay_format.c
    LABELS   "emu;replay"
)

# Cesta vstupů záznamu bez GUI: čekající matice, reset na hranici snímku,
# zahození živého vstupu při přehrávání, přehrání bez rozjetí.
mz_add_test(replay-input
    TYPE     EMU
    SOURCES  test_replay_input.c
    LABELS   "emu;replay"
)
