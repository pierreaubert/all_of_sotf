# Software Quality Matrix

Scores are 0-5 unless otherwise noted. Higher is better.

| Repo | Lang | Unit | Integ | Docs | Arch | Patterns | Bench | CI | Lint | Sec | Maint | Type | Pyramid | Fuzz | Cx Cov | **Overall** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sotf | Rust | 5 (49.1%) | 5 | 4 | 4 | 5 | 4 | 4 | 0 | 3 | 3 | 5 | 4 | 5 | 19.4% (6/8 uncovered) | **3.92** |
| gpui-toolkit | Rust | 5 (60.3%) | 0 | 4 | 4 | 5 | 4 | 4 | 3 | 1 | 2 | 5 | 2 | 0 | 44.9% (1/3 uncovered) | **3.33** |
| math-audio | Rust | 5 (N/A) | 0 | 4 | 4 | 4 | 4 | 4 | 3 | 1 | 2 | 5 | 2 | 3 | N/A | **3.29** |
| autoeq | Rust | 5 (N/A) | 0 | 4 | 2 | 5 | 4 | 4 | 3 | 1 | 2 | 5 | 2 | 3 | N/A | **2.98** |
| symphonia-add-ons | Rust | 5 (43.2%) | 0 | 2 | 4 | 4 | 4 | 0 | 2 | 1 | 1 | 5 | 2 | 0 | 38.4% (1/3 uncovered) | **2.27** |
| sofa-reader | Rust | 5 (50.7%) | 0 | 2 | 1 | 2 | 4 | 0 | 0 | 1 | 1 | 5 | 2 | 0 | 26.0% (1/1 uncovered) | **1.63** |

## Coverage Notes

- **sotf**: from executed coverage run [unit_ok=False, coverage_ok=True]
- **gpui-toolkit**: from executed coverage run [unit_ok=True, coverage_ok=True]
- **math-audio**: tests executed, coverage command failed or unavailable [unit_ok=True, coverage_ok=False]
- **autoeq**: tests executed, coverage command failed or unavailable [unit_ok=True, coverage_ok=False]
- **symphonia-add-ons**: from executed coverage run [unit_ok=True, coverage_ok=True]
- **sofa-reader**: from executed coverage run [unit_ok=True, coverage_ok=True]

## High-Complexity Coverage

Average line coverage of functions with cyclomatic complexity > 25, plus the count of such functions with < 50% line coverage.

- **sotf**: 19.4% avg coverage; 6/8 complex functions are < 50% covered
- **gpui-toolkit**: 44.9% avg coverage; 1/3 complex functions are < 50% covered
- **math-audio**: no complex functions found or analysis skipped
- **autoeq**: no complex functions found or analysis skipped
- **symphonia-add-ons**: 38.4% avg coverage; 1/3 complex functions are < 50% covered
- **sofa-reader**: 26.0% avg coverage; 1/1 complex functions are < 50% covered

## Methodology

See `quality-matrix/README.md` for rubric definitions and weighting.
