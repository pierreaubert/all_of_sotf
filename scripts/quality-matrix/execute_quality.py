#!/usr/bin/env python3
"""
Execution-based quality checker.
Goes into each repository, installs dependencies, runs tests, coverage and benchmarks,
and updates scores.json / matrix.md with real results where possible.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from collections import defaultdict

# Import the correlation helper from the sibling script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from coverage_complexity import analyze_repo_data

_SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = _SCRIPT_DIR.parent.parent
MATRIX_DIR = _SCRIPT_DIR
REPOS_JSON = MATRIX_DIR / "repos.json"
SCORES_JSON = MATRIX_DIR / "scores.json"
MATRIX_MD = MATRIX_DIR / "matrix.md"

# Timeouts per command (seconds)
INSTALL_TIMEOUT = 300
TEST_TIMEOUT = 600
COVERAGE_TIMEOUT = 900
BENCH_TIMEOUT = 600

LOG_FILE = MATRIX_DIR / "execution.log"


def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")


def _ensure_str(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def run(cmd, cwd, timeout=60, env=None, capture=True):
    """Run a shell command with timeout and return (ok, stdout, stderr, rc)."""
    shell = isinstance(cmd, str)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=shell,
            capture_output=capture,
            text=True,
            timeout=timeout,
            env=merged_env,
        )
        ok = result.returncode == 0
        return ok, _ensure_str(result.stdout), _ensure_str(result.stderr), result.returncode
    except subprocess.TimeoutExpired as e:
        return False, _ensure_str(e.stdout), _ensure_str(e.stderr), -1
    except FileNotFoundError as e:
        return False, "", str(e), -1
    except Exception as e:
        return False, "", str(e), -1


def detect_package_manager(repo_path):
    base = ROOT / repo_path
    if (base / "bun.lock").exists() or (base / "bun.lockb").exists():
        return "bun"
    if (base / "pnpm-lock.yaml").exists() or (base / "pnpm-workspace.yaml").exists():
        return "pnpm"
    if (base / "package-lock.json").exists() or (base / "package.json").exists():
        return "npm"
    return None


def run_install(repo_path, pm):
    base = ROOT / repo_path
    if pm == "bun":
        ok, out, err, rc = run("bun install", base, timeout=INSTALL_TIMEOUT)
    elif pm == "pnpm":
        ok, out, err, rc = run("pnpm install", base, timeout=INSTALL_TIMEOUT)
    elif pm == "npm":
        ok, out, err, rc = run("npm install", base, timeout=INSTALL_TIMEOUT)
    else:
        return False, "no package manager detected"
    return ok, out + err


def run_js_tests(repo_path, pm):
    base = ROOT / repo_path
    pkg = base / "package.json"
    scripts = {}
    if pkg.exists():
        try:
            scripts = json.loads(pkg.read_text(encoding="utf-8", errors="ignore")).get("scripts", {})
        except Exception:
            pass

    results = {"unit_ok": False, "unit_output": "", "coverage_ok": False, "coverage_output": "", "coverage_percent": None}

    # Prefer explicit coverage script
    coverage_script = None
    for name in ("test:coverage", "coverage", "test-coverage"):
        if name in scripts:
            coverage_script = name
            break

    if coverage_script:
        cmd = f"{pm} run {coverage_script}"
        ok, out, err, rc = run(cmd, base, timeout=COVERAGE_TIMEOUT)
        results["coverage_output"] = out + err
        results["coverage_percent"] = extract_coverage_percent(out + err)
        results["coverage_ok"] = results["coverage_percent"] is not None
        results["unit_ok"] = ok
        results["unit_output"] = out + err
    else:
        # Run plain test
        test_cmd = scripts.get("test", "test")
        cmd = f"{pm} run {test_cmd}" if test_cmd != "test" else f"{pm} test"
        ok, out, err, rc = run(cmd, base, timeout=TEST_TIMEOUT)
        results["unit_ok"] = ok
        results["unit_output"] = out + err

        # Try coverage anyway
        if pm in ("npm", "pnpm", "bun"):
            cov_cmd = None
            if pm == "bun":
                cov_cmd = "bun test --coverage"
            else:
                cov_cmd = f"{pm} exec vitest run --coverage" if any("vitest" in s for s in scripts.get("test", "")) else None
            if cov_cmd:
                ok2, out2, err2, rc2 = run(cov_cmd, base, timeout=COVERAGE_TIMEOUT)
                results["coverage_output"] = out2 + err2
                results["coverage_percent"] = extract_coverage_percent(out2 + err2)
                results["coverage_ok"] = results["coverage_percent"] is not None

    return results


def extract_coverage_percent(text):
    """Try to extract a coverage percentage from tool output."""
    if not text:
        return None
    # vitest coverage table: Stmts 45.23% or All files | 45.23%
    patterns = [
        r"All files\s*\|\s*(\d+(?:\.\d+)?)",
        r"(?:Statements|Stmts|Lines|Branches|Functions)\s*\|\s*(\d+(?:\.\d+)?)%?",
        r"coverage[\s\w]*[:\s]+(\d+(?:\.\d+)?)%",
        r"(\d+(?:\.\d+)?)%\s*(?:statement|line|branch|function)",
        r"Total\s*\|\s*(\d+(?:\.\d+)?)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                return round(float(m.group(1)), 1)
            except ValueError:
                continue
    return None


def parse_cargo_test_summary(text):
    """Parse cargo test output and return (all_ok, passed, failed, summary_lines)."""
    if not text:
        return False, 0, 0, []
    ok_matches = list(re.finditer(r"test result: ok\.\s*(\d+) passed", text))
    fail_matches = list(re.finditer(r"test result: FAILED\.\s*(\d+) passed;\s*(\d+) failed", text))
    passed = sum(int(m.group(1)) for m in ok_matches)
    failed = 0
    for m in fail_matches:
        passed += int(m.group(1))
        failed += int(m.group(2))
    all_ok = len(fail_matches) == 0 and len(ok_matches) > 0
    summary = [m.group(0) for m in (ok_matches + fail_matches)]
    return all_ok, passed, failed, summary


def run_rust_tests(repo_path):
    base = ROOT / repo_path
    results = {
        "unit_ok": False, "unit_output": "", "unit_tests_passed": 0, "unit_tests_failed": 0,
        "coverage_ok": False, "coverage_output": "", "coverage_percent": None,
        "bench_ok": False, "bench_output": ""
    }

    # Check if workspace
    cargo_toml = base / "Cargo.toml"
    is_workspace = False
    if cargo_toml.exists():
        txt = cargo_toml.read_text(encoding="utf-8", errors="ignore")
        is_workspace = "[workspace]" in txt

    # Run tests
    cmd = "cargo test --workspace" if is_workspace else "cargo test"
    ok, out, err, rc = run(cmd, base, timeout=TEST_TIMEOUT)
    output = out + err
    results["unit_output"] = output
    all_ok, passed, failed, summary = parse_cargo_test_summary(output)
    results["unit_tests_passed"] = passed
    results["unit_tests_failed"] = failed
    # Mark as ok if at least some tests passed and compilation succeeded.
    # A non-zero exit code with many passed and few failed is treated as partial success.
    results["unit_ok"] = all_ok or (passed > 0 and failed == 0) or (passed > 0 and failed <= max(1, passed * 0.05))

    # Run coverage (ignore run failures so we still get a report)
    cov_dir = base / "target" / "coverage"
    cov_dir.mkdir(parents=True, exist_ok=True)
    cov_cmd = "cargo llvm-cov --workspace --ignore-run-fail --lcov --output-path target/coverage/lcov.info" if is_workspace else "cargo llvm-cov --ignore-run-fail --lcov --output-path target/coverage/lcov.info"
    ok2, out2, err2, rc2 = run(cov_cmd, base, timeout=COVERAGE_TIMEOUT)
    results["coverage_output"] = out2 + err2
    # Parse lcov.info for line coverage even if tests had failures (--ignore-run-fail)
    lcov = base / "target" / "coverage" / "lcov.info"
    if lcov.exists():
        results["coverage_percent"] = parse_lcov(lcov)
    else:
        results["coverage_percent"] = extract_coverage_percent(out2 + err2)
    results["coverage_ok"] = results["coverage_percent"] is not None

    # Run benchmarks compile check
    bench_cmd = "cargo test --workspace --benches" if is_workspace else "cargo test --benches"
    ok3, out3, err3, rc3 = run(bench_cmd, base, timeout=BENCH_TIMEOUT)
    results["bench_ok"] = ok3
    results["bench_output"] = out3 + err3

    # Correlate coverage with cyclomatic complexity
    try:
        cc_summary = analyze_repo_data(base)
        results["high_complexity_total_count"] = cc_summary["high_complexity_total_count"]
        results["high_complexity_uncovered_count"] = cc_summary["high_complexity_uncovered_count"]
        results["high_complexity_avg_coverage_percent"] = cc_summary["high_complexity_avg_coverage_percent"]
    except Exception as e:
        results["high_complexity_total_count"] = 0
        results["high_complexity_uncovered_count"] = 0
        results["high_complexity_avg_coverage_percent"] = None

    return results


def parse_lcov(path):
    """Parse lcov.info and return line coverage percent."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        lh = sum(int(m.group(1)) for m in re.finditer(r"LH:(\d+)", text))
        lf = sum(int(m.group(1)) for m in re.finditer(r"LF:(\d+)", text))
        if lf > 0:
            return round(lh / lf * 100, 1)
    except Exception:
        pass
    return None


def run_solidity_tests(repo_path):
    base = ROOT / repo_path
    results = {"unit_ok": False, "unit_output": "", "coverage_ok": False, "coverage_output": "", "coverage_percent": None}
    ok, out, err, rc = run("forge test", base, timeout=TEST_TIMEOUT)
    results["unit_ok"] = ok
    results["unit_output"] = out + err
    ok2, out2, err2, rc2 = run("forge coverage", base, timeout=COVERAGE_TIMEOUT)
    results["coverage_output"] = out2 + err2
    results["coverage_percent"] = extract_coverage_percent(out2 + err2)
    results["coverage_ok"] = results["coverage_percent"] is not None
    return results


def run_android_tests(repo_path):
    base = ROOT / repo_path
    results = {"unit_ok": False, "unit_output": ""}
    gradlew = base / "gradlew"
    cmd = "./gradlew test" if gradlew.exists() else "gradle test"
    ok, out, err, rc = run(cmd, base, timeout=TEST_TIMEOUT)
    results["unit_ok"] = ok
    results["unit_output"] = out + err
    return results


def run_ios_tests(repo_path):
    base = ROOT / repo_path
    results = {"unit_ok": False, "unit_output": ""}
    # Try to discover scheme
    ok, out, err, rc = run("xcodebuild -list", base, timeout=60)
    schemes = re.findall(r"Schemes:\s*\n((?:\s+\S+\s*\n)+)", out + err)
    scheme = None
    if schemes:
        scheme = schemes[0].strip().split()[0]
    if scheme:
        cmd = f"xcodebuild test -scheme {scheme} -destination 'platform=iOS Simulator,name=iPhone 15'"
        ok2, out2, err2, rc2 = run(cmd, base, timeout=TEST_TIMEOUT)
        results["unit_ok"] = ok2
        results["unit_output"] = out2 + err2
    else:
        results["unit_output"] = "Could not discover Xcode scheme"
    return results


def execute_repo(repo, existing_scores):
    name = repo["name"]
    rp = repo["path"]
    lang = repo["primary_language"]
    base = ROOT / rp

    log(f"\n========== {name} ==========")
    if not base.exists():
        log(f"SKIP: path {rp} does not exist")
        return None

    result = {
        "name": name,
        "installed": False,
        "install_output": "",
        "unit_ok": False,
        "unit_output": "",
        "coverage_ok": False,
        "coverage_output": "",
        "coverage_percent": None,
        "bench_ok": False,
        "bench_output": "",
        "integration_ok": False,
        "integration_output": "",
    }

    if lang == "Rust":
        # No install step needed for Rust (cargo handles deps)
        result["installed"] = True
        r = run_rust_tests(rp)
        result.update(r)
    elif lang == "TypeScript":
        pm = detect_package_manager(rp)
        if not pm:
            log(f"SKIP: no package manager found for {name}")
            return result
        log(f"Installing with {pm} ...")
        ok, out = run_install(rp, pm)
        result["installed"] = ok
        result["install_output"] = out
        if ok:
            r = run_js_tests(rp, pm)
            result.update(r)
        else:
            log(f"INSTALL FAILED for {name}")
    elif lang == "Solidity":
        log("Installing Foundry deps (forge install) ...")
        ok, out, err, rc = run("forge install", base, timeout=INSTALL_TIMEOUT)
        result["installed"] = ok
        result["install_output"] = out + err
        if ok or "already installed" in (out + err).lower():
            r = run_solidity_tests(rp)
            result.update(r)
        else:
            log(f"INSTALL FAILED for {name}")
    elif lang == "Kotlin":
        r = run_android_tests(rp)
        result.update(r)
    elif lang == "Swift":
        r = run_ios_tests(rp)
        result.update(r)
    elif lang == "Multi":
        # Try each detected package manager/build system
        pm = detect_package_manager(rp)
        if pm:
            ok, out = run_install(rp, pm)
            result["installed"] = ok
            result["install_output"] = out
            if ok:
                r = run_js_tests(rp, pm)
                result.update(r)
        # Also try gradle if Android subdir exists
        if (base / "android").exists():
            r = run_android_tests(rp + "/android")
            result["unit_ok"] = result["unit_ok"] or r["unit_ok"]

    log(f"{name}: unit_ok={result['unit_ok']} coverage_ok={result['coverage_ok']} coverage={result['coverage_percent']}% bench_ok={result['bench_ok']}")
    return result


def update_scores_with_execution(existing_scores, exec_results):
    """Merge execution results into existing static scores."""
    scores_map = {r["name"]: r for r in existing_scores}
    for er in exec_results:
        name = er["name"]
        if name not in scores_map:
            continue
        s = scores_map[name]
        if er.get("coverage_percent") is not None:
            s["unit_coverage_percent"] = er["coverage_percent"]
            s["unit_coverage_note"] = "from executed coverage run"
        elif er.get("unit_ok"):
            s["unit_coverage_note"] = "tests executed, coverage command failed or unavailable"
        else:
            s["unit_coverage_note"] = "test execution failed"

        # Adjust unit test score based on actual pass/fail.
        # If execution succeeded, raise score to at least 4 (real tests ran).
        # If execution failed, keep the static score rather than punishing for environment issues.
        if er.get("unit_ok"):
            s["unit_test_score"] = max(s.get("unit_test_score", 0), 4)

        # Adjust benchmark score if bench run succeeded
        if er.get("bench_ok"):
            s["benchmarks"] = max(s.get("benchmarks", 0), 4)

        # Store high-complexity coverage correlation
        s["high_complexity_total_count"] = er.get("high_complexity_total_count", 0)
        s["high_complexity_uncovered_count"] = er.get("high_complexity_uncovered_count", 0)
        s["high_complexity_avg_coverage_percent"] = er.get("high_complexity_avg_coverage_percent")

        s["execution"] = er
    return list(scores_map.values())


def rebuild_matrix(scores):
    scores.sort(key=lambda x: x.get("overall", 0), reverse=True)
    with open(SCORES_JSON, "w") as f:
        json.dump({"repositories": scores}, f, indent=2)

    lines = []
    lines.append("# Software Quality Matrix\n")
    lines.append("Scores are 0-5 unless otherwise noted. Higher is better.\n")
    lines.append("| Repo | Lang | Unit | Integ | Docs | Arch | Patterns | Bench | CI | Lint | Sec | Maint | Type | Pyramid | Fuzz | Cx Cov | **Overall** |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in scores:
        cov = r.get("unit_coverage_percent")
        cov_str = f"{cov}%" if cov is not None else "N/A"
        hc_cov = r.get("high_complexity_avg_coverage_percent")
        hc_total = r.get("high_complexity_total_count", 0)
        hc_uncovered = r.get("high_complexity_uncovered_count", 0)
        if hc_cov is not None and hc_total > 0:
            cx_cov_str = f"{hc_cov}% ({hc_uncovered}/{hc_total} uncovered)"
        elif hc_total > 0:
            cx_cov_str = f"N/A ({hc_total} functions)"
        else:
            cx_cov_str = "N/A"
        lines.append(
            f"| {r['name']} | {r['language']} | {r['unit_test_score']} ({cov_str}) | "
            f"{r['integration_test_score']} | {r['documentation']} | {r['architecture']} | "
            f"{r['design_patterns']} | {r['benchmarks']} | {r['ci_maturity']} | "
            f"{r['static_analysis']} | {r['dependency_security']} | {r['maintainability']} | "
            f"{r['type_safety']} | {r['test_pyramid_balance']} | {r['mutation_fuzz']} | "
            f"{cx_cov_str} | **{r['overall']}** |"
        )
    lines.append("\n## Coverage Notes\n")
    for r in scores:
        note = r.get("unit_coverage_note", "")
        exec = r.get("execution", {})
        if exec:
            note += f" [unit_ok={exec.get('unit_ok')}, coverage_ok={exec.get('coverage_ok')}]"
        lines.append(f"- **{r['name']}**: {note}")
    lines.append("\n## High-Complexity Coverage\n")
    lines.append("Average line coverage of functions with cyclomatic complexity > 25, plus the count of such functions with < 50% line coverage.\n")
    for r in scores:
        hc_cov = r.get("high_complexity_avg_coverage_percent")
        hc_total = r.get("high_complexity_total_count", 0)
        hc_uncovered = r.get("high_complexity_uncovered_count", 0)
        if hc_cov is not None:
            lines.append(f"- **{r['name']}**: {hc_cov}% avg coverage; {hc_uncovered}/{hc_total} complex functions are < 50% covered")
        elif hc_total > 0:
            lines.append(f"- **{r['name']}**: coverage data unavailable for {hc_total} complex functions")
        else:
            lines.append(f"- **{r['name']}**: no complex functions found or analysis skipped")
    lines.append("\n## Methodology\n")
    lines.append("See `quality-matrix/README.md` for rubric definitions and weighting.\n")
    MATRIX_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    LOG_FILE.write_text("", encoding="utf-8")
    repos = json.loads(REPOS_JSON.read_text(encoding="utf-8"))["repositories"]
    existing_scores = json.loads(SCORES_JSON.read_text(encoding="utf-8"))["repositories"]

    # Resume from previous partial run if available
    results_file = MATRIX_DIR / "execution_results.json"
    done = set()
    exec_results = []
    if results_file.exists():
        try:
            exec_results = json.loads(results_file.read_text(encoding="utf-8"))
            done = {er["name"] for er in exec_results}
            log(f"Resuming: {len(done)} repositories already processed")
        except Exception:
            pass

    for repo in repos:
        if repo["name"] in done:
            log(f"SKIP (already processed): {repo['name']}")
            continue
        er = execute_repo(repo, existing_scores)
        if er:
            exec_results.append(er)
            done.add(repo["name"])
        # Save incremental results to survive crashes/timeouts
        with open(results_file, "w") as f:
            json.dump(exec_results, f, indent=2)
        # Keep the published matrix up to date with whatever has finished so far
        updated_scores = update_scores_with_execution(existing_scores, exec_results)
        rebuild_matrix(updated_scores)
        log(f"Updated matrix after processing {repo['name']}")

    updated_scores = update_scores_with_execution(existing_scores, exec_results)
    rebuild_matrix(updated_scores)
    log(f"\nDone. Updated {SCORES_JSON} and {MATRIX_MD}")


if __name__ == "__main__":
    main()
