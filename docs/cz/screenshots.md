# Screenshoty

PNG obrázky obrazovky emulátoru na všech platformách (MZ-800, MZ-700 PAL
a NTSC, MZ-1500). Menu **Tools -> Screenshot**:

| Položka | Klávesa | Co dělá |
|---------|---------|---------|
| Save Screenshot | `Alt + F` | Uloží PNG obrazu zobrazeného v okně do výstupní složky se jménem `<platforma>_RRRRMMDD_HHMMSS.png` (např. `mz800_20261013_183005.png`). Notifikace ukáže rozměr a cestu. |
| Save Screenshot As... | | Totéž, ale zeptá se na jméno souboru. |
| Settings... | | Oblast, měřítko a výstupní složka (viz níže). |
| Open Output Folder | | Otevře výstupní složku ve správci souborů. |

Screenshot je přesně ten obraz, který okno v tu chvíli zobrazuje.

## Nastavení

Menu **Tools -> Screenshot -> Settings...**, ukládá se do konfigurace
(sekce `[SCREENSHOT]`):

| Nastavení | Hodnoty | Klíč v INI |
|-----------|---------|------------|
| Oblast | Celý obraz s borderem / Obraz bez borderu | `area` = `full` / `canvas` |
| Měřítko | Nativní / 1x / 2x / 3x / 4x | `scale` = `native` / `1` .. `4` (výchozí `2`) |
| Výstupní složka | prázdná = složka `screenshots` vedle emulátoru | `output_dir` |

- **Nativní** - jeden pixel obrázku na bod počítače: obraz MZ-800 má
  320x200 (v režimech 640 bodů 640x200), celý obraz s borderem 464x288
  (928x288). Hodí se pro porovnání s grafickými daty.
- **1x až 4x** - poměr stran jako v okně emulátoru; **2x** odpovídá oknu
  na 100 % (MZ-800 celý obraz 928x576, obraz bez borderu 640x400). 1x
  v režimech 640 bodů vynechá každý druhý sloupec.

Dialog ukazuje výsledný rozměr obrázku.

## MCP

AI klienti ukládají screenshoty nástrojem `emu_screenshot_save_to_file`
(stejná oblast a měřítko, navíc ořez), viz
[mcp-server/headless-mode.md](mcp-server/headless-mode.md) a MCP dokument
`emulator://docs/screenshot_workflow`.
