import unittest

from policy import public_text_violations

PUBLIC = "noreply@openai.com"
FOOTER = f"Co-authored-by: OpenAI <{PUBLIC}>"


def owner_scan(text):
    return ("locally-restricted-address",) if PUBLIC in text else ()


class PublicTextBoundaryTests(unittest.TestCase):
    def check(self, text, context="commit-message", private=(), scanner=owner_scan):
        return public_text_violations(
            text,
            context=context,
            private_literals=private,
            approved_coauthor_addresses=frozenset({PUBLIC}),
            inspect_remaining=scanner,
        )

    def test_exact_approved_final_coauthor_footer_is_accepted(self):
        self.assertEqual(self.check("Fix current behavior\n\n" + FOOTER), ())

    def test_source_does_not_receive_a_commit_metadata_exemption(self):
        self.assertEqual(self.check("Example\n\n" + FOOTER, context="source"), ("locally-restricted-address",))

    def test_same_address_elsewhere_in_the_message_remains_visible(self):
        self.assertEqual(self.check("Contact: " + PUBLIC + "\n\n" + FOOTER), ("locally-restricted-address",))

    def test_private_identifier_check_precedes_public_metadata_exception(self):
        self.assertEqual(self.check("Fix\n\n" + FOOTER, private=("OpenAI",)), ("private-identifier",))
        self.assertEqual(self.check("Fix\n\n" + FOOTER, private=(PUBLIC,)), ("private-identifier",))

    def test_adjacent_private_data_is_not_removed_with_public_footer(self):
        text = "Fix\n\n" + FOOTER + "\nReviewed-by: person@private.example"
        self.assertEqual(self.check(text, private=("person@private.example",)), ("private-identifier",))

    def test_display_name_is_still_passed_to_the_owner_scanner(self):
        scanner = lambda text: ("unapproved-display",) if "unapproved" in text else ()
        self.assertEqual(self.check("Fix\n\n" + FOOTER.replace("OpenAI", "unapproved"), scanner=scanner), ("unapproved-display",))

    def test_nonfinal_or_malformed_footer_does_not_gain_an_exception(self):
        for text in ["Fix\n\n" + FOOTER + "\n\nMore prose", "Fix\n\n" + FOOTER + "\nNot a trailer", FOOTER]:
            with self.subTest(text=text):
                self.assertEqual(self.check(text), ("locally-restricted-address",))

    def test_unrelated_public_names_and_addresses_are_not_globally_prohibited(self):
        self.assertEqual(self.check("Public contact: developer@example.org", context="source"), ())

    def test_another_public_address_is_not_silently_exempted(self):
        alternate = "somebody@openai.com"
        scanner = lambda text: ("owner-address-rule",) if alternate in text else ()
        self.assertEqual(self.check("Fix\n\nCo-authored-by: OpenAI <" + alternate + ">", scanner=scanner), ("owner-address-rule",))


if __name__ == "__main__":
    unittest.main()
