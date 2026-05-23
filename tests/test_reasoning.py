from __future__ import annotations

import unittest

from runtime.reasoning import (
    REASONING_BUDGETS,
    normalize_reasoning_effort,
    reasoning_budget,
)


class TestReasoningStandards(unittest.TestCase):
    def test_normalizes_chinese_shortcuts(self):
        self.assertEqual(normalize_reasoning_effort("低"), "low")
        self.assertEqual(normalize_reasoning_effort("中"), "medium")
        self.assertEqual(normalize_reasoning_effort("高"), "high")

    def test_normalizes_english_values(self):
        self.assertEqual(normalize_reasoning_effort(" LOW "), "low")
        self.assertEqual(normalize_reasoning_effort("medium"), "medium")
        self.assertEqual(normalize_reasoning_effort("high"), "high")

    def test_rejects_unknown_value(self):
        with self.assertRaises(ValueError):
            normalize_reasoning_effort("deeper")

    def test_budget_standards_are_explicit(self):
        self.assertEqual(REASONING_BUDGETS, {"low": 1000, "medium": 4000, "high": 8000})
        self.assertEqual(reasoning_budget("高"), 8000)
        self.assertEqual(reasoning_budget(None), 4000)


if __name__ == "__main__":
    unittest.main()
