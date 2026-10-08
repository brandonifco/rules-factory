"""`ActionSurfaceAcceptance.g.cs`: the full-play acceptance harness of an engine that declares an
action surface (decision 0078).

Most engines answer requests, and the correspondence tests hold that at each entry. An engine that
also exposes an **action surface** -- a way to start a state, list the actions legal in it and apply
one -- is not shown to work by its entries' tests alone. So an engine that wants the harness
declares its surface, and the factory does not guess it:

  * `acceptance.json` at the engine root is the declaration. It is engine-owned: its presence is the
    declaration, and `produce` reads it and never writes it. This module validates it (`load`), so
    a malformed one is refused at produce time, naming the field.
  * The harness (`tests_cs`) is generated into the test project only when that file exists. It holds
    the declared numbers as constants, the invariants as xUnit facts, and the members the engine
    implements in its own adapter (`tests/{name}.Tests/ActionSurface.cs`, which `produce` never
    writes) as C# partial methods with an accessibility modifier, which the compiler requires an
    implementation of (CS8795): a declaration with no adapter does not build, and the error names
    each missing member.

The state and action types are the engine's. A partial method cannot take a type parameter the
adapter chooses without making the class generic, and xUnit does not run a generic test class, so
the harness names two aliases, `ActionSurfaceState` and `ActionSurfaceAction`, which the adapter
binds with `global using`.

The resolutions are the kernel's: `Resolution<T>` and `UnresolvedReason`, so `RequiresInterpretation`
and the locator a decline carries are the ones every other part of the engine means.

When the file is absent nothing is emitted, and `produce` removes a harness emitted earlier, as it
removes any generated file whose source is gone.
"""
import decimal
import importlib.util
import json
import os
import re

import acceptancecs
import csharp
import semantics

FILE = "acceptance.json"
ADAPTER = "ActionSurface.cs"

#: The declared fields, each with the sentence a refusal says about it.
#: The largest count a declaration may hold: the harness declares them as C# `int` constants.
MAXIMUM = 2147483647

FIELDS = {
    "seedsPerConfiguration": f"an integer from 1 to {MAXIMUM}: how many seeds each configuration plays",
    "stepCap": f"an integer from 1 to {MAXIMUM}: the most steps a run may take before it is over",
    "leastCompleted": "a number above 0 and at most 1: the fraction of a configuration's seeds that must reach "
                      "a natural end",
    "allowlist": "an object mapping an entry id to a sentence saying where the engine documents that reading",
}


def harness_path(name):
    return f"tests/{name}.Tests/Generated/ActionSurfaceAcceptance.g.cs"


def _refuse(message):
    return semantics.GenerationError(f"{FILE}: {message}")


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    for key in keys:
        if keys.count(key) > 1:
            raise ValueError(f"the key {key!r} appears twice")
    return dict(pairs)


def _no_constants(token):
    raise ValueError(f"{token} is not a number a declaration can hold")


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _shown(value):
    """A declared value as it was written: a number is held exactly (a Decimal), and says so as written."""
    return str(value) if isinstance(value, decimal.Decimal) else repr(value)


_PLACEHOLDER_RULE = []


def _placeholder_problem(text):
    """Why `text` is not a sentence, or None: the floor the overlay's mutations are held to (#239).

    It is `placeholder_problem` of the gate recipe (`map-overlay.py`), loaded from where this module
    sits: `scripts/` in an engine, `recipe/` in the factory. Not a copy of it, so the two cannot drift.
    """
    if not _PLACEHOLDER_RULE:
        here = os.path.dirname(os.path.abspath(__file__))
        for candidate in (os.path.join(here, os.pardir, "map-overlay.py"), os.path.join(here, "recipe", "map-overlay.py")):
            if os.path.isfile(candidate):
                spec = importlib.util.spec_from_file_location("map_overlay_recipe", candidate)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                _PLACEHOLDER_RULE.append(module.placeholder_problem)
                break
        else:
            raise _refuse("cannot check an allowlist item for a placeholder: map-overlay.py is not where this module expects it")
    return _PLACEHOLDER_RULE[0](text)


def load(root, model):
    """The validated declaration in `root`, or None when the engine declares no action surface.

    A refusal names the field. An allowlist id is checked against the entries of `model`, the merged
    (possibly composed) map, in the form the registry uses: a composed engine's `Package.entry-id`.
    """
    path = os.path.join(root, FILE)
    if not os.path.lexists(path):
        return None
    if os.path.islink(path):
        raise _refuse("is a symbolic link; the declaration is the engine's own file, and a link would read "
                      "whatever it points to")
    if not os.path.isfile(path):
        raise _refuse("is not a file")
    try:
        with open(path, encoding="utf-8") as handle:
            declared = json.load(handle, object_pairs_hook=_no_duplicates, parse_constant=_no_constants,
                                 parse_float=decimal.Decimal)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise _refuse(f"cannot be read as JSON ({error})")
    if not isinstance(declared, dict):
        raise _refuse("is not an object of seedsPerConfiguration, stepCap, leastCompleted and allowlist")
    extra = sorted(set(declared) - set(FIELDS))
    if extra:
        raise _refuse(f"{', '.join(repr(k) for k in extra)} is not a field of the declaration "
                      f"({', '.join(FIELDS)})")
    for field in FIELDS:
        if field not in declared:
            raise _refuse(f"`{field}` is missing; it is {FIELDS[field]}")
    for field in ("seedsPerConfiguration", "stepCap"):
        if not _integer(declared[field]) or not 1 <= declared[field] <= MAXIMUM:
            raise _refuse(f"`{field}` is {_shown(declared[field])}; it must be {FIELDS[field]}")
    # Read exactly (a Decimal), so 1.00000000000000001 is above 1 and is not rounded into it; and the
    # constant the harness holds, a double, must still be above 0.
    least = declared["leastCompleted"]
    if (isinstance(least, bool) or not isinstance(least, (int, decimal.Decimal)) or not 0 < least <= 1
            or not 0 < float(least) <= 1):
        raise _refuse(f"`leastCompleted` is {_shown(least)}; it must be {FIELDS['leastCompleted']}")
    allowlist = declared["allowlist"]
    if not isinstance(allowlist, dict):
        raise _refuse(f"`allowlist` is {allowlist!r}; it must be {FIELDS['allowlist']}")
    for entry_id, documented in allowlist.items():
        if not isinstance(documented, str):
            raise _refuse(f"`allowlist` item {entry_id!r} is {documented!r}; it must say, in a string, where "
                          f"the engine documents that reading")
        why = _placeholder_problem(documented)
        if why:
            raise _refuse(f"`allowlist` item {entry_id!r} is below the floor an overlay's mutations are held to, "
                          f"{why}; it must be a sentence saying where the engine documents that reading")
        if entry_id not in model.by_id:
            raise _refuse(f"`allowlist` item {entry_id!r} is not an entry of this engine's map; an item is an "
                          f"entry id, in the form the registry uses")
    return {"seedsPerConfiguration": declared["seedsPerConfiguration"], "stepCap": declared["stepCap"],
            "leastCompleted": float(least), "allowlist": dict(sorted(allowlist.items()))}


def _double(value):
    return repr(float(value))


def tests_cs(model):
    """The harness for `model.acceptance`, with the declared numbers baked in."""
    declared = model.acceptance
    allowlist = "".join(f"        ({csharp.cs_string(entry_id)}, {csharp.cs_string(documented)}),\n"
                        for entry_id, documented in declared["allowlist"].items())
    values = {"@HEADER@": model.header, "@NAME@": model.name,
              "@SEEDS@": str(declared["seedsPerConfiguration"]), "@CAP@": str(declared["stepCap"]),
              "@LEAST@": _double(declared["leastCompleted"]), "@ALLOWLIST@": allowlist}
    # One pass, so nothing a value says is read as a marker.
    return re.sub("|".join(values), lambda match: values[match.group(0)],
                  acceptancecs.HARNESS.replace("@DUMP@", DUMP))


#: The nested `StructuralDump` class: a reflective walk, written apart so the harness reads as the invariants.
DUMP = """    // A reflective walk over every instance field, public and private, sorted by name. A map (a type
    // that implements IDictionary, IDictionary<,> or IReadOnlyDictionary<,>, and nothing else) and a
    // set are sorted by the dump of each entry; every other sequence keeps its order, a sequence of
    // KeyValuePair included. Every scalar carries its runtime type's full name, and its value in a
    // format that round-trips. It depends on no hash code, culture or clock, and a record's own
    // equality, which compares its collections by reference, is not used. Not compared: object
    // identity and aliasing, a collection's comparer, NaN payloads, array lower bounds.
    internal static class StructuralDump
    {
        private const int DepthLimit = 64;

        private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        public static string Of(object? value)
        {
            var text = new StringBuilder();
            Write(text, value, 0, "$");
            return text.ToString();
        }

        public static int FirstDifference(string left, string right)
        {
            var i = 0;
            while (i < left.Length && i < right.Length && left[i] == right[i])
            {
                i++;
            }

            return i;
        }

        public static string Around(string left, string right)
        {
            var at = FirstDifference(left, right);
            var from = Math.Max(0, at - 40);
            string Cut(string s) => s.Substring(from, Math.Min(s.Length - from, 100));
            return $"'{Cut(left)}' then '{Cut(right)}'";
        }

        // The engine's own type: not System and not inside it. An array of an engine type is not one.
        private static bool Owned(Type type)
        {
            var space = type.Namespace ?? "";
            return !type.IsArray && space != "System" && !space.StartsWith("System.", StringComparison.Ordinal);
        }

        private static void Write(StringBuilder text, object? value, int depth, string path)
        {
            if (depth > DepthLimit)
            {
                throw new InvalidOperationException($"the structural dump is deeper than {DepthLimit} levels at {path}");
            }

            switch (value)
            {
                case null:
                    text.Append("null");
                    return;
                case Delegate or Pointer:
                    text.Append("<skipped>");
                    return;
                case Type t:
                    text.Append("typeof(").Append(t.FullName).Append(')');
                    return;
            }

            var type = value.GetType();
            if (Scalar(text, value, type))
            {
                return;
            }

            if (type.IsGenericType && type.GetGenericTypeDefinition() == typeof(ImmutableArray<>)
                && (bool)type.GetProperty("IsDefault")!.GetValue(value)!)
            {
                text.Append("default<").Append(type.GetGenericArguments()[0].FullName).Append('>');
                return;
            }

            if (value is IEnumerable sequence && !Owned(type))
            {
                WriteSequence(text, sequence, type, depth, path);
                return;
            }

            // The engine's own enumerable is its fields and its items; the fields of a System base
            // class it derives from are that class's bookkeeping, which its items already stand for.
            text.Append(type.FullName).Append('{');
            WriteFields(text, value, type, depth, path, value is IEnumerable);
            if (value is IEnumerable items)
            {
                text.Append("items=");
                WriteSequence(text, items, type, depth, path);
            }

            text.Append('}');
        }

        private static void WriteFields(StringBuilder text, object value, Type type, int depth, string path, bool ownedOnly)
        {
            for (var t = type; t is not null && t != typeof(object) && t != typeof(ValueType) && (!ownedOnly || Owned(t)); t = t.BaseType)
            {
                var fields = t.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
                    .Where(f => !f.FieldType.IsPointer && !typeof(Delegate).IsAssignableFrom(f.FieldType))
                    .OrderBy(f => f.Name, StringComparer.Ordinal);
                foreach (var field in fields)
                {
                    text.Append(t == type ? "" : t.Name + ".").Append(field.Name).Append('=');
                    Write(text, field.GetValue(value), depth + 1, path + "." + field.Name);
                    text.Append(';');
                }
            }
        }

        private static void WriteSequence(StringBuilder text, IEnumerable sequence, Type type, int depth, string path)
        {
            var interfaces = type.GetInterfaces();
            var map = sequence is IDictionary
                || interfaces.Any(i => i.IsGenericType && (i.GetGenericTypeDefinition() == typeof(IDictionary<,>)
                    || i.GetGenericTypeDefinition() == typeof(IReadOnlyDictionary<,>)));
            var set = interfaces.Any(i => i.IsGenericType && (i.GetGenericTypeDefinition() == typeof(ISet<>)
                || i.GetGenericTypeDefinition() == typeof(IReadOnlySet<>)
                || i.GetGenericTypeDefinition() == typeof(System.Collections.Immutable.IImmutableSet<>)));
            var items = new List<string>();
            if (map)
            {
                foreach (var (key, entry) in Entries(sequence))
                {
                    var one = new StringBuilder();
                    Write(one, key, depth + 1, path + "[key]");
                    one.Append("=>");
                    Write(one, entry, depth + 1, path + "[value]");
                    items.Add(one.ToString());
                }
            }
            else
            {
                var index = 0;
                foreach (var item in sequence)
                {
                    var one = new StringBuilder();
                    Write(one, item, depth + 1, path + "[" + index + "]");
                    items.Add(one.ToString());
                    index++;
                }
            }

            if (map || set)
            {
                items.Sort(StringComparer.Ordinal);
            }

            text.Append(map ? "map" : set ? "set" : "seq").Append(type.IsArray ? "[" + string.Join(",", Enumerable.Range(0, type.GetArrayRank()).Select(d => ((Array)sequence).GetLength(d))) + "]" : "")
                .Append('(').Append(items.Count).Append("){").Append(string.Join(", ", items)).Append('}');
        }

        private static IEnumerable<(object? Key, object? Value)> Entries(IEnumerable sequence)
        {
            if (sequence is IDictionary dictionary)
            {
                var entries = dictionary.GetEnumerator();
                while (entries.MoveNext())
                {
                    yield return (entries.Key, entries.Value);
                }

                yield break;
            }

            foreach (var item in sequence)
            {
                var itemType = item?.GetType();
                if (itemType is { IsGenericType: true } && itemType.GetGenericTypeDefinition() == typeof(KeyValuePair<,>))
                {
                    yield return (itemType.GetProperty("Key")!.GetValue(item), itemType.GetProperty("Value")!.GetValue(item));
                }
                else
                {
                    throw new InvalidOperationException($"a map enumerates {itemType?.FullName ?? "null"}, which is not a key/value pair");
                }
            }
        }

        private static bool Scalar(StringBuilder text, object value, Type type)
        {
            // An exact format where the type has one; the fallback is only for a type that has none:
            // the integers, decimal, Guid, Half, BigInteger and the rest of System and System.Numerics,
            // whose default format under the invariant culture is exact.
            var shown = value switch
            {
                string s => Quoted(s),
                char c => Quoted(c.ToString()),
                bool b => b ? "true" : "false",
                Enum => value.ToString(),
                float or double => ((IFormattable)value).ToString("R", Inv),
                DateTime d => d.ToString("O", Inv),
                DateTimeOffset o => o.ToString("O", Inv),
                DateOnly o => o.ToString("O", Inv),
                TimeOnly o => o.ToString("O", Inv),
                TimeSpan s => s.ToString("c", Inv),
                _ => null,
            };
            if (shown is null && (type.IsPrimitive || (value is IFormattable && type.Namespace is "System" or "System.Numerics" && value is not IEnumerable)))
            {
                shown = value is IFormattable formattable ? formattable.ToString(null, Inv) : value.ToString();
            }

            if (shown is null)
            {
                return false;
            }

            text.Append(type.FullName).Append(':').Append(shown);
            return true;
        }

        private static string Quoted(string value)
        {
            var text = new StringBuilder("\\"");
            foreach (var c in value)
            {
                if (c is '\\\\' or '"' || c < ' ')
                {
                    text.Append("\\\\u").Append(((int)c).ToString("x4", Inv));
                }
                else
                {
                    text.Append(c);
                }
            }

            return text.Append('"').ToString();
        }
    }
"""
