"""Licence class and distribution requirement are two facts, and neither reads the other (0068).

These are the unit tests of the admission contract itself: one classification, fail-closed, with
no path through it that admits a licensed-proprietary corpus into public distribution. The
package-level and publish-level consequences are tested in test_factory_intake.py and
test_pack_map.py; what is here is the predicate they all reach.

Every proprietary fixture is invented. No real licence, contract or proprietary text appears in
this repository (0068 section 6).
"""
import importlib.util
import os
import sys
import unittest

FACTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "factory")
_spec = importlib.util.spec_from_file_location("factory_intake_unit", os.path.join(FACTORY, "intake.py"))
intake = importlib.util.module_from_spec(_spec)
# Loading by path caches bytecode beside the source, and the factory refuses to run with a `.pyc`
# it did not write (#373) -- so this import, like validate.sh's whole run, leaves none behind.
_writes_bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
try:
    _spec.loader.exec_module(intake)
finally:
    sys.dont_write_bytecode = _writes_bytecode


def corpus(licence, distribution=..., source_id="synthetic-corpus"):
    """A manifest corpus entry carrying only what admission reads."""
    entry = {"sourceId": source_id, "licence": licence}
    if licence is None:
        del entry["licence"]
    if distribution is not ...:
        entry["distribution"] = distribution
    return entry


class TestLicenceClass(unittest.TestCase):
    def test_public_domain(self):
        for licence in ("public-domain",
                        "public-domain-us-government",
                        "public-domain-underlying-work; Project Gutenberg trademark terms apply"):
            with self.subTest(licence=licence):
                self.assertEqual("public-domain", intake.licence_class(licence))

    def test_open(self):
        for licence in ("CC0-1.0", "CC-BY-4.0", "CC-BY-4.0. Attribution required: synthetic."):
            with self.subTest(licence=licence):
                self.assertEqual("open", intake.licence_class(licence))

    def test_licensed_proprietary(self):
        for licence in ("licensed-proprietary",
                        "licensed-proprietary; written permission of 2026-01-01, reference SYN-1",
                        "licensed-proprietary."):
            with self.subTest(licence=licence):
                self.assertEqual("licensed-proprietary", intake.licence_class(licence))

    def test_unknown_or_missing(self):
        for licence in ("commercial", "All rights reserved", "CC-BY-NC-4.0", "licensed-proprietaryish",
                        "Licensed-Proprietary", "public-domainish", "", None, 7, True):
            with self.subTest(licence=licence):
                self.assertIsNone(intake.licence_class(licence))


class TestAdmission(unittest.TestCase):
    """The table of 0068 section 1, row by row."""

    def admit(self, *args, **kwargs):
        return intake.admit(corpus(*args, **kwargs))

    def refused(self, *args, **kwargs):
        with self.assertRaises(intake.Refused) as raised:
            intake.admit(corpus(*args, **kwargs))
        return str(raised.exception)

    def test_public_domain_public_is_admitted(self):
        self.assertEqual(("public-domain", "public"), self.admit("public-domain", "public"))

    def test_public_domain_private_is_admitted(self):
        """A publicly licensed corpus may still sit inside a private project (0068 section 1)."""
        self.assertEqual(("public-domain", "private"), self.admit("public-domain", "private"))

    def test_open_public_is_admitted(self):
        self.assertEqual(("open", "public"), self.admit("CC-BY-4.0", "public"))

    def test_open_private_is_admitted(self):
        self.assertEqual(("open", "private"), self.admit("CC0-1.0", "private"))

    def test_licensed_proprietary_private_is_admitted(self):
        self.assertEqual(("licensed-proprietary", "private"),
                         self.admit("licensed-proprietary; synthetic permission", "private"))

    def test_licensed_proprietary_public_is_refused(self):
        message = self.refused("licensed-proprietary; synthetic permission", "public")
        self.assertIn("licensed-proprietary", message)
        self.assertIn("public", message)
        self.assertIn("0068", message)

    def test_licensed_proprietary_undeclared_is_refused(self):
        """Absence is a refusal here, never a default (0068 section 2)."""
        message = self.refused("licensed-proprietary; synthetic permission")
        self.assertIn("declares no `distribution`", message)
        self.assertIn("0068", message)

    def test_unknown_licence_is_refused_whatever_the_distribution(self):
        for distribution in ("public", "private", ...):
            with self.subTest(distribution=distribution):
                message = self.refused("commercial", distribution)
                self.assertIn("0028", message)

    def test_missing_licence_is_refused(self):
        message = self.refused(None, "private")
        self.assertIn("0028", message)

    def test_a_distribution_the_factory_does_not_know_is_refused(self):
        for distribution in ("PUBLIC", "restricted", "", None, True, 1, []):
            with self.subTest(distribution=distribution):
                message = self.refused("public-domain", distribution)
                self.assertIn("distribution", message)
                self.assertIn("0068", message)

    def test_an_undeclared_distribution_reads_as_public_for_an_admitted_public_licence(self):
        self.assertEqual(("public-domain", "public"), self.admit("public-domain"))
        self.assertEqual(("open", "public"), self.admit("CC-BY-4.0"))

    def test_a_corpus_that_is_not_a_mapping_is_refused(self):
        for value in (None, "public-domain", [], 7):
            with self.subTest(value=value):
                with self.assertRaises(intake.Refused):
                    intake.admit(value)


class TestStrictestDistribution(unittest.TestCase):
    """0068 section 3: a product inherits the strictest requirement of what it is made from."""

    def test_the_table(self):
        self.assertEqual("public", intake.strictest_distribution(["public", "public"]))
        self.assertEqual("private", intake.strictest_distribution(["public", "private"]))
        self.assertEqual("private", intake.strictest_distribution(["private", "public"]))
        self.assertEqual("private", intake.strictest_distribution(["private", "private"]))

    def test_one_and_many(self):
        self.assertEqual("public", intake.strictest_distribution(["public"]))
        self.assertEqual("private", intake.strictest_distribution(["private"]))
        self.assertEqual("private", intake.strictest_distribution(["public"] * 9 + ["private"]))

    def test_nothing_at_all_is_public(self):
        """No corpus is no restriction; the callers all refuse an empty citation before this."""
        self.assertEqual("public", intake.strictest_distribution([]))

    def test_a_value_it_does_not_know_is_refused_rather_than_ignored(self):
        with self.assertRaises(intake.Refused):
            intake.strictest_distribution(["public", "secret"])


if __name__ == "__main__":
    unittest.main()
