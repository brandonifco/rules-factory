#!/usr/bin/env python3
"""check-readme-status.py, proved able to fail.

The fixtures are a small CLI module and a README written here, so a case does not move when the
real CLI does. Three cases use the real README and the real parser: the table agrees with main as
it stands, and a subcommand or flag added to that parser without a row fails.

Run: python3 -m unittest discover -s tools/tests
"""
import argparse
import importlib.util
import io
import os
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TOOL = os.path.join(ROOT, "tools", "check-readme-status.py")

_spec = importlib.util.spec_from_file_location("check_readme_status", TOOL)
status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(status)

CLI = textwrap.dedent('''
    import argparse

    def build_parser():
        parser = argparse.ArgumentParser(prog="factory")
        commands = parser.add_subparsers(dest="command", required=True)
        p = commands.add_parser("produce")
        p.add_argument("--package", required=True)
        p.add_argument("-n", "--no-verify", action="store_true")
        s = commands.add_parser("show")
        s.add_argument("engine")
        return parser
''')

ROWS = [
    "| `produce` | — | implemented | |",
    "| `produce` | `--package` | implemented | |",
    "| `produce` | `--no-verify` | implemented | |",
    "| `produce` | domain pack | not implemented | #1 |",
    "| `show` | — | implemented | |",
    "| `show` | `<engine>` | implemented | |",
]


def readme(rows, begin=status.BEGIN, end=status.END):
    table = ["| Command | Argument | Status | Notes |", "|---|---|---|---|", *rows]
    return "\n".join(["# Fixture", "", "prose", begin, *table, end, "", "more prose", ""])


class Fixture:
    def __init__(self, tmp, cli=CLI):
        self.cli = os.path.join(tmp, "cli.py")
        with open(self.cli, "w", encoding="utf-8") as handle:
            handle.write(cli)
        self.readme = os.path.join(tmp, "README.md")

    def run(self, text):
        with open(self.readme, "w", encoding="utf-8") as handle:
            handle.write(text)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = status.main(["--readme", self.readme, "--cli", self.cli])
        return code, out.getvalue() + err.getvalue()


class FixtureCases(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def assertFails(self, text, *fragments):
        code, output = self.fx.run(text)
        self.assertEqual(code, 1, output)
        for fragment in fragments:
            self.assertIn(fragment, output)

    def test_an_agreeing_table_passes(self):
        code, output = self.fx.run(readme(ROWS))
        self.assertEqual(code, 0, output)
        self.assertIn("6 status row(s) agree with the CLI's 2 subcommand(s) and 3 argument(s)", output)

    def test_a_flag_the_readme_does_not_list_fails(self):
        self.assertFails(readme([r for r in ROWS if "--no-verify" not in r]),
                         "`produce --no-verify` is in the CLI and not in the README")

    def test_a_subcommand_the_readme_does_not_list_fails(self):
        self.assertFails(readme([r for r in ROWS if "`show`" not in r]),
                         "subcommand `show` is in the CLI", "`show <engine>` is in the CLI")

    def test_a_listed_flag_the_cli_does_not_have_fails(self):
        self.assertFails(readme(ROWS + ["| `produce` | `--domain-pack` | implemented | |"]),
                         "`produce --domain-pack` is marked implemented")

    def test_a_listed_subcommand_the_cli_does_not_have_fails(self):
        self.assertFails(readme(ROWS + ["| `rails` | — | implemented | |"]),
                         "`rails` is marked implemented")

    def test_not_implemented_for_something_the_cli_has_fails(self):
        rows = [r.replace("implemented", "not implemented") if "--package" in r else r for r in ROWS]
        self.assertFails(readme(rows), "`produce --package` is marked not implemented, and the CLI has it")

    def test_not_implemented_flag_under_no_command_is_checked_against_every_subcommand(self):
        self.assertFails(readme(ROWS + ["| — | `--no-verify` | not implemented | |"]),
                         "`--no-verify` is marked not implemented")
        code, output = self.fx.run(readme(ROWS + ["| — | `--rails` | not implemented | |"]))
        self.assertEqual(code, 0, output)

    def test_an_implemented_row_must_name_a_quoted_argument(self):
        self.assertFails(readme(ROWS + ["| `produce` | package | implemented | |"]),
                         "an implemented row names a `subcommand`")

    def test_an_unknown_status_fails(self):
        self.assertFails(readme(ROWS + ["| `produce` | rails | planned | |"]), "status 'planned'")

    def test_a_repeated_row_fails(self):
        self.assertFails(readme(ROWS + [ROWS[1]]), "listed twice")

    def test_an_empty_table_proved_nothing(self):
        self.assertFails(readme([]), "proved nothing")

    def test_missing_markers_fail(self):
        self.assertFails(readme(ROWS, begin="<!-- nothing -->"), "expected exactly one")
        self.assertFails(readme(ROWS) + status.BEGIN + "\n", "expected exactly one")

    def test_a_malformed_row_fails(self):
        self.assertFails(readme(ROWS + ["| `produce` | `--package` | implemented |"]), "expected 4 cells")

    def test_a_cli_without_build_parser_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp, cli="import argparse\n")
            code, output = fx.run(readme(ROWS))
        self.assertEqual(code, 1, output)
        self.assertIn("has no build_parser()", output)

    def test_flags_in_help_text_are_not_arguments(self):
        cli = CLI.replace('add_parser("show")', 'add_parser("show", help="like --secret")')
        with tempfile.TemporaryDirectory() as tmp:
            code, output = Fixture(tmp, cli=cli).run(readme(ROWS))
        self.assertEqual(code, 0, output)


class TheRealReadme(unittest.TestCase):
    """README.md against tools/factory/__main__.py as they are on this branch."""

    README = os.path.join(ROOT, "README.md")
    CLI_PATH = os.path.join(ROOT, "tools", "factory", "__main__.py")

    def text(self):
        with open(self.README, encoding="utf-8") as handle:
            return handle.read()

    def test_the_readme_agrees_with_the_cli(self):
        problems, examined = status.check(self.text(), status.cli_surface(status.load_parser(self.CLI_PATH)))
        self.assertEqual(problems, [])
        self.assertGreater(examined, 0)

    def test_a_subcommand_added_to_the_real_cli_fails(self):
        parser = status.load_parser(self.CLI_PATH)
        commands = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        commands.add_parser("rails")
        problems, _ = status.check(self.text(), status.cli_surface(parser))
        self.assertIn("subcommand `rails` is in the CLI and not in the README's status table", problems)

    def test_a_flag_added_to_the_real_cli_fails(self):
        parser = status.load_parser(self.CLI_PATH)
        commands = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        commands.choices["produce"].add_argument("--domain-pack")
        problems, _ = status.check(self.text(), status.cli_surface(parser))
        self.assertIn("`produce --domain-pack` is in the CLI and not in the README's status table", problems)


if __name__ == "__main__":
    unittest.main()
