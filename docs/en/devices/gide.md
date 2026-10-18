# KC-Club GIDE for the MZ-700

This local extension emulates the software interface of the KC-Club GIDE
CPU-socket adapter: a jumper-selected I/O block, two-byte ATA data latch,
master/slave raw disk images and an RTC72421 clock. It is separate from IDE8.
The card is optional and disabled by default. MZ-800 behaviour is unchanged.

## Using it

Open **HW & Devices → KC-Club GIDE**. Select **Card fitted**, an I/O base,
and an existing image under **Master** or **Slave**. Image selection explicitly
offers read-only and writable modes. Eject before replacing external media.
The emulator never creates, formats or truncates an image through this menu.
Changes are saved in the current emulator configuration.

Use a raw ATA image containing complete 512-byte sectors, from 512 bytes up to
128 GiB. A CPC DSK container is not a raw ATA image. A blank image still needs
partitioning/formatting appropriate to the intended CP/M BIOS.

Example configuration (paths relative to the configuration directory):

```ini
[GIDE]
enabled = 1
base = 0xa0
hdd0_filepath = development.img
hdd0_readonly = 1
hdd1_filepath =
hdd1_readonly = 1
```

Numeric configuration values are hexadecimal, including values without a prefix.
Use `0xa0` explicitly. The supported conflict-free bases are 10, 20, 30, 40, 80,
90, A0, B0 and C0 (hexadecimal). Other blocks overlap native banking, existing
emulated expansions or emulator hooks and are rejected. An invalid base disables
the card and resets its configured base to A0. The physical board's jumpers can
select additional blocks; bus contention between colliding devices is not modelled.

**The archived SUC Personal CP/M floppy has no GIDE disk driver.** It still
boots from the MZ-1E05 floppy interface. Adding this card does not introduce a
CP/M drive letter or boot ROM. A GIDE BIOS and suitable boot code are separate work.

## Registers

For base `x0`, the low address byte selects the following. ATA accesses ignore
the high address byte, allowing Z80 INIR/OTIR block transfers.

| Offset | Read | Write |
|---|---|---|
| x0–x3 | Unclaimed | Unclaimed |
| x4 | Reserved expansion, unclaimed | Unclaimed |
| x5 | RTC register selected by A8–A11 | RTC register selected by A8–A11 |
| x6 | ATA alternate status | Device control (SRST and nIEN) |
| x7 | Legacy drive address | Ignored |
| x8 | ATA data, low byte then high byte | ATA data, low byte then high byte |
| x9 | Error | Features |
| xA | Sector count | Sector count |
| xB | Sector number / LBA bits0–7 | Same |
| xC | Cylinder low / LBA bits8–15 | Same |
| xD | Cylinder high / LBA bits16–23 | Same |
| xE | Device/head and LBA bits24–27 | Same; bit4 selects slave |
| xF | Status | Command |

Task-register accesses x9–xF reset the GAL low/high phase. Reads and writes
of the data register advance the same shared phase. RTC, alternate status and
drive-address accesses leave it unchanged. A low-byte read fetches an ATA word;
a high-byte write commits one. In particular, polling xF between the two bytes
will discard the pending high-byte read or restart a low-byte write. Poll x6 if
phase preservation is required. ATA software reset does not itself clock the
GAL latch; a subsequent task-register access re-establishes low-byte phase.
Host reset starts the emulated card in low-byte phase.

ATA parameter writes reach both devices, even when drive selection follows those
writes. Each device retains its own command, transfer buffer and current position.

## ATA implementation

Implemented commands: READ SECTORS 20/21, WRITE SECTORS 30/31, IDENTIFY DEVICE EC,
RECALIBRATE10, EXECUTE DEVICE DIAGNOSTIC90, INITIALISE DEVICE PARAMETERS91,
FLUSH CACHE E7 and SET FEATURES EF for default PIO mode only (feature03,
sector-count00 or08). Other commands/features return ABRT. No DMA, ATAPI,
LBA48, 8-bit ATA transfer mode or READ/WRITE MULTIPLE is advertised or implemented.

Both CHS and LBA28 addressing work. LBA zero addresses the first sector; CHS sector
numbers start at one. Sector count zero means 256 sectors. Default CHS translation
is 16 heads, 63 sectors/track and whole cylinders derived from the image size,
capped at 16383. Tiny images report one cylinder; all accesses are still checked
against their actual length. Trailing sectors outside the CHS translation remain
accessible through LBA. Command91 changes the CHS translation.

Transfers are synchronous PIO. DRQ remains set during the data phase and clears
on completion. Read-only writes and unsupported commands fail with ABRT;
out-of-range transfers fail with IDNF before any sector is written. Host I/O
failures report UNC. Successful writes flush the C stream after each sector.
There is no emulated interrupt line, rotational delay, BSY timing or power-loss
atomicity guarantee. nIEN is retained but has no interrupt output to control.
No guest filesystem or partition table is interpreted by the card.

## RTC

RTC registers0–C contain decimal digits for seconds, minutes, hours, day, month,
two-digit year and weekday. D/E/F are the Epson control registers. Data is
four bits wide; A12–A15 are ignored. Use `IN r,(C)` / `OUT (C),r` with the register
number in B, for example port0DA5 accesses control D at base A0.

The clock starts from host local time in 24-hour mode. Digit reads/writes,
HOLD/BUSY, STOP, subsecond RESET, 12/24-hour representation, independent weekday
and 30-second adjustment are supported. HOLD can retain one missed second;
STOP freezes counting. Host reset clears HOLD and RESET without resetting the
calendar or STOP. Guest changes affect only the emulated clock.

Updates occur atomically at host-second resolution: there is no transient BUSY
window or subsecond oscillator model. The STD.P pulse output/IRQ flag and factory
TEST behaviour are not implemented; E is retained for register compatibility.
Supported calendar years are 2000–2099. The clock continues with host wall time
while the emulator is paused or running at maximum speed. It is stored in a
snapshot, but is reseeded from host time on a fresh process, without a separate
battery-state file.

## Snapshots and media

Snapshots store the ATA registers, per-drive transfer buffers, card byte phase,
pending word, write protection, RTC digits and clock state. The same image paths,
lengths and write protection must already be mounted when restoring. The image
contents are external: loading a snapshot does not undo completed disk writes or
check that a file of the same length still contains the same bytes. RTC time
resumes from the saved value rather than adding time spent in the snapshot file.
Old snapshots without GIDE state reset the configured controller.

The upstream CP/M floppy I/O stall after a full snapshot restore remains a separate
known issue. Use a fresh CP/M boot for functional testing.

## Basis and verification

Sources already preserved in this project:

* Tilmann Reh, `GIDE.txt`, 12 October1995, sections4 and6; `gide1.pds` and
  `gide2.pds`, revision02, 26 September1995, establish decoding and latch logic.
* KC-Club2001/2 circuit and assembly material establishes the later board's
  software-compatible ATA latch and RTC72421 arrangement. This implements its
  software-visible interface, not the electrical behaviour of a particular PCB.
* Epson *RTC-72421/72423 Application Manual*, MQ-162-02, pages8–16.
* X3T13/2008D revision7b, [ATA-3 working draft](https://www.scs.stanford.edu/23wi-cs212/pintos/specs/ata-3-std.pdf),
  especially sections5 and7, for register broadcasts, addressing and PIO commands.

`ctest -R '^(gide_core|mcp_gide|mcp_suc80_display)$'` tests the portable core,
real Z80 INIR/OTIR transfers, boundary errors, both devices, write protection,
RTC high-address decoding, byte-phase rules, reset and mid-transfer snapshots,
and checks the existing SUC display. The core also runs independently under
AddressSanitizer and UndefinedBehaviourSanitizer with arbitrary ATA-register traffic.
No physical KC-Club board or CF/IDE device has been used for validation.
