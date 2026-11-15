# Linux release investigation — sotf + sotf-systemwide

Date: 2026-11-14. Host used for live probes: Ubuntu 24.04.5, kernel 6.8,
AMD Threadripper PRO 3995WX (Zen 2: AVX2/FMA, no AVX-512, has SSE4a),
PipeWire 1.0.5 + WirePlumber running, USB audio + NVIDIA HDMI, no
X11/Wayland display in the shell session.

Versions in checkout: sotf workspace 0.7.18 (`v0.7.17-3-g301a288c8`),
sotf-systemwide 0.7.19 (`v0.7.19-2-gb604686`). The reported issues are
against 0.7.17, which is three commits behind sotf HEAD, so most
findings below describe current code unless stated otherwise.

GitHub issues investigated: #258, #247, #246, #222, #221, #192, #191
(repo `pierreaubert/sotf`), plus a local reproduction of
`just dev-driver-all` in `sotf/`.

## Verdict

Neither product is ready for a general Linux release today.

- sotf-systemwide 0.7.18 Linux artifacts in `sotf-systemwide/dist/`
  contain AMD-only SSE4a instructions and will SIGILL on Intel CPUs
  (same defect class as #246, still unfixed in this workspace).
- Measurement channel routing on Linux is wrong by construction
  (#258): no path guarantees stream-index = sink-position through
  PipeWire.
- Linux systemwide has no virtual sink. Out of the box it captures
  the default *microphone* and plays it to the speakers, reporting
  `Playing` with no error. That is a feedback hazard, not a feature.
- `just dev-driver-all` does not pass on Linux: it fails in the first
  (smoke) suite, and the remaining suites each have real failures.

Everything else is fixable in a bounded hardening pass. The rest of
this document goes issue by issue, then gives the common Linux
platform requirements and a recommended sequence.

## #258 — PipeWire channel outputs incorrect (CONFIRMED)

SotF uses cpal with only the ALSA host on Linux (`cpal = "0.18.2"`,
no `pipewire`/`jack`/`pulseaudio` cpal features anywhere:
`sotf/Cargo.toml:243`, `sotf-daw/crates/sotf-engine/Cargo.toml:22`).
"PipeWire output" therefore means the ALSA `pipewire`/`default` PCM.
cpal's ALSA backend sets no channel map, and no SotF code sets
channel positions (`audio.position`, ALSA chmap, dont-remix) anywhere.

The measurement defect: sweep playback opens the narrowest stream
that fits the target channel.

- `sotf-capture/src/signal_recorder/playback.rs:219`:
  `min_channels = channel + 1`, and
  `sotf-capture/src/signal_recorder/choose.rs:13` sorts candidates by
  ascending channel count and takes the smallest.
- Same truncation in the multi-capture path
  (`sotf-capture/src/signal_recorder/multi_capture.rs:559`, `:103`)
  and the per-channel probe path
  (`sotf-capture/src/signal_recorder/types.rs:366`).
- The engine path opens `channel+1` logical channels and pads
  (`sotf-daw/crates/sotf-engine/src/engine_playback.rs:146`), but
  pads to an enumerated "max" width that is fictional on plugin PCMs
  (cpal enumerates every count up to 64 on pipewire/plughw PCMs).

PipeWire assigns default positions *by stream width* and remixes by
position into the reporter's 8-channel sink. That reproduces his
table exactly: FL opens a 1-channel mono stream and is upmixed to
FL+FR; LFE (index 3) opens a 4-channel stream whose position map is
quad (FL FR RL RR), so index 3 is RR; SL (index 4) opens a 5-channel
stream whose last position is FC in ALSA order. REW works because it
opens the sink at full width with named positions.

A second, independent bug waits behind the first: SotF's canonical
order is side-before-back (FL FR C LFE SL SR BL BR,
`sotf-daw/crates/sotf-plugins/crates/sotf-host/src/speaker_config/consts.rs:866`),
while the sink declares rear-before-side (… RL RR SL SR). Even at
full width, raw index copying swaps side and rear surrounds.
Routing must go through channel roles, not list indices.

Fixes, in order:

1. Never truncate measurement width. Open at the device's default
   (sink) width and write silence to non-target channels (the writer
   already zero-fills).
2. Treat plugin-PCM capability enumeration as untrusted; only the
   default config width is meaningful. Log negotiated width + PCM
   name in every measurement record.
3. Route by `ChannelRole`/layout against the sink's position order.
4. For a guarantee, add a native PipeWire measurement backend that
   sets `audio.position`; with cpal/ALSA the app can at best warn
   that channel identity is not guaranteed.

## #246 — AppImage "Illegal instruction" (CONFIRMED, root cause refined)

The faulting instructions in the shipped 0.7.17 binary are not
AVX-512. Disassembly finds 12 SSE4a sites (`extrq`/`insertq`) in
ordinary unguarded code (including GPUI text paint). SSE4a exists on
AMD Zen only, on no Intel CPU, which is why the reporter's three
Intel machines (13500, 1255U, N-series) all died and every AMD
maintainer machine ran fine. At tag v0.7.17,
`sotf/.cargo/config.toml` used `target-cpu=native`; the x86 release
builder is a Zen host running Docker, and Docker does not mask CPU
features.

Status:

- Fixed for sotf: `target-cpu=x86-64-v2` is now pinned for
  `x86_64-unknown-linux-gnu` in `sotf/.cargo/config.toml:54`, root
  `.cargo/config.toml:58`, `math-audio/.cargo/config.toml:30`,
  `sotf-daw/.cargo/config.toml:57`. First-party SIMD is behind
  runtime CPU probes. Not yet in any release.
- NOT fixed for sotf-systemwide: `.cargo/config.toml:50` is still
  `target-cpu=native`, and the shipped 0.7.18 daemon AppImage
  already contains 2 SSE4a instructions. Those artifacts must be
  rebuilt and replaced before any public Linux release.
- `autoeq/.cargo/config.toml:61` is still `native` for standalone
  builds. `[build] target-cpu=native` survives everywhere as a
  silent fallback for unlisted targets; musl sections force AVX2.
- Shipped binaries require GLIBC 2.39 (Ubuntu 24.04 class) although
  the canonical builder image declares `rust:bookworm` (2.36). They
  will not start on Debian 12, Ubuntu 22.04, or RHEL 9. Decide the
  floor and assert it in the release script (`readelf -V`).
- No CI gate would have caught this: the artifact check builds from
  source with `--release` (not the shipped `dist` AppImage), runs on
  the project's own AMD-class host, and the tag workflow builds the
  AppImage but never executes it. Add an instruction-scan gate over
  shipped ELFs (`extrq|insertq|clzero|zmm|%k[0-7]` outside known
  dispatched code) or run the AppImage under an Intel-class CPU
  model.
- The ALSA stderr spew in the report is cosmetic but hits every
  first launch: startup enumerates all cpal devices and their
  configs (`sotf-capture/src/devices/get.rs:115`), ALSA probes every
  PCM and prints to stderr, and no `snd_lib_error_set_handler`
  silencer exists in the tree.

## #247 — build failure, no sound, sweep lock failure (mixed)

Three separate problems were filed as one issue.

Build: a sotf-only clone still cannot build, by design of the path
dependencies (`sotf/crates/sotf-report-host/Cargo.toml:20` needs
`../autoeq`, `sotf/Cargo.toml:143` and `:177` need `../autoeq` and
`../sotf-daw`), and `post-install` still ends in a workspace
`cargo check` that fails without the siblings. The
`--recurse-submodules` prerequisite is documented only in the root
`README.md:29`; `sotf/README.md:83` — the page a GitHub visitor
lands on — still says just run `just post-install`. Either document
the prerequisite there or make `post-install` detect missing
siblings and say so.

No sound on direct ALSA: WirePlumber owns the hardware PCM, so a
direct `hw:` open is busy or rejects the synthesized format; the
pipewire PCM accepts anything. The failure then goes silent because
`EnginePlayback` never overrides `check_health` (trait default is
`Ok(())`, `sotf-capture/src/signal_recorder/playback.rs:51`), so a
dead output stream looks like a finished sweep and the user is told
"No reliable signal lock" instead of "device busy". Device
enumeration also merges capabilities from sibling PCMs into one
representative device (`sotf-capture/src/devices/types.rs:253`), so
the UI can promise formats the PCM it opens cannot do.

Sweep lock: the lag estimator has no maximum-lag window
(`math-audio/crates/math-dsp/src/analysis/sweep_lag.rs:44`), so
PipeWire latency alone cannot fail it; failure follows from the
wrong/silent channel above. Split-clock drift (USB mic in, DAC out)
is uncorrected for chirpless sweeps by design
(`sotf-capture/src/signal_recorder/record.rs:896`), which erodes
lock confidence on long sweeps. The "missing" evidence WAV is most
plausibly a path/suffix confusion (`.nolock-take<N>.wav`), but the
write path should still `create_dir_all` and put the absolute path
in the returned error.

The UI complaints in #247 (unreachable dialog content at 1080p,
no visible scrollbars) are #221.

## #221 — no scrollbars in GPUI on Linux (CONFIRMED)

No scrollbar thumb is rendered anywhere in the stack. The toolkit's
`ScrollArea`, `Dialog`, `Select`, `Combobox`, and `Menu` are bare
`overflow_y_scroll()` divs; GPUI core renders no div scrollbars and
nothing consumes its scrollbar APIs. Wheel scrolling works, which
matches both reporters. There is also no keyboard scrolling for page
content and no scroll-on-focus, so a touchpad-without-wheel or
keyboard user genuinely cannot reach below-fold form fields (the
#247 Measure Config case, which is a workflow step, not a modal).
Toolkit `Dialog` caps height at a fixed 45rem instead of a
viewport-relative value. Dropdowns cap at 200px with no thumb, no
PageUp/PageDown/Home/End, and no viewport flip/clamp.

Fix belongs in gpui-toolkit (a real scrollbar component honoring
always-show on Linux/Windows), adopted by Dialog/Select and by the
app's workflow body first. Note that sotf builds against the
lockfile-pinned gpui-toolkit checkout, not the root submodule —
align them before fixing.

## #192 — multichannel export refusal (partially fixed)

The gate is `ensure_external_export_supported`
(`autoeq/crates/roomeq-export/src/export_format.rs:433`): any routed
bass-management graph or any non-empty `global_plugins` was refused
for every non-native format. CamillaDSP has since been carved out
and now renders routed graphs for real (expand mixer, per-route
crossover + delay, sum mixer; `autoeq/crates/roomeq-export/src/lib.rs:404`),
with conformance tests. PipeWire filter-chain could express the
same topology but the exporter is serial-only
(`autoeq/crates/roomeq-export/src/conformance.rs:191`) — missing
work, not a format limit. EasyEffects and Wavelet refusals are
correct: neither format can represent cross-channel route summation.

The remaining defect is UX: the wizard's format list is static and
always selectable (`sotf/crates/app-gpui/components/room_eq/step_6_export/misc.rs:27`),
so the user learns about the limitation only after a full 5.1
optimization, at export time. A capability API exists
(`query_export_capabilities`, `export_format.rs:238`) with zero
callers in the app. Wire it into step 6 (disable + reason) and warn
in step 3 when bass management is enabled. For Linux users the
missing piece is routed PipeWire export; until then the honest
options are CamillaDSP, SotF JSON/Apply, or WAV convolution (which
cannot encode LFE redirection).

## #222 — optimization appears stuck on an N100 (mostly perception)

Three compounding causes, all in current code:

1. Home-cinema progress divides by the wrong number. `max_iter`
   (50,000) is mapped to objective *evaluations*, CMA-ES evaluates
   300 offspring per generation, so one pass is about 166
   generations — but home-cinema reports progress against 50,000
   (`autoeq/crates/roomeq-workflow/src/topology/home_cinema.rs:2911`).
   The reporter's "112 iterations in 15 minutes" was about 67% of a
   pass, displayed as 0.2%.
2. The real budget is a multiple of 50,000 per channel: greedy
   filter-count search sums to roughly 200k evaluations per channel
   per EQ stage, times pre- and post-route stages, times channels.
   A shared-budget cap landed 2026-10-03, after the report.
3. Nested rayon parallelism (channels in parallel, each running
   parallel offspring evaluation) oversubscribes a 4-core N100.

There is no time-based budget and no speed/quality preset in the
wizard. Fixes: correct the progress denominator and show
evaluations/sec + ETA, pick one level of parallelism, add a time
budget and Fast/Balanced/Thorough presets (with an upfront estimate
on low-core machines).

## #191 — stale binary names in build recipes (FIXED)

`math-audio/Justfile` now builds `plot-functions` and `plot-de`,
matching the actual bin targets; the reporter's follow-up already
confirmed a clean build. The issue can be closed as fixed once a
release notes entry points at it. The general lesson stands:
release recipes must be exercised from a clean clone in CI (see
#247 build, same class).

## `just dev-driver-all` on this machine (reproduced)

Run 2026-11-14 in `sotf/` (logs under `sotf/tmp/linux-investigation/`):

- `dev-driver-smoke`: FAIL. `recording-fake-capture` —
  `assert_visible recording.capture_all` not present. Root cause:
  this shell has no display, GPUI's Linux headless platform never
  delivers frame callbacks after the first frame, so the dev-api
  element registry stays frozen on the Home screen. State asserts
  pass; every painted-selector assert after navigation fails. The
  suite runner neither provisions a virtual display nor verifies a
  frame was painted.
- `dev-driver-full`: 115 pass, 2 fail (`loudness-empty-editor`,
  `heavy-3d`) — both die at a `screenshot` step: GPUI
  `render_to_image` is unimplemented on Linux and the X11 fallback
  needs a visible window, `xdotool`, and ImageMagick.
- `dev-driver-roomeq`: 22 pass, 4 fail — one 300 s timeout
  (`roomeq-workflow`), one frozen-registry selector failure
  (`roomeq-export-recovery`), two screenshot failures.
- `dev-driver-tui`: 21 pass, 1 fail, 2 skipped — the one failure is
  a *real product bug*, not harness: `tui-roomeq-optimize-export-apply`
  fails to load a stereo plugin graph into the daemon with
  "Submitted graph snapshot expansion changed graph output channels
  from 2 to 64 while replacing physical input width 2".

So `dev-driver-all` fails fast (first suite) and cannot currently
serve as a Linux release gate. Fixes: make the GPUI headless
platform drive frames (or force a draw before serving painted state
from dev-api), make `assert_visible`/`click` retry until timeout,
have the runner fail fast with a clear message when no display is
available (or provision Xvfb, as `.gitea/workflows/ui-release-check.yml`
already does), give Linux a screenshot path that does not need X11,
and fix the graph channel-expansion bug the TUI suite found.

## sotf-systemwide on Linux (live probe, this host)

What exists today: a cpal capture driver
(`sotf-systemwide/crates/daemon/bin/cpal_capture.rs`, default or
`SOTF_CAPTURE_DEVICE` input, bounded drop-oldest queue, sensible
rate clamping), a systemd user unit
(`sotf-systemwide/builds/linux/sotf-daemon.service`), AppImage/.deb/
tarball packaging (`sotf-systemwide/scripts/build-linux.sh`), and a
virtual-output name denylist
(`sotf-systemwide/crates/daemon/bin/sotf_daemon/misc.rs:912`).

What does not exist: any Linux virtual sink. Nothing creates a
PipeWire null sink / loopback for applications to play into (no
`pw-loopback`, `module-null-sink`, or `Audio/Sink` node creation in
the tree). The docs assume the default input "is typically a
monitor source"; on a stock PipeWire system the default source is a
microphone.

Live probe results (prebuilt daemon, isolated runtime dirs):

- `list_devices` returned about 60 output entries with heavy
  duplication ("USB Audio, USB Audio" many times over), including
  the ALSA null PCM ("Discard all samples (playback) or generate
  zero samples (capture)"), "PipeWire Sound Server", and "Default
  ALSA Output (currently PipeWire Media Server)" — all reported as
  2 channels. The daemon's list dedupes only the default entry; the
  player's own `player-cli devices` dedupes better (8 outputs) but
  still shows fictional ranges ("64 ch, 1-4294967295 Hz"), keeps the
  null device, and duplicates some HDMI ports. Device selection is
  by name substring, which is ambiguous among the duplicates.
- With `SOTF_OUTPUT_DEVICE` set to the null/discarder PCM, the
  daemon honored it ("Explicit virtual output device … honoring
  selection"), captured the USB microphone (`wpctl` showed
  `input_FL/FR < USB Audio:capture_*`), and reported
  `state=Playing`, `last_error=None`, `recovery_actions=[]` while
  spinning 10.5M callbacks and 14M underruns in a minute. The
  denylist is macOS-centric (BlackHole, Soundflower, …) and does not
  recognize Linux null/monitor/pipewire names; the engine's extra
  null check is overridden by explicit selection.
- Default capture is the microphone. With a real output selected
  that is an acoustic feedback path (mic → plugin chain → speakers)
  with no warning anywhere. There is no "is this capture endpoint a
  monitor?" check and no fault state for it.
- RT priority fails without `CAP_SYS_NICE`/rtkit and is only logged
  (acceptable, but the unit file sets no `LimitRTPRIO` and the docs
  do not mention `audio`/`realtime` group setup).

Also relevant to both products: capture and playback run on two
independent clocks on Linux (USB mic vs output device). Nominal
rate conversion exists; drift compensation for systemwide capture
and for chirpless measurement sweeps does not, so rings slowly
fill/drain and drop-oldest absorbs it as periodic jumps.

## Common Linux requirements (both products)

1. CPU floor: pin a portable baseline (`x86-64-v2` chosen for sotf)
   in *every* shipped workspace, remove the `[build] native`
   fallback, and gate shipped artifacts with an instruction scan.
2. glibc floor: build in the oldest declared image and assert the
   max `GLIBC_` symbol version in the release script.
3. Device model: one shared Linux device layer that dedupes PCM
   aliases by stable identity (not display-name substring), hides
   or clearly labels null/discarder and monitor endpoints, never
   merges capabilities across sibling PCMs, clamps fictional
   capability ranges, and prefers the PipeWire PCM when the hardware
   PCM is held by WirePlumber — saying so in UI and logs.
4. Channel identity: open streams at sink width, route by channel
   role, set PipeWire `audio.position` where the backend allows,
   and surface an explicit fault (not silent remix) when identity
   cannot be guaranteed.
5. Fault reporting: stream-build and stream-death errors must reach
   the user as named causes ("device busy, held by PipeWire"),
   never as successful playback into a null sink or as a downstream
   analysis failure.
6. Packaging: `.deb` depends must use names that exist on target
   distros (`libasound2` is satisfied on noble only via a versioned
   Provides from `libasound2t64`; verify per distro), fix the stray
   Homepage in the sotf deb control, and test-install artifacts in
   clean distro containers.
7. QA gates that run on Linux: dev-driver under a virtual display,
   AppImage execution (not just build) smoke, and a no-audio-hardware
   container run. Today the Linux gates are manual or macOS/arm64
   Docker only.

## Release blockers, in order

1. sotf-systemwide: pin `x86-64-v2`, rebuild and replace the 0.7.18
   Linux artifacts (SSE4a → SIGILL on Intel). Same for autoeq
   standalone config.
2. Measurement width/positions (#258 items 1–3 above).
3. Systemwide Linux capture safety: refuse (or loudly fault) when
   the capture endpoint is not a monitor/virtual source; extend the
   virtual/null denylist with Linux names and never let an explicit
   env selection turn the null PCM into a "Playing" pipeline.
4. Graph channel-expansion bug found by `dev-driver-tui`
   (2 → 64 channels) — same fictional-width family as #258.
5. `EnginePlayback::check_health` so dead ALSA devices report their
   real error.
6. Make `dev-driver-all` pass on a display-less Linux box (headless
   frames or Xvfb provisioning + Linux screenshot path), then put
   it in the release checklist.

## Recommended sequence

1. One hardening branch: CPU/glibc pins + artifact gates (both
   products), ALSA error silencer, README/`post-install` fix (#247),
   close #191.
2. Audio correctness branch: measurement width + role routing,
   device-layer dedup/null handling, `check_health`, systemwide
   capture-endpoint guard. Add PipeWire-loopback regression tests
   (virtual sink + `pw-record`-style assertion of which position
   received the sweep).
3. UI branch: toolkit scrollbar + dialog/dropdown fixes (#221),
   export capability wiring + early warning (#192), optimizer
   progress/parallelism/presets (#222).
4. Dev-driver on Linux green, then a 0.7.19 RC validated on:
   Intel + AMD x86-64, one pre-AVX2 machine if available,
   Ubuntu 24.04 and one older-glibc distro, PipeWire multichannel
   (MOTU-class) measurement, and an N100-class optimization run.

## Decisions needed from the maintainer

1. Native PipeWire backend in scope for this release, or ALSA-only
   with loud warnings where channel identity cannot be guaranteed?
   (Recommendation: native PipeWire for measurement playback and
   systemwide virtual sink; ALSA stays as fallback.)
2. Systemwide Linux model: create and manage a PipeWire virtual
   sink from the daemon/installer, or document a manual monitor
   setup? Shipping the current default-mic behavior is not safe.
3. Support floor: `x86-64-v2` + glibc 2.36 (bookworm) as proposed
   here, or Ubuntu 24.04+ only?
4. Routed PipeWire export now, or is CamillaDSP + early capability
   warnings enough for this release?
