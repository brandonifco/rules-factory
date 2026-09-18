"""`Contracts.g.cs` and `Requests.g.cs`: the typed contract over the registry (#76).

The typed contract (#76). The registry dispatches on a string id and a `RuleRequest` that is a
dictionary of assertion values, and it stays: it is the one mechanism every entry shares, and the
correspondence tests read it. Over it, each entry gets

  * a request type of its own, `{Engine}.Requests.{Member}Request`, and a typed entry point,
    `EntryPoints.{Member}`, a `RuleEntry<{Member}Request, TOutput>`. Handing one entry's request to
    another entry does not compile. (`EntryPoints`, not `Rules`: an engine's hand-written code
    commonly lives in a `{Engine}.Rules` namespace, which a class of that name would collide with).
    The request type is `sealed partial` (#93): the map names no inputs, so an engine declares an
    entry's inputs itself, as `init` properties in a file of its own, and a caller sets them in an
    object initializer (`new {Member}Request { Position = p }`). The entry point hands that very
    object to the handler (`Registry.Resolve(IEntryRequest)`); only the dictionary dispatch,
    `Registry.Resolve(id, RuleRequest)`, builds one from the assertions, with every input at its
    default. The generated members are the constructors `()` and `(RuleRequest)`, `Empty`,
    `Asserting` on an assertion, `EntryId` and `Assertions`; since the generated code constructs
    requests, an engine's input may not be a C# `required` member;
  * a handler declaration, a partial method of `Handlers`, whose implementation is the
    hand-written code. For an entry whose merged status is `implemented` and whose row is not 8
    (the entries a correspondence test already requires a handler for) it is an extended partial
    method, `internal static partial Resolution<TOutput> {Member}({Member}Request request)`, so a
    missing implementation is CS8795 and one with another return type CS8817 or parameter
    CS0759: build errors, and the engine builds with warnings as errors, so a nullability
    mismatch (CS8826 and kin) is one too. Every other entry gets an optional hook,
    `static partial void {Member}({Member}Request request, ref Resolution<TOutput>? resolution)`,
    which may stay unimplemented and, when implemented with the wrong signature, is CS0759. An
    entry moving to `implemented` turns its hook into the required form, and the build names the
    handler to change.

Why partial methods rather than a Roslyn analyzer or source generator. An analyzer could check
`[Implements]` methods where they stand, but it is a compiled netstandard2.0 assembly referencing
Microsoft.CodeAnalysis: the factory writes source and runs no compiler, so the analyzer would have
to be a package of its own, versioned and restored and locked alongside the kernel, pinned to a
Roslyn the engine's SDK may not load, and its diagnostics would be the factory's code running
inside every engine build. A generated partial declaration costs nothing of that: it is ordinary
C# the regeneration gate already compares byte for byte, and the C# compiler itself refuses a
missing or mis-typed handler.
"""
import csharp
import semantics

CONTRACTS_SUPPORT = """
/// <summary>A request for one map entry; each entry has its own type (<c>Requests</c> namespace).</summary>
public interface IEntryRequest
{
    /// <summary>The map entry this request resolves.</summary>
    string EntryId { get; }

    /// <summary>What the caller asserts, as the registry's dictionary dispatch reads it.</summary>
    RuleRequest Assertions { get; }
}

/// <summary>
/// The typed entry point of one map entry. <typeparamref name="TInput"/> is the entry's own
/// request type, so a request for another entry does not compile. <typeparamref name="TOutput"/>
/// is the type the map declares for the entry's value, and <c>object</c> where it declares none.
/// </summary>
/// <typeparam name="TInput">The entry's request type.</typeparam>
/// <typeparam name="TOutput">The entry's value type.</typeparam>
public sealed class RuleEntry<TInput, TOutput>
    where TInput : IEntryRequest
{
    private readonly Func<TInput, Resolution<TOutput>> resolve;

    internal RuleEntry(string id, Func<TInput, Resolution<TOutput>> resolve)
    {
        Id = id;
        this.resolve = resolve;
    }

    /// <summary>The map entry's id.</summary>
    public string Id { get; }

    /// <summary>The entry as the registry holds it: status, row and citations.</summary>
    public RegisteredEntry Registered => Registry.Entry(Id);

    /// <summary>Resolves the entry through <see cref="Registry.Resolve(IEntryRequest)"/>, so its handler receives <paramref name="request"/> itself.</summary>
    /// <param name="request">The entry's request.</param>
    /// <returns>The resolution.</returns>
    public Resolution<TOutput> Resolve(TInput request)
    {
        ArgumentNullException.ThrowIfNull(request);
        return resolve(request);
    }
}
"""


def contracts_cs(model):
    """`Contracts.g.cs`: the typed entry points (`EntryPoints`) and the handler declarations (`Handlers`)."""
    lines = [model.header,
             "using System.Reflection;\n",
             "using RulesKernel.Resolution;\n\n",
             f"namespace {model.name};\n",
             CONTRACTS_SUPPORT,
             "\n/// <summary>The typed entry point of every map entry, in the map's order.</summary>\n",
             "public static class EntryPoints\n{\n"]
    for index, item in enumerate(model.entries):
        entry, c = item["entry"], semantics.contract(model, item)
        lines.append("\n" if index else "")
        lines.append(f"    /// <summary>{csharp.xml_text(entry.get('name', entry['id']))} (<c>{csharp.xml_text(entry['id'])}</c>).</summary>\n"
                     f"    public static RuleEntry<{c['request_cs']}, {c['output']}> {item['member']} {{ get; }} =\n"
                     f"        new({csharp.cs_string(entry['id'])}, request => Registry.Resolve(request));\n")
    lines.append("}\n\n")
    lines.append(
        "/// <summary>\n"
        "/// The hand-written handler of every map entry, declared as partial methods the engine implements\n"
        "/// in a file of its own. An <c>implemented</c> entry whose correspondence row has no default must\n"
        "/// have one, with exactly the declared signature, or the engine does not build. Every other entry's\n"
        "/// hook may stay unimplemented; implemented, it answers once the entry is <c>implemented</c>, and a\n"
        "/// resolution it leaves null falls through to the row's default.\n"
        "/// </summary>\n"
        "internal static partial class Handlers\n{\n")
    hooks = []
    for item in model.entries:
        entry, c = item["entry"], semantics.contract(model, item)
        summary = f"    /// <summary>{csharp.xml_text(entry.get('name', entry['id']))} (<c>{csharp.xml_text(entry['id'])}</c>)"
        if c["required"]:
            lines.append(f"{summary}: required, the entry is implemented.</summary>\n"
                         f"    internal static partial Resolution<{c['output']}> {item['member']}({c['request_cs']} request);\n\n")
        else:
            hooks.append(item)
            lines.append(f"{summary}: optional.</summary>\n"
                         f"    static partial void {item['member']}({c['request_cs']} request, ref Resolution<{c['output']}>? resolution);\n\n")
    lines.append("    /// <summary>\n"
                 "    /// The typed handler's resolution of <paramref name=\"entryId\"/>, or null when it has none or leaves it null.\n"
                 "    /// The handler receives <paramref name=\"request\"/> when it is of the entry's request type, and otherwise\n"
                 "    /// (the dictionary dispatch) a request of that type built from <paramref name=\"assertions\"/>.\n"
                 "    /// </summary>\n"
                 "    internal static Resolution<object>? Dispatch(string entryId, RuleRequest assertions, IEntryRequest? request)\n"
                 "    {\n"
                 "        Resolution<object>? resolution = null;\n")
    if model.entries:
        lines.append("        switch (entryId)\n        {\n")
        for item in model.entries:
            c = semantics.contract(model, item)
            lines.append(f"            case {csharp.cs_string(item['entry']['id'])}:\n")
            if c["required"]:
                lines.append(f"                resolution = {item['member']}(request as {c['request_cs']} ?? new(assertions));\n")
            else:
                lines.append(f"                {item['member']}(request as {c['request_cs']} ?? new(assertions), ref resolution);\n")
            lines.append("                break;\n")
        lines.append("        }\n\n")
    else:
        lines.append("        _ = entryId;\n        _ = assertions;\n        _ = request;\n")
    lines.append("        return resolution;\n    }\n\n")
    lines.append("    /// <summary>Whether <paramref name=\"entryId\"/> has a typed handler: always when it is required, and an\n"
                 "    /// optional hook when the engine implemented it (an unimplemented partial method is not compiled).</summary>\n"
                 "    internal static bool Has(string entryId) => entryId switch\n    {\n")
    for item in model.entries:
        c = semantics.contract(model, item)
        if c["required"]:
            lines.append(f"        {csharp.cs_string(item['entry']['id'])} => true,\n")
        else:
            lines.append(f"        {csharp.cs_string(item['entry']['id'])} => Hooked({csharp.cs_string(item['member'])}, typeof({c['request_cs']})),\n")
    lines.append("        _ => false,\n    };\n\n")
    lines.append("    private static bool Hooked(string name, Type request) =>\n"
                 "        typeof(Handlers).GetMethod(name, BindingFlags.NonPublic | BindingFlags.Static, [request, typeof(Resolution<object>).MakeByRefType()]) is not null;\n")
    lines.append("}\n")
    return "".join(lines)


def requests_cs(model):
    """`Requests.g.cs`: one request type per entry, in a namespace of their own."""
    lines = [model.header,
             f"namespace {model.name}.Requests;\n"]
    for item in model.entries:
        entry, c = item["entry"], semantics.contract(model, item)
        eid = csharp.cs_string(entry["id"])
        lines.append(
            "\n"
            f"/// <summary>A request to resolve {csharp.xml_text(entry.get('name', entry['id']))} (<c>{csharp.xml_text(entry['id'])}</c>).</summary>\n"
            "/// <remarks>Partial: an engine declares the entry's inputs as <c>init</c> properties in a file of its own, and a\n"
            "/// caller sets them in an object initializer; the handler receives this very object through <c>EntryPoints</c>.</remarks>\n"
            f"public sealed partial class {c['request']} : IEntryRequest\n{{\n"
            f"    /// <summary>A request for <c>{csharp.xml_text(entry['id'])}</c> asserting nothing.</summary>\n"
            f"    public {c['request']}()\n"
            "        : this(RuleRequest.Empty)\n"
            "    {\n"
            "    }\n\n"
            f"    /// <summary>A request for <c>{csharp.xml_text(entry['id'])}</c> carrying <paramref name=\"assertions\"/>.</summary>\n"
            "    /// <param name=\"assertions\">What the caller asserts.</param>\n"
            f"    public {c['request']}(RuleRequest assertions)\n"
            "    {\n"
            "        ArgumentNullException.ThrowIfNull(assertions);\n"
            "        Assertions = assertions;\n"
            "    }\n\n"
            "    /// <summary>A request asserting nothing.</summary>\n"
            f"    public static {c['request']} Empty {{ get; }} = new(RuleRequest.Empty);\n\n")
        if c["asserts"]:
            lines.append(
                "    /// <summary>A request asserting <paramref name=\"value\"/> for this assertion entry, which is what it resolves to.</summary>\n"
                "    /// <param name=\"value\">The caller's value.</param>\n"
                "    /// <returns>The request.</returns>\n"
                f"    public static {c['request']} Asserting({c['output']} value) => new(RuleRequest.Empty.Assert({eid}, value));\n\n")
        lines.append(
            "    /// <inheritdoc/>\n"
            f"    public string EntryId => {eid};\n\n"
            "    /// <inheritdoc/>\n"
            "    public RuleRequest Assertions { get; }\n"
            "}\n")
    return "".join(lines)
