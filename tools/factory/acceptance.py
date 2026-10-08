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
import json
import os
import re

import acceptancecs
import csharp
import semantics

FILE = "acceptance.json"
ADAPTER = "ActionSurface.cs"

#: The declared fields, each with the sentence a refusal says about it.
FIELDS = {
    "seedsPerConfiguration": "an integer of at least 1: how many seeds each configuration plays",
    "stepCap": "an integer of at least 1: the most steps a run may take before it is over",
    "leastCompleted": "a number above 0 and at most 1: the fraction of a configuration's seeds that must reach "
                      "a natural end",
    "allowlist": "an object mapping an entry id to a non-empty string saying where the engine documents that "
                 "reading",
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


def load(root, model):
    """The validated declaration in `root`, or None when the engine declares no action surface.

    A refusal names the field. An allowlist id is checked against the entries of `model`, the merged
    (possibly composed) map, in the form the registry uses: a composed engine's `Package.entry-id`.
    """
    path = os.path.join(root, FILE)
    if not os.path.lexists(path):
        return None
    if not os.path.isfile(path):
        raise _refuse("is not a file")
    try:
        with open(path, encoding="utf-8") as handle:
            declared = json.load(handle, object_pairs_hook=_no_duplicates, parse_constant=_no_constants)
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
        if not _integer(declared[field]) or declared[field] < 1:
            raise _refuse(f"`{field}` is {declared[field]!r}; it must be {FIELDS[field]}")
    least = declared["leastCompleted"]
    if isinstance(least, bool) or not isinstance(least, (int, float)) or not 0 < least <= 1:
        raise _refuse(f"`leastCompleted` is {least!r}; it must be {FIELDS['leastCompleted']}")
    allowlist = declared["allowlist"]
    if not isinstance(allowlist, dict):
        raise _refuse(f"`allowlist` is {allowlist!r}; it must be {FIELDS['allowlist']}")
    for entry_id, documented in allowlist.items():
        if not isinstance(documented, str) or not documented.strip():
            raise _refuse(f"`allowlist` item {entry_id!r} is {documented!r}; it must say, in a non-empty "
                          f"string, where the engine documents that reading")
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
DUMP = """    // A reflective walk over every instance field, public and private, sorted by name; sequences
    // item by item; dictionaries and sets by the sorted dump of each key or item. It depends on
    // no hash code, culture or clock, and a record's own equality, which compares its collections
    // by reference, is not used.
    private static class StructuralDump
    {
        private const int DepthLimit = 64;

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
                case string s:
                    Quote(text, s);
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
                text.Append("default");
                return;
            }

            if (value is IEnumerable sequence)
            {
                WriteSequence(text, sequence, type, depth, path);
                return;
            }

            text.Append(type.FullName).Append('{');
            for (var t = type; t is not null && t != typeof(object) && t != typeof(ValueType); t = t.BaseType)
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

            text.Append('}');
        }

        private static void WriteSequence(StringBuilder text, IEnumerable sequence, Type type, int depth, string path)
        {
            var interfaces = type.GetInterfaces();
            var pairs = sequence is IDictionary
                || interfaces.Any(i => i.IsGenericType && i.GetGenericTypeDefinition() == typeof(IEnumerable<>)
                    && i.GetGenericArguments()[0].IsGenericType
                    && i.GetGenericArguments()[0].GetGenericTypeDefinition() == typeof(KeyValuePair<,>));
            var set = interfaces.Any(i => i.IsGenericType && (i.GetGenericTypeDefinition() == typeof(ISet<>)
                || i.GetGenericTypeDefinition() == typeof(IReadOnlySet<>)
                || i.GetGenericTypeDefinition() == typeof(System.Collections.Immutable.IImmutableSet<>)));
            var items = new List<string>();
            var index = 0;
            foreach (var item in sequence)
            {
                var one = new StringBuilder();
                if (pairs)
                {
                    var (key, entry) = item is DictionaryEntry de
                        ? (de.Key, de.Value)
                        : (item!.GetType().GetProperty("Key")!.GetValue(item), item.GetType().GetProperty("Value")!.GetValue(item));
                    Write(one, key, depth + 1, path + "[key]");
                    one.Append("=>");
                    Write(one, entry, depth + 1, path + "[" + one + "]");
                }
                else
                {
                    Write(one, item, depth + 1, path + "[" + index + "]");
                }

                items.Add(one.ToString());
                index++;
            }

            if (pairs || set)
            {
                items.Sort(StringComparer.Ordinal);
            }

            text.Append(pairs ? "map" : set ? "set" : "seq").Append(type.IsArray ? "[" + string.Join(",", Enumerable.Range(0, type.GetArrayRank()).Select(d => ((Array)sequence).GetLength(d))) + "]" : "")
                .Append('(').Append(items.Count).Append("){").Append(string.Join(", ", items)).Append('}');
        }

        private static bool Scalar(StringBuilder text, object value, Type type)
        {
            switch (value)
            {
                case Enum:
                    text.Append(type.Name).Append('.').Append(value.ToString());
                    return true;
                case float or double:
                    text.Append(((IFormattable)value).ToString("R", CultureInfo.InvariantCulture));
                    return true;
                case DateTime d:
                    text.Append(d.ToString("O", CultureInfo.InvariantCulture));
                    return true;
                case DateTimeOffset o:
                    text.Append(o.ToString("O", CultureInfo.InvariantCulture));
                    return true;
                case TimeSpan s:
                    text.Append(s.ToString("c", CultureInfo.InvariantCulture));
                    return true;
                case bool b:
                    text.Append(b ? "true" : "false");
                    return true;
                case char c:
                    text.Append('\\'').Append(c).Append('\\'');
                    return true;
            }

            if (type.IsPrimitive || (value is IFormattable && type.Namespace is "System" or "System.Numerics" && value is not IEnumerable))
            {
                text.Append(value is IFormattable formattable ? formattable.ToString(null, CultureInfo.InvariantCulture) : value.ToString());
                return true;
            }

            return false;
        }

        private static void Quote(StringBuilder text, string value)
        {
            text.Append('"');
            foreach (var c in value)
            {
                if (c is '\\\\' or '"' || c < ' ')
                {
                    text.Append("\\\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                }
                else
                {
                    text.Append(c);
                }
            }

            text.Append('"');
        }
    }
"""
