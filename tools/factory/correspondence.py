"""`CorrespondenceTests.g.cs`: the generated proof that the engine and the map still agree.

  * `CorrespondenceTests.g.cs` -- every entry is registered, in map order; every entry that
    is not `implemented` declines with its row's reason and its own locator, through the
    dictionary dispatch and through its typed entry point alike, and registers every locator it
    cites (all of a derived entry's premises); every `implemented` entry has a hand-written
    handler unless its row's default can serve.

These are the engine's tests, not the factory's: they run in the produced engine's test project,
against the registry and the entry points it was produced with, and they are the reason a map
entry cannot quietly stop declining what the corpus does not settle.
"""
import csharp
import semantics


def tests_cs(model):
    lines = [model.header,
             "using RulesKernel.Provenance;\n",
             "using RulesKernel.Resolution;\n",
             "using Xunit;\n\n",
             f"namespace {model.name}.Tests;\n\n",
             "public sealed class CorrespondenceTests\n{\n",
             "    private static readonly string[] MapOrder =\n    [\n"]
    for item in model.entries:
        lines.append(f"        {csharp.cs_string(item['entry']['id'])},\n")
    lines.append("    ];\n\n")
    lines.append("    [Fact]\n"
                 "    public void Every_map_entry_is_registered_in_map_order() =>\n"
                 "        Assert.Equal(MapOrder, Registry.Entries.Select(e => e.Id));\n\n")
    lines.append("    [Fact]\n"
                 "    public void Every_hand_written_handler_names_a_map_entry_once_with_the_handler_signature() =>\n"
                 "        Assert.All(MapOrder, id => _ = Registry.HasImplementation(id));\n\n")
    lines.append("    [Fact]\n"
                 "    public void Every_map_entry_has_a_typed_entry_point_in_map_order() =>\n"
                 "        Assert.Equal(MapOrder, new string[]\n"
                 "        {\n"
                 + "".join(f"            EntryPoints.{item['member']}.Id,\n" for item in model.entries) +
                 "        });\n\n")
    lines.append("    private static void AssertDeclines(string entryId, UnresolvedReason reason, Resolution<object> typed, params SourceLocator[] cited)\n"
                 "    {\n"
                 "        foreach (var resolution in new[] { Registry.Resolve(entryId, RuleRequest.Empty), typed })\n"
                 "        {\n"
                 "            var unresolved = resolution.Match<UnresolvedResult?>(_ => null, u => u);\n"
                 "            Assert.NotNull(unresolved);\n"
                 "            Assert.Equal(reason, unresolved.Reason);\n"
                 "            Assert.Equal(cited[0], unresolved.Locator);\n"
                 "        }\n\n"
                 "        Assert.Equal(cited, Registry.Citations(entryId));\n"
                 "    }\n")
    for item in model.entries:
        entry, row = item["entry"], item["row"]
        method = semantics.snake(entry["id"])
        cited = ", ".join(csharp.locator_cs(model.locator_of(m)) for m in item["locators"])
        lines.append("\n")
        if not model.located(item):
            # Whatever its row, a derived entry's citation is every premise, in the generator's
            # order, and MapEntries and the Registry must both say so.
            lines.append("    [Fact]\n"
                         f"    public void {method}__cites_every_premise()\n"
                         "    {\n"
                         f"        SourceLocator[] cited = [{cited}];\n"
                         f"        Assert.Equal(cited, MapEntries.{item['member']}.Locators);\n"
                         f"        Assert.Equal(cited, Registry.Citations({csharp.cs_string(entry['id'])}));\n"
                         "    }\n\n")
        if entry["status"] == "implemented":
            if row == 8:
                lines.append("    [Fact]\n"
                             f"    public void {method}__is_implemented_and_answers_or_demands_the_assertion()\n"
                             "    {\n"
                             f"        if (Registry.HasImplementation({csharp.cs_string(entry['id'])}))\n"
                             "        {\n            return;\n        }\n\n"
                             "        var value = new object();\n"
                             f"        var resolved = Registry.Resolve({csharp.cs_string(entry['id'])}, RuleRequest.Empty.Assert({csharp.cs_string(entry['id'])}, value))"
                             ".Match<object?>(v => v, _ => null);\n"
                             "        Assert.Same(value, resolved);\n"
                             f"        var typed = EntryPoints.{item['member']}.Resolve({semantics.contract(model, item)['request_cs']}.Asserting(value)).Match<object?>(v => v, _ => null);\n"
                             "        Assert.Same(value, typed);\n"
                             f"        Assert.Throws<AssertionRequiredException>(() => Registry.Resolve({csharp.cs_string(entry['id'])}, RuleRequest.Empty));\n"
                             "    }\n")
            else:
                lines.append("    [Fact]\n"
                             f"    public void {method}__is_implemented_so_a_hand_written_handler_answers_it() =>\n"
                             f"        Assert.True(Registry.HasImplementation({csharp.cs_string(entry['id'])}), "
                             f"{csharp.cs_string(entry['id'] + ' is implemented in the overlay and has no [Implements] handler')});\n")
        elif row in (1, 2, 3, 4, 5, 6):
            reason = semantics.ROWS[row][1]
            lines.append("    [Fact]\n"
                         f"    public void {method}__declines_{reason}_row_{row}() =>\n"
                         f"        AssertDeclines({csharp.cs_string(entry['id'])}, UnresolvedReason.{reason}, "
                         f"EntryPoints.{item['member']}.Resolve({semantics.contract(model, item)['request_cs']}.Empty), "
                         f"{cited});\n")
        else:
            raise semantics.GenerationError(f"entry {entry['id']!r} is {entry['status']!r} and matches no declining row; "
                                  f"check-map.py --phase consumer should have refused it")
    lines.append("}\n")
    return "".join(lines)
