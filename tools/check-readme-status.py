#!/usr/bin/env python3
"""README.md's status table agrees with the factory's CLI (#75).

The README said "Nothing here builds anything yet" after the factory had started building
engines, and listed a domain-pack input the CLI never had. Prose about status drifts because
nothing reads it. So the part of the status that can be checked is a table, and this reads it.

README.md holds one table between these two lines:

    <!-- factory-cli-status:begin -->
    <!-- factory-cli-status:end -->

with the columns `Command | Argument | Status | Notes`. Each row is one of:

  * a subcommand: Command is `` `produce` ``, Argument is `—`;
  * one of its arguments: Command is the subcommand, Argument is `` `--flag` `` (an option,
    by its long spelling) or `` `<dest>` `` (a positional);
  * an input the factory does not take: Argument is plain text (`domain pack`), or a flag
    that does not exist, and Status is `not implemented`. Command may be `—` when the input
    belongs to no subcommand yet.

Status is exactly `implemented` or `not implemented`. The parser is the one
`tools/factory/__main__.py` builds (`build_parser()`), imported and introspected, never grepped,
so a flag in a help string or a comment is not mistaken for one. The check fails when:

  * a subcommand or argument the parser has is not a row marked `implemented`;
  * a row marked `implemented` names a subcommand or argument the parser does not have;
  * a row marked `not implemented` names a subcommand or argument the parser does have;
  * a row is malformed or repeated, the markers are missing, or the table has no rows.

`-h/--help`, which argparse adds to every parser, is not listed. What this does not check: the
prose around the table. It holds the table to the parser and nothing more; a sentence can still
be wrong, and a reviewer still has to read it.

Usage: check-readme-status.py [--readme FILE] [--cli FILE]
Exit 0 when the table and the parser agree and at least one row was examined; 1 otherwise;
2 on a usage error. Standard library only.
"""
import argparse
import importlib.util
import os
import re
import sys

# load_parser() imports the factory's CLI and the modules beside it, and bytecode written into
# tools/factory/__pycache__ is what the next `factory produce` refuses: no commit holds it, and it
# is what Python would run (#373). Set here rather than beside the import it disarms, because the
# loader reads the flag when the import happens -- and here rather than relying on the CLI's own
# flag, which is set by the very module this loads.
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BEGIN = "<!-- factory-cli-status:begin -->"
END = "<!-- factory-cli-status:end -->"
NONE = {"—", "-", ""}
STATUSES = ("implemented", "not implemented")
CODE = re.compile(r"^`([^`]+)`$")


class Problem(Exception):
    pass


def load_parser(cli_path):
    """The ArgumentParser `build_parser()` in `cli_path` returns, by importing the module."""
    directory = os.path.dirname(os.path.abspath(cli_path))
    sys.path.insert(0, directory)  # __main__.py imports the modules beside it
    try:
        spec = importlib.util.spec_from_file_location("factory_cli_for_status", cli_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(directory)
    build = getattr(module, "build_parser", None)
    if not callable(build):
        raise Problem(f"{cli_path} has no build_parser(); there is no parser to check the README against")
    return build()


def cli_surface(parser):
    """{subcommand: {argument}} where an argument is its long option (or only option) or `<dest>`."""
    subparsers = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if not subparsers:
        raise Problem("the parser has no subcommands")
    surface = {}
    for action in subparsers:
        for name, sub in action.choices.items():
            arguments = set()
            for arg in sub._actions:
                if isinstance(arg, argparse._HelpAction):
                    continue
                if arg.option_strings:
                    longs = [o for o in arg.option_strings if o.startswith("--")]
                    arguments.add(longs[0] if longs else arg.option_strings[0])
                else:
                    arguments.add(f"<{arg.dest}>")
            surface[name] = arguments
    return surface


def read_table(text):
    """[(line number, command, argument, status)] from the marked table."""
    lines = text.splitlines()
    begins = [i for i, line in enumerate(lines) if line.strip() == BEGIN]
    ends = [i for i, line in enumerate(lines) if line.strip() == END]
    if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
        raise Problem(f"expected exactly one {BEGIN} followed by one {END}")
    rows = []
    header_seen = False
    for number in range(begins[0] + 1, ends[0]):
        line = lines[number].strip()
        if not line:
            continue
        if not (line.startswith("|") and line.endswith("|")):
            raise Problem(f"line {number + 1}: not a table row: {line!r}")
        cells = [c.strip() for c in line[1:-1].split("|")]
        if len(cells) != 4:
            raise Problem(f"line {number + 1}: expected 4 cells (Command | Argument | Status | Notes), got {len(cells)}")
        if not header_seen:
            if [c.lower() for c in cells[:3]] != ["command", "argument", "status"]:
                raise Problem(f"line {number + 1}: the header must be Command | Argument | Status | Notes")
            header_seen = True
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue  # the separator row
        rows.append((number + 1, cells[0], cells[1], cells[2]))
    return rows


def unquote(cell):
    match = CODE.match(cell)
    return match.group(1) if match else None


def check(readme_text, surface):
    """Every disagreement between the table and `surface`, as lines; and how many rows were read."""
    problems = []
    rows = read_table(readme_text)
    if not rows:
        raise Problem("the status table has no rows -- this check proved nothing")
    listed = set()
    for number, command_cell, argument_cell, status in rows:
        where = f"README line {number}"
        if status not in STATUSES:
            problems.append(f"{where}: status {status!r} is neither 'implemented' nor 'not implemented'")
            continue
        command = None if command_cell in NONE else unquote(command_cell)
        if command is None and command_cell not in NONE:
            problems.append(f"{where}: command {command_cell!r} is not `quoted` or —")
            continue
        argument = None if argument_cell in NONE else (unquote(argument_cell) or argument_cell)
        key = (command, argument)
        if key in listed:
            problems.append(f"{where}: {command_cell} {argument_cell} is listed twice")
            continue
        listed.add(key)
        if command is None:  # an input no subcommand takes: it must be in none of them
            exists = argument is not None and any(argument in arguments for arguments in surface.values())
        else:
            exists = command in surface and (argument is None or argument in surface[command])
        if status == "implemented":
            if command is None or (argument is not None and unquote(argument_cell) is None):
                problems.append(f"{where}: an implemented row names a `subcommand` and a `--flag`, `<positional>` or —")
            elif not exists:
                what = f"`{command}`" if argument is None else f"`{command} {argument}`"
                problems.append(f"{where}: {what} is marked implemented, and tools/factory/__main__.py has no such "
                                f"{'subcommand' if argument is None else 'argument'}")
        elif exists:
            what = f"`{argument}`" if command is None else f"`{command}`" if argument is None else f"`{command} {argument}`"
            problems.append(f"{where}: {what} is marked not implemented, and the CLI has it")
    for command in sorted(surface):
        if (command, None) not in listed:
            problems.append(f"subcommand `{command}` is in the CLI and not in the README's status table")
        for argument in sorted(surface[command]):
            if (command, argument) not in listed:
                problems.append(f"`{command} {argument}` is in the CLI and not in the README's status table")
    return problems, len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="check-readme-status.py", description=__doc__.split("\n")[0])
    parser.add_argument("--readme", default=os.path.join(ROOT, "README.md"))
    parser.add_argument("--cli", default=os.path.join(ROOT, "tools", "factory", "__main__.py"))
    args = parser.parse_args(argv)
    try:
        with open(args.readme, encoding="utf-8") as handle:
            text = handle.read()
        surface = cli_surface(load_parser(args.cli))
        problems, examined = check(text, surface)
    except (OSError, Problem) as error:
        print(f"check-readme-status: {error}", file=sys.stderr)
        return 1
    for line in problems:
        print(f"  X  {line}")
    if problems:
        print(f"\n{len(problems)} disagreement(s) between README.md and the factory CLI")
        return 1
    arguments = sum(len(a) for a in surface.values())
    print(f"{examined} status row(s) agree with the CLI's {len(surface)} subcommand(s) and {arguments} argument(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
