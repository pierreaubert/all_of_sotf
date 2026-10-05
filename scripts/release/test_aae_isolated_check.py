"""Positive AAE QA inventory and original threshold checks."""
import unittest

from scripts.release.aae_isolated_check import qa_result

LABELS = ["Reverb Tail", "Channel Energy Distribution", "RT60 Parameter",
          "12-channel processing", "Bypass Transparency", "No NaN/Inf",
          "Energy Bounded", "Latency", "Zero Allocations", "Performance"]


def transcript(cpu: float = 4.2) -> str:
    rows = []
    for index, label in enumerate(LABELS, 1):
        rows.extend((f"[Test {index}] original QA section", f"  {label}: PASS"))
    rows.extend((f"  Estimated CPU Usage: {cpu:.2f}%",
                 "  callback p50/p95/max: 0.4/0.6/1.2 ms (deadline 10.667 ms)"))
    return "\n".join(rows) + "\n"


class AaeInventoryTests(unittest.TestCase):
    def test_ten_exact_positive_tests_and_original_thresholds(self):
        result = qa_result(transcript())
        self.assertEqual(result["pass_labels"], LABELS)
        self.assertEqual(len(result["tests"]), 10)

    def test_missing_or_replaced_test_fails(self):
        for log in (transcript().replace("[Test 10]", "[Test 11]"),
                    transcript().replace("  Performance: PASS\n", "")):
            with self.subTest(log=log), self.assertRaises(ValueError):
                qa_result(log)

    def test_duplicate_or_failed_test_fails(self):
        for log in (transcript().replace("[Test 9]", "[Test 8]"),
                    transcript().replace("  Reverb Tail: PASS", "  Reverb Tail: FAIL")):
            with self.subTest(log=log), self.assertRaises(ValueError):
                qa_result(log)

    def test_original_cpu_and_callback_limits_fail(self):
        for log in (transcript(5.0),
                    transcript().replace("0.4/0.6/1.2", "0.4/0.6/10.667")):
            with self.subTest(log=log), self.assertRaises(ValueError):
                qa_result(log)
