# HAL Laboratory PCG-700

The MZ-700 PAL and NTSC executables support an optional PCG-700. Select
**HW & Devices > HAL PCG-700 > Card fitted**. The **HSW: PCG display** switch
selects PCG output or the original character generator. Software control
uses the board's SSW-enabled configuration. The expansion is absent by
default; it works with both the native 40-column display and SUC 80 columns.
The MZ-1500's built-in PCG and the MZ-800's character RAM are separate devices.

Configuration persists in the normal emulator INI:

```ini
[PCG700]
fitted=1
hsw=1
```

## Programming interface

The device provides 2 KiB of RAM: two banks of 128 eight-byte characters.
Only character codes `80h–FFh` are replaced. Attribute bit 7 selects the
character bank for display; the programming bank does not change that selection.
Patterns are monochrome, with the existing foreground/background colours.

| Memory address | Write operation |
| --- | --- |
| `E010h` | Pattern data latch |
| `E011h` | Address bits 7–0 |
| `E012h` bits 1–0 | Address bits 9–8 within the selected 1 KiB bank |
| `E012h` bit 2 | Programming bank: 0 or 1 |
| `E012h` bit 3 | Display bypass: 0 selects PCG, 1 selects original characters |
| `E012h` bit 4 | Write strobe; release before programming the next byte |
| `E012h` bit 5 | Source: 0 uses E010h, 1 copies the corresponding original CGROM byte |
| `E012h` bits 7–6 | Ignored |

These are write-only memory-mapped registers. Z80 `OUT` instructions do not
programme them. Reading them follows the existing mapped memory behaviour.
The address within PCG RAM is `((control & 7) << 8) | address_low`.
A ROM-copy write uses the original upper half of the corresponding CGROM bank,
regardless of the currently displayed PCG contents.

A pattern's bit 7 is its leftmost pixel. Repository CGROM arrays use the
renderer’s opposite bit order, so the device converts at the ROM-copy and
rendering boundaries. PCG RAM and snapshots contain physical pattern bytes.

Example, programme the first row of character 80h in bank 0:

```asm
    LD A,80h
    LD (0E010h),A      ; leftmost pixel set
    XOR A
    LD (0E011h),A      ; row 0 of character 80h
    LD A,10h
    LD (0E012h),A      ; strobe, bank 0, PCG display selected
    XOR A
    LD (0E012h),A      ; release strobe
```

## Mapping and lifecycle decisions

**The requested implementation qualifies PCG access by upper-memory banking.**
After `OUT (E1h),A`, writes to E010h–E012h affect upper RAM only. `OUT (E3h),A`
restores the peripheral mapping. Both CPU and debugger logical writes honour
this rule. It deliberately differs from the unconditional decoding described
in Youkan's hardware map; this is the user's explicit compatibility requirement.
The existing E5h/E6h inhibit handling is unchanged.

HSW bypasses display substitution without preventing programming. Removing the
card disables both programming and display substitution. The SSW and GSW jumper
circuits are not independently configurable.

Power-on RAM contents are unspecified by the available hardware evidence.
The emulator chooses zeroed RAM and CGROM bypass for reproducibility. Soft reset
retains character RAM and physical switches, clears data/address latches and
selects CGROM bypass. These are explicit emulator reset policies, not measured
claims about the original board.

Snapshots preserve RAM, switches and all three register latches, including a
high strobe. Old snapshots without `hw/pcg700.bin` restore the expansion as
absent. The binary entry is 2,053 bytes: fitted, HSW, data, address-low, control,
then 2,048 pattern bytes. Invalid lengths or switch/control values are rejected.

## Source audit and accuracy limits

Research checked on 20 October 2026:

1. [Youkan's MZ-700 hardware register map](http://www.maroon.dti.ne.jp/youkan/mz700/mziomap.html)
   documents ADDR, SSW, WE and COPY, including the 0–1–0 write sequence and
   decoding while DRAM is selected. The original server timed out during this
   audit; its preserved [2021 capture](https://manuals.plus/m/ba2222b125aa1fb6382e7aeb846135ae00b33843b6ba8e72616c6da324784949)
   was readable, especially page 17. Its DRAM behaviour is deliberately overridden
   here as described above.
2. [Common Source Project, MZ-700 memory implementation](https://github.com/Artanejp/common_source_project-fm7/blob/master/source/src/vm/mz700/memory.cpp)
   is an independent implementation source. Its PCG-700 write handler commits
   on a rising bit-4 strobe, using the newly written high address and COPY bit.
   This implementation follows that convention.
3. [Takamin's PCG-700 implementation](https://github.com/takamin/mz700-js/blob/master/lib/PCG-700.ts)
   instead commits on a falling edge. Its
   [caller](https://github.com/takamin/mz700-js/blob/master/MZ-700/mz700.ts)
   updates address and COPY before applying that edge. This disagreement prevents
   claiming that either edge is established from hardware measurements alone.
4. [PCG-700 programming examples](https://www.idealine.info/sharpmz/mz-700/pcg700_05.htm)
   and [operating notes](https://www.idealine.info/sharpmz/mz-700/pcg700_03.htm)
   corroborate the interface and bypass controls. These are translated/manual-derived
   secondary references, not an original schematic. Their examples can clear
   the entire control byte when releasing the strobe; sampling address/COPY
   on assertion preserves those examples' intended transfers.

An original HAL schematic or a measured board trace has not been obtained.
Sub-scanline write/display contention and analogue switching artefacts are not
modelled; display updates use the existing MZ-700 scanline renderer. The
MZ-1500 debugger PCG editor does not edit this expansion's RAM.

## Verification

`tests/mcp/test_pcg700.py` starts isolated emulator processes and executes real
Z80 instructions. It compares complete 40- and 80-column canvases against an
independent pattern model, including both banks, fixed lower characters,
colours, pixel orientation, repeated strobes, ROM copying, upper-RAM isolation,
reads and I/O writes, HSW/SSW bypass, reset and snapshot restoration.

Run through CTest after building `mz700emu-pal`, or directly:

```sh
MZ_EMU=/absolute/path/to/mz700emu-pal python3 tests/mcp/test_pcg700.py
```

## Rally-X: starting the native PCG version

The native `Rally X (PCG-700).mzt` from the
[Japanese game collection](https://archive.org/details/mz-700-jp-set)
(11,770 bytes; SHA-1 `a5f74219e27ef3d0703bcb572f52358605b556bc`)
works with `STANDARD-JP`, the card fitted and HSW enabled. Press **P** to
start, wait for the opening tune, then use the **cursor keys** to steer and
**A** for smoke. PAL and NTSC gameplay checks confirm keyboard reads,
scrolling and programmed glyphs in both PCG banks. No game patch is needed.

The idle loop calls the monitor's vertical-blank wait at `0DA6h`; sampling
the PC there each frame does not establish a hang. An earlier local test
incorrectly used B, a start key shown by a separate MZ-800 conversion, and
reported a stall. That finding is superseded. MZ-800 `PCGRALLY.mzf` images
use different character-generator hardware and are separate releases.
