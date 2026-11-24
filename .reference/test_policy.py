from dataclasses import replace
import unittest

from policy import Shard, plan_identity, require_partition


class PartitionTests(unittest.TestCase):
    def setUp(self):
        self.collected = ("first[0]", "first[1]", "last")
        self.assignments = {"left": self.collected[:2], "right": self.collected[2:]}
        self.origins = {"left": "run-5/attempt-1/job-left", "right": "run-5/attempt-2/job-right"}
        self.plan = plan_identity("commit", "python-exact/linux", self.assignments)
        self.shards = tuple(
            Shard(name, "commit", "python-exact/linux", self.plan, self.origins[name], cases)
            for name, cases in self.assignments.items()
        )

    def check(self, shards=None, collected=None, assignments=None):
        require_partition(
            self.collected if collected is None else collected,
            self.assignments if assignments is None else assignments,
            self.shards if shards is None else shards,
            source="commit", conditions="python-exact/linux", accepted_origins=self.origins,
        )

    def test_exact_shards_with_independently_accepted_reused_job_origins_pass(self):
        self.check()

    def test_new_collected_case_and_overlapping_assignment_cannot_disappear(self):
        with self.assertRaises(ValueError):
            self.check(collected=(*self.collected, "added"))
        with self.assertRaises(ValueError):
            self.check(assignments={"left": self.collected, "right": ("last",)})

    def test_missing_duplicate_and_unexecuted_shard_cases_fail(self):
        for shards in [self.shards[:1], (*self.shards, self.shards[0]),
                       (replace(self.shards[0], cases=("first[0]",)), self.shards[1])]:
            with self.subTest(shards=shards), self.assertRaises(ValueError):
                self.check(shards=shards)

    def test_equal_counts_do_not_hide_replaced_cases_or_provenance_drift(self):
        for changes in [
            {"cases": ("first[0]", "unknown")}, {"source": "other"},
            {"conditions": "python-other/linux"}, {"plan": "old"},
            {"origin": "unreviewed-run/job-left"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.check(shards=(replace(self.shards[0], **changes), self.shards[1]))


if __name__ == "__main__":
    unittest.main()
