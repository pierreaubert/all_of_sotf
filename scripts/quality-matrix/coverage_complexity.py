#!/usr/bin/env python3
"""
Correlate code coverage with cyclomatic complexity.

For a given Rust repository this script:
1. Runs `cargo llvm-cov` (or re-uses an existing lcov.info).
2. Queries the existing TokenSave index for the most complex functions.
3. Computes the line coverage of each high-complexity function from the lcov data.
4. Reports the average coverage of high-complexity functions and highlights the
   ones that are poorly covered, so test effort can be prioritised.

Usage:
    python3 scripts/quality-matrix/coverage_complexity.py <repo-path>
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent.parent


def _safe_json_loads(text):
    if not text:
        return None
    text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
    text = "".join(ch for ch in text if ch in ("\t", "\n", "\r") or ord(ch) >= 32)
    try:
        return json.loads(text)
    except Exception:
        return None


def _tokensave_ranking_once(repo_dir, source_dir, limit):
    cmd = ["tokensave", "tool", "complexity", "--limit", str(limit)]
    if source_dir:
        cmd.extend(["--path", source_dir])
    result = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True, timeout=180)
    data = _safe_json_loads(result.stdout)
    if data is None:
        return None
    return data.get("ranking", [])


def _tokensave_ranking(repo_dir, source_dir, max_limit=100):
    for limit in [max_limit, max(10, max_limit // 2), max(10, max_limit // 4), 10]:
        ranking = _tokensave_ranking_once(repo_dir, source_dir, limit)
        if ranking is not None:
            return ranking
    return []


def source_dirs(repo_dir):
    dirs = []
    for d in ["crates", "src", "tests", "benches", "examples"]:
        if (repo_dir / d).is_dir():
            dirs.append(d)
    cargo_toml = repo_dir / "Cargo.toml"
    if cargo_toml.exists() and not dirs:
        text = cargo_toml.read_text(encoding="utf-8", errors="ignore")
        if "[workspace]" in text:
            members_match = re.search(r"members\s*=\s*\[(.*?)\]", text, re.DOTALL)
            if members_match:
                for member in re.findall(r'"([^"]+)"', members_match.group(1)):
                    top = member.split("/")[0]
                    if top and (repo_dir / top).is_dir() and top not in dirs:
                        dirs.append(top)
    if not dirs:
        dirs.append("")
    return dirs


def high_complexity_functions(repo_dir, threshold=25, max_per_query=100):
    """Return list of {name, file, line, lines, complexity} for functions above threshold."""
    seen = set()
    funcs = []
    for source_dir in source_dirs(repo_dir):
        ranking = _tokensave_ranking(repo_dir, source_dir, max_limit=max_per_query)
        for item in ranking:
            fid = item.get("id")
            if fid in seen:
                continue
            seen.add(fid)
            file_path = item.get("file", "")
            if not file_path.endswith(".rs"):
                continue
            cc = item.get("cyclomatic_complexity", 0)
            if not isinstance(cc, (int, float)) or cc <= threshold:
                continue
            funcs.append({
                "name": item.get("name", "<unknown>"),
                "file": file_path,
                "line": item.get("line", 0),
                "lines": item.get("lines", 1),
                "complexity": cc,
            })
    return funcs


def parse_lcov(lcov_path):
    """Parse lcov.info into {file_path: {line: hit_count}}."""
    coverage = defaultdict(dict)
    current_file = None
    with open(lcov_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("SF:"):
                current_file = line[3:]
            elif line.startswith("DA:") and current_file is not None:
                parts = line[3:].split(",")
                if len(parts) >= 2:
                    try:
                        lineno = int(parts[0])
                        hits = int(parts[1])
                        coverage[current_file][lineno] = hits
                    except ValueError:
                        pass
    return coverage


def function_coverage(func, lcov_data, repo_dir):
    """Return (covered_lines, executable_lines, coverage_percent) for a function."""
    file_path = func["file"]
    # lcov SF paths are absolute; tokensave returns repo-relative paths
    abs_file = repo_dir / file_path
    key = str(abs_file)
    line_hits = lcov_data.get(key, {})

    start = func["line"]
    end = start + func["lines"]

    executable = 0
    covered = 0
    for lineno in range(start, end):
        if lineno in line_hits:
            executable += 1
            if line_hits[lineno] > 0:
                covered += 1

    if executable == 0:
        return 0, 0, None
    return covered, executable, round(covered / executable * 100, 1)


def ensure_lcov(repo_dir):
    lcov_path = repo_dir / "target" / "coverage" / "lcov.info"
    if lcov_path.exists():
        return lcov_path

    print(f"No existing lcov.info for {repo_dir.name}; running cargo llvm-cov ...")
    (repo_dir / "target" / "coverage").mkdir(parents=True, exist_ok=True)
    is_workspace = "[workspace]" in (repo_dir / "Cargo.toml").read_text(encoding="utf-8", errors="ignore")
    cmd = ["cargo", "llvm-cov"]
    if is_workspace:
        cmd.append("--workspace")
    cmd.extend(["--ignore-run-fail", "--lcov", "--output-path", str(lcov_path)])
    subprocess.run(cmd, cwd=repo_dir, check=True, timeout=900)
    return lcov_path


def analyze(repo_dir, complexity_threshold=25):
    repo_dir = Path(repo_dir).resolve()
    print(f"Analyzing {repo_dir.name} ...")

    lcov_path = ensure_lcov(repo_dir)
    lcov_data = parse_lcov(lcov_path)

    funcs = high_complexity_functions(repo_dir, threshold=complexity_threshold)
    print(f"Found {len(funcs)} functions with cyclomatic complexity > {complexity_threshold}\n")

    results = []
    for func in funcs:
        covered, executable, pct = function_coverage(func, lcov_data, repo_dir)
        results.append({
            **func,
            "covered_lines": covered,
            "executable_lines": executable,
            "coverage_percent": pct,
        })

    results.sort(key=lambda x: (x["coverage_percent"] if x["coverage_percent"] is not None else -1, -x["complexity"]))
    return results


def analyze_repo_data(repo_dir, complexity_threshold=25):
    """
    Return a structured summary for the repo without printing.

    Returns a dict with keys:
      - high_complexity_total_count
      - high_complexity_uncovered_count  (coverage < 50%)
      - high_complexity_avg_coverage_percent
      - high_complexity_functions        (list, may be empty)
      - note
    """
    repo_dir = Path(repo_dir).resolve()
    summary = {
        "high_complexity_total_count": 0,
        "high_complexity_uncovered_count": 0,
        "high_complexity_avg_coverage_percent": None,
        "high_complexity_functions": [],
        "note": "",
    }

    lcov_path = repo_dir / "target" / "coverage" / "lcov.info"
    if not lcov_path.exists():
        summary["note"] = "lcov.info not found"
        return summary

    try:
        lcov_data = parse_lcov(lcov_path)
        funcs = high_complexity_functions(repo_dir, threshold=complexity_threshold)
        summary["high_complexity_total_count"] = len(funcs)

        results = []
        covered_total = 0
        executable_total = 0
        uncovered = []
        for func in funcs:
            covered, executable, pct = function_coverage(func, lcov_data, repo_dir)
            entry = {
                "name": func["name"],
                "file": func["file"],
                "line": func["line"],
                "complexity": func["complexity"],
                "coverage_percent": pct,
                "covered_lines": covered,
                "executable_lines": executable,
            }
            results.append(entry)
            if pct is not None:
                covered_total += covered
                executable_total += executable
                if pct < 50:
                    uncovered.append(entry)

        if executable_total > 0:
            summary["high_complexity_avg_coverage_percent"] = round(covered_total / executable_total * 100, 1)
        summary["high_complexity_uncovered_count"] = len(uncovered)
        summary["high_complexity_functions"] = sorted(
            results,
            key=lambda x: (x["coverage_percent"] if x["coverage_percent"] is not None else -1, -x["complexity"]),
        )
    except Exception as e:
        summary["note"] = f"error during analysis: {e}"

    return summary


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <repo-path>")
        sys.exit(1)

    repo_path = sys.argv[1]
    results = analyze(ROOT / repo_path)

    covered_total = 0
    executable_total = 0
    uncovered = []
    for r in results:
        if r["coverage_percent"] is None:
            continue
        covered_total += r["covered_lines"]
        executable_total += r["executable_lines"]
        if r["coverage_percent"] < 50:
            uncovered.append(r)

    if executable_total > 0:
        avg = round(covered_total / executable_total * 100, 1)
        print(f"Average line coverage of high-complexity functions: {avg}%")
    else:
        print("No coverage data found for high-complexity functions.")

    print(f"\nHigh-complexity functions with < 50% line coverage ({len(uncovered)}):")
    for r in uncovered:
        print(f"  {r['file']}:{r['line']}  {r['name']}  "
              f"cc={r['complexity']}  coverage={r['coverage_percent']}%  "
              f"({r['covered_lines']}/{r['executable_lines']} lines)")

    print(f"\nTop 10 high-complexity functions by coverage:")
    for r in results[:10]:
        pct = r['coverage_percent'] if r['coverage_percent'] is not None else "N/A"
        print(f"  {r['file']}:{r['line']}  {r['name']}  "
              f"cc={r['complexity']}  coverage={pct}%")


if __name__ == "__main__":
    main()
