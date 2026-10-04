"""Root checkout guard examples for the scoped macOS QA workflow."""

from unittest.mock import patch

from scripts.release.mac_safe_full_qa import root_checkout_status
from scripts.release.qa import source_issues


PINS = {"autoeq": "a" * 40, "sotf": "b" * 40}


def status(body: str) -> dict:
    with patch("scripts.release.mac_safe_full_qa.subprocess.check_output", return_value=body):
        return root_checkout_status(PINS)


def test_mac_safe_checkout_accepts_only_named_sibling_directories() -> None:
    result = status("?? autoeq/\n?? sotf/\n")
    assert result["allowed_sibling_checkouts"] == ["?? autoeq/", "?? sotf/"]
    assert result["unexpected_root_paths"] == []
    assert result["missing_sibling_checkouts"] == []


def test_mac_safe_checkout_rejects_unknown_root_directory() -> None:
    result = status("?? autoeq/\n?? sotf/\n?? extra-source/\n")
    assert result["unexpected_root_paths"] == ["?? extra-source/"]


def test_mac_safe_checkout_rejects_tracked_root_change() -> None:
    result = status("?? autoeq/\n?? sotf/\n M scripts/release/sources.json\n")
    assert result["unexpected_root_paths"] == [" M scripts/release/sources.json"]


def test_mac_safe_checkout_does_not_hide_dirty_sibling() -> None:
    result = status("?? autoeq/\n?? sotf/\n")
    assert result["unexpected_root_paths"] == []
    child = {"revision": PINS["autoeq"], "dirty": True,
             "lock_sha256": "lock", "nested_lock_sha256": "nested"}
    assert source_issues({"autoeq": child}, {"autoeq": child}, True) == [
        "autoeq: source tree was dirty before validation"
    ]
