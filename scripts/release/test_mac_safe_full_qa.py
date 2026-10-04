"""Root checkout guard examples for the scoped macOS QA workflow."""

from unittest.mock import patch

from scripts.release import checkout_sources
from scripts.release.mac_safe_full_qa import root_checkout_status
from scripts.release.qa import source_issues


PINS = {"autoeq": "a" * 40, "sotf": "b" * 40}


def status(body: str, indexed: dict[str, str | None]) -> dict:
    with patch.object(checkout_sources, "git", return_value=body), patch.object(
        checkout_sources, "gitlink_revision", side_effect=lambda _root, name: indexed[name]
    ):
        return root_checkout_status(PINS)


def test_mac_safe_checkout_accepts_exact_tracked_gitlinks() -> None:
    result = status("", PINS)
    assert result == {"allowed_siblings": [], "tracked_gitlinks": ["autoeq", "sotf"],
                      "missing": [], "unexpected": []}


def test_mac_safe_checkout_rejects_mismatched_gitlink() -> None:
    result = status("", {"autoeq": "c" * 40, "sotf": PINS["sotf"]})
    assert result["missing"] == ["autoeq: root gitlink pin mismatch"]


def test_mac_safe_checkout_rejects_missing_tracked_gitlink() -> None:
    result = status(" D autoeq", PINS)
    assert result["unexpected"] == [" D autoeq"]


def test_mac_safe_checkout_accepts_only_named_legacy_sibling_directories() -> None:
    result = status("?? autoeq/\n?? sotf/", dict.fromkeys(PINS))
    assert result["allowed_siblings"] == ["?? autoeq/", "?? sotf/"]
    assert result["tracked_gitlinks"] == []
    assert result["missing"] == result["unexpected"] == []


def test_mac_safe_checkout_rejects_unknown_root_directory() -> None:
    result = status("?? autoeq/\n?? sotf/\n?? extra-source/", dict.fromkeys(PINS))
    assert result["unexpected"] == ["?? extra-source/"]


def test_mac_safe_checkout_rejects_tracked_root_change() -> None:
    result = status(" M scripts/release/sources.json", PINS)
    assert result["unexpected"] == [" M scripts/release/sources.json"]


def test_mac_safe_checkout_does_not_hide_dirty_sibling() -> None:
    result = status("", PINS)
    assert result["unexpected"] == []
    child = {"revision": PINS["autoeq"], "dirty": True,
             "lock_sha256": "lock", "nested_lock_sha256": "nested"}
    assert source_issues({"autoeq": child}, {"autoeq": child}, True) == [
        "autoeq: source tree was dirty before validation"
    ]
