import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.interviewer import Interview, load, save

NAME = "tidy-imports"
PURPOSE = "Rewrites import blocks in Python files for developers."
TRIGGERS = ["clean up the imports in foo.py", "sort my import statements", ""]
NON_TRIGGERS = ["write new features", ""]
INPUTS = "A Python file path."
POLICY = "scoped"
VERIFICATION = ["imports are sorted and grouped", "no unused imports remain", ""]
BOUNDARIES = ["will not change function bodies", ""]
HAPPY = [NAME, PURPOSE, *TRIGGERS, *NON_TRIGGERS, INPUTS, POLICY, *VERIFICATION, *BOUNDARIES]


class HappyPathTests(unittest.TestCase):
    def test_scripted_answers_yield_complete_valid_spec(self):
        spec = Interview(answers=list(HAPPY)).run()
        self.assertEqual(spec.name, NAME)
        self.assertEqual(spec.purpose, PURPOSE)
        self.assertEqual(spec.triggers, TRIGGERS[:-1])
        self.assertEqual(spec.non_triggers, NON_TRIGGERS[:-1])
        self.assertEqual(spec.inputs, INPUTS)
        self.assertEqual(spec.mutation_policy, POLICY)
        self.assertEqual(spec.verification, VERIFICATION[:-1])
        self.assertEqual(spec.boundaries, BOUNDARIES[:-1])
        self.assertEqual(spec.open_questions, [])
        spec.validate()


class GrillingTests(unittest.TestCase):
    def test_bad_name_twice_then_good(self):
        answers = ["My Skill", "BAD_NAME!", NAME, PURPOSE, *TRIGGERS, *NON_TRIGGERS,
                   INPUTS, POLICY, *VERIFICATION, *BOUNDARIES]
        spec = Interview(answers=answers).run()
        self.assertEqual(spec.name, NAME)
        self.assertEqual(spec.open_questions, [])
        spec.validate()

    def test_bad_mutation_policy_three_times_defaults_read_only(self):
        answers = [NAME, PURPOSE, *TRIGGERS, *NON_TRIGGERS, INPUTS,
                   "fast", "auto", "yolo", *VERIFICATION, *BOUNDARIES]
        spec = Interview(answers=answers).run()
        self.assertEqual(spec.mutation_policy, "read_only")
        self.assertEqual(
            len([q for q in spec.open_questions if q.startswith("unresolved mutation_policy:")]), 1)
        spec.validate()

    def test_missing_verification_deferred_to_open_questions(self):
        answers = [NAME, PURPOSE, *TRIGGERS, *NON_TRIGGERS, INPUTS, POLICY,
                   "", "", "", *BOUNDARIES]
        spec = Interview(answers=answers).run()
        self.assertEqual(spec.verification, [])
        self.assertEqual(
            len([q for q in spec.open_questions if q.startswith("unresolved verification:")]), 1)

class PersistenceTests(unittest.TestCase):
    def test_save_load_round_trip_resumes_and_completes(self):
        prefix = [NAME, PURPOSE, *TRIGGERS, *NON_TRIGGERS, INPUTS, POLICY]
        rest = [*VERIFICATION, *BOUNDARIES]
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            first = Interview(answers=list(prefix))
            partial = first.run()
            self.assertEqual(partial.name, NAME)
            self.assertEqual(partial.mutation_policy, POLICY)
            save(state, first)

            resumed = load(state)
            self.assertEqual(resumed.spec.name, NAME)
            self.assertEqual(resumed.spec.triggers, TRIGGERS[:-1])
            resumed.answers = list(rest)
            spec = resumed.run()
            self.assertEqual(spec.verification, VERIFICATION[:-1])
            self.assertEqual(spec.boundaries, BOUNDARIES[:-1])
            self.assertEqual(spec.open_questions, [])
            spec.validate()


if __name__ == "__main__":
    unittest.main()
