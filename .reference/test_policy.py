import unittest

from policy import check_linux_runners, declared_ubuntu_lanes


class LinuxBaselineTests(unittest.TestCase):
    def test_explicit_generation_passes(self):
        self.assertEqual(check_linux_runners({"unit": "ubuntu-24.04"}), [])

    def test_latest_and_other_generation_fail(self):
        for label in ("ubuntu-latest", "ubuntu-22.04"):
            self.assertTrue(check_linux_runners({"unit": label}))

    def test_unresolved_selected_lane_is_not_success(self):
        self.assertTrue(check_linux_runners({"unit": "${{ matrix.os }}"}))

    def test_platform_qualification_is_preserved(self):
        text = """jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-24.04, macos-15, windows-2025]
"""
        self.assertEqual(declared_ubuntu_lanes(text), {"test.matrix.os[0]": "ubuntu-24.04"})
        self.assertEqual(check_linux_runners(declared_ubuntu_lanes(text)), [])

    def test_exact_abi_exception(self):
        rule = {"observed": "ubuntu-22.04", "reason": "The lane qualifies the supported older glibc baseline.",
                "revisit_when": "That supported ABI is retired."}
        self.assertEqual(check_linux_runners({"abi": "ubuntu-22.04"}, {"abi": rule}), [])
        self.assertTrue(check_linux_runners({"abi": "ubuntu-latest"}, {"abi": rule}))

    def test_stale_unknown_or_unexplained_exception_fails(self):
        self.assertTrue(check_linux_runners({"x": "ubuntu-24.04"}, {"x":
            {"observed": "ubuntu-24.04", "reason": "x", "revisit_when": "y"}}))
        self.assertTrue(check_linux_runners({}, {"x": {}}))
        self.assertTrue(check_linux_runners({"x": "ubuntu-22.04"}, {"x":
            {"observed": "ubuntu-22.04", "reason": "", "revisit_when": "y"}}))

    def test_unresolved_matrix_and_duplicate_yaml_fail(self):
        with self.assertRaises(ValueError):
            declared_ubuntu_lanes("jobs: {test: {runs-on: '${{ matrix.os }}', strategy: {matrix: dynamic}}}")
        with self.assertRaises(ValueError):
            declared_ubuntu_lanes("jobs: {}\njobs: {}")


if __name__ == "__main__":
    unittest.main()
