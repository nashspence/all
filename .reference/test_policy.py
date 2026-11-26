"""Small deterministic witnesses; illustrative numbers, no host qualification."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from all_policy.performance.contracts import Limit, evaluate, load_authority
from all_policy.performance.profiles import CORE
from policy import FEATURES, compile_limits, require_activity, require_selections


def plan():
    # Tiny invented nanoseconds make arithmetic visible; never product limits.
    return compile_limits("publish", CORE, 100,
                          dict(progress=10, resumability=20, logging=30))


def raw(values):
    return [dict(elapsed_ns=n, completed=True, verified=True) for n in values]


def synthetic_operation(root, enabled, *, omit=None, leaked=None):
    # One useful operation with observable optional events, not a benchmark.
    (root / "result").write_bytes(b"complete core result")
    for feature in FEATURES:
        if (feature in enabled and feature != omit) or feature == leaked:
            (root / feature).write_bytes(b"completed event\n")


def independently_verify(root):
    if (root / "result").read_bytes() != b"complete core result":
        raise AssertionError("required result is missing")
    return {feature: len((root / feature).read_bytes().splitlines())
            if (root / feature).exists() else 0 for feature in FEATURES}


class Allowances(unittest.TestCase):
    def test_compiles_only_core_singletons_and_combined_configuration(self):
        limits, selections = plan()
        self.assertEqual({name: row["max_wall_ns"]
                          for name, row in limits["operations"].items()}, {
            "publish_core": 100, "publish_progress": 110,
            "publish_resumability": 120, "publish_logging": 130,
            "publish_all": 160,
        })
        self.assertEqual(selections["publish_core"], ())
        self.assertEqual(selections["publish_progress"], ("progress",))
        self.assertEqual(selections["publish_all"], FEATURES)
        _, one = compile_limits("read", CORE, 100,
                                dict(progress=None, resumability=None, logging=30))
        self.assertEqual(one, {"read_core": (), "read_logging": ("logging",)})
        _, none = compile_limits("read", CORE, 100, dict.fromkeys(FEATURES))
        self.assertEqual(none, {"read_core": ()})
        zero, zero_selections = compile_limits(
            "read", CORE, 100, dict(progress=0, resumability=None, logging=None))
        self.assertEqual(zero["operations"]["read_progress"]["max_wall_ns"], 100)
        self.assertEqual(zero_selections["read_progress"], ("progress",))

    def test_no_pooled_or_unconsidered_feature_allowance(self):
        for amounts in ({"optional": 60}, {"progress": 10, "logging": 30},
                        dict(progress=10, resumability=-1, logging=30),
                        dict(progress=True, resumability=20, logging=30)):
            with self.subTest(amounts=amounts), self.assertRaises(ValueError):
                compile_limits("publish", CORE, 100, amounts)

    def test_binding_cannot_omit_case_or_mislabel_all_as_one_feature(self):
        _, expected = plan()
        require_selections(expected, deepcopy(expected))
        missing = deepcopy(expected)
        del missing["publish_all"]
        false_all = deepcopy(expected)
        false_all["publish_all"] = ("logging",)
        overenabled = deepcopy(expected)
        overenabled["publish_progress"] = FEATURES
        for bound in (missing, false_all, overenabled):
            with self.subTest(bound=bound), self.assertRaises(ValueError):
                require_selections(expected, bound)

    def test_real_fixture_activity_exposes_untriggered_and_disabled_work(self):
        for enabled in ((), ("resumability",), FEATURES):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                synthetic_operation(root, enabled)
                require_activity(enabled, independently_verify(root))
        for enabled, mutation in ((FEATURES, {"omit": "resumability"}),
                                  ((), {"leaked": "logging"})):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                synthetic_operation(root, enabled, **mutation)
                with self.assertRaises(ValueError):
                    require_activity(enabled, independently_verify(root))
        with self.assertRaises(ValueError):
            require_activity(FEATURES, dict.fromkeys(FEATURES, True))

    def test_shared_raw_rule_retains_miss_and_rejects_unused_allowance_pool(self):
        limits, _ = plan()
        progress = Limit(**limits["operations"]["publish_progress"])
        admitted = {"admitted": True, "profile": CORE}
        result = evaluate(progress, admitted, raw([100, 111, 100]))
        self.assertEqual(result["verdict"], "miss")
        self.assertEqual(result["samples_ns"], [100, 111, 100])
        self.assertLess(result["raw_mean_ns"], progress.max_wall_ns)
        self.assertEqual(evaluate(progress, admitted, raw([125] * 3))["verdict"], "miss")
        combined = Limit(**limits["operations"]["publish_all"])
        self.assertEqual(evaluate(combined, admitted, raw([125] * 3))["verdict"], "pass")
        self.assertEqual(evaluate(progress, admitted, raw([100] * 2))["verdict"], "failed")
        self.assertEqual(evaluate(progress, {}, raw([100] * 3))["verdict"], "unqualified")

    def test_configuration_pass_does_not_establish_marginal_feature_cap(self):
        limits, _ = plan()
        progress = Limit(**limits["operations"]["publish_progress"])
        # Core 20 + feature 50 fits C=100 plus P=10: this is not a 10 ns feature proof.
        result = evaluate(progress, {"admitted": True, "profile": CORE}, raw([70] * 3))
        self.assertEqual(result["verdict"], "pass")
        self.assertGreater(50, 10)

    def test_generated_schema_uses_existing_approved_git_object_loader(self):
        limits, _ = plan()
        env = {"PATH": os.environ["PATH"], "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(
                    ["git", "-c", "init.defaultBranch=main", "-c", "core.hooksPath=/dev/null",
                     "-c", "commit.gpgsign=false", "-c", "user.name=Proffer",
                     "-c", "user.email=proffer@example.invalid", "-C", str(root), *args],
                    env=env, text=True, stderr=subprocess.DEVNULL).strip()
            git("init", "--quiet")
            witness = b"# Synthetic binding-loading fixture; never timed.\n"
            (root / "witness.py").write_bytes(witness)
            binding = dict(mode="command", unit="synthetic complete unit",
                           completion="foreground command exit with no deferred work",
                           approved_files={"witness.py": hashlib.sha256(witness).hexdigest()},
                           command=["{python}", "{subject}/witness.py"],
                           verify=["{python}", "{subject}/witness.py"])
            folder = root / ".all/performance"
            folder.mkdir(parents=True)
            (folder / "limits.json").write_text(json.dumps(limits))
            (folder / "bindings.json").write_text(json.dumps({
                "schema": 1, "repository": "nashspence/all",
                "operations": {name: binding for name in limits["operations"]}}))
            git("add", ".")
            git("commit", "--quiet", "-m", "Synthetic independent authority")
            revision = git("rev-parse", "HEAD")
            limits["operations"]["publish_progress"]["max_wall_ns"] = 999
            (folder / "limits.json").write_text(json.dumps(limits))
            authority = load_authority(root, revision, "nashspence/all")
            self.assertEqual(authority.limits["publish_progress"].max_wall_ns, 110)


if __name__ == "__main__":
    unittest.main()
