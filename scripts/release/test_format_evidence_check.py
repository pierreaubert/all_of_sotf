"""Guard the exact gitlink and tracked-blob changes permitted for rustfmt evidence."""
from __future__ import annotations

import copy
import unittest

from scripts.release.format_evidence_check import format_errors

NAMES = ("autoeq", "gpui-toolkit", "math-audio", "sotf", "sotf-capture",
         "sotf-daw", "sotf-systemwide", "sofa-reader", "symphonia-add-ons")
PINS = {name: name + "-revision" for name in NAMES}
HEX_A = "a" * 64
HEX_B = "b" * 64


def fixture(changed: str | None = None) -> tuple[dict, dict, list[dict]]:
    workspaces = {name: {"revision": PINS[name], "dirty": False,
                         "lock_sha256": HEX_A,
                         "nested_lock_sha256": HEX_A if name == "autoeq" else None}
                  for name in NAMES}
    layout = {"missing": [], "allowed_siblings": [],
              "tracked_gitlinks": sorted(NAMES), "unexpected": []}
    before = {"root_revision": "root-revision", "manifest_sha256": HEX_A,
              "root_layout": layout, "workspaces": workspaces}
    after = copy.deepcopy(before)
    patches = [{"workspace": name, "paths": [], "tracked_blobs": []} for name in NAMES]
    if changed:
        after["root_layout"]["unexpected"] = [f" M {changed}"]
        after["workspaces"][changed]["dirty"] = True
        patch = next(item for item in patches if item["workspace"] == changed)
        patch["paths"] = ["src/lib.rs"]
        patch["tracked_blobs"] = [{"path": "src/lib.rs", "before_sha256": HEX_A,
                                   "after_sha256": HEX_B}]
    return before, after, patches


class FormatGuardTests(unittest.TestCase):
    def test_clean_noop_and_exact_formatted_gitlink(self):
        for owner in (None, *NAMES):
            with self.subTest(owner=owner):
                self.assertEqual(format_errors(*fixture(owner)[:2], PINS, fixture(owner)[2]), [])

    def test_all_nine_formatting_owners_require_exact_dirty_gitlinks(self):
        before, after, patches = fixture()
        after["root_layout"]["unexpected"] = ["M " + NAMES[0], *(" M " + name for name in NAMES[1:])]
        for name in NAMES:
            after["workspaces"][name]["dirty"] = True
            patch = next(item for item in patches if item["workspace"] == name)
            patch["paths"] = ["src/lib.rs"]
            patch["tracked_blobs"] = [{"path": "src/lib.rs", "before_sha256": HEX_A,
                                        "after_sha256": HEX_B}]
        self.assertEqual(format_errors(before, after, PINS, patches), [])
        after["root_layout"]["unexpected"].pop()
        self.assertTrue(format_errors(before, after, PINS, patches))

    def test_root_and_staged_gitlink_changes_rejected(self):
        before, after, patches = fixture("sotf-capture")
        for unexpected in (["M  sotf-capture"], ["m sotf-capture"],
                           ["M  docs/plan.md"], ["?? rogue/"],
                           ["AM sotf-capture"], [" M rogue"], []):
            candidate = copy.deepcopy(after)
            candidate["root_layout"]["unexpected"] = unexpected
            self.assertTrue(format_errors(before, candidate, PINS, patches))
        candidate = copy.deepcopy(after)
        candidate["root_revision"] = "new-root"
        self.assertTrue(format_errors(before, candidate, PINS, patches))
        candidate = copy.deepcopy(after)
        candidate["root_layout"]["unexpected"] = [" M sotf-capture", " M sotf-capture"]
        self.assertTrue(format_errors(before, candidate, PINS, patches))

    def test_unpinned_child_and_wrong_owner_rejected(self):
        before, after, patches = fixture("sotf-capture")
        candidate = copy.deepcopy(after)
        candidate["workspaces"]["sotf-capture"]["revision"] = "other"
        self.assertTrue(format_errors(before, candidate, PINS, patches))
        before, after, patches = fixture("sotf")
        next(item for item in patches if item["workspace"] == "sotf")["workspace"] = "rogue"
        self.assertTrue(format_errors(before, after, PINS, patches))

    def test_non_rust_and_blob_inventory_tampering_rejected(self):
        before, after, patches = fixture("sotf-capture")
        changed = next(item for item in patches if item["workspace"] == "sotf-capture")
        changed["paths"] = ["Cargo.toml"]
        self.assertTrue(format_errors(before, after, PINS, patches))
        changed["paths"] = ["src/lib.rs"]
        changed["tracked_blobs"][0]["after_sha256"] = HEX_A
        self.assertTrue(format_errors(before, after, PINS, patches))

    def test_lock_and_child_dirty_must_match_patch(self):
        before, after, patches = fixture("sotf-capture")
        candidate = copy.deepcopy(after)
        candidate["workspaces"]["sotf-capture"]["lock_sha256"] = HEX_B
        self.assertTrue(format_errors(before, candidate, PINS, patches))
        candidate = copy.deepcopy(after)
        candidate["workspaces"]["sotf-capture"]["dirty"] = False
        self.assertTrue(format_errors(before, candidate, PINS, patches))


if __name__ == "__main__":
    unittest.main()
