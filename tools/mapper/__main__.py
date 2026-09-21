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
sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mapper.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
