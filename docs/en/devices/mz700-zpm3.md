# MZ-700 GIDE and banked ZP/M development

This fork adds an MZ-700 development environment using the existing PEHU
memory expansion, SUC 80-column display, KC-Club GIDE ATA interface and
RTC72421 clock. The current system uses banked ZP/M 3 N10 and ZCCP. The
application TPA is 60,672 bytes, 0100h–EDFFh. This is emulator validation;
the BIOS has not been tested on physical hardware.

## Source and hardware

The current BIOS, bootstrap, RTC utility and native tests are in
[`cpm/zpm3-pehu-keyboard-fast`](../../../cpm/zpm3-pehu-keyboard-fast).
Original project files are preserved without changing their build logic.
Native 512-byte ATA sectors are buffered by CP/M 3/ZP/M, with LBA28
addressing in the BIOS. The BIOS does not perform 128-byte deblocking.
System bank 0 and application bank 1 use PEHU windows 2000h–BFFFh; low
8 KiB and upper 16 KiB are common. SUC VRAM and keyboard access temporarily
map the Sharp upper peripherals with interrupts masked. This retains the
original SUC keyboard macros and ALPHA/GRAPH behaviour.

Enable SUC 80-column expansion, PEHU and GIDE in the emulator. Use a stock
Sharp monitor/font base ROM and a separate 4 KiB expansion boot ROM at
F000h. At the monitor, press **F**, then **Return**. The optional 2 KiB E800h
ROM supports automatic startup. GIDE itself provides no ROM. The former
K&P I/O display adapter has been removed; the BIOS uses bank-switched VRAM.
See [GIDE](gide.md), [SUC](suc80.md) and [boot ROM](boot-rom.md).

## Third-party inputs and media

See the [ready-to-run images and launcher](../../../systems/mz700-zpm3/README.md).

The emulator GPL licence does not relicense CP/M, ZP/M, ZCCP, Sharp ROMs,
the preserved original SUC keyboard bytes or bundled applications. Those
retain their original notices and terms. Third-party binary inputs,
populated hard-drive images and the reconstructed SUC byte listing are
preserved under `systems/mz700-zpm3`, including the full reconstruction packs. The BIOS source headers
identify our GPL-3.0-or-later modules; this does not extend to original
third-party content.

The checked-in support pack preserves the original inputs, their hashes,
original terms, source/media/evidence ZIPs, ready-to-boot images and portable
launch instructions. It includes both the earlier factory software image
and the current Sharp archive application image. Use a copy of a pristine
image for each writable session; do not modify the preservation copy.

## Build and reproduce

Build the host emulator using the upstream build instructions. On the tested
macOS environment, with the required SDL/GLib/OpenGL dependencies installed:

```sh
cmake -S . -B build-mac -DCMAKE_BUILD_TYPE=RelWithDebInfo -DMZ_NO_MCP_TCP=ON
cmake --build build-mac --target mz700emu-pal test_gide_core test_gide_rtc -j4
ctest --test-dir build-mac --output-on-failure \
  -R '^(gide_core|gide_rtc|mcp_gide|mcp_suc80_display)$'
```

For a complete BIOS rebuild, extract the preserved Keyboard Fast source
ZIP into a separate directory and run its README commands. Its pinned
inputs include RMAC, LINK, GENCPM, original N10 SPRs, ZCCP, the SUC reference
system, pyz80 and ZXCC source. The preserved source-only rebuild produced
22 byte-identical outputs. Tests in this fork retain their original workspace
paths; use the support pack's reconstructed workspace for those tests.
Run `build.py` then `media.py` to reproduce factory media. `prepare.py`
migrates an interactive working image and must not be run against an active
emulator. The Sharp applications overlay is a separate reproducible pack.

## Validation

The current system retains the earlier 14 system and 6 application suite
results in `VALIDATION.json`, with measured keyboard/disk/display comparisons
in `PERFORMANCE.json`. The subsequent Sharp application replacement has its
own eight-group evidence in the support pack. After removing the K&P
adapter, PAL MZ-700, MZ-800 and MZ-1500 builds passed, together with native
SUC pixels/banking/reset/snapshots, legacy configuration/snapshot handling,
current-image boot, 229 terminal contracts and 28 original keyboard cases.
The source and media are experimental; individual bundled games have not
all been tested through completion.
