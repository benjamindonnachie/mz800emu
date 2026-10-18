# MZ-700 SUC 40/80-column display

The optional John Edwards / Sharp Users Club expansion is available in
the dedicated MZ-700 build. An alternative K&P I/O protocol uses this same
SUC display and video RAM; it does not install a second video card.

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

## Alternative K&P interface

Enable the expansion, then select **HW & Devices > SUC display interface >
K&P I/O interface** before starting K&P software. Select **SUC memory
interface** for the existing SUC CP/M boot media. Interface changes retain
VRAM but reset the CRTC registers and return to 40 columns. The selected
interface is saved in configuration; normal reset retains that selection.

```ini
[VIDEO_MZ700]
suc80_enabled = 1
suc80_kp_interface = 1
```

The default is 0 (SUC). The expansion must be enabled separately.
The K&P ports are unclaimed when that interface or the expansion is off.
Only the low I/O address byte is decoded, so Z80 OUT(C),r/OTIR and immediate
OUT instructions may use arbitrary high bytes.

| Port | Read | Write |
| --- | --- | --- |
|70h|Raw byte at current VRAM address; no increment|Ignored|
|71h|FFh|Write raw character, then increment 14-bit address|
|72h|Status: bit 7 ready; bit 5 follows SUC vertical blanking|Select register 0–31|
|73h|Selected register value|Write selected register|

R18/R19 hold the staged transparent address; selectingR31 latches that
pair as the live VRAM address. Sequential writes update both the live
address andR18/R19. Reads do not increment. Stage a new pair and selectR31
for a different read address. R12/R13 set the display start for circular
scrolling. R14/R15 set the cursor address; R10/R11 select its shape and
steady, disabled, 16-frame or 32-frame blinking mode. R16/R17 light-pen
registers are read-only zero; no light-pen device is attached. Registers
outside 0–19 return zero and ignore data writes. R1=80 enables 80 columns;
other geometries and CRTC sync timings are not simulated.

This is an interface adaptation for SUC's 80×25/640×200 display, rather
than emulation of a separate SY6845E card's 640×250 raster. Cursor scanlines
are scaled into the existing 8-line SUC character cell. Transfers complete
synchronously: software can poll bit 7, but precise transparent-access or
blanking delays are not reproduced. SUC's E00C–E00F mode latch still works.

There is no second character buffer. All2048 logical addresses map bijectively
to the original character RAM using:

```c
odd = address & 1;
offset = (((address >> 1) + odd) & 0x3ff) | (odd << 10);
```

Thus addresses 0,1,2,3 use D000,D401,D001,D402. Address 2047 uses the otherwise
unused D400 byte, never D800 attribute RAM. R12/R13 scrolling wraps modulo 2048.
CPU banking does not restrict these I/O writes; hidden main RAM is untouched.
Each K&P data write puts the original 8-bit byte directly into shared VRAM
and sets its SUC attribute to 70h (white on black). Port 70 reads it unchanged,
including bit 7. Direct memory writes and port reads see the same storage.
Native memory writes can subsequently edit the associated colours.

K&P uses ASCII-like character codes; the renderer maps printable ASCII
onto the existing European Sharp font in this interface. Glyph selection
ignores bit 7. Upper/lower-case letters, digits and ordinary punctuation are
supported. K&P-specific control-code graphics, German substitutions and its
original 10-row character ROM are not reproduced exactly. This restriction
concerns glyph appearance, not the stored bytes or port readback. Select
SUC memory interface for software writing native Sharp display codes.

Snapshots preserve the selected interface, all registers, staged/live
addresses and the shared VRAM. Snapshots predating this interface restore
SUC mode with cleared K&P state. Reset clears the registers/live address
and selects 40 columns; the guest's normal CRTC initialisation selects 80.

The native test `mcp_kp80_suc` checks full VRAM mapping, raw readback, banking,
address staging/wrap, pixel-exact shared scanout and circular scrolling,
cursor steady/off/blink, snapshots and reset. The project's preserved BKK
MZF demo is also executed unmodified when that reference is present.
Existing `mcp_suc80_display`, `mcp_gide` and `gide_core` remain regressions.

Programming references: Bernd Krueger-Knauber's [K&P interface description
and original source library](https://idealine.info/sharpmz/mz-700/80zkup.htm).
Use the 72h status port shown in its code examples: one explanatory sentence
on that page incorrectly refers to 70h as the status port. The linked CAST
PDF describes a C6845-compatible core and does not specify the K&P extended
R18/R19/R31 protocol; the author's interface description/library establish
those accesses. Source documents and hashes are retained in sources/kp80
in the project preservation workspace.
