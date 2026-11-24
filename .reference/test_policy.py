import unittest

from policy import Page, require_complete


def reader(values, batch=3, cap=None):
    def fetch(cursor):
        start = 0 if cursor is None else int(cursor)
        stop = min(start + batch, len(values))
        next_cursor = str(stop) if stop < len(values) else None
        if cap is not None and stop >= cap:
            next_cursor = None
        return Page(tuple(values[start:stop]), next_cursor)
    return fetch


class ExtentTests(unittest.TestCase):
    def test_one_batch_bound_handles_larger_total_extents(self):
        for total in [0, 1, 3, 4, 37]:
            values = [f"item-{i}" for i in range(total)]
            with self.subTest(total=total):
                self.assertEqual(require_complete(values, reader(values)), total)

    def test_hidden_total_cap_and_missing_final_page_fail(self):
        values = [f"item-{i}" for i in range(11)]
        with self.assertRaisesRegex(AssertionError, "missing"):
            require_complete(values, reader(values, cap=6))

    def test_retries_remain_owner_owned_without_losing_or_duplicating_results(self):
        values = [f"item-{i}" for i in range(11)]
        raw = reader(values)
        attempts = {}

        def fetch(cursor):
            # The owner retries the same continuation after a transient failure.
            for attempt in range(2):
                attempts[cursor] = attempts.get(cursor, 0) + 1
                if cursor == "3" and attempt == 0:
                    continue
                return raw(cursor)
            raise AssertionError("unreachable")

        self.assertEqual(require_complete(values, fetch), len(values))
        self.assertEqual(attempts["3"], 2)

    def test_duplicates_unknown_ids_and_cursor_cycles_fail(self):
        for pages in [
            {None: Page(("a", "a"), None)},
            {None: Page(("wrong",), None)},
            {None: Page(("a",), "next"), "next": Page((), "next")},
        ]:
            with self.subTest(pages=pages), self.assertRaises(AssertionError):
                require_complete(["a"], pages.__getitem__)


if __name__ == "__main__":
    unittest.main()
