#!/usr/bin/env python3
"""The generator's modules (#171): what each may import, what every engine must receive, and what
a produced engine is allowed to reach through `import generate`.

`tools/factory/generate.py` was one 88 KB module and is now nine beside it. Three things that were
free while it was one file have to be held to now:

  * **The layering.** A renderer may reach down to the C# text and the semantic model and no
    further; the rails emission may not reach into a renderer, and no renderer may reach into the
    rails. LAYERS below is the whole declaration, and the test compares it with the imports the
    modules actually have -- equality, not containment, so a new edge has to be declared here
    before it exists.
  * **What an engine receives.** `produce` vendors the generator into every engine under
    `scripts/factory/` (gate.py's FILES), where the engine's own gate imports it to regenerate its
    `*.g.cs`. An engine that received eight of the nine modules could not import the generator at
    all, and would find out at its own gate, months later. So the vendoring table is compared with
    the import closure of what the engine's scripts import, not with a list written by hand.
  * **The names `import generate` still answers.** `scripts/engine-gate.py`,
    `tools/entry-packet.py` and `tools/agent-doctor.py` run inside engines this factory produced
    before the split and reach for `generate.Model`, `generate.generated`, `generate.RAILS` and the
    rest by name. Those names are an interface: the test reads every `generate.<name>` in the
    recipe and asserts the module still answers it, so a re-export deleted as dead code fails here
    rather than in every engine's gate at once.

And the size the issue asked for: no module over 25 KB, measured on the files themselves.

Run: python3 -m pytest tools/tests/factory/test_factory_modules.py
"""
import ast
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
FACTORY = os.path.join(TOOLS, "factory")
RECIPE = os.path.join(FACTORY, "recipe")

_spec = importlib.util.spec_from_file_location("factory_main_modules", os.path.join(FACTORY, "__main__.py"))
factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factory)
generate = factory.generate
gate = factory.gate

# Every module of tools/factory, and exactly the factory modules it may import. The first group is
# the generator #171 split out of generate.py, in dependency order; the rest are the modules that
# were already there, declared so that a new edge anywhere in the factory is a change to this file.
LAYERS = {
    # The generator.
    "csharp": set(),
    "semantics": {"csharp", "overlay", "rulings"},
    "entries": {"csharp"},
    "registry": {"csharp", "semantics"},
    "contracts": {"csharp", "semantics"},
    "correspondence": {"csharp", "semantics"},
    "pins": {"csharp", "semantics"},
    "agentrails": {"overlay", "pins"},
    "scaffold": {"agentrails", "ownership", "pins"},
    "generate": {"agentrails", "contracts", "correspondence", "entries", "overlay", "ownership",
                 "pins", "registry", "rulings", "scaffold", "semantics"},
    # The rest of the factory.
    "__main__": {"backlog", "gate", "generate", "intake", "ownership", "provenance", "rails",
                 "transaction", "verify"},
    "backlog": {"agentrails", "intake", "overlay", "semantics"},
    "gate": set(),
    "intake": set(),
    "overlay": set(),
    "ownership": {"overlay"},
    "provenance": {"agentrails", "intake", "overlay", "ownership", "pins", "semantics"},
    "rails": {"agentrails", "ownership"},
    "rulings": set(),
    "transaction": {"intake"},
    "verify": {"intake"},
}
# The renderers of C# text, and the rails. #171 took the rails emission out of the generator; these
# two sets are what "out of" has to keep meaning.
RENDERERS = frozenset({"csharp", "entries", "registry", "contracts", "correspondence"})
RAILS = frozenset({"agentrails"})
# The modules #171 split generate.py into, generate.py itself included: what the issue's "no
# resulting module over ~25 KB" is measured against. The rest of the factory has monoliths of its
# own and issues of its own; this cap is the one the split was made to hold.
GENERATOR = frozenset(RENDERERS | RAILS | {"semantics", "pins", "scaffold", "generate"})
LIMIT = 25 * 1024


def modules():
    """Every module of tools/factory: name -> path."""
    return {name[:-3]: os.path.join(FACTORY, name)
            for name in sorted(os.listdir(FACTORY)) if name.endswith(".py")}


def imports(path, known):
    """The factory modules `path` imports, at the top of the file or inside a function."""
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), path)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module.split(".")[0])
    return found & set(known)


def reached(name, known, seen=None):
    """`name` and every factory module reachable from it by import."""
    seen = seen if seen is not None else set()
    if name in seen:
        return seen
    seen.add(name)
    for other in sorted(imports(known[name], known)):
        reached(other, known, seen)
    return seen


def recipe_files():
    """Every Python file of the recipe: the files that run inside a produced engine."""
    out = []
    for directory, dirs, names in os.walk(RECIPE):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        out += [os.path.join(directory, n) for n in sorted(names) if n.endswith(".py")]
    return out


def generate_attributes():
    """Every `generate.<name>` the recipe reads, as {name: the file that reads it}."""
    found = {}
    for path in recipe_files():
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), path)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id == "generate"):
                found.setdefault(node.attr, os.path.relpath(path, FACTORY))
    return found


class TestTheLayering(unittest.TestCase):
    def test_every_module_imports_exactly_what_it_is_declared_to(self):
        known = modules()
        self.assertEqual(set(known), set(LAYERS),
                         "a module was added to or removed from tools/factory without declaring what it imports")
        for name, path in known.items():
            self.assertEqual(imports(path, known), LAYERS[name], f"{name}.py imports something else now")

    def test_the_declaration_is_not_empty(self):
        self.assertGreaterEqual(len(modules()), 20, "the modules were not found; this test proved nothing")

    def test_the_rails_emission_and_the_csharp_renderers_do_not_reach_into_each_other(self):
        known = modules()
        for name in RAILS:
            self.assertEqual(imports(known[name], known) & RENDERERS, set(),
                             f"{name}.py reaches into the C# renderers; #171 took the rails out of the generator")
        for name in RENDERERS:
            self.assertEqual(imports(known[name], known) & RAILS, set(),
                             f"{name}.py reaches into the rails")

    def test_no_module_imports_itself_through_a_cycle(self):
        known = modules()
        for name in known:
            for other in sorted(imports(known[name], known)):
                self.assertNotIn(name, reached(other, known),
                                 f"{name}.py and {other}.py import each other")

    def test_no_module_of_the_generator_is_over_the_size_the_split_was_for(self):
        known = modules()
        self.assertEqual(GENERATOR - set(known), set(), "a module of the generator is missing")
        for name in sorted(GENERATOR):
            self.assertLessEqual(os.path.getsize(known[name]), LIMIT,
                                 f"{name}.py is over {LIMIT // 1024} KB; #171 split generate.py for exactly this")


class TestWhatAnEngineReceives(unittest.TestCase):
    def test_the_gate_vendors_every_module_the_engine_can_import(self):
        known = modules()
        vendored = {os.path.basename(source)[:-3] for relative, (source, _) in gate.FILES.items()
                    if relative.startswith("scripts/factory/")}
        self.assertTrue(vendored, "the gate vendors no factory module; this test proved nothing")
        needed = set()
        for name in sorted(vendored):
            needed |= reached(name, known)
        self.assertEqual(vendored, needed,
                         "an engine would receive part of the generator: gate.FILES and the imports disagree")

    def test_the_names_the_recipe_reaches_through_import_generate_all_exist(self):
        attributes = generate_attributes()
        self.assertIn("generated", attributes, "the recipe does not regenerate; this test proved nothing")
        for attribute, where in sorted(attributes.items()):
            self.assertTrue(hasattr(generate, attribute),
                            f"recipe/{where} reads generate.{attribute}, which generate.py no longer answers; "
                            f"every engine produced before that removal breaks at its own gate")


if __name__ == "__main__":
    unittest.main()
