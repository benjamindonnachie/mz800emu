# MZ-700 expansion boot ROM

HW & Devices > Boot ROM selects a separately supplied expansion ROM:

- Disabled: use the base ROM configuration without this additional ROM.
- F000: wait for the stock monitor. Enter F and Return to boot.
- E800: the stock monitor automatically chains into the ROM at startup.

Choose the appropriate ROM image in the same menu, select its mode, then reset.
Images are address-specific: F000 requires4096bytes, E800 requires2048bytes,
and both must start with00h. An image assembled forF000 cannot simply be moved
toE800. The menu rejects invalid images. Configuration loading reports invalid
images and leaves the additional ROM absent. Changing modes reloads the base
ROM before installing the selected image, removing the previous overlay.
The base ROM should contain the normal monitor/font and no conflicting ROM.

INI settings in [ROM]:

```ini
boot_rom_mode = F000
boot_rom_f000_filepath = /path/to/f000.bin
boot_rom_e800_filepath = /path/to/e800.bin
```

DISABLED is the general emulator default. The CP/M development launcher selects
F000. The setting and filenames use the emulator's normal configuration storage.
The low monitor and character ROM remain unchanged. All transitions are ordinary
Z80 instructions executed by the original monitor, with no injected jump/reset.

This is separate from KC-Club GIDE. GIDE supplies disk access and contains no
boot ROM. On a physical Sharp, separate ROM hardware and address decoding must
supply the selected ROM and respect standard upper-memory bank switching.
No physical hardware validation has been performed.

The source-built CP/M examples are provided by cpm/suc-native/media.py in the
parent workspace. They copy the boot stage toRAM8000h before mapping all RAM.
The automatic convention is documented in Sharp's MZ-1E14 Service Manual,
section2-2 (printedpage2): https://www.idealine.info/sharpmz/mz-700/download/mz1e14_sm_gb.pdf .
