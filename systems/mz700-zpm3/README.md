# MZ-700 banked ZP/M with GIDE

Two complete raw ATA images are provided. Each contains two 8 MiB CP/M
volumes, C: and D:, followed by the GIDE boot loader. Native physical sectors
are 512 bytes. Both use the same Keyboard Fast BIOS, banked ZP/M N10 and ZCCP,
with a 60,672-byte application TPA.

| Image | Contents |
| --- | --- |
| `images/sharp-applications.img` | Current working snapshot: Sharp archive WordStar 3.30, dBASE II, Hi-Tech C, Multiplan, Microsoft BASIC/BASCOM, Turbo Pascal, games and CP/M utilities. Includes retained example/test/user files from the development image. |
| `images/keyboard-fast-factory.img` | Preserved earlier factory image and application selection, useful as a baseline. |

`APPLICATIONS.txt` describes the current user areas and commands. The media
manifest records exact hashes and source paths; it does not imply new
licensing permissions. The files are provided as an experimental preservation
and development collection. Original third-party notices and restrictions
remain applicable. The emulator and new GPL BIOS modules do not relicense
those components. See `notices/` and the original documents in the source ZIPs.
In particular, the included ZCCP notice restricts commercial/institutional use;
the original ZP/M notice restricts commercial use and package redistribution.
No general claim that copyrights have expired or been relinquished is made.

## Run

Build `mz700emu-pal` from this fork, then from the repository root:

```sh
python3 systems/mz700-zpm3/launch.py
```

At the Sharp monitor press **F**, then **Return**. Use `APPS` at `C0>` for the
application index. `D0:`, `D1:`, etc. select application user areas; `C0:`
returns to the system tools. `DATE` and `RTC` exercise the emulated GIDE clock.

The launcher verifies the selected preservation image and ROM checksums, then
creates a writable working copy under `.local/mz700-zpm3/`. Later launches
retain that copy. The checked-in images remain pristine. Close the emulator
before deleting a working directory to start again. Avoid opening the same
working image in multiple emulator processes.

```sh
python3 systems/mz700-zpm3/launch.py --image keyboard-fast-factory
python3 systems/mz700-zpm3/launch.py --automatic
python3 systems/mz700-zpm3/launch.py --read-only
python3 systems/mz700-zpm3/launch.py --emulator /path/to/mz700emu-pal
```

F000 is the default manual boot; E800 is optional automatic boot. The stock
monitor/font file leaves low ROM intact. The boot ROM is a separate expansion,
not part of the GIDE card. The MZF boot stage is preserved for investigation.

## Rebuild the BIOS and images

`preservation/*-source.zip` contains the exact standalone reconstruction inputs,
original notices and build scripts. Extract the Keyboard Fast source ZIP into
a separate directory. From that directory:

```sh
python3 cpm/zpm3-pehu-keyboard-fast/build.py
python3 cpm/zpm3-pehu-keyboard-fast/media.py
```

A C compiler, make, Python 3 and the normal ZXCC build dependencies are needed.
The builder can compile its archived ZXCC source automatically; pyz80 and the
CP/M build tools are pinned in the pack. `*-clean-rebuild.json` records the
22-output source-only byte-identity proof. This rebuild produces the factory
image; it does not recreate subsequent changes to the current working image.

Extract the Sharp applications source ZIP into another separate directory and
run `python3 cpm/zpm3-pehu-sharp-apps/build.py` there to reproduce its factory
overlay image and 178 payloads. Preserve the configured overlay files supplied
in that pack. `APPLICATION-PROVENANCE.json` records individual payload origins.
The exact current working snapshot is `images/sharp-applications.img`, covered
by `manifest.json`.

`*-evidence.zip` retains the original native tests, screenshots and benchmark
results. `validation/emulator-update.json` records the subsequent K&P removal
regressions. Build the emulator locally; host macOS dependencies are not bundled.
This system has not been validated on physical MZ-700 hardware.
