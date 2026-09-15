#!/usr/bin/env bash
# Check out the factory the rebuild must be produced with: rules-factory @TAG@ (@COMMIT@),
# holding only tools/factory/, tools/check-map.py and the root .gitignore (which ignores __pycache__,
# so running the factory does not make its own tree dirty).
#
# `factory produce` names the factory by the git commit it runs from and refuses a dirty tree, so the
# factory has to be a real checkout of the tag. A full clone would also hold the rest of rules-factory,
# which includes examples/hoyle-blind-rebuild/ (the target's test names and this brief's sources) and
# examples/hoyle-backgammon/ (earlier evidence about the engine). This clone is shallow, fetches no file
# contents outside those three paths, and removes its remote, so nothing else can be fetched into it later.
#
# This is the one network fetch of rules-factory the brief allows (README.md, "Rules").
#
#   ./GET-FACTORY.sh DIR
set -euo pipefail

DIR="${1:?usage: GET-FACTORY.sh DIR}"
TAG="@TAG@"
COMMIT="@COMMIT@"

git clone --quiet --depth 1 --branch "$TAG" --filter=blob:none --no-checkout \
  https://github.com/brandonifco/rules-factory "$DIR"
git -C "$DIR" sparse-checkout set --no-cone /tools/factory/ /tools/check-map.py /.gitignore
git -C "$DIR" checkout --quiet "$TAG"
git -C "$DIR" remote remove origin

actual="$(git -C "$DIR" rev-parse HEAD)"
if [[ "$actual" != "$COMMIT" ]]; then
  echo "error: $TAG is $actual, expected $COMMIT" >&2
  exit 1
fi
echo "factory $TAG ($COMMIT) checked out in $DIR, tools only. Run it as: python3 $DIR/tools/factory produce ..."
