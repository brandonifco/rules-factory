"""`python3 tools/mapper <command>`.

The package is imported by name, so `tools/` goes on the path rather than `tools/mapper/`:
`mapcontract` is a sibling package, not a module beside these, and the boundary checker holds
the mapper to importing it and nothing else (0032).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mapper.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
