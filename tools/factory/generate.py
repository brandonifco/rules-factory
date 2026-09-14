"""M2 of #3: scaffold a .NET engine and generate the `*.g.cs` files that tie it to its map.

Two kinds of output, and the line between them is the file name:

  * **Scaffold** -- global.json, NuGet.config, Directory.Build.props, Directory.Packages.props,
    the solution, both project files and an empty `corpus-map.overlay.json`. Written only when
    absent: after the first `produce` they belong to the engine, and a second `produce` must
    not undo an edit to them (above all to the overlay, which is the engine's own file, 0015).
  * **Generated** -- every file named `*.g.cs`, under `Generated/`. Rewritten on every
    `produce`, from the package map merged with the engine's overlay, and never edited by
    hand. Hand-written code lives in any other file and is never touched.

The corpus is copied to `corpus/` on every run; intake has already proved its bytes.

What the generated code states:

  * `MapEntries.g.cs` -- one static per map entry, its citation verbatim, and the baseline;
  * `Registry.g.cs` -- every entry registered with the correspondence row it matches first
    (docs/corpus-map.md, "The map and the engine agree"), and a default handler per row:
      1 `scope: out`                                  -> OutsideCurrentScope
      2 `status: mapped` or `blocked`                 -> UnsupportedRule (#47: refuse until proven)
      3 `definedElsewhere`, 4 `beyondAdapter`,
      5 an operation on an unimplemented value        -> MissingRulesData
      6 `ambiguity.fate: unresolved`                  -> RequiresInterpretation
      8 `kind: assertion`                             -> no decline: the value is demanded of the caller
      no row (a built, clear rule)                    -> nothing; a hand-written handler must answer.
    Row 7 is a fact about pairs of entries and has no single-entry handler.
    A hand-written `[Implements("entry-id")]` method replaces the default -- **only for an
    entry whose merged status is `implemented`**. A `mapped` entry declines even when its code
    exists (corpus-map.md, `status`), so the override is ignored until the overlay says so;
  * `CorrespondenceTests.g.cs` -- every entry is registered, in map order; every entry that
    is not `implemented` declines with its row's reason and its own locator; every
    `implemented` entry has a hand-written handler unless its row's default can serve.

Deterministic: the output depends only on the package map, the overlay, the corpus and the
engine name. No timestamps, no machine paths, no dictionary-order accidents.
"""
import json
import os
import re

KERNEL_VERSION = "0.2.0"
# The SDK rules-kernel pins (its global.json), so a produced engine builds with the kernel's
# toolchain. This is the kernel's pin, not this machine's: never substitute a local SDK here.
SDK_VERSION = "10.0.112"
TEST_PACKAGES = (
    ("Microsoft.NET.Test.Sdk", "17.11.1"),
    ("xunit", "2.9.2"),
    ("xunit.runner.visualstudio", "2.8.2"),
)
OVERLAY_NAME = "corpus-map.overlay.json"
OWNED = ("status", "implementedIn", "tests")

ROWS = {
    1: ("ScopeOut", "OutsideCurrentScope"),
    2: ("NotBuilt", "UnsupportedRule"),
    3: ("DefinedElsewhere", "MissingRulesData"),
    4: ("BeyondAdapter", "MissingRulesData"),
    5: ("ValueDependencyUnimplemented", "MissingRulesData"),
    6: ("UnresolvedAmbiguity", "RequiresInterpretation"),
    8: ("Assertion", None),
}
STATUSES = {"mapped": "Mapped", "blocked": "Blocked", "implemented": "Implemented", "declined": "Declined"}
RESERVED_MEMBERS = {"SourceId", "Baseline", "Entry", "Derived", "Equals", "ReferenceEquals", "GetHashCode", "ToString"}


class GenerationError(Exception):
    """The map cannot be turned into an engine as it stands."""


# --- the overlay ---------------------------------------------------------------------------


def merge(document, overlay):
    """merge(package, overlay) per 0015 rules 1-4; refuses on rules 1 and 2."""
    if not isinstance(overlay, dict):
        raise GenerationError(f"{OVERLAY_NAME} is not an object of entry id -> {', '.join(OWNED)}")
    ids = [e.get("id") for e in document.get("entries") or []]
    for entry_id, item in overlay.items():
        if entry_id not in ids:
            raise GenerationError(f"{OVERLAY_NAME} names {entry_id!r}, which the package map has no entry for")
        if not isinstance(item, dict) or "status" not in item:
            raise GenerationError(f"{OVERLAY_NAME} item {entry_id!r} does not set status")
        extra = sorted(set(item) - set(OWNED))
        if extra:
            raise GenerationError(f"{OVERLAY_NAME} item {entry_id!r} sets {extra}; an engine owns only {', '.join(OWNED)}")
    merged = dict(document)
    entries = []
    for entry in document.get("entries") or []:
        item = overlay.get(entry.get("id"))
        if item is None:
            entries.append(entry)
        else:
            base = {k: v for k, v in entry.items() if k not in OWNED}
            base.update({k: item[k] for k in OWNED if k in item})
            entries.append(base)
    merged["entries"] = entries
    return merged


# --- the correspondence table --------------------------------------------------------------


def first_row(entry, by_id):
    """The first correspondence row the entry matches, in table order; None when it matches none."""
    if entry.get("scope") == "out":
        return 1
    if entry.get("status") in ("mapped", "blocked"):
        return 2
    if "definedElsewhere" in entry:
        return 3
    if "beyondAdapter" in entry:
        return 4
    if entry.get("kind") == "operation":
        for dep in entry.get("dependsOn") or []:
            target = by_id.get(dep)
            if isinstance(target, dict) and target.get("kind") == "value" and target.get("status") != "implemented":
                return 5
    ambiguity = entry.get("ambiguity")
    if isinstance(ambiguity, dict) and ambiguity.get("fate") == "unresolved":
        return 6
    if entry.get("kind") == "assertion":
        return 8
    return None


# --- C# text -------------------------------------------------------------------------------


def cs_string(text):
    out = ['"']
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20 or ch in "\u2028\u2029":
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def xml_text(text):
    return " ".join(str(text).split()).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pascal(entry_id):
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", entry_id) if p]
    name = "".join(p[0].upper() + p[1:] for p in parts)
    if not name or not name[0].isalpha():
        name = "Entry" + name
    if name in RESERVED_MEMBERS:
        name += "Entry"
    return name


def snake(entry_id):
    name = re.sub(r"[^A-Za-z0-9]+", "_", entry_id).strip("_")
    return name if name[:1].isalpha() else "Entry_" + name


HEADER = ("// <auto-generated>\n"
          "//   Generated by rules-factory tools/factory from {package} {version}.\n"
          "//   Every *.g.cs file is rewritten by `factory produce`; edit hand-written files instead.\n"
          "// </auto-generated>\n"
          "#nullable enable\n\n")


class Model:
    """The merged map, in the shape the templates read."""

    def __init__(self, intake, merged, name):
        self.name = name
        self.package_id = intake.package_id
        self.version = intake.version
        self.header = HEADER.format(package=intake.package_id, version=intake.version)
        self.source_id = merged["corpus"]
        self.baseline = merged["baseline"]
        entries = merged.get("entries") or []
        by_id = {e["id"]: e for e in entries}
        members = {}
        self.entries = []
        for entry in entries:
            member = pascal(entry["id"])
            if member in members:
                raise GenerationError(f"entries {members[member]!r} and {entry['id']!r} both name the C# member {member}")
            members[member] = entry["id"]
            self.entries.append({"entry": entry, "member": member, "row": first_row(entry, by_id)})
        self.by_id = {item["entry"]["id"]: item for item in self.entries}
        for item in self.entries:
            item["decline_locator"] = self._decline_locator(item, set())

    def _decline_locator(self, item, seen):
        """A located entry cites itself; a derived one (0012) cites the first passage it is derived from."""
        entry = item["entry"]
        locator = entry.get("locator")
        if isinstance(locator, dict):
            return item["member"]
        if entry["id"] in seen:
            raise GenerationError(f"derived entry {entry['id']!r} is derived, through a cycle, from itself")
        sources = entry.get("derivedFrom") or []
        if not sources or sources[0] not in self.by_id:
            raise GenerationError(f"entry {entry['id']!r} has no locator and no derivedFrom to cite")
        return self._decline_locator(self.by_id[sources[0]], seen | {entry["id"]})

    def located(self, item):
        return isinstance(item["entry"].get("locator"), dict)


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
             "    /// <inheritdoc/>\n",
             "    public override string ToString() => $\"{Id} [{Locator}]\";\n}\n\n",
             "/// <summary>A derived entry (rules-factory decision 0012): a fact the corpus entails and never states.</summary>\n",
             "/// <param name=\"Id\">The map entry's stable slug.</param>\n",
             "/// <param name=\"Name\">The entry's name, as the map records it.</param>\n",
             "/// <param name=\"DerivedFrom\">The entry ids it is derived from, in the map's order.</param>\n",
             "public sealed record DerivedMapEntry(string Id, string Name, ImmutableArray<string> DerivedFrom)\n{\n",
             "    /// <inheritdoc/>\n",
             "    public override string ToString() => $\"{Id} [derived from {string.Join(\", \", DerivedFrom)}]\";\n}\n\n",
             f"/// <summary>The {len(model.entries)} entries of {xml_text(model.package_id)} {xml_text(model.version)}, "
             "one static per entry, citations copied verbatim from the map.</summary>\n",
             "public static class MapEntries\n{\n",
             "    /// <summary>The corpus every entry cites.</summary>\n",
             f"    public const string SourceId = {cs_string(model.source_id)};\n\n",
             "    /// <summary>The corpus baseline the map is true of.</summary>\n",
             "    public static SourceBaselineId Baseline { get; } = new(\n",
             "        sourceId: SourceId,\n",
             f"        contentHash: {cs_string(b['contentHash'])},\n",
             f"        hashDerivation: {cs_string(b['hashDerivation'])},\n",
             f"        asOf: {as_of_cs});\n"]
    for item in model.entries:
        entry = item["entry"]
        lines.append("\n")
        lines.append(f"    /// <summary>{xml_text(entry.get('name', entry['id']))} (<c>{xml_text(entry['id'])}</c>).</summary>\n")
        if model.located(item):
            locator = entry["locator"]
            lines.append(f"    public static MapEntry {item['member']} {{ get; }} = new(\n"
                         f"        {cs_string(entry['id'])},\n"
                         f"        {cs_string(entry.get('name', entry['id']))},\n"
                         f"        new SourceLocator({cs_string(locator['sourceId'])}, {cs_string(locator['citation'])}));\n")
        else:
            sources = ", ".join(cs_string(s) for s in entry.get("derivedFrom") or [])
            lines.append(f"    public static DerivedMapEntry {item['member']} {{ get; }} = new(\n"
                         f"        {cs_string(entry['id'])},\n"
                         f"        {cs_string(entry.get('name', entry['id']))},\n"
                         f"        [{sources}]);\n")
    lines.append("}\n")
    return "".join(lines)


REGISTRY_SUPPORT = """
/// <summary>Whether the engine has built an entry, as the map merged with the overlay says.</summary>
public enum EntryStatus
{
    /// <summary>Enumerated and classified; not yet worked.</summary>
    Mapped,
    /// <summary>A dependency is unmet.</summary>
    Blocked,
    /// <summary>In the engine, naming the tests that prove it.</summary>
    Implemented,
    /// <summary>No implemented path at all.</summary>
    Declined,
}

/// <summary>The first row of the map-to-runtime correspondence table an entry matches (docs/corpus-map.md).</summary>
public enum CorrespondenceRow
{
    /// <summary>No row: a built, clear rule the engine simply answers.</summary>
    None = 0,
    /// <summary>Row 1, <c>scope: out</c>: OutsideCurrentScope.</summary>
    ScopeOut = 1,
    /// <summary>Row 2, <c>status: mapped</c> or <c>blocked</c>: UnsupportedRule.</summary>
    NotBuilt = 2,
    /// <summary>Row 3, <c>definedElsewhere</c>: MissingRulesData.</summary>
    DefinedElsewhere = 3,
    /// <summary>Row 4, <c>beyondAdapter</c>: MissingRulesData.</summary>
    BeyondAdapter = 4,
    /// <summary>Row 5, an operation whose value dependency is unimplemented: MissingRulesData.</summary>
    ValueDependencyUnimplemented = 5,
    /// <summary>Row 6, <c>ambiguity.fate: unresolved</c>: RequiresInterpretation.</summary>
    UnresolvedAmbiguity = 6,
    /// <summary>Row 8, <c>kind: assertion</c>: nothing; the engine demands the value.</summary>
    Assertion = 8,
}

/// <summary>What a caller supplies to resolve an entry: the values of the assertions it makes (row 8).</summary>
public sealed class RuleRequest
{
    private readonly ImmutableDictionary<string, object> assertions;

    private RuleRequest(ImmutableDictionary<string, object> assertions) => this.assertions = assertions;

    /// <summary>A request asserting nothing.</summary>
    public static RuleRequest Empty { get; } = new(ImmutableDictionary<string, object>.Empty.WithComparers(StringComparer.Ordinal));

    /// <summary>This request, also asserting <paramref name="value"/> for the assertion entry <paramref name="entryId"/>.</summary>
    /// <param name="entryId">The id of a <c>kind: assertion</c> entry.</param>
    /// <param name="value">The caller's value for it.</param>
    /// <returns>A new request.</returns>
    public RuleRequest Assert(string entryId, object value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(entryId);
        ArgumentNullException.ThrowIfNull(value);
        return new(assertions.SetItem(entryId, value));
    }

    /// <summary>The value asserted for <paramref name="entryId"/>.</summary>
    /// <param name="entryId">The id of a <c>kind: assertion</c> entry.</param>
    /// <returns>The caller's value.</returns>
    /// <exception cref="AssertionRequiredException">The caller asserted nothing for it.</exception>
    public object Asserted(string entryId) =>
        assertions.TryGetValue(entryId, out var value) ? value : throw new AssertionRequiredException(entryId);
}

/// <summary>
/// An assertion the corpus leaves to the caller was not supplied. Not an unresolved result:
/// the corpus gave the engine the means to proceed, and the caller owes the value (row 8).
/// </summary>
public sealed class AssertionRequiredException : ArgumentException
{
    /// <summary>Creates the exception for the assertion entry <paramref name="entryId"/>.</summary>
    /// <param name="entryId">The assertion the caller did not supply.</param>
    public AssertionRequiredException(string entryId)
        : base($"the map entry '{entryId}' is an assertion; the caller must supply its value") => EntryId = entryId;

    /// <summary>The assertion the caller did not supply.</summary>
    public string EntryId { get; }
}

/// <summary>
/// Marks a hand-written handler for a map entry. The method must be static, take one
/// <see cref="RuleRequest"/> and return <c>Resolution&lt;object&gt;</c>. It answers only once
/// the entry's merged status is <c>implemented</c>; until then the entry declines as its row says.
/// </summary>
/// <param name="entryId">The map entry this method implements.</param>
[AttributeUsage(AttributeTargets.Method, AllowMultiple = true, Inherited = false)]
public sealed class ImplementsAttribute(string entryId) : Attribute
{
    /// <summary>The map entry this method implements.</summary>
    public string EntryId { get; } = entryId;
}

/// <summary>One registered map entry.</summary>
/// <param name="Id">The map entry's id.</param>
/// <param name="Status">Its merged status.</param>
/// <param name="Row">The first correspondence row it matches.</param>
/// <param name="Locator">The locator its declines cite.</param>
public sealed record RegisteredEntry(string Id, EntryStatus Status, CorrespondenceRow Row, SourceLocator Locator);
"""

REGISTRY_BODY = """
    private static readonly Lazy<ImmutableDictionary<string, Func<RuleRequest, Resolution<object>>>> Implementations =
        new(DiscoverImplementations);

    /// <summary>Every map entry, in the map's order.</summary>
    public static ImmutableArray<RegisteredEntry> Entries => All;

    /// <summary>The registered entry <paramref name="entryId"/>.</summary>
    /// <param name="entryId">A map entry id.</param>
    /// <returns>The entry.</returns>
    /// <exception cref="KeyNotFoundException">The map has no such entry.</exception>
    public static RegisteredEntry Entry(string entryId) =>
        ById.TryGetValue(entryId, out var entry) ? entry : throw new KeyNotFoundException($"the map has no entry '{entryId}'");

    /// <summary>Whether a hand-written <see cref="ImplementsAttribute"/> handler exists for <paramref name="entryId"/>.</summary>
    /// <param name="entryId">A map entry id.</param>
    /// <returns>True when one exists, whether or not the entry's status lets it answer.</returns>
    public static bool HasImplementation(string entryId) => Implementations.Value.ContainsKey(entryId);

    /// <summary>
    /// Resolves <paramref name="entryId"/>: through its hand-written handler when the entry is
    /// <c>implemented</c> and has one, otherwise through the default its correspondence row fixes.
    /// </summary>
    /// <param name="entryId">A map entry id.</param>
    /// <param name="request">What the caller asserts.</param>
    /// <returns>The resolution.</returns>
    public static Resolution<object> Resolve(string entryId, RuleRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        var entry = Entry(entryId);
        if (entry.Status == EntryStatus.Implemented && Implementations.Value.TryGetValue(entryId, out var handler))
        {
            return handler(request);
        }

        return Default(entry, request);
    }

    private static Resolution<object> Default(RegisteredEntry entry, RuleRequest request) => entry.Row switch
    {
        CorrespondenceRow.ScopeOut => Decline(entry, UnresolvedReason.OutsideCurrentScope),
        CorrespondenceRow.NotBuilt => Decline(entry, UnresolvedReason.UnsupportedRule),
        CorrespondenceRow.DefinedElsewhere or CorrespondenceRow.BeyondAdapter or CorrespondenceRow.ValueDependencyUnimplemented =>
            Decline(entry, UnresolvedReason.MissingRulesData),
        CorrespondenceRow.UnresolvedAmbiguity => Decline(entry, UnresolvedReason.RequiresInterpretation),
        CorrespondenceRow.Assertion => Resolution<object>.FromValue(request.Asserted(entry.Id)),
        _ => throw new InvalidOperationException(
            $"the map entry '{entry.Id}' is {entry.Status} and matches no declining row, so a hand-written [Implements] handler must answer it"),
    };

    private static Resolution<object> Decline(RegisteredEntry entry, UnresolvedReason reason) =>
        Resolution<object>.FromUnresolved(new UnresolvedResult(reason, $"resolve the map entry '{entry.Id}'", entry.Locator));

    private static ImmutableDictionary<string, Func<RuleRequest, Resolution<object>>> DiscoverImplementations()
    {
        var found = ImmutableDictionary.CreateBuilder<string, Func<RuleRequest, Resolution<object>>>(StringComparer.Ordinal);
        const BindingFlags Everywhere = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.DeclaredOnly;
        foreach (var type in typeof(Registry).Assembly.GetTypes())
        {
            foreach (var method in type.GetMethods(Everywhere))
            {
                foreach (var implements in method.GetCustomAttributes<ImplementsAttribute>())
                {
                    var where = $"{type.FullName}.{method.Name}";
                    if (!ById.ContainsKey(implements.EntryId))
                    {
                        throw new InvalidOperationException($"{where} implements '{implements.EntryId}', which the map has no entry for");
                    }

                    var parameters = method.GetParameters();
                    if (method.ReturnType != typeof(Resolution<object>) || parameters.Length != 1 || parameters[0].ParameterType != typeof(RuleRequest))
                    {
                        throw new InvalidOperationException($"{where} must be static Resolution<object> (RuleRequest) to implement '{implements.EntryId}'");
                    }

                    if (found.ContainsKey(implements.EntryId))
                    {
                        throw new InvalidOperationException($"'{implements.EntryId}' has more than one [Implements] handler; {where} is the second");
                    }

                    found.Add(implements.EntryId, method.CreateDelegate<Func<RuleRequest, Resolution<object>>>());
                }
            }
        }

        return found.ToImmutable();
    }
"""


def registry_cs(model):
    lines = [model.header,
             "using System.Collections.Immutable;\n",
             "using System.Reflection;\n",
             "using RulesKernel.Provenance;\n",
             "using RulesKernel.Resolution;\n\n",
             f"namespace {model.name};\n",
             REGISTRY_SUPPORT,
             "\n/// <summary>Every map entry, the correspondence row it matches first, and the handler that answers it.</summary>\n",
             "public static class Registry\n{\n",
             "    private static readonly ImmutableArray<RegisteredEntry> All =\n    [\n"]
    for item in model.entries:
        entry = item["entry"]
        row = ROWS[item["row"]][0] if item["row"] else "None"
        lines.append(f"        new({cs_string(entry['id'])}, EntryStatus.{STATUSES[entry['status']]}, "
                     f"CorrespondenceRow.{row}, MapEntries.{item['decline_locator']}.Locator),\n")
    lines.append("    ];\n\n")
    lines.append("    private static readonly ImmutableDictionary<string, RegisteredEntry> ById =\n"
                 "        All.ToImmutableDictionary(e => e.Id, StringComparer.Ordinal);\n")
    lines.append(REGISTRY_BODY)
    lines.append("}\n")
    return "".join(lines)


def tests_cs(model):
    lines = [model.header,
             "using RulesKernel.Provenance;\n",
             "using RulesKernel.Resolution;\n",
             "using Xunit;\n\n",
             f"namespace {model.name}.Tests;\n\n",
             "public sealed class CorrespondenceTests\n{\n",
             "    private static readonly string[] MapOrder =\n    [\n"]
    for item in model.entries:
        lines.append(f"        {cs_string(item['entry']['id'])},\n")
    lines.append("    ];\n\n")
    lines.append("    [Fact]\n"
                 "    public void Every_map_entry_is_registered_in_map_order() =>\n"
                 "        Assert.Equal(MapOrder, Registry.Entries.Select(e => e.Id));\n\n")
    lines.append("    [Fact]\n"
                 "    public void Every_hand_written_handler_names_a_map_entry_once_with_the_handler_signature() =>\n"
                 "        Assert.All(MapOrder, id => _ = Registry.HasImplementation(id));\n\n")
    lines.append("    private static void AssertDeclines(string entryId, UnresolvedReason reason, string sourceId, string citation)\n"
                 "    {\n"
                 "        var unresolved = Registry.Resolve(entryId, RuleRequest.Empty).Match<UnresolvedResult?>(_ => null, u => u);\n"
                 "        Assert.NotNull(unresolved);\n"
                 "        Assert.Equal(reason, unresolved.Reason);\n"
                 "        Assert.Equal(new SourceLocator(sourceId, citation), unresolved.Locator);\n"
                 "    }\n")
    for item in model.entries:
        entry, row = item["entry"], item["row"]
        method = snake(entry["id"])
        cited = _cited_locator(model, item)
        lines.append("\n")
        if entry["status"] == "implemented":
            if row == 8:
                lines.append("    [Fact]\n"
                             f"    public void {method}__is_implemented_and_answers_or_demands_the_assertion()\n"
                             "    {\n"
                             f"        if (Registry.HasImplementation({cs_string(entry['id'])}))\n"
                             "        {\n            return;\n        }\n\n"
                             "        var value = new object();\n"
                             f"        var resolved = Registry.Resolve({cs_string(entry['id'])}, RuleRequest.Empty.Assert({cs_string(entry['id'])}, value))"
                             ".Match<object?>(v => v, _ => null);\n"
                             "        Assert.Same(value, resolved);\n"
                             f"        Assert.Throws<AssertionRequiredException>(() => Registry.Resolve({cs_string(entry['id'])}, RuleRequest.Empty));\n"
                             "    }\n")
            else:
                lines.append("    [Fact]\n"
                             f"    public void {method}__is_implemented_so_a_hand_written_handler_answers_it() =>\n"
                             f"        Assert.True(Registry.HasImplementation({cs_string(entry['id'])}), "
                             f"{cs_string(entry['id'] + ' is implemented in the overlay and has no [Implements] handler')});\n")
        elif row in (1, 2, 3, 4, 5, 6):
            reason = ROWS[row][1]
            lines.append("    [Fact]\n"
                         f"    public void {method}__declines_{reason}_row_{row}() =>\n"
                         f"        AssertDeclines({cs_string(entry['id'])}, UnresolvedReason.{reason}, "
                         f"{cs_string(cited['sourceId'])}, {cs_string(cited['citation'])});\n")
        else:
            raise GenerationError(f"entry {entry['id']!r} is {entry['status']!r} and matches no declining row; "
                                  f"check-map.py --phase consumer should have refused it")
    lines.append("}\n")
    return "".join(lines)


def _cited_locator(model, item):
    member = item["decline_locator"]
    for other in model.entries:
        if other["member"] == member:
            return other["entry"]["locator"]
    raise GenerationError(f"no located entry {member}")



# --- scaffold ------------------------------------------------------------------------------


def scaffold(model, corpus_file):
    name, pid, version = model.name, model.package_id, model.version
    packages = "\n".join(f'    <PackageVersion Include="{p}" Version="{v}" />' for p, v in TEST_PACKAGES)
    return {
        "global.json": json.dumps({"sdk": {"version": SDK_VERSION, "rollForward": "disable"}}, indent=2) + "\n",
        "NuGet.config": (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<!-- Restore talks to nuget.org and nothing else; packages.lock.json pins every content hash. -->\n"
            "<configuration>\n"
            "  <packageSources>\n"
            "    <clear />\n"
            '    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />\n'
            "  </packageSources>\n"
            "  <packageSourceMapping>\n"
            '    <packageSource key="nuget.org">\n'
            '      <package pattern="*" />\n'
            "    </packageSource>\n"
            "  </packageSourceMapping>\n"
            "</configuration>\n"),
        "Directory.Build.props": (
            "<Project>\n\n"
            "  <!-- Produced by rules-factory tools/factory. Zero-warning, deterministic builds. -->\n"
            "  <PropertyGroup>\n"
            "    <TargetFrameworks>net8.0;net10.0</TargetFrameworks>\n"
            "    <LangVersion>latest</LangVersion>\n"
            "    <Nullable>enable</Nullable>\n"
            "    <ImplicitUsings>enable</ImplicitUsings>\n"
            "    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>\n"
            "    <AnalysisLevel>latest</AnalysisLevel>\n"
            "    <EnableNETAnalyzers>true</EnableNETAnalyzers>\n"
            "    <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>\n"
            "    <Deterministic>true</Deterministic>\n"
            "    <ContinuousIntegrationBuild Condition=\"'$(CI)' == 'true'\">true</ContinuousIntegrationBuild>\n"
            "    <InvariantGlobalization>true</InvariantGlobalization>\n"
            "    <GenerateDocumentationFile>true</GenerateDocumentationFile>\n"
            "  </PropertyGroup>\n\n"
            "  <!-- Every package, the map included, is pinned by content hash in packages.lock.json;\n"
            "       CI restores in locked mode. -->\n"
            "  <PropertyGroup>\n"
            "    <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>\n"
            "    <RestoreLockedMode Condition=\"'$(CI)' == 'true'\">true</RestoreLockedMode>\n"
            "  </PropertyGroup>\n\n"
            "</Project>\n"),
        "Directory.Packages.props": (
            "<Project>\n\n"
            "  <PropertyGroup>\n"
            "    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>\n"
            "    <CentralPackageTransitivePinningEnabled>true</CentralPackageTransitivePinningEnabled>\n"
            "  </PropertyGroup>\n\n"
            "  <ItemGroup>\n"
            "    <!-- The kernel is referenced, never copied. -->\n"
            f'    <PackageVersion Include="RulesKernel" Version="{KERNEL_VERSION}" />\n'
            "  </ItemGroup>\n\n"
            "  <ItemGroup>\n"
            "    <!-- The map is referenced, never copied (rules-factory decision 0015), at an exact\n"
            "         version. The engine's own build facts live in corpus-map.overlay.json. -->\n"
            f'    <PackageVersion Include="{pid}" Version="[{version}]" />\n'
            "  </ItemGroup>\n\n"
            "  <ItemGroup>\n"
            f"{packages}\n"
            "  </ItemGroup>\n\n"
            "</Project>\n"),
        f"{name}.slnx": (
            "<Solution>\n"
            f'  <Project Path="src/{name}/{name}.csproj" />\n'
            f'  <Project Path="tests/{name}.Tests/{name}.Tests.csproj" />\n'
            "</Solution>\n"),
        f"src/{name}/{name}.csproj": (
            '<Project Sdk="Microsoft.NET.Sdk">\n\n'
            "  <ItemGroup>\n"
            '    <PackageReference Include="RulesKernel" />\n'
            "    <!-- The map this engine is built from. It carries no assemblies; its build props add\n"
            "         one RulesFactoryMap item naming the restored map, manifest and checker. -->\n"
            f'    <PackageReference Include="{pid}" PrivateAssets="all" />\n'
            "  </ItemGroup>\n\n"
            "</Project>\n"),
        f"tests/{name}.Tests/{name}.Tests.csproj": (
            '<Project Sdk="Microsoft.NET.Sdk">\n\n'
            "  <PropertyGroup>\n"
            "    <IsPackable>false</IsPackable>\n"
            "    <IsTestProject>true</IsTestProject>\n"
            "    <!-- Test names are the documentation here. -->\n"
            "    <GenerateDocumentationFile>false</GenerateDocumentationFile>\n"
            "  </PropertyGroup>\n\n"
            "  <ItemGroup>\n"
            + "".join(f'    <PackageReference Include="{p}" />\n' for p, _ in TEST_PACKAGES) +
            "  </ItemGroup>\n\n"
            "  <ItemGroup>\n"
            f'    <ProjectReference Include="../../src/{name}/{name}.csproj" />\n'
            "  </ItemGroup>\n\n"
            "</Project>\n"),
        OVERLAY_NAME: "{}\n",
    }


def generated(model):
    name = model.name
    return {
        f"src/{name}/Generated/MapEntries.g.cs": map_entries_cs(model),
        f"src/{name}/Generated/Registry.g.cs": registry_cs(model),
        f"tests/{name}.Tests/Generated/CorrespondenceTests.g.cs": tests_cs(model),
    }


def _write(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)


def produce(intake, name, out, log=None):
    """Scaffold (when absent) and generate (always) an engine for `intake` under `out`."""
    overlay_path = os.path.join(out, OVERLAY_NAME)
    overlay = {}
    if os.path.isfile(overlay_path):
        try:
            with open(overlay_path, encoding="utf-8") as handle:
                overlay = json.load(handle)
        except (OSError, ValueError) as error:
            raise GenerationError(f"cannot read {overlay_path}: {error}")
    model = Model(intake, merge(intake.map, overlay), name)
    corpus_file = os.path.basename(str(intake.corpus.get("committedPath") or intake.corpus_name))

    written = []
    for relative, text in scaffold(model, corpus_file).items():
        path = os.path.join(out, *relative.split("/"))
        if not os.path.exists(path):
            _write(path, text.encode("utf-8"))
            written.append(relative)
    _write(os.path.join(out, "corpus", corpus_file), intake.corpus_bytes)
    written.append(f"corpus/{corpus_file}")
    for relative, text in generated(model).items():
        _write(os.path.join(out, *relative.split("/")), text.encode("utf-8"))
        written.append(relative)
    if log is not None:
        rows = {}
        for item in model.entries:
            rows[item["row"]] = rows.get(item["row"], 0) + 1
        summary = ", ".join(f"row {r}: {n}" if r else f"no row: {n}" for r, n in sorted(rows.items(), key=lambda kv: kv[0] or 0))
        print(f"--- produce: {len(model.entries)} entries registered ({summary})", file=log)
        for relative in written:
            print(f"wrote {relative}", file=log)
    return model
