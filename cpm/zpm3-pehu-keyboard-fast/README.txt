Sharp MZ-700 banked ZPM3/ZCCP: Keyboard Fast trial0.1.0
19 October2026

Launch emulators/Start MZ-700 ZPM3 ZCCP PEHU Keyboard Fast - TEST.command.
Press F and Return at the stock Sharp monitor. This trial has a separate
writable disk/profile retaining current software and user files. Screen Fast's
launcher, source, build and working disk remain unchanged.

Restore point
 build-records/mz800emu/restore-points/zpm3-screen-fast-before-keyboard-fast/
 screen-fast-restore.zip, SHA256.json and RESTORE.txt.
All189 source/build/reference/profile/launcher/disk files were hashed and
verified inside the ZIP and checked unchanged after the native suites.
To restore, close the relevant emulator and extract that ZIP into the project
root, retaining relative paths. The old launcher remains directly usable.

Single runtime change
The original SUC F0F6-F0FD internal routine changes from:
 PUSH HL; LD HL,(state+29); LD A,L; SUB H; POP HL; RET
into:
 LD DE,(state+29); LD A,E; SUB D; RET; RET
The first RET returns immediately; the second is the original final RET,
retained as the eighth byte. No padding instruction executes. The address
word remains at the same offset and all later scanner offsets are unchanged.
Including RET but excluding the caller's CALL, the routine takes55->38T,
saving17T per invocation. Only five instruction bytes change. The two-byte
state is read in the same order with interrupts already masked.

DE changes inside this private routine. Its single internal call is from the
SUC status scanner; subsequent paths either return or initialise DE before
using it. keyboard_safe_call preserves the external caller's DE. BC and HL
remain unchanged and the result A/flags are identical. This is not a general
replacement for an arbitrary caller requiring preserved DE.

Preservation and memory
The builder verifies the complete original scanner block after declared
relocations, existing ROM-banking adaptations and the two explicit opcode
patches in keyboard-relocations.json. keyboard-provenance.json documents the
change. Function/editing macros, ALPHA/GRAPH logic, monitor lookup tables and
character conversion data remain byte-identical. All28 original SUC keyboard
oracle cases pass, including four function-key pages, F5 page switching and
a custom XY/Return macro.
Native bytes remain6,545; common BIOS remains1,998bytes and is byte-identical
to Screen Fast. All native/common symbol offsets are identical. Allocations
remainA600-BFFF andF800-FFFF; resident N10 remainsF200-F7FF. Application TPA
is60,672bytes (59.25KiB),0100-EDFF, unchanged after SUBMIT as well. Original
N10 SPRs, native512/LBA disk handling, GIDE RTC, Sharp cursor/ROM attributes,
Screen Fast display code and private masked mapper remain unchanged.
The deferred Monopoly listing is unchanged.

Measured keyboard comparison
Workload                    Screen Fast Keyboard Fast    Reduction
raw_word_load                  960000       790000   17.7083%
empty_const                   8766000      8732000    0.3879%
pending_const                 2950000      2916000    1.1525%
Raw_word_load contains10,000 calls plus loop overhead. Empty_const and
pending_const contain2,000 public BIOS CONST calls plus status checks/loop
overhead. Pending input is a synthetic queue-index word0500h, not host typing.
The profiler counts each leaf invocation. The measured routine body itself
is55T before and38T after in every case. Every whole-loop difference is
exactly17T multiplied by its invocation count.
Three fresh emulator processes per build agree exactly. Timings exclude
setup/boot/debugger pacing; the cursor is disabled to remove blink-phase
variance. Results are emulated CPU cycles, not host or physical-hardware time.

Canonical disk/display comparison
Workload                               Screen Fast Keyboard Fast
sequential_read                        12442809     12442809
sequential_write_flush                 11474070     11474070
print_1000                              2088141      2088141
erase_1999_cells_10_times                788476       788476
scroll_100_times                       13609466     13609466
clear_screen_100_times                  7179540      7179540
All six workloads are cycle-for-cycle identical across three fresh processes
per build. They do not invoke this keyboard routine inside their timed
segments. Both builds use the same latest captured working-disk contents,
replace only system/boot payloads and install identical benchmark input.
Absolute disk counts can differ from earlier published comparisons using
older working-disk contents; the within-trial comparison is matched.
ATA command counts and host-verified file payloads remain unchanged.

Exhaustive native comparison and regressions
The real emulated Z80 executes all65,536 possible input words on both builds.
All A and full flag bytes are identical. Output buffers are preserved as
all-word-af.bin with hashes. BC, HL and SP are checked; internal DE changes
are permitted, while public gateway tests verify caller-visible DE.
14system and6application suites pass, including229 terminal cases,124 MOVE
contracts and28 gateway cases, with IRQ/map/stack/register restoration checks.
They cover boot/load-map retention, original keyboard, C/D I/O and sector
preservation, native512 DMA, RTC/DATE, ZCCP paths/history and user areas.
Applications cover BASIC, WordStar editing/cold reopening, indexed dBASE
records, BDS C compile/link/SUBMIT and81,920byte I/O verification, SuperCalc
save/reload/formulas and utilities. All156 other guest files and the complete
D volume are unchanged. VALIDATION.json and the build-records evidence hold
all detailed results. PERFORMANCE.json combines both benchmark comparisons.

Reproduce
 python3 cpm/zpm3-pehu-keyboard-fast/build.py
 python3 cpm/zpm3-pehu-keyboard-fast/media.py
 python3 cpm/zpm3-pehu-keyboard-fast/prepare.py
 python3 cpm/zpm3-pehu-keyboard-fast/validate.py
 python3 cpm/zpm3-pehu-keyboard-fast/keyboard_benchmark.py
 python3 cpm/zpm3-pehu-keyboard-fast/benchmark.py
 python3 cpm/zpm3-pehu-keyboard-fast/package.py

Close this trial's emulator before prepare.py migrates its working disk.
Tests use disposable/read-only images. package.py rebuilds22 binary/media
outputs from its source ZIP alone, including a fresh source build of ZXCC.
Source, media and evidence ZIPs are under preservation/0.1.0 with CRC/SHA
verification. The BIOS remains polling-only and non-reentrant; IRQs stay
masked during banked/mapped access. NMI/bank-aware handlers are unsupported.
Original programme copyrights and distribution terms remain applicable.
