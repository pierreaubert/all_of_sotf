"""Focused regression cases for the dependency remediation planner.

Runs under both ``python3 -m unittest`` (the scripts/release gate) and
pytest. All fixtures are synthetic; no repository lockfile is touched.
"""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import dependency_graph as graph
import dependency_remediation as remediation


def lock(*packages: str) -> str:
    return "version = 3\n" + "".join(packages)


def package(name: str, version: str, source: str | None = None,
            deps: list[str] | None = None) -> str:
    text = f'[[package]]\nname = "{name}"\nversion = "{version}"\n'
    if source is not None:
        text += f'source = "{source}"\n'
    if deps:
        entries = ", ".join(f'"{entry}"' for entry in deps)
        text += f"dependencies = [{entries}]\n"
    return text


REGISTRY = "registry+https://github.com/rust-lang/crates.io-index"
GIT_FORK = "git+https://github.com/example/fontconfig-parser.git#abc123"


class RemediationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.names = sorted(graph.LAYERS)
        for name in self.names:
            workspace = self.root / name
            workspace.mkdir()
            (workspace / "Cargo.toml").write_text(
                f'[package]\nname = "{name}"\nversion = "0.1.0"\n')
            (workspace / "Cargo.lock").write_text(
                lock(package("serde", "1.0.219", REGISTRY)))
        nested = self.root / "autoeq" / "crates" / "autoeq-gpui-examples"
        nested.mkdir(parents=True)
        (nested / "Cargo.lock").write_text(
            lock(package("serde", "1.0.219", REGISTRY)))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def customize(self) -> None:
        (self.root / "sotf" / "Cargo.lock").write_text(lock(
            package("app-core", "0.1.0", None, ["rand 0.8.5", "serde 1.0.210"]),
            package("tool", "0.1.0", None, ["rand 0.9.0"]),
            package("rand", "0.8.5", REGISTRY),
            package("rand", "0.9.0", REGISTRY),
            package("serde", "1.0.210", REGISTRY),
            package("ambig", "1.0.0", REGISTRY),
            package("ambig", "2.0.0", REGISTRY),
            package("consumer", "0.1.0", None, ["ambig", "missing 9.9.9"]),
        ))
        (self.root / "sotf-daw" / "Cargo.lock").write_text(lock(
            package("daw-core", "0.1.0", None, ["rand 0.9.0", "bitflags 1.3.2"]),
            package("rand", "0.9.0", REGISTRY),
            package("bitflags", "1.3.2", REGISTRY),
            package("serde", "1.0.219", REGISTRY),
        ))
        (self.root / "math-audio" / "Cargo.lock").write_text(lock(
            package("math-core", "0.1.0", None, ["bitflags 2.6.0"]),
            package("bitflags", "2.6.0", REGISTRY),
            package("serde", "1.0.219", REGISTRY),
        ))
        (self.root / "sotf-capture" / "Cargo.lock").write_text(lock(
            package("capture-core", "0.1.0", None,
                    ["fontconfig-parser 0.5.8", f"fontconfig-parser 0.5.8 ({GIT_FORK})"]),
            package("fontconfig-parser", "0.5.8", REGISTRY),
            package("fontconfig-parser", "0.5.8", GIT_FORK),
            package("serde", "1.0.219", REGISTRY),
        ))
        (self.root / "sotf" / "Cargo.toml").write_text(
            '[package]\nname = "sotf"\nversion = "0.1.0"\n'
            '[dependencies]\nrandom = { package = "rand", version = "0.8" }\n')
        (self.root / "sotf-daw" / "Cargo.toml").write_text(
            '[package]\nname = "sotf-daw"\nversion = "0.1.0"\n'
            '[dependencies]\nrand = "0.9"\n')
        (self.root / "sotf-capture" / "Cargo.toml").write_text(
            '[package]\nname = "sotf-capture"\nversion = "0.1.0"\n'
            '[patch.crates-io]\nfontconfig-parser = '
            '{ git = "https://github.com/example/fontconfig-parser.git", rev = "abc123" }\n')

    def snapshot(self) -> dict[str, str]:
        digest = {}
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                digest[str(path.relative_to(self.root))] = hashlib.sha256(
                    path.read_bytes()).hexdigest()
        return digest

    def families(self) -> dict[str, dict]:
        self.customize()
        report = remediation.plan(self.root, self.names)
        return {family["package"]: family for family in report["families"]}

    def test_lock_dependency_entry_formats(self) -> None:
        self.assertEqual(remediation.parse_lock_dep("serde"),
                         ("serde", None, None))
        self.assertEqual(remediation.parse_lock_dep("serde 1.0.219"),
                         ("serde", "1.0.219", None))
        self.assertEqual(
            remediation.parse_lock_dep(f"rand 0.9.0 ({REGISTRY})"),
            ("rand", "0.9.0", REGISTRY))
        with self.assertRaises(ValueError):
            remediation.parse_lock_dep("broken entry with too many parts here")

    def test_compatibility_groups(self) -> None:
        self.assertEqual(remediation.compatibility("1.2.3"), (1,))
        self.assertEqual(remediation.compatibility("0.9.1"), (0, 9))
        self.assertEqual(remediation.compatibility("0.0.4"), (0, 0, 4))
        self.assertIsNone(remediation.compatibility("1.0.0-alpha"))
        self.assertIsNone(remediation.compatibility("not-a-version"))

    def test_exact_reverse_parents_by_scope_and_version(self) -> None:
        families = self.families()
        locations = {(item["scope"], item["version"]): item
                     for item in families["rand"]["locations"]}
        old = locations[("sotf", "0.8.5")]
        new_sotf = locations[("sotf", "0.9.0")]
        new_daw = locations[("sotf-daw", "0.9.0")]
        self.assertEqual([(parent["name"], parent["version"]) for parent in old["parents"]],
                         [("app-core", "0.1.0")])
        self.assertEqual([(parent["name"], parent["version"]) for parent in new_sotf["parents"]],
                         [("tool", "0.1.0")])
        self.assertEqual([(parent["name"], parent["version"]) for parent in new_daw["parents"]],
                         [("daw-core", "0.1.0")])

    def test_coexisting_and_cross_lock_classification(self) -> None:
        families = self.families()
        self.assertEqual(families["rand"]["kind"], "version")
        self.assertEqual(families["rand"]["coexisting_scopes"], ["sotf"])
        self.assertFalse(families["rand"]["cross_lock_only"])
        self.assertEqual(families["bitflags"]["kind"], "version")
        self.assertEqual(families["bitflags"]["coexisting_scopes"], [])
        self.assertTrue(families["bitflags"]["cross_lock_only"])

    def test_source_split_is_separate_from_version_split(self) -> None:
        families = self.families()
        fork = families["fontconfig-parser"]
        self.assertEqual(fork["kind"], "source")
        self.assertEqual(fork["versions"], ["0.5.8"])
        self.assertEqual(fork["action"]["type"], "source_change")
        self.assertEqual(fork["rank"], 5)
        self.assertFalse(fork["convergent"])

    def test_convergent_family_selects_max_target_and_lock_step(self) -> None:
        self.customize()
        report = remediation.plan(self.root, self.names)
        serde = next(family for family in report["families"]
                     if family["package"] == "serde")
        self.assertTrue(serde["convergent"])
        self.assertEqual(serde["target"], "1.0.219")
        self.assertEqual(serde["rank"], 1)
        steps = [step for step in report["steps"] if step["package"] == "serde"]
        self.assertEqual(len(steps), 1)
        step = steps[0]
        self.assertEqual(step["scope"], "sotf")
        self.assertEqual(step["command"],
                         ["cargo", "update", "-p", "serde@1.0.210",
                          "--precise", "1.0.219"])
        self.assertEqual(step["cwd"], str(self.root / "sotf"))
        self.assertFalse(step["gpui_owned"])

    def test_incompatible_groups_rank_by_local_parents(self) -> None:
        families = self.families()
        self.assertFalse(families["rand"]["convergent"])
        self.assertEqual(families["rand"]["action"]["type"], "owner_port")
        self.assertEqual(families["rand"]["rank"], 3)
        self.assertEqual(families["bitflags"]["rank"], 3)

    def test_shared_parent_cluster_groups_families(self) -> None:
        self.customize()
        report = remediation.plan(self.root, self.names)
        cluster = next(item for item in report["clusters"]
                       if item["parent"] == "app-core")
        self.assertEqual(cluster["families"], ["rand", "serde"])
        self.assertEqual(cluster["scopes"], ["sotf"])

    def test_manifest_attribution_finds_renames_and_patches(self) -> None:
        families = self.families()
        declarers = {(entry["workspace"], entry["alias"]): entry
                     for entry in families["rand"]["declarers"]}
        renamed = declarers[("sotf", "random")]
        self.assertEqual(renamed["requirement"], "version 0.8")
        self.assertEqual(renamed["section"], "dependencies")
        plain = declarers[("sotf-daw", "rand")]
        self.assertEqual(plain["requirement"], "version 0.9")
        fork_declarers = families["fontconfig-parser"]["declarers"]
        self.assertEqual(len(fork_declarers), 1)
        self.assertEqual(fork_declarers[0]["role"], "source_override")
        self.assertIn("git https://github.com/example/fontconfig-parser.git@abc123",
                      fork_declarers[0]["requirement"])

    def test_lock_edge_quality_issues_are_reported(self) -> None:
        self.customize()
        report = remediation.plan(self.root, self.names)
        codes = {(issue["scope"], issue["code"]) for issue in report["data_quality"]}
        self.assertIn(("sotf", "ambiguous_lock_edge"), codes)
        self.assertIn(("sotf", "unresolved_lock_edge"), codes)

    def test_plan_is_read_only(self) -> None:
        self.customize()
        before = self.snapshot()
        output = self.root / "out" / "report.json"
        self.assertEqual(
            remediation.main(["--root", str(self.root), "--output", str(output)]), 0)
        self.assertTrue(output.is_file())
        after = self.snapshot()
        after.pop("out/report.json")
        self.assertEqual(before, after)

    def test_markdown_covers_families_steps_and_vendors(self) -> None:
        self.customize()
        report = remediation.plan(self.root, self.names)
        text = remediation.render_markdown(report)
        for package in ("rand", "bitflags", "fontconfig-parser", "serde"):
            self.assertIn(package, text)
        self.assertIn("cargo update -p serde@1.0.210 --precise 1.0.219", text)
        self.assertIn("app-core", text)


if __name__ == "__main__":
    unittest.main()
