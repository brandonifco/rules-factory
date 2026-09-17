"""The corpus map's contract: what a map's fields mean, and how an entry is read.

Three subsystems share it and nothing else -- the mapper that produces a map, the validation
that certifies one, and the factory that builds an engine from one (0032). It is therefore the
one place the map's closed vocabularies are written down. A copy kept by a consumer is a second
definition of the interface 0001 says the map is, and it drifts.

This package depends on nothing else in the repository, so that the direction of dependency is
a fact tools/check-boundaries.py can hold: the contract knows no subsystem, and no subsystem
knows another.

Nothing here judges anything. The readers tolerate a malformed map -- a missing block reads as
empty, a non-list `entries` as no entries -- so that each check reports the malformation it
owns and no check crashes on one another check owns.
"""
