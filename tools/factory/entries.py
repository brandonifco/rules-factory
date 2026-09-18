"""`MapEntries.g.cs` and `Rulings.g.cs`: the map, and the owner's rulings over it, as data.

  * `MapEntries.g.cs` -- one static per map entry, its citation verbatim, and the baseline. A
    derived entry (0012) has no citation of its own; its `Locators` are every citation it
    rests on (see `semantics.Model._leaf_locators` for which, and in what order). An assertion's static
    also carries `AssertedBy`, the map's `assertedBy` (decision 0025), as an init property so the
    records' constructors do not change; `draws` is not generated, because its `count` is prose;
  * `Rulings.g.cs` -- only when the overlay holds an owner's ruling (decision 0027, rulings.py):
    `OwnerRuling` and `OwnerRulings`, one static per ruling and `All`, from the overlay's id, entry,
    span, answer, ruledBy, ruledOn and record, so an engine surfaces a ruling without restating
    it. Both are partial. The merge refuses a ruling that breaks 0027 before anything is written,
    and a produce with no rulings removes the file;
"""
import csharp


def map_entries_cs(model):
    b = model.baseline
    as_of = b.get("asOf")
    if as_of:
        year, month, day = (int(part) for part in as_of.split("-"))
        as_of_cs = f"new DateOnly({year}, {month}, {day})"
    else:
        as_of_cs = "null"
    lines = [model.header,
             "using System.Collections.Immutable;\n",
             "using RulesKernel.Identity;\n",
             "using RulesKernel.Provenance;\n\n",
             f"namespace {model.name};\n\n",
             "/// <summary>One located entry of the map: its id, its name and its citation, verbatim.</summary>\n",
             "/// <param name=\"Id\">The map entry's stable slug.</param>\n",
             "/// <param name=\"Name\">The entry's name, as the map records it.</param>\n",
             "/// <param name=\"Locator\">Corpus id plus citation, as the map records it.</param>\n",
             "public sealed record MapEntry(string Id, string Name, SourceLocator Locator)\n{\n",
             csharp.ASSERTED_BY_MEMBER,
             "    /// <inheritdoc/>\n",
             "    public override string ToString() => $\"{Id} [{Locator}]\";\n}\n\n",
             "/// <summary>A derived entry (rules-factory decision 0012): a fact the corpus entails and never states.</summary>\n",
             "/// <param name=\"Id\">The map entry's stable slug.</param>\n",
             "/// <param name=\"Name\">The entry's name, as the map records it.</param>\n",
             "/// <param name=\"DerivedFrom\">The entry ids it is derived from, in the map's order.</param>\n",
             "/// <param name=\"Locators\">\n",
             "/// Its citation: the locator of every located entry it rests on, following derived sources down to\n",
             "/// located ones, depth-first in <paramref name=\"DerivedFrom\"/> order, each locator once, at its first place.\n",
             "/// </param>\n",
             "public sealed record DerivedMapEntry(string Id, string Name, ImmutableArray<string> DerivedFrom, ImmutableArray<SourceLocator> Locators)\n{\n",
             csharp.ASSERTED_BY_MEMBER,
             "    /// <inheritdoc/>\n",
             "    public override string ToString() => $\"{Id} [derived from {string.Join(\", \", DerivedFrom)}]\";\n}\n\n",
             f"/// <summary>The {len(model.entries)} entries of {csharp.xml_text(model.package_id)} {csharp.xml_text(model.version)}, "
             "one static per entry, citations copied verbatim from the map.</summary>\n",
             "public static class MapEntries\n{\n",
             "    /// <summary>The corpus every entry cites.</summary>\n",
             f"    public const string SourceId = {csharp.cs_string(model.source_id)};\n\n",
             "    /// <summary>The corpus baseline the map is true of.</summary>\n",
             "    public static SourceBaselineId Baseline { get; } = new(\n",
             "        sourceId: SourceId,\n",
             f"        contentHash: {csharp.cs_string(b['contentHash'])},\n",
             f"        hashDerivation: {csharp.cs_string(b['hashDerivation'])},\n",
             f"        asOf: {as_of_cs});\n"]
    for item in model.entries:
        entry = item["entry"]
        lines.append("\n")
        lines.append(f"    /// <summary>{csharp.xml_text(entry.get('name', entry['id']))} (<c>{csharp.xml_text(entry['id'])}</c>).</summary>\n")
        if model.located(item):
            locator = entry["locator"]
            lines.append(f"    public static MapEntry {item['member']} {{ get; }} = new(\n"
                         f"        {csharp.cs_string(entry['id'])},\n"
                         f"        {csharp.cs_string(entry.get('name', entry['id']))},\n"
                         f"        {csharp.locator_cs(locator)}){csharp.asserted_by_init(entry)};\n")
        else:
            sources = ", ".join(csharp.cs_string(s) for s in entry.get("derivedFrom") or [])
            # Literals, not references to the located statics: a static initializer runs in
            # textual order, and a premise may come later in the map than what it entails.
            cited = "".join(f"            {csharp.locator_cs(model.locator_of(m))},\n" for m in item["locators"])
            lines.append(f"    public static DerivedMapEntry {item['member']} {{ get; }} = new(\n"
                         f"        {csharp.cs_string(entry['id'])},\n"
                         f"        {csharp.cs_string(entry.get('name', entry['id']))},\n"
                         f"        [{sources}],\n"
                         f"        [\n{cited}        ]){csharp.asserted_by_init(entry)};\n")
    lines.append("}\n")
    return "".join(lines)


RULINGS_FILE = "Rulings.g.cs"


def rulings_cs(model):
    """The owner's rulings the overlay holds (decision 0027), as data an engine surfaces to its callers.

    Generated only for an engine whose overlay has a ruling, so an engine with none gains no type. The
    record and the class are partial: an engine may add members (an alias, a derived property) in a
    file of its own, and never restates the metadata, which has one home, the overlay."""
    lines = [model.header,
             "using System.Collections.Immutable;\n\n",
             f"namespace {model.name};\n\n",
             "/// <summary>\n",
             "/// An owner's ruling (rules-factory decision 0027): this engine's answer to part of a question its map\n",
             "/// records as <c>fate: unresolved</c>. It is the owner's, not the corpus's, so a result that relies on it\n",
             "/// names it, and nothing presents it as what the corpus says.\n",
             "/// </summary>\n",
             "/// <param name=\"Id\">A stable id, <c>&lt;entry id&gt;/&lt;slug&gt;</c>.</param>\n",
             "/// <param name=\"EntryId\">The map entry whose <c>ambiguity.question</c> it answers part of.</param>\n",
             "/// <param name=\"Span\">The part of that question it answers, quoted verbatim from the map.</param>\n",
             "/// <param name=\"Answer\">The ruling, stated briefly.</param>\n",
             "/// <param name=\"RuledBy\">Who ruled.</param>\n",
             "/// <param name=\"RuledOn\">When.</param>\n",
             "/// <param name=\"Record\">The engine's decision record that holds the ruling, relative to the engine root.</param>\n",
             "public sealed partial record OwnerRuling(string Id, string EntryId, string Span, string Answer, string RuledBy, "
             "DateOnly RuledOn, string Record);\n\n",
             f"/// <summary>The {len(model.rulings)} owner's ruling(s) in corpus-map.overlay.json, one static each, in overlay order.</summary>\n",
             "public static partial class OwnerRulings\n{\n"]
    for ruling in model.rulings:
        year, month, day = (int(part) for part in ruling["ruledOn"].split("-"))
        lines.append(f"    /// <summary><c>{csharp.xml_text(ruling['id'])}</c>: {csharp.xml_text(ruling['answer'])}</summary>\n"
                     f"    public static OwnerRuling {ruling['member']} {{ get; }} = new(\n"
                     f"        {csharp.cs_string(ruling['id'])},\n"
                     f"        {csharp.cs_string(ruling['entry'])},\n"
                     f"        {csharp.cs_string(ruling['span'])},\n"
                     f"        {csharp.cs_string(ruling['answer'])},\n"
                     f"        {csharp.cs_string(ruling['ruledBy'])},\n"
                     f"        new DateOnly({year}, {month}, {day}),\n"
                     f"        {csharp.cs_string(ruling['record'])});\n\n")
    lines.append("    /// <summary>Every ruling, in overlay order.</summary>\n"
                 f"    public static ImmutableArray<OwnerRuling> All {{ get; }} = [{', '.join(r['member'] for r in model.rulings)}];\n"
                 "}\n")
    return "".join(lines)
