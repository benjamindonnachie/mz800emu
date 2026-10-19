# MZ-700 ZP/M development release 0.1.0

This is an experimental Apple Silicon build for **macOS 27 or later**.
It includes the built PAL MZ-700 emulator, its non-system runtime libraries,
SUC 80-column support, PEHU RAM banking, GIDE/RTC, separate boot ROMs and two
populated virtual GIDE hard drives. Intel Macs are not supported by this binary.
No Homebrew or Python installation is required to run the app.

## Start ZP/M

1. Download and extract `MZ700-ZPM3-v0.1.0-macOS27-arm64.zip`.
2. Move `MZ-700 ZPM3.app` to Applications, or another writable local folder.
3. Open the app. This is an ad-hoc signed development build, not notarised by
   Apple. If macOS blocks it, use **System Settings > Privacy & Security >
   Open Anyway** for this app, then confirm opening it.
4. At the Sharp monitor, press **F**, then **Return**. The normal Sharp monitor
   is retained so other software can still be loaded before booting ZP/M.
5. At the `C0>` prompt, type `APPS` and press Return for the software index.

See [Apple’s instructions for opening an unidentified app](https://support.apple.com/en-gb/102445)
if macOS requests approval.

ZP/M N10 and ZCCP run in SUC 80 × 25 mode with **60,672 bytes of application
space**. The boot loader retains the familiar `60K TPA` display, which is rounded.

Try:

```text
TPA
DATE
RTC
DIR [FULL]
D4:
MBASIC
PRINT 6*7
SYSTEM
C0:
```

`RTC` displays the GIDE RTC; `DATE` exercises CP/M date/time support. The clock
starts from host local time when the emulator process starts. The original
SUC keyboard macros and ALPHA/GRAPH modes are retained. The display uses
bank-switched SUC VRAM, without the retired K&P I/O adapter.

## Software

| User area | Selected software |
| --- | --- |
| C0: | System tools, DATE/RTC, PIP, directory and TPA utilities |
| D0: | WordStar 3.30 |
| D1: | dBASE II 2.41 |
| D2: | Hi-Tech C 3.09 |
| D3: | Microsoft Multiplan 1.06, configured for VT52 |
| D4: | Microsoft BASIC 5.21 and BASCOM 5.30a |
| D5: | Turbo Pascal 3.00A |
| D6: | Games, including Zork, Adventure, Ladder and others |

The app's `Contents/Resources/system/APPLICATIONS.txt` provides command notes.
The current Sharp-software image and the earlier factory image are both
included. Some retained example/test/user files remain in the working snapshot.
Not every included game has been tested through completion.

## Working disks and restarting

On first launch the app copies the Sharp-software image into:

```text
~/Library/Application Support/MZ700-ZPM3/sharp-applications/gide.img
```

That working copy retains changes between sessions. The preserved image inside
the app is unchanged. Quit the emulator before copying, replacing or backing
up a working disk. Avoid opening one working disk in multiple processes.
The launcher regenerates its hardware/ROM configuration on each launch.
To start again, quit the emulator and rename the `sharp-applications` directory;
the next launch creates a fresh working copy.

Advanced options can be passed from Terminal:

```sh
"/Applications/MZ-700 ZPM3.app/Contents/MacOS/MZ700-ZPM3" --automatic
"/Applications/MZ-700 ZPM3.app/Contents/MacOS/MZ700-ZPM3" --read-only
"/Applications/MZ-700 ZPM3.app/Contents/MacOS/MZ700-ZPM3" --factory
```

`--automatic` selects the E800 boot ROM. The default F000 ROM waits for F and
Return. `--factory` uses a separate factory working directory. `--work-dir`
selects another working directory, and `--prepare-only` creates its initial
copy/configuration without starting the emulator.

## ROMs and media for another emulator build

`MZ700-ZPM3-v0.1.0-GIDE-media.zip` contains the same two raw ATA images, ROMs,
checksums and software notes. Each disk contains C: and D: 8 MiB volumes plus
the boot-loader tail. Keep the entire image, including its tail.

Enable GIDE at base A0h, PEHU RAM expansion and SUC 80-column expansion. Use
`stock-monitor-font.bin` as the all-in-one base ROM, select the separate
`boot-f000.bin` expansion ROM at F000h and attach either GIDE image as master.
For automatic boot use `boot-e800.bin` at E800h. The two boot ROMs are assembled
for their respective addresses and are not interchangeable. GIDE itself does
not supply ROM; real hardware needs a separate boot ROM and memory expansion.

## Verification and source

`SHA256SUMS.txt` checks the downloadable assets. `RELEASE-MANIFEST.json` records
the source commit, binary architecture, minimum OS, bundled library origins,
licence/source references and preserved media hashes. Checksums establish
integrity, not Apple notarisation.

The tagged GitHub source archive contains the emulator and launcher source,
current BIOS, original pinned reconstruction packs, licence notices and test
evidence. See `systems/mz700-zpm3/README.md` for the BIOS/media rebuild commands,
and `packaging/macos-zpm3/build_release.py` for the app packaging process.
Video recording through an external FFmpeg executable is not included.

The emulator and new BIOS modules retain their GPL terms. Third-party CP/M,
ZP/M, ZCCP, Sharp ROMs and applications retain their original notices and
restrictions. These are preserved with the software; the project does not
claim that age has extinguished copyright. This build is tested in emulation,
not on a physical Sharp.

Thanks to the Sharp Users Club, Maurice Hawes, John Edwards, Peroutka and Hučík,
and to Michal Hučík for the original emulator. Codex (OpenAI) is credited as
co-author of this fork's MZ-700 extensions, BIOS and supporting tools.
