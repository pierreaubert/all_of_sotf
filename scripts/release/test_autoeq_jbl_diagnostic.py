"""Parser checks for the expected-red JBL candidate evidence."""
import unittest

from scripts.release.autoeq_jbl_diagnostic import candidate_evidence


def log() -> str:
    return (
        "DE maxeval=100000 with population_size=300 and fresh initialization cost 301 "
        "is below the floor. Running 332 generations (≈99901 evals)\n"
        "ERROR rejected PEQ candidate autoeq:de: model=HpPk max_db=6 min_db=0 "
        "required_spacing=0.2 raw_ceiling=0 projected_ceiling=0.00001254 "
        "final_ceiling=0.00001254 final_spacing=0 final_min_gain=0 final_loss=92.1 "
        "raw=[1.0, 2.0] projected=[1.1, 2.0] finalized=[1.1, 2.0] "
        "lower=[0.0, 0.0] upper=[4.0, 4.0]\n"
        "Optimization failed: spacing repair refused: within_bounds=true, "
        "spacing=0, ceiling=0.00001254, min_gain=0\n"
    )


class CandidateEvidenceTests(unittest.TestCase):
    def test_exact_red_candidate_and_budget(self):
        result = candidate_evidence(log())
        self.assertEqual(result["vector_length"], 2)
        self.assertEqual(result["declared_budget"][0], "100000")
        self.assertGreater(result["constraint_residuals"]["final_ceiling"], 0)

    def test_missing_or_duplicate_vector_row_rejected(self):
        for transcript in (log().replace("raw=[1.0, 2.0]", ""),
                           log() + log().splitlines()[1] + "\n"):
            with self.subTest(transcript=transcript), self.assertRaises(ValueError):
                candidate_evidence(transcript)

    def test_nonfinite_or_nonpositive_ceiling_rejected(self):
        for transcript in (log().replace("final_ceiling=0.00001254", "final_ceiling=NaN"),
                           log().replace("final_ceiling=0.00001254", "final_ceiling=0")):
            with self.subTest(transcript=transcript), self.assertRaises(ValueError):
                candidate_evidence(transcript)

    def test_budget_and_original_refusal_cannot_be_waived(self):
        for transcript in (log().replace("maxeval=100000", "maxeval=150000"),
                           log().replace("≈99901 evals", "≈150001 evals"),
                           log().replace("spacing repair refused", "accepted")):
            with self.subTest(transcript=transcript), self.assertRaises(ValueError):
                candidate_evidence(transcript)
