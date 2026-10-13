# Screenshots

PNG pictures of the emulator screen on all platforms (MZ-800, MZ-700 PAL
and NTSC, MZ-1500). Menu **Tools -> Screenshot**:

| Item | Key | What it does |
|------|-----|--------------|
| Save Screenshot | `Alt + F` | Saves a PNG of the picture shown in the window into the output folder, named `<platform>_YYYYMMDD_HHMMSS.png` (e.g. `mz800_20261013_183005.png`). A notification shows the size and the path. |
| Save Screenshot As... | | The same, but asks for the file name. |
| Settings... | | Area, scale and output folder (see below). |
| Open Output Folder | | Opens the output folder in the file manager. |

The screenshot is exactly the picture the window shows at that moment.

## Settings

Menu **Tools -> Screenshot -> Settings...**, saved in the configuration
(section `[SCREENSHOT]`):

| Setting | Values | INI key |
|---------|--------|---------|
| Area | Whole frame with border / Picture without border | `area` = `full` / `canvas` |
| Scale | Native / 1x / 2x / 3x / 4x | `scale` = `native` / `1` .. `4` (default `2`) |
| Output folder | empty = the `screenshots` folder next to the emulator | `output_dir` |

- **Native** - one image pixel per dot of the computer: the MZ-800 picture
  is 320x200 (640x200 in the 640-dot modes), the whole frame with the
  border 464x288 (928x288). Good for comparing with graphics data.
- **1x to 4x** - the aspect ratio of the emulator window; **2x** is the
  window at 100 % (MZ-800 whole frame 928x576, picture 640x400). 1x drops
  every second column in the 640-dot modes.

The dialog shows the resulting image size.

## MCP

AI clients save screenshots with `emu_screenshot_save_to_file` (same
area and scale, plus a crop), see
[mcp-server/headless-mode.md](mcp-server/headless-mode.md) and the MCP
document `emulator://docs/screenshot_workflow`.
