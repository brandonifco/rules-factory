"""`Registry.g.cs`: every entry, the correspondence row it matches, and the handler that answers it.

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
    A hand-written handler (the typed partial method `Handlers` declares, contracts.py, or an `[Implements("entry-id")]`
    method) replaces the default -- **only for an entry whose merged status is `implemented`**.
    A `mapped` entry declines even when its code exists (corpus-map.md, `status`), so the
    override is ignored until the overlay says so;

`[Implements]` is kept, and is the migrating part. Reflection still discovers it, as the runtime
cross-check it was: it names a map entry, has the untyped signature, and appears once, and now
also that the same entry has no typed handler as well. It can still answer an entry whose handler
is optional. An engine whose `implemented` entry was answered only by an `[Implements]` method no
longer builds until the required partial method exists (it may simply call the old method).
"""
import csharp
import semantics

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
/// Marks an untyped hand-written handler for a map entry. The method must be static, take one
/// <see cref="RuleRequest"/> and return <c>Resolution&lt;object&gt;</c>, and it is checked only at
/// runtime. It answers only once the entry's merged status is <c>implemented</c>; until then the
/// entry declines as its row says. Prefer the typed partial method <see cref="Handlers"/> declares
/// for the entry, which the compiler checks; an entry that has both is refused, and an
/// <c>implemented</c> entry whose row has no default needs the typed one to build at all.
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
/// <param name="Locators">
/// Every locator the entry cites. One, its own, for a located entry. For a derived entry
/// (rules-factory decision 0012), the locator of every located entry it rests on, following
/// derived sources down, depth-first in <c>derivedFrom</c> order, each locator once at its first
/// place: the premises entail the fact together, so a decline citing only the first says less
/// than the map knows. <see cref="Registry.Citations"/> reads them for a declined entry.
/// </param>
public sealed record RegisteredEntry(string Id, EntryStatus Status, CorrespondenceRow Row, ImmutableArray<SourceLocator> Locators)
{
    /// <summary>
    /// Who the corpus lets assert this entry, the map's <c>assertedBy</c> (rules-factory decision 0025): the
    /// corpus's own words, or <c>caller</c> where the corpus names nobody. Empty on an entry that is not
    /// <c>kind: assertion</c>. An engine checks an assertion's attribution against these, not its own reading.
    /// </summary>
    public ImmutableArray<string> AssertedBy { get; init; } = [];

REGISTERED_ENTRY_EQUALITY

    /// <summary>
    /// The locator its declines cite, the first of <see cref="Locators"/>: the kernel's
    /// <see cref="UnresolvedResult"/> holds one, and the rest are read through <see cref="Registry.Citations"/>.
    /// </summary>
    public SourceLocator Locator => Locators[0];
}
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

    /// <summary>
    /// Every locator <paramref name="entryId"/> cites, for a caller holding its decline. The
    /// kernel's <see cref="UnresolvedResult.Locator"/> is one locator, the first of these; a
    /// derived entry rests on all of them.
    /// </summary>
    /// <param name="entryId">A map entry id.</param>
    /// <returns>The entry's <see cref="RegisteredEntry.Locators"/>.</returns>
    /// <exception cref="KeyNotFoundException">The map has no such entry.</exception>
    public static ImmutableArray<SourceLocator> Citations(string entryId) => Entry(entryId).Locators;

    /// <summary>
    /// Whether a hand-written handler exists for <paramref name="entryId"/>: a typed partial method
    /// of <see cref="Handlers"/>, or an <see cref="ImplementsAttribute"/> method.
    /// </summary>
    /// <param name="entryId">A map entry id.</param>
    /// <returns>True when one exists, whether or not the entry's status lets it answer.</returns>
    /// <exception cref="InvalidOperationException">An <see cref="ImplementsAttribute"/> method is malformed or duplicates a handler.</exception>
    public static bool HasImplementation(string entryId) => Implementations.Value.ContainsKey(entryId) || Handlers.Has(entryId);

    /// <summary>
    /// Resolves <paramref name="entryId"/>: through its hand-written handler when the entry is
    /// <c>implemented</c> and has one (the typed handler first, which answers unless an optional
    /// hook leaves the resolution null), otherwise through the default its correspondence row fixes.
    /// A typed handler receives a request of its entry's type built from <paramref name="request"/>
    /// alone, so any input property an engine declares on that type has its default value; to pass
    /// inputs, resolve through <see cref="Resolve(IEntryRequest)"/> or <see cref="EntryPoints"/>.
    /// </summary>
    /// <param name="entryId">A map entry id.</param>
    /// <param name="request">What the caller asserts.</param>
    /// <returns>The resolution.</returns>
    public static Resolution<object> Resolve(string entryId, RuleRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        return Answer(Entry(entryId), request, null);
    }

    /// <summary>
    /// Resolves the entry <paramref name="request"/> is for, exactly as
    /// <see cref="Resolve(string, RuleRequest)"/> does for its id and assertions, except that a
    /// typed handler receives <paramref name="request"/> itself, with every input property the
    /// engine declared on its type. The typed entry points in <see cref="EntryPoints"/> resolve
    /// through here.
    /// </summary>
    /// <param name="request">A request for one map entry.</param>
    /// <returns>The resolution.</returns>
    public static Resolution<object> Resolve(IEntryRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        var assertions = request.Assertions ?? throw new ArgumentException("the request carries no assertions", nameof(request));
        return Answer(Entry(request.EntryId), assertions, request);
    }

    private static Resolution<object> Answer(RegisteredEntry entry, RuleRequest assertions, IEntryRequest? request)
    {
        // Discovery runs on the first resolve whatever answers it, so a malformed or duplicate
        // [Implements] handler is refused even for an entry a typed handler answers.
        var untyped = Implementations.Value;
        if (entry.Status == EntryStatus.Implemented)
        {
            if (Handlers.Dispatch(entry.Id, assertions, request) is { } typed)
            {
                return typed;
            }

            if (untyped.TryGetValue(entry.Id, out var handler))
            {
                return handler(assertions);
            }
        }

        return Default(entry, assertions);
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

                    if (Handlers.Has(implements.EntryId))
                    {
                        throw new InvalidOperationException($"'{implements.EntryId}' has a typed handler in Handlers and an [Implements] handler, {where}; keep one");
                    }

                    found.Add(implements.EntryId, method.CreateDelegate<Func<RuleRequest, Resolution<object>>>());
                }
            }
        }

        return found.ToImmutable();
    }
"""


def registry_cs(model):
    support = REGISTRY_SUPPORT.replace(
        "REGISTERED_ENTRY_EQUALITY",
        csharp.value_record_equality(
            "RegisteredEntry", ("Id", "Status", "Row"), ("Locators", "AssertedBy")).rstrip())
    lines = [model.header,
             "using System.Collections.Immutable;\n",
             "using System.Reflection;\n",
             "using RulesKernel.Provenance;\n",
             "using RulesKernel.Resolution;\n\n",
             f"namespace {model.name};\n",
             support,
             "\n/// <summary>Every map entry, the correspondence row it matches first, and the handler that answers it.</summary>\n",
             "public static class Registry\n{\n",
             "    private static readonly ImmutableArray<RegisteredEntry> All =\n    [\n"]
    for item in model.entries:
        entry = item["entry"]
        row = semantics.ROWS[item["row"]][0] if item["row"] else "None"
        lines.append(f"        new({csharp.cs_string(entry['id'])}, EntryStatus.{semantics.STATUSES[entry['status']]}, "
                     f"CorrespondenceRow.{row}, "
                     f"[{', '.join(f'MapEntries.{m}.Locator' for m in item['locators'])}]){csharp.asserted_by_init(entry)},\n")
    lines.append("    ];\n\n")
    lines.append("    private static readonly ImmutableDictionary<string, RegisteredEntry> ById =\n"
                 "        All.ToImmutableDictionary(e => e.Id, StringComparer.Ordinal);\n")
    lines.append(REGISTRY_BODY)
    lines.append("}\n")
    return "".join(lines)
