"""`python3 tools/mapper <command>`.

The package is imported by name, so `tools/` goes on the path rather than `tools/mapper/`:
`mapcontract` is a sibling package, not a module beside these, and the boundary checker holds
the mapper to importing it and nothing else (0032).
"""
import os
import sys

# Puts tools/ on the path and imports mapper.cli, whose bytecode -- and mapcontract's -- the
# loader writes into the checkout. No caller's environment is relied on to stop it (#384): module
# level and above the insert, because the loader reads the flag when the import happens.
#
# One thing it cannot stop is this file's own caching. `python3 tools/mapper` executes a
# directory, which makes Python *import* `__main__` and write __pycache__/__main__.cpython-*.pyc
# before the first line below runs. Run as a file -- `python3 tools/mapper/__main__.py`, which is
# what the gate does -- there is no cache at all. The documented form stays the directory, and it
# leaves that one git-ignored file behind; nothing written here can prevent it.
sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mapper.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
