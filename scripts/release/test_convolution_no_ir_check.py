from __future__ import annotations

import unittest

from scripts.release.convolution_no_ir_check import clap_state_positives, rust_positive, STATE


class InventoryTests(unittest.TestCase):
    def test_exact_rust_positive(self) -> None:
        name = "params::convolution_no_ir_restore_tests::dry_state_restore_publishes_mix_and_gain_without_pending_resource"
        log = f"running 1 test\ntest {name} ... ok\ntest result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 120 filtered out\n"
        self.assertTrue(rust_positive(log, name))
        self.assertFalse(rust_positive(log.replace("1 passed", "0 passed"), name))
        self.assertFalse(rust_positive(log.replace("0 ignored", "1 ignored"), name))
        self.assertFalse(rust_positive(log + "test unexpected ... ok\n", name))

    def test_three_strict_clap_state_positives(self) -> None:
        log = "\n".join(f"INFO Test {name} completed" for name in STATE)
        self.assertTrue(clap_state_positives(log))
        self.assertFalse(clap_state_positives(log.replace(f"Test {STATE[0]} completed", f"Test {STATE[0]} failed")))
        self.assertFalse(clap_state_positives(log.replace(f"Test {STATE[1]} completed", "")))
        self.assertFalse(clap_state_positives(log + f"\nTest {STATE[2]} completed"))


if __name__ == "__main__":
    unittest.main()
