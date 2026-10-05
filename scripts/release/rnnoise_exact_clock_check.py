#!/usr/bin/env python3
"""Qualify the exact host-rate speech path and its retained DSP oracles."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.buildbot.ci_matrix import workspace_map
from scripts.release import qa
if platform.system() == "Darwin":
    from scripts.release import nih_macos_artifact_check as owned
else:
    from scripts.release import nih_native_artifact_check as owned
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release.process_supervision import enable_subreaper

OUTPUT = ROOT / "target/release-gitea/rnnoise-exact-clock"
DAW = "sotf-daw/Cargo.toml"
SPEECH = "sotf-plugin-speech-denoiser"
SUITES = {
    "host_rate_adapter": ("all_validator_rates_preserve_full_band_at_zero_strength_and_exact_host_latency adapted_output_is_independent_of_host_callback_partition adapted_process_has_no_heap_allocation_after_preparation failed_rate_reinitialization_retains_active_backend_and_adapter enabled_adapted_stream_emits_bounded_tail_and_then_stays_complete", ""),
    "timing": ("bypass_dense_waveform_has_exact_total_latency_through_ring_wraps every_first_model_frame_phase_preserves_dry_first_and_final_markers enabled_impulse_main_peak_agrees_with_declared_delay empty_calls_do_not_choose_the_first_audio_bypass_state errors_reset_and_reinitialize_preserve_current_settings_and_history_contract cold_callbacks_toggles_and_reset_allocate_and_free_nothing first_disabled_drain_queries_snapshots_and_reset_allocate_and_free_nothing enabled_eof_process_drain_backend_cutoff_and_zero_calls_allocate_and_free_nothing", ""),
    "finite_stream": ("disabled_final_marker_is_returned_at_its_independent_delayed_position all_model_phases_and_dense_callbacks_preserve_complete_disabled_program disabled_eof_during_live_fades_matches_ordinary_zero_continuation_exactly call_bounds_count_remaining_frames_after_partial_drains rejected_calls_preserve_waveform_and_finite_eof_freezes_controls_until_reset enabled_partial_eof_preserves_accepted_program_and_terminal_state enabled_eof_matches_zero_continuation_for_every_terminal_model_residue enabled_eof_is_partition_invariant_for_mono_and_stereo enabled_eof_after_enable_transitions_matches_zero_continuation enabled_eof_preflight_errors_do_not_consume_input_or_freeze_the_plugin enabled_partial_eof_preserves_accepted_program_like_zero_continuation", "capture_aud136_pre_edit_audio_baselines replay_aud136_pre_edit_audio_baselines_bit_exact"),
    "strength_model": ("latency_constant_matches_backend_and_documented_delay default_and_disabled_audio_match_the_backend_bit_exactly strength_zero_enabled_matches_disabled_dry_exactly constant_strength_is_partition_invariant mid_strength_matches_independent_f64_blend_oracle strength_automation_slews_and_settles_deterministically rejected_strength_writes_retain_config_and_audio model_selection_validates_and_continues_on_failure mixed_batch_with_rejected_entry_is_atomic drain_freezes_strength_and_model_until_reset enabled_drain_applies_strength_like_zero_continuation fresh_restore_matches_live_configured_twin stereo_image_survives_all_strengths strength_path_is_cold_allocation_free schema_metadata_names_ranges_and_update_modes", ""),
    "accuracy": ("harness_baseline_matches_mixing_snr single_speaker_denoising_improves_sisdr two_speaker_mixture_reports_per_strength_gains overlapped_two_speaker_at_minus5db_is_documented_not_claimed music_like_mixture_is_documented_not_claimed noise_only_suppression_exceeds_floor full_scale_white_noise_is_documented_not_claimed clean_voiced_speech_is_preserved fixed_model_output_is_deterministic_across_partitions supported_rate_contract_includes_prepared_host_adaptation", "corpus_wav_pairs_si_sdr"),
    "sofa_resampling": ("first_and_last_impulses_preserve_physical_time_across_rates independent_passband_phase_has_no_backend_delay_or_fractional_offset same_rate_is_exact_and_measurements_have_independent_resampler_history fractional_target_keeps_exact_clock_duration_and_independent_ears invalid_rates_dimensions_and_unsupported_grids_leave_source_unchanged empty_datasets_convert_metadata_without_a_backend", ""),
}
CONVOLUTION = (
    "tests::resampled_ir_delta_at_start_has_no_rubato_startup_delay",
    "tests::resampled_ir_delta_at_tail_preserves_the_last_response",
    "tests::fractional_host_rate_ir_keeps_duration_channels_and_impulse_origin",
    "tests::fractional_ir_resampling_rejects_unbounded_temporary_output_before_allocation",
)
IGNORE_REASONS = {
    "capture_aud136_pre_edit_audio_baselines": "manual AUD136 pre-edit audio capture",
    "replay_aud136_pre_edit_audio_baselines_bit_exact": "manual AUD136 pre-edit enabled/disabled sample replay",
    "corpus_wav_pairs_si_sdr": "manual corpus gate: set SOTF_SPEECH_CORPUS_DIR to 48 kHz clean/noisy WAV pairs",
}
RESULT = re.compile(r"^test ([A-Za-z0-9_:]+) \.\.\. (ok|ignored(?:,.*)?)$", re.MULTILINE)
SUMMARY = re.compile(r"^test result: ok\. (\d+) passed; 0 failed; (\d+) ignored;", re.MULTILINE)


def snapshot(pins: dict[str, str]) -> dict:
    os_name = "macos" if platform.system() == "Darwin" else "linux"
    return {
        "root_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "manifest_sha256": hashlib.sha256((ROOT / "scripts/release/sources.json").read_bytes()).hexdigest(),
        "root_layout": root_layout_status(ROOT, pins),
        "workspaces": qa.source_state(ROOT, list(workspace_map()), os_name),
    }


def inventory(log: Path, expected_pass: set[str], expected_ignored: dict[str, str]) -> dict:
    body = log.read_text(encoding="utf-8")
    found = RESULT.findall(body)
    passed = [name for name, outcome in found if outcome == "ok"]
    ignored = {name: outcome.removeprefix("ignored, ") for name, outcome in found
               if outcome.startswith("ignored")}
    summaries = SUMMARY.findall(body)
    if len(summaries) != 1 or (int(summaries[0][0]), int(summaries[0][1])) != (len(expected_pass), len(expected_ignored)):
        raise ValueError(f"{log.name}: absent or incorrect successful test summary")
    if len(passed) != len(set(passed)) or len(ignored) != sum(outcome.startswith("ignored") for _, outcome in found):
        raise ValueError(f"{log.name}: duplicate test result")
    if set(passed) != expected_pass or ignored != expected_ignored:
        raise ValueError(f"{log.name}: named passed/ignored inventory differs")
    return {"passed": sorted(passed), "ignored": ignored}


def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        print("Disposable Gitea runner required", file=sys.stderr)
        return 2
    signal.signal(signal.SIGINT, owned.interrupted)
    signal.signal(signal.SIGTERM, owned.interrupted)
    enable_subreaper()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "logs").mkdir(exist_ok=False)
    owned.OUTPUT = OUTPUT
    _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
    report: dict = {
        "status": "RUNNING", "commands": [], "inventories": {}, "errors": [],
        "coverage_limits": [
            "manual AUD136 pre-edit audio capture was not run",
            "manual AUD136 pre-edit enabled/disabled replay was not run",
            "optional 48 kHz clean/noisy corpus gate was not run",
            "this focused gate alone does not establish full DSP release acceptance",
        ],
    }
    before = None
    try:
        before = snapshot(pins)
        report["before"] = before
        owned.save(report)
        report["errors"].extend(owned.source_errors(before, before, pins))
        if report["errors"]:
            return 1
        env = os.environ.copy()
        original_home = Path.home()
        env.setdefault("CARGO_HOME", str(original_home / ".cargo"))
        env.setdefault("RUSTUP_HOME", str(original_home / ".rustup"))
        private = OUTPUT / "private-home"
        private.mkdir()
        env.update(HOME=str(private), XDG_CONFIG_HOME=str(private / "config"),
                   XDG_CACHE_HOME=str(private / "cache"), XDG_DATA_HOME=str(private / "data"),
                   PULSE_SERVER=f"unix:{OUTPUT}/no-pulse", PIPEWIRE_REMOTE="no-pipewire",
                   JACK_NO_START_SERVER="1")
        for name, (passes, skips) in SUITES.items():
            package = "sotf-plugin-binaural" if name == "sofa_resampling" else SPEECH
            command = ["cargo", "test", "--locked", "--manifest-path", DAW,
                       "-p", package, "--test", name, "--", "--show-output"]
            result = owned.run_owned(name, command, report, env)
            if result["status"] != "PASS":
                report["errors"].append(f"{name}: command or owned cleanup failed")
                break
            report["inventories"][name] = inventory(
                OUTPUT / "logs" / f"{name}.log", set(passes.split()),
                {ignored: IGNORE_REASONS[ignored] for ignored in skips.split()}
            )
        if not report["errors"]:
            for index, test in enumerate(CONVOLUTION):
                name = f"convolution-{index}"
                command = ["cargo", "test", "--locked", "--manifest-path", DAW,
                           "-p", "sotf-plugin-convolution", "--lib", test,
                           "--", "--exact", "--show-output"]
                result = owned.run_owned(name, command, report, env)
                if result["status"] != "PASS":
                    report["errors"].append(f"{name}: command or owned cleanup failed")
                    break
                report["inventories"][name] = inventory(OUTPUT / "logs" / f"{name}.log", {test}, {})
    except KeyboardInterrupt:
        report["errors"].append("interrupted")
    except Exception as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        if owned.STOP:
            report["errors"].append("interrupted")
        try:
            after = snapshot(pins)
            report["after"] = after
            if before is not None:
                report["errors"].extend(owned.source_errors(before, after, pins))
        except Exception as error:
            report["errors"].append(f"after snapshot failed: {type(error).__name__}: {error}")
        report["status"] = (
            "PASS" if not report["errors"] and not owned.STOP
            and len(report["inventories"]) == len(SUITES) + len(CONVOLUTION)
            else "FAIL"
        )
        owned.save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
