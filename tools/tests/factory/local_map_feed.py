"""A scratch engine's NuGet.config, with `RulesFactory.Maps.*` restored from the folder a test packed into.

A produced engine's NuGet.config sends `RulesFactory.Maps.*` to nuget.org, so a build restores
whatever nuget.org holds at the version the map declares: not the package the suite packed, and
nothing at all while a new version is not yet published (a map's version is bumped, reviewed and
merged before its tag publishes it, and publish-map's gate runs this suite). A test that builds an
engine moves the map's id pattern to the folder feed `pack-map.py` wrote, restores into a scratch
NUGET_PACKAGES so the unpublished package never enters the user's cache, and keeps the user's global
packages folder as a read-only fallback for everything else.

NuGet.config is a managed file (tools/factory/ownership.py): a produced engine that carries the
edited copy was re-produced with `--adopt NuGet.config`.
"""
import os


def localized(text, feed):
    """`text`, a NuGet.config as produced, with the map pattern restored from the folder `feed`."""
    fallback = os.path.join(os.path.expanduser("~"), ".nuget", "packages")
    return (text
            .replace("<clear />", f'<clear />\n    <add key="local-maps" value="{feed}" />', 1)
            .replace("  </packageSourceMapping>", '    <packageSource key="local-maps">\n'
                     '      <package pattern="RulesFactory.Maps.*" />\n    </packageSource>\n'
                     "  </packageSourceMapping>" + (f'\n  <fallbackPackageFolders>\n    <add key="user" value="{fallback}" />\n'
                                                    "  </fallbackPackageFolders>" if os.path.isdir(fallback) else ""), 1))


def localize(engine, feed):
    """Edit `engine`'s NuGet.config in place to restore the map from `feed`."""
    path = os.path.join(engine, "NuGet.config")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    changed = localized(text, feed)
    if changed.count("local-maps") != 2:
        raise AssertionError(f"NuGet.config did not take the local map feed:\n{changed}")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(changed)
