"""The checkers' own tests, laid out by subsystem (0033).

A subdirectory per subsystem -- `mapper/`, `mapvalidator/`, `factory/` -- and, at this level,
the tests of the checkers that hold *this repository* to its word rather than any subsystem:
the boundary, the pull request's documentation section, the README's status, the workflow pins
and repository hygiene.

This file is what makes the layout importable rather than shadowing: without it the directory
holding a test package goes on `sys.path`, and `tools/tests/mapper/` would answer `import
mapper` instead of `tools/mapper/`. With it, `tools/` goes on the path and a test gets the
subsystem it is testing.
"""
