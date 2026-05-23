import subprocess
import sys
import unittest


class EvaluateClassifierTest(unittest.TestCase):
    def test_evaluate_classifier_help_runs(self):
        result = subprocess.run(
            [sys.executable, "tools/evaluate_classifier.py", "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Evaluate classifier", result.stdout)
