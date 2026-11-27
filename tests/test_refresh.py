"""Approval transitions over retained original allocations, without timing work."""
import copy
from datetime import datetime, timedelta, timezone
import unittest

from all_policy.performance.refresh import CORE, PREPARED_EXT4, WORKFLOWS, evaluate, validate_index, validate_registry


SOURCE = "a" * 40
DIGEST = "b" * 64
WORKFLOW_DIGEST = "c" * 64
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def run(identity, day, profile=CORE, cohorts=1):
    created = START + timedelta(days=day)
    values = [{"completed_at": stamp(created + timedelta(minutes=10 * (number + 1))),
               "workers": [{"slot": slot, "runner_id": identity * 100 + number * 12 + slot,
                            "outcome": "pass"} for slot in range(1, 13)]}
              for number in range(cohorts)]
    return {"run_id": identity, "workflow": WORKFLOWS[profile], "source_commit": SOURCE,
            "source_digest": DIGEST, "workflow_digest": WORKFLOW_DIGEST, "run_attempt": 1,
            "event": "schedule", "ref": "refs/heads/main", "created_at": stamp(created),
            "started_at": stamp(created + timedelta(minutes=1)),
            "completed_at": stamp(created + timedelta(minutes=10 * cohorts + 2)),
            "cohorts": values, "evidence_path": f"runs/{identity}.json", "evidence_sha256": "d" * 64}


def registry(profile=CORE, qualification=None):
    return {"schema": 1, "profiles": {profile: {
        "source_commit": SOURCE, "source_digest": DIGEST, "workflow": WORKFLOWS[profile],
        "workflow_digest": WORKFLOW_DIGEST,
        "qualification_runs": qualification or ([1, 2] if profile == CORE else [1]),
        "disposition": {"url": "https://github.com/nashspence/all/pull/70",
                        "reason": "Reviewed exact-source qualification and retained first attempts."}}}}


def observed(value, **changes):
    row = {"id": value["run_id"], "path": value["workflow"], "head_sha": value["source_commit"],
           "head_branch": "main", "event": value["event"], "created_at": value["created_at"],
           "status": "completed", "conclusion": "success", "run_attempt": 1}
    row.update(changes)
    return row


class RefreshTests(unittest.TestCase):
    def evaluate(self, runs, *, policy=None, profile=CORE, day=2, live=None, digest=DIGEST):
        return evaluate(policy or registry(profile), {"schema": 1, "runs": runs}, profile,
                        digest, START + timedelta(days=day), observed_runs=live)

    def test_bootstrap_two_cohorts_and_one_environmental_rejection(self):
        rows = [run(1, 0), run(2, 1)]
        rows[0]["cohorts"][0]["workers"][0]["outcome"] = "environment"
        self.assertEqual(self.evaluate(rows)["status"], "active")
        rows[1]["cohorts"][0]["workers"][1]["outcome"] = "environment"
        self.assertEqual(self.evaluate(rows)["status"], "suspended")
        # One prospectively declared bootstrap run may hold two sequential cohorts.
        self.assertEqual(self.evaluate([run(1, 0, cohorts=2)], policy=registry(qualification=[1]))["status"], "active")
        self.assertEqual(self.evaluate([run(1, 0)], policy=registry(qualification=[1]))["status"], "suspended")

    def test_operation_failure_and_missing_evidence_never_consume_allowance(self):
        for outcome in ("failed", "incomplete"):
            with self.subTest(outcome=outcome):
                rows = [run(1, 0), run(2, 1)]
                rows[0]["cohorts"][0]["workers"][0]["outcome"] = outcome
                self.assertEqual(self.evaluate(rows)["status"], "suspended")
        incomplete = run(1, 0)
        incomplete["started_at"] = None
        for worker in incomplete["cohorts"][0]["workers"]:
            worker.update(outcome="incomplete", runner_id=0)
        self.assertEqual(validate_index({"schema": 1, "runs": [incomplete]})["runs"], [incomplete])
        self.assertEqual(self.evaluate([incomplete, run(2, 1)])["status"], "suspended")

    def test_rolling_availability_failure_does_not_age_out(self):
        rows = [run(number, number - 1) for number in range(1, 6)]
        for worker in rows[2]["cohorts"][0]["workers"][:2]:
            worker["outcome"] = "environment"
        result = self.evaluate(rows, day=6)
        self.assertEqual(result["status"], "suspended")
        self.assertTrue(any("availability" in reason for reason in result["reasons"]))
        rows[2]["cohorts"][0]["workers"][0]["outcome"] = "failed"
        self.assertEqual(self.evaluate(rows, day=6)["status"], "suspended")

    def test_freshness_boundary_and_historical_gap_are_binding(self):
        rows = [run(1, 0), run(2, 1)]
        expiry = START + timedelta(days=11, minutes=10)
        index = {"schema": 1, "runs": rows}
        self.assertEqual(evaluate(registry(), index, CORE, DIGEST, expiry)["status"], "active")
        self.assertEqual(evaluate(registry(), index, CORE, DIGEST, expiry + timedelta(microseconds=1))["status"], "suspended")
        rows += [run(3, 12), run(4, 13)]
        self.assertEqual(self.evaluate(rows, day=14)["status"], "suspended")
        # Explicit reviewed fresh qualification starts a new epoch; old evidence stays.
        self.assertEqual(self.evaluate(rows, day=14, policy=registry(qualification=[3, 4]))["status"], "active")

    def test_prepared_storage_keeps_strict_twelve_of_twelve(self):
        rows = [run(1, 0, PREPARED_EXT4)]
        self.assertEqual(self.evaluate(rows, profile=PREPARED_EXT4)["status"], "active")
        rows[0]["cohorts"][0]["workers"][0]["outcome"] = "environment"
        self.assertEqual(self.evaluate(rows, profile=PREPARED_EXT4)["status"], "suspended")

    def test_material_identity_changes_and_exact_qualification_source(self):
        rows = [run(1, 0), run(2, 1), run(3, 2)]
        self.assertEqual(self.evaluate(rows, day=3, digest="f" * 64)["status"], "unapproved")
        self.assertEqual(evaluate({"schema": 1, "profiles": {}}, {"schema": 1, "runs": []}, CORE,
                                  DIGEST, START)["status"], "unapproved")
        rows[2]["source_commit"] = "f" * 40  # Documentation-only commit, identical material digest.
        self.assertEqual(self.evaluate(rows, day=3)["status"], "active")
        rows[0]["source_commit"] = "f" * 40
        self.assertEqual(self.evaluate(rows, day=3)["status"], "suspended")
        rows[0]["source_commit"] = SOURCE
        for key in ("source_digest", "workflow_digest"):
            with self.subTest(key=key):
                changed = copy.deepcopy(rows)
                changed[2][key] = "f" * 64
                self.assertEqual(self.evaluate(changed, day=3)["status"], "suspended")

    def test_original_slot_and_runner_inventory(self):
        base = [run(1, 0), run(2, 1)]
        for mutation in ("slot", "runner", "missing", "run", "attempt"):
            with self.subTest(mutation=mutation):
                rows = copy.deepcopy(base)
                workers = rows[1]["cohorts"][0]["workers"]
                if mutation == "slot":
                    workers[0]["slot"] = workers[1]["slot"]
                elif mutation == "runner":
                    workers[0]["runner_id"] = rows[0]["cohorts"][0]["workers"][0]["runner_id"]
                elif mutation == "missing":
                    workers.pop()
                elif mutation == "run":
                    rows.append(copy.deepcopy(rows[0]))
                else:
                    rows[1]["run_attempt"] = 2
                self.assertEqual(self.evaluate(rows)["status"], "suspended")

    def test_live_inventory_catches_unpublished_completion_and_old_pending(self):
        rows = [run(1, 0), run(2, 1)]
        seen = [observed(row) for row in rows]
        self.assertEqual(self.evaluate(rows, live=seen)["status"], "active")
        pending = observed(run(3, 2), status="in_progress", conclusion=None)
        self.assertEqual(self.evaluate(rows, live=seen + [pending], day=2)["status"], "active")
        self.assertEqual(self.evaluate(rows, live=seen + [pending], day=2.1)["status"], "suspended")
        pending.update(status="completed", conclusion="success")
        self.assertEqual(self.evaluate(rows, live=seen + [pending], day=2)["status"], "suspended")
        self.assertEqual(self.evaluate(rows, live=seen[:1])["status"], "suspended")
        seen[0]["created_at"] = stamp(START + timedelta(minutes=1))
        self.assertEqual(self.evaluate(rows, live=seen)["status"], "suspended")

    def test_later_green_attempt_cannot_replace_failed_original(self):
        rows = [run(1, 0), run(2, 1)]
        rows[1]["cohorts"][0]["workers"][0]["outcome"] = "failed"
        seen = [observed(rows[0]), observed(rows[1], run_attempt=2, conclusion="success")]
        self.assertEqual(self.evaluate(rows, live=seen)["status"], "suspended")
        rows[1]["cohorts"][0]["workers"][0]["outcome"] = "pass"
        # Original completed workers and indexed packets are the completion
        # boundary; an outer status lookup is not another profile measurement.
        self.assertEqual(self.evaluate(rows, live=seen)["status"], "active")
        seen[1].update(run_attempt=1, conclusion="failure")
        self.assertEqual(self.evaluate(rows, live=seen)["status"], "active")
        seen[1]["conclusion"] = "success"
        self.assertEqual(self.evaluate(rows, live=seen)["status"], "active")
        self.assertEqual(self.evaluate(rows[:1], live=seen)["status"], "suspended")

    def test_published_cohort_does_not_recursively_depend_on_its_status_lookup(self):
        rows = [run(1, 0), run(2, 2)]
        seen = [observed(rows[0]), observed(rows[1], status="in_progress", conclusion=None)]
        self.assertEqual(self.evaluate(rows, live=seen, day=2.04)["status"], "active")
        self.assertEqual(self.evaluate(rows, live=seen, day=2.1)["status"], "active")
        seen[1].update(status="completed", conclusion="failure")
        self.assertEqual(self.evaluate(rows, live=seen, day=2.04)["status"], "active")

    def test_durable_history_survives_live_workflow_retention(self):
        rows = [run(1, 0), run(2, 1)] + [run(number, 1 + (number - 2) * 7) for number in range(3, 8)]
        live = [observed(row) for row in rows if row["run_id"] >= 4]
        self.assertEqual(self.evaluate(rows, live=live, day=40)["status"], "active")
        # An old failure remains binding after it no longer appears in the live API.
        rows[2]["cohorts"][0]["workers"][0]["outcome"] = "failed"
        self.assertEqual(self.evaluate(rows, live=live, day=40)["status"], "suspended")

    def test_strict_declarations_and_no_cherry_picked_qualification(self):
        baseline = registry()
        for mutation in ("bool", "unknown", "review", "duplicate"):
            changed = copy.deepcopy(baseline)
            entry = changed["profiles"][CORE]
            if mutation == "bool":
                entry["qualification_runs"] = [True, 2]
            elif mutation == "unknown":
                entry["tolerance"] = 12
            elif mutation == "review":
                entry["disposition"]["reason"] = " "
            else:
                entry["qualification_runs"] = [1, 1]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_registry(changed)
        rows = [run(1, 0), run(2, 1), run(3, 2)]
        self.assertEqual(self.evaluate(rows, day=3, policy=registry(qualification=[1, 3]))["status"], "suspended")
        rows[1]["cohorts"][0]["workers"][0]["slot"] = True
        with self.assertRaises(ValueError):
            validate_index({"schema": 1, "runs": rows})


if __name__ == "__main__":
    unittest.main()
