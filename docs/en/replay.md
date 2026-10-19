# Replay: recording and playing back inputs

Records the inputs of a run once and plays them back exactly - in the
same or a new emulator process, at any speed. Typical uses:

- play a game or a program until a bug shows up, then repeat exactly the
  same run as many times as needed with other breakpoints, trace or the
  RAM Write Log switched on;
- keep a recorded run as a regression test: `--replay-verify` checks in
  CI that a new build still runs it the same way.

All platforms (MZ-800, MZ-700 PAL and NTSC, MZ-1500). A replay plays back
only in the binary of the same platform and TV system.

## How it works

A recording starts from a complete snapshot of the machine (always with
the RAM disk, whatever the snapshot settings say), taken and loaded back
at the start. From then on it stores, in emulated frames:

- every change of the keyboard (the whole key matrix, keyboard of the
  host, virtual keyboard window and MCP keys together), of the joystick
  from the numeric keypad and of the MCP joystick,
- resets and autotype,
- writes of the debugger and of MCP tools (memory, memory regions,
  registers, CPU flags, I/O ports, injected IRQ and NMI),
- every N frames (default 50, one second on PAL) a SHA-256 hash of the
  CPU (registers including the hidden Z80 state), the RAM, the MemExt
  RAM, the VRAM and the PCG, together with the emulated time.

All inputs are taken at the boundary of a frame: a key pressed in the
middle of a frame reaches the emulated computer at the end of that frame,
both while recording and while playing back. Playback loads the start
snapshot, applies the inputs at the same places and compares the hashes.
The first frame whose state differs stops the playback.

## Recording

| Way | How |
|-----|-----|
| Menu | **Replay -> Record Inputs...** asks for the file (`.mzr`) and starts. **Replay -> Stop Replay** saves it. |
| Command line | `--replay-record <file>` records from the first frame; the file is written when the emulator exits. `--replay-hash-interval <N>` sets the frames between hashes (1-100000). |
| MCP | `emu_replay_record_start`, `emu_replay_record_stop`, `emu_replay_status` (see [`mcp-server/tools-overview.md`](mcp-server/tools-overview.md)). |

If the emulation runs, it pauses at the next frame boundary, the
recording starts and the emulation runs on. While recording, the lower
left corner of the picture shows **REPLAY REC** and the frame number.

While recording:

- **Machine settings** (the Devices menu, platform, peripherals, memory
  expansions, ROM), **loading a snapshot** and **tape control** (the
  Virtual CMT and Tape Filelist windows) are not available: the replay
  could not repeat them. Over MCP the tools that change the
  machine this way (snapshot load, media, tape control, settings) are
  refused with an explanation.
- **Writes of the debugger** are recorded while the emulation runs and
  while it is paused at a frame boundary - after a pause (the pause
  button or MCP `emu_pause` pause at the end of the frame), after
  `emu_run(frames=N)` or a deadline. In a pause between frame boundaries
  (after a step or a breakpoint) a write is refused: run to the next
  frame boundary first.
- **Breakpoint actions** that write (`poke`, `set`) are not recorded;
  the recording gets a warning and plays back correctly only with the
  same breakpoints.
- Recording does not start while autotype runs or Freeze Bytes are
  active.

## Playback

| Way | How |
|-----|-----|
| Menu | **Replay -> Play Replay...** asks for the file, loads the start snapshot and runs. **Replay -> Stop Replay** ends it. |
| Command line | `--replay <file>` plays it back after startup. `--exit-at-replay-end` ends the run at the end of the playback, `--replay-verify` does the same at MAX SPEED (see below). |
| MCP | `emu_replay_play` (`pause_after_load` to set breakpoints before it runs), `emu_replay_play_stop`, `emu_replay_status`; the end is a pause with reason `replay_end` or `replay_desync` (`emu_wait_stop`). |

While playing back, the picture shows **REPLAY PLAY** with the frame and
the length of the replay. Live input (keyboard, virtual keyboard, MCP
keys) is ignored. Breakpoints, trace, the RAM Write Log, screenshots and
video recording work as usual; pausing and stepping do not change the
result.

At the end the emulation pauses and a notification shows the result:

| Result | Meaning |
|--------|---------|
| ended | the replay was played to its end, every hash matched |
| differs at frame N | the state differs from the recording; the notification names the parts (`cpu`, `ram`, `memext`, `vram`, `pcg`, `time`) |
| deviated | something wrote into the machine during playback (a debugger write, a breakpoint action `poke` / `set`, Freeze Bytes, a reset); the playback went on to the end, but the hashes were not checked after that |

A difference means that the emulated computer does not behave as during
the recording: other emulator version or settings, a disk image that
changed since the recording, or input that is not recorded (see below).

## Checking a replay in CI

```
mz800emu --headless --replay run.mzr --replay-verify --result-json result.json
```

`--replay-verify` plays the replay at MAX SPEED and ends the process at
its end: exit code 0 when every hash matched (`reason: "replay_end"`),
4 when the state differs (`replay_desync`, `replay.outcome_frame` and
`replay.desync_parts` in `result.json`), 3 when the replay cannot be
started (unreadable file, other platform or TV system). See
[`mcp-server/headless-mode.md`](mcp-server/headless-mode.md).

Note: a correction of the emulator that changes timing changes the
result legitimately - a difference on a new build means "the behaviour
changed", not necessarily a bug.

## What is not recorded

| Input | What to do |
|-------|------------|
| host joystick (joystick type JOYSTICK) | use the numeric keypad joystick or MCP; the recording gets a warning |
| contents of disk, Quick Disk and IDE8 images | keep the images unchanged between recording and playback (a program that writes to a disk changes the image) |
| tape buttons (play, stop, record) | not available while recording or playing (the Virtual CMT and Tape Filelist windows are disabled, MCP refuses it); start the tape before the recording |
| Unicard clock and SD card directory | values come from the host |
| emulator settings outside the snapshot (INI) | play back with the same settings |

## Replay file

A `.mzr` file is a ZIP archive:

| File | Content |
|------|---------|
| `manifest.json` | format, version, platform, frame length of the TV system (`screen_ticks`), length, hash interval, warnings |
| `start.mzs` | the start snapshot |
| `inputs.jsonl` | one event per line: frame `f`, position `at` (`b` frame boundary, `d` debugger write while running, `p` pause at a frame boundary), kind `k` (`kbd`, `joy`, `autotype`, `reset`, `dbg`) and its data; the last line is `end` |
| `hashes.csv` | `frame,ticks,cpu,ram,memext,vram,pcg` |

`inputs.jsonl` is text: an event can be removed or moved to see what a
key changed. The hashes then show where the run differs.
