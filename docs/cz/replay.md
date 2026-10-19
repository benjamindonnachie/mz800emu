# Záznam a přehrání vstupů (Replay)

Vstupy jednoho běhu se jednou nahrají a pak přesně přehrají - ve stejném
nebo v novém procesu emulátoru, při libovolné rychlosti. Typické použití:

- hraji hru nebo program, dokud se neobjeví chyba, a pak přesně stejný
  běh opakuji, kolikrát potřebuji, s jinými breakpointy, trace nebo
  záznamem zápisů do paměti;
- nahraný běh slouží jako regresní test: `--replay-verify` v CI ověří,
  že ho nový build pořád odehraje stejně.

Všechny platformy (MZ-800, MZ-700 PAL i NTSC, MZ-1500). Záznam jde
přehrát jen v binárce téže platformy a TV normy.

## Jak to funguje

Záznam začíná kompletním snapshotem stroje (vždy s RAMdiskem, bez ohledu
na nastavení snapshotů), který se při startu uloží a hned znovu načte.
Od té chvíle ukládá po emulovaných snímcích:

- každou změnu klávesnice (celou klávesnicovou matici: klávesnice
  počítače, okno virtuální klávesnice i klávesy z MCP dohromady),
  joysticku z numerické klávesnice a joysticku z MCP,
- resety a autotype,
- zápisy debuggeru a nástrojů MCP (paměť, regiony paměti, registry,
  příznaky CPU, porty I/O, vyvolané IRQ a NMI),
- každých N snímků (výchozí 50, na PAL jedna sekunda) SHA-256 CPU
  (registry včetně skrytého stavu Z80), RAM, RAM MemExt, VRAM a PCG
  spolu s emulovaným časem.

Všechny vstupy se přebírají na hranici snímku: klávesa stisknutá uprostřed
snímku se do emulovaného počítače dostane na jeho konci, při záznamu
i při přehrávání. Přehrávání načte startovní snapshot, na stejných místech
použije vstupy a porovnává hashe. První snímek, jehož stav se liší,
přehrávání zastaví.

## Záznam

| Způsob | Jak |
|--------|-----|
| Menu | **Replay -> Record Inputs...** se zeptá na soubor (`.mzr`) a začne. **Replay -> Stop Replay** ho uloží. |
| Příkazová řádka | `--replay-record <soubor>` nahrává od prvního snímku; soubor se zapíše při ukončení emulátoru. `--replay-hash-interval <N>` nastaví počet snímků mezi hashi (1-100000). |
| MCP | `emu_replay_record_start`, `emu_replay_record_stop`, `emu_replay_status` (viz [`mcp-server/tools-overview.md`](mcp-server/tools-overview.md)). |

Když emulace běží, pozastaví se na nejbližší hranici snímku, záznam začne
a emulace běží dál. Během záznamu je v levém dolním rohu obrazu
**REPLAY REC** a číslo snímku.

Během záznamu:

- **Nastavení stroje** (menu Devices, platforma, periferie, rozšíření
  paměti, ROM), **načtení snapshotu** a **ovládání kazety** (okna Virtual
  CMT a Tape Filelist) nejsou k dispozici: záznam by je nezopakoval. Přes
  MCP se nástroje, které stroj takto mění (načtení snapshotu, média,
  ovládání kazety, nastavení), odmítnou s vysvětlením.
- **Zápisy debuggeru** se zaznamenají, když emulace běží, a v pauze na
  hranici snímku - po pauze (tlačítko pauzy i MCP `emu_pause` pozastaví
  na konci snímku), po `emu_run(frames=N)` nebo po deadlinu. V pauze mezi
  hranicemi snímků (po kroku nebo breakpointu) se zápis odmítne: nejdřív
  doběhnout na další hranici snímku.
- **Akce breakpointů**, které zapisují (`poke`, `set`), se nezaznamenají;
  záznam dostane varování a správně se přehraje jen se stejnými
  breakpointy.
- Záznam nezačne, dokud běží autotype nebo jsou aktivní Freeze Bytes.

## Přehrání

| Způsob | Jak |
|--------|-----|
| Menu | **Replay -> Play Replay...** se zeptá na soubor, načte startovní snapshot a rozběhne emulaci. **Replay -> Stop Replay** přehrávání ukončí. |
| Příkazová řádka | `--replay <soubor>` přehraje záznam po startu. `--exit-at-replay-end` ukončí běh na konci přehrávání, `--replay-verify` totéž v MAX SPEED (viz níže). |
| MCP | `emu_replay_play` (`pause_after_load` pro nastavení breakpointů před rozběhem), `emu_replay_play_stop`, `emu_replay_status`; konec je pauza s důvodem `replay_end` nebo `replay_desync` (`emu_wait_stop`). |

Při přehrávání je v obraze **REPLAY PLAY** se snímkem a délkou záznamu.
Živý vstup (klávesnice, virtuální klávesnice, klávesy z MCP) se
ignoruje. Breakpointy, trace, záznam zápisů do paměti, screenshoty
i nahrávání videa fungují jako obvykle; pauza a krokování výsledek
nemění.

Na konci se emulace pozastaví a oznámení ukáže výsledek:

| Výsledek | Význam |
|----------|--------|
| ended | záznam se přehrál do konce, všechny hashe souhlasily |
| differs at frame N | stav se od záznamu liší; oznámení vyjmenuje části (`cpu`, `ram`, `memext`, `vram`, `pcg`, `time`) |
| deviated | během přehrávání něco zapsalo do stroje (zápis debuggeru, akce breakpointu `poke` / `set`, Freeze Bytes, reset); přehrávání doběhlo do konce, ale hashe se od té chvíle neověřovaly |

Rozdíl znamená, že se emulovaný počítač nechová jako při záznamu: jiná
verze nebo nastavení emulátoru, obraz disku změněný od záznamu, nebo vstup,
který se nezaznamenává (viz níže).

## Ověření záznamu v CI

```
mz800emu --headless --replay run.mzr --replay-verify --result-json result.json
```

`--replay-verify` přehraje záznam v MAX SPEED a na jeho konci ukončí
proces: návratový kód 0, když všechny hashe souhlasily (`reason:
"replay_end"`), 4 při rozdílném stavu (`replay_desync`,
`replay.outcome_frame` a `replay.desync_parts` v `result.json`), 3 když
záznam nejde spustit (nečitelný soubor, jiná platforma nebo TV norma).
Viz [`mcp-server/headless-mode.md`](mcp-server/headless-mode.md).

Pozor: oprava emulátoru, která změní časování, výsledek legitimně změní -
rozdíl na novém buildu znamená "chování se změnilo", ne nutně chybu.

## Co se nezaznamenává

| Vstup | Co dělat |
|-------|----------|
| joystick hostitele (typ joysticku JOYSTICK) | použít joystick z numerické klávesnice nebo MCP; záznam dostane varování |
| obsah obrazů disket, Quick Disku a IDE8 | obrazy mezi záznamem a přehráním neměnit (program, který zapisuje na disk, obraz změní) |
| tlačítka kazety (play, stop, record) | během záznamu a přehrávání nejsou k dispozici (okna Virtual CMT a Tape Filelist jsou zakázaná, MCP je odmítne); kazetu spustit před záznamem |
| hodiny a adresář SD karty Unicardu | hodnoty jdou z hostitele |
| nastavení emulátoru mimo snapshot (INI) | přehrávat se stejným nastavením |

## Soubor záznamu

Soubor `.mzr` je ZIP archiv:

| Soubor | Obsah |
|--------|-------|
| `manifest.json` | formát, verze, platforma, délka snímku TV normy (`screen_ticks`), délka záznamu, interval hashů, varování |
| `start.mzs` | startovní snapshot |
| `inputs.jsonl` | jedna událost na řádek: snímek `f`, poloha `at` (`b` hranice snímku, `d` zápis debuggeru za běhu, `p` pauza na hranici snímku), druh `k` (`kbd`, `joy`, `autotype`, `reset`, `dbg`) a jeho data; poslední řádek je `end` |
| `hashes.csv` | `frame,ticks,cpu,ram,memext,vram,pcg` |

`inputs.jsonl` je text: událost jde odebrat nebo posunout a zjistit, co
klávesa změnila. Hashe pak ukážou, kde se běh liší.
