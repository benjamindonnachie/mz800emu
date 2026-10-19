# MZ-700 SUC 40/80-column display

The optional John Edwards / Sharp Users Club expansion is available in
the dedicated MZ-700 build. Software accesses the display through the
original memory-mapped SUC interface.

Enable **HW & Devices > SUC 80-column expansion**, or use:

```ini
[VIDEO_MZ700]
suc80_enabled = 1
```

The expansion is disabled by default. Installation is persistent; the
display mode is a hardware latch that resets to 40 columns. The loaded
programme selects 80 columns. Enabling the menu item alone does not
change the programme's screen layout.

## Programming interface

With the upper memory-mapped peripherals enabled, a memory write to any
address E00C–E00F latches data bit 4. Clear selects 40 columns; set selects
80. The documented convenience values are 28h and 50h. Reads do not
change the latch. When E1h maps the upper region as ordinary RAM, writes
to those addresses update RAM and do not change the display mode.

The 80-column screen is 80 by 25 characters. Logical character positions
alternate between the existing character RAM banks:

| Character | Character address | Attribute address |
| --- | --- | --- |
| First | D000h | D800h |
| Second | D401h | DC01h |
| Third | D001h | D801h |
| Fourth | D402h | DC02h |
| Last (row 25, column 80) | D7E8h | DFE8h |

The second bank starts one byte beyond D400h, unlike the older Xtal
MZ-80K layout. Both foreground/background colours and the attribute's
character-ROM bank selector apply independently to every character.
The existing 640-dot framebuffer canvas holds eight pixels per
80-column character, or doubled pixels for 40-column characters.

Snapshots preserve the fitted expansion and its mode latch. Old snapshots
without the new latch default to 40-column rendering. The debugger exposes
both complete 2 KB physical video RAM banks, including their upper halves.

## Validation and scope

`CPM7004.dsk` (also distributed as `CPM SUC MZ700.dsk`, SHA-256
`eceb88f75a8c70e3e4265d77474f79cf2ec79105d1294720b4ed6afd9aedf510`)
boots with an MZ-1E05 ROM and selects the expansion automatically. Its
banner identifies `SHARP MZ-700 80-col P-CP/M`.

The pipe integration test `mcp_suc80_display` checks the actual rendered
pixels against the font and test video RAM, all four mode addresses,
data-bit selection, absence of the expansion, RAM banking, reset and
snapshot compatibility. It runs the native PAL binary without a display
server, external ROM or disk image:

```sh
cmake --build build-mac --target mz700emu-pal
ctest --test-dir build-mac --output-on-failure -R '^mcp_suc80_display$'
```

This implements the documented register range and logical display
behaviour. It does not simulate the analogue clock doubler, propagation
delays, serializer glitches or exact pixel-level effects of a mode change
within a scanline. Existing MZ-700 raster/VRAM arbitration remains in use.
No claim is made about additional motherboard address aliases or PCG
expansion compatibility.

The hardware reference is John Edwards' *MZ-700 80 Column Kit*, reprinted
in the Sharp Users Club magazine, May 2015, printed pages 13–19 (PDF pages
15–21). The layout and mode programming are on printed pages 13–14;
the D4 latch and shared RAM-address selection are in the circuit on
printed page 18. The project preservation collection retains that PDF.

## Retired experimental interface

The experimental K&P I/O adapter and the **SUC display interface** submenu
have been removed. Ports 70h–73h are no longer claimed by a display device.
The old `suc80_kp_interface` configuration key and K&P snapshot fields are
ignored; SUC mode and video RAM remain supported. Historical K&P snapshots
retain their stored bytes but no longer reproduce K&P rendering or cursor
registers. The preserved K&P reference documents remain in `sources/kp80`.
