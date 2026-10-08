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
import sys

import acceptancecs
import csharp
import semantics

FILE = "acceptance.json"
ADAPTER = "ActionSurface.cs"

#: The declared fields, each with the sentence a refusal says about it.
#: The largest count a declaration may hold: the harness declares them as C# `int` constants.
MAXIMUM = 2147483647

#: The most decimal places `leastCompleted` may have. The harness compares `completed >= LeastCompleted *
#: played` in `decimal`, which holds 28 digits: 18 places and a count's 10 digits fit, so the product is exact.
PLACES = 18

FIELDS = {
    "seedsPerConfiguration": f"an integer from 1 to {MAXIMUM}: how many seeds each configuration plays",
    "stepCap": f"an integer from 1 to {MAXIMUM}: the most steps a run may take before it is over",
    "leastCompleted": f"a number above 0 and at most 1, to at most {PLACES} decimal places: the fraction of a "
                      f"configuration's seeds that must reach a natural end",
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


# map-overlay.py is loaded by path, below, and the loader writes a module's bytecode beside it unless this
# is set before it does: a checkout the run dirties (#384). Set at import, so before that load.
sys.dont_write_bytecode = True

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
    # Read exactly (a Decimal), so 1.00000000000000001 is above 1 and is not rounded into it, and held
    # exactly: the harness holds a C# decimal, so a value it cannot hold in PLACES is refused, not rounded.
    least = declared["leastCompleted"]
    if isinstance(least, bool) or not isinstance(least, (int, decimal.Decimal)) or not 0 < least <= 1:
        raise _refuse(f"`leastCompleted` is {_shown(least)}; it must be {FIELDS['leastCompleted']}")
    least = _exact(decimal.Decimal(least))
    if -least.as_tuple().exponent > PLACES:
        raise _refuse(f"`leastCompleted` is {_shown(declared['leastCompleted'])}; it must be {FIELDS['leastCompleted']}")
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
            "leastCompleted": least, "allowlist": dict(sorted(allowlist.items()))}


def _exact(value):
    """`value` without the trailing zeros of its fraction (no rounding: that is a context's, not a digit's)."""
    sign, digits, exponent = value.as_tuple()
    digits = list(digits)
    while exponent < 0 and len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    return decimal.Decimal((sign, tuple(digits), exponent))


def _decimal(value):
    """A C# `decimal` literal for the exact value."""
    return format(value, "f") + "m"


def tests_cs(model):
    """The harness for `model.acceptance`, with the declared numbers baked in."""
    declared = model.acceptance
    allowlist = "".join(f"        ({csharp.cs_string(entry_id)}, {csharp.cs_string(documented)}),\n"
                        for entry_id, documented in declared["allowlist"].items())
    values = {"@HEADER@": model.header, "@NAME@": model.name,
              "@SEEDS@": str(declared["seedsPerConfiguration"]), "@CAP@": str(declared["stepCap"]),
              "@LEAST@": _decimal(declared["leastCompleted"]), "@ALLOWLIST@": allowlist}
    # One pass, so nothing a value says is read as a marker.
    return re.sub("|".join(values), lambda match: values[match.group(0)],
                  acceptancecs.HARNESS.replace("@DUMP@", DUMP))


#: The nested `StructuralDump` class: a reflective walk, written apart so the harness reads as the invariants.
DUMP = """    // A reflective walk. A value is written one of three ways. A type that is known to be an exact
    // scalar is written as its type, its length and its text, in a format that round-trips: the
    // primitives, string, char, decimal (from decimal.GetBits, so the sign of zero and the scale are
    // kept), enums (the assembly-qualified type and the underlying value), DateTime, DateTimeOffset,
    // DateOnly, TimeOnly, TimeSpan, Guid, BigInteger, Half, Int128 and UInt128. A type that is known to
    // be a collection (an array, List, HashSet, SortedSet, Queue, Stack, LinkedList, Dictionary,
    // SortedDictionary, SortedList and the System.Collections.Immutable collections) is written by its
    // items alone, its fields being bookkeeping: a map and a set are sorted by the dump of each entry,
    // and every other sequence keeps its order, a sequence of KeyValuePair included. A grouping is
    // written as its Key and its items. Any other enumerable of a System namespace, or marked
    // CompilerGenerated (an iterator method's state machine), is written by its items alone: its fields
    // are iteration machinery, and a deferred LINQ iterator is its own enumerator, so reading them and
    // then enumerating moves them. Every other type, any System IFormattable (a Uri) included, is
    // written by every instance field, public and private, sorted by name, and by its items too if it
    // is enumerable, enumerated first so that a self-enumerating type is in one state each time; the
    // walk of a type that derives from a known collection stops at it, its items standing for its
    // fields. Every string-valued element is framed by its kind and its length, so no text can
    // reproduce a neighbouring field. Delegates and pointers are skipped. A dump depends on no
    // hash code, culture or clock, and a record's own equality, which compares its collections by
    // reference, is not used. Not compared: object identity and aliasing, a collection's comparer, NaN
    // payloads, array lower bounds.
    internal static class StructuralDump
    {
        private const int DepthLimit = 64;

        private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        private static readonly HashSet<Type> KnownSequences =
        [
            typeof(List<>), typeof(Queue<>), typeof(Stack<>), typeof(LinkedList<>),
            typeof(ImmutableArray<>), typeof(ImmutableList<>), typeof(ImmutableQueue<>), typeof(ImmutableStack<>),
        ];

        private static readonly HashSet<Type> KnownMaps =
        [
            typeof(Dictionary<,>), typeof(SortedDictionary<,>), typeof(SortedList<,>),
            typeof(ImmutableDictionary<,>), typeof(ImmutableSortedDictionary<,>),
        ];

        private static readonly HashSet<Type> KnownSets =
        [
            typeof(HashSet<>), typeof(SortedSet<>), typeof(ImmutableHashSet<>), typeof(ImmutableSortedSet<>),
        ];

        public static string Of(object? value)
        {
            var text = new StringBuilder();
            Write(text, value, 0, "$", []);
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

        // Kind, then the length of the text in brackets, then the text: the one way anything that is
        // text is written, so what follows a frame is the next field and never a part of this one.
        private static void Frame(StringBuilder text, string kind, string value) =>
            text.Append(kind).Append('[').Append(value.Length).Append("]:").Append(value);

        // The type that identifies a Type, an enum or a missing element: assembly-qualified, and for a
        // generic parameter (which has no name of its own to qualify) its declaring type's and its position.
        private static string NameOf(Type type)
        {
            if (type.IsGenericParameter)
            {
                var owner = type.DeclaringMethod is { } method
                    ? method.DeclaringType?.AssemblyQualifiedName + " " + method
                    : type.DeclaringType?.AssemblyQualifiedName;
                return owner + " #" + type.GenericParameterPosition;
            }

            return type.AssemblyQualifiedName ?? type.FullName ?? type.ToString();
        }

        // "seq", "map" or "set" for a type that is known to be a collection, or null.
        private static string? Known(Type type)
        {
            if (type.IsArray)
            {
                return "seq";
            }

            if (!type.IsGenericType)
            {
                return null;
            }

            var definition = type.GetGenericTypeDefinition();
            return KnownSequences.Contains(definition) ? "seq" : KnownMaps.Contains(definition) ? "map" : KnownSets.Contains(definition) ? "set" : null;
        }

        private static void Write(StringBuilder text, object? value, int depth, string path, List<object> above)
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
                    Frame(text, "type", NameOf(t));
                    return;
            }

            var type = value.GetType();
            if (Exact(text, value, type))
            {
                return;
            }

            // Reached again while it is still being written: a cycle, written as how far back it is.
            // Aliasing without a cycle is written in full each time.
            var back = above.FindIndex(ancestor => ReferenceEquals(ancestor, value));
            if (back >= 0)
            {
                Frame(text, "cycle", back.ToString(Inv));
                return;
            }

            above.Add(value);
            try
            {
                Structure(text, value, type, depth, path, above);
            }
            finally
            {
                above.RemoveAt(above.Count - 1);
            }
        }

        private static void Structure(StringBuilder text, object value, Type type, int depth, string path, List<object> above)
        {
            var known = Known(type);
            if (known is not null)
            {
                if (type.IsGenericType && type.GetGenericTypeDefinition() == typeof(ImmutableArray<>)
                    && (bool)type.GetProperty("IsDefault")!.GetValue(value)!)
                {
                    Frame(text, "default", NameOf(type.GetGenericArguments()[0]));
                    return;
                }

                WriteItems(text, (IEnumerable)value, known, type, depth, path, above);
                return;
            }

            Frame(text, "object", type.FullName ?? type.Name);
            text.Append('{');

            // Enumerated before its fields are read.
            string? itemsText = null;
            if (value is IEnumerable items)
            {
                var one = new StringBuilder();
                var grouping = type.GetInterfaces()
                    .FirstOrDefault(i => i.IsGenericType && i.GetGenericTypeDefinition() == typeof(IGrouping<,>));
                if (grouping is not null)
                {
                    one.Append("key=");
                    Write(one, grouping.GetProperty("Key")!.GetValue(value), depth + 1, path + ".Key", above);
                    one.Append(";items=");
                }
                else
                {
                    one.Append("items=");
                }

                WriteItems(one, items, Shape(type, items), type, depth, path, above);
                itemsText = one.ToString();
                if (grouping is not null || IsIterationMachinery(type))
                {
                    text.Append(itemsText).Append('}');
                    return;
                }
            }

            for (var t = type; t is not null && t != typeof(object) && t != typeof(ValueType) && Known(t) is null; t = t.BaseType)
            {
                var fields = t.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
                    .Where(f => !f.FieldType.IsPointer && !typeof(Delegate).IsAssignableFrom(f.FieldType))
                    .OrderBy(f => f.Name, StringComparer.Ordinal);
                foreach (var field in fields)
                {
                    Frame(text, "field", (t == type ? "" : t.FullName + ".") + field.Name);
                    text.Append('=');
                    Write(text, field.GetValue(value), depth + 1, path + "." + field.Name, above);
                    text.Append(';');
                }
            }

            if (itemsText is not null)
            {
                text.Append(itemsText);
            }

            text.Append('}');
        }

        // An enumerable whose fields are how it iterates.
        private static bool IsIterationMachinery(Type type) =>
            type.Namespace is "System" || (type.Namespace?.StartsWith("System.", StringComparison.Ordinal) ?? false)
            || type.IsDefined(typeof(System.Runtime.CompilerServices.CompilerGeneratedAttribute), false);

        // The shape of an enumerable that is not a known collection: a map is a value whose type
        // implements IDictionary, IDictionary<,> or IReadOnlyDictionary<,>; a set implements ISet<>,
        // IReadOnlySet<> or IImmutableSet<>; every other sequence keeps its order.
        private static string Shape(Type type, IEnumerable sequence)
        {
            var interfaces = type.GetInterfaces();
            if (sequence is IDictionary
                || interfaces.Any(i => i.IsGenericType && (i.GetGenericTypeDefinition() == typeof(IDictionary<,>)
                    || i.GetGenericTypeDefinition() == typeof(IReadOnlyDictionary<,>))))
            {
                return "map";
            }

            return interfaces.Any(i => i.IsGenericType && (i.GetGenericTypeDefinition() == typeof(ISet<>)
                || i.GetGenericTypeDefinition() == typeof(IReadOnlySet<>)
                || i.GetGenericTypeDefinition() == typeof(IImmutableSet<>))) ? "set" : "seq";
        }

        private static void WriteItems(StringBuilder text, IEnumerable sequence, string shape, Type type, int depth, string path, List<object> above)
        {
            var items = new List<string>();
            if (shape == "map")
            {
                foreach (var (key, entry) in Entries(sequence))
                {
                    var one = new StringBuilder();
                    Write(one, key, depth + 1, path + "[key]", above);
                    one.Append("=>");
                    Write(one, entry, depth + 1, path + "[value]", above);
                    items.Add(one.ToString());
                }
            }
            else
            {
                var index = 0;
                foreach (var item in sequence)
                {
                    var one = new StringBuilder();
                    Write(one, item, depth + 1, path + "[" + index + "]", above);
                    items.Add(one.ToString());
                    index++;
                }
            }

            if (shape != "seq")
            {
                items.Sort(StringComparer.Ordinal);
            }

            text.Append(shape).Append(type.IsArray ? "[" + string.Join(",", Enumerable.Range(0, type.GetArrayRank()).Select(d => ((Array)sequence).GetLength(d))) + "]" : "")
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

        // The closed list of types written as scalars: nothing else is, however it formats.
        private static bool Exact(StringBuilder text, object value, Type type)
        {
            string shown;
            switch (value)
            {
                case string s:
                    shown = s;
                    break;
                case char c:
                    shown = c.ToString();
                    break;
                case bool b:
                    shown = b ? "true" : "false";
                    break;
                case float or double or Half:
                    shown = ((IFormattable)value).ToString("R", Inv);
                    break;
                case decimal m:
                    shown = string.Join(",", decimal.GetBits(m).Select(bits => bits.ToString(Inv)));
                    break;
                case Enum:
                    Frame(text, NameOf(type), ((IFormattable)value).ToString("d", Inv));
                    return true;
                case DateTime or DateTimeOffset or DateOnly or TimeOnly:
                    shown = ((IFormattable)value).ToString("O", Inv);
                    break;
                case TimeSpan span:
                    shown = span.ToString("c", Inv);
                    break;
                case Guid guid:
                    shown = guid.ToString("D", Inv);
                    break;
                case System.Numerics.BigInteger or Int128 or UInt128:
                    shown = ((IFormattable)value).ToString(null, Inv);
                    break;
                default:
                    if (!type.IsPrimitive)
                    {
                        return false;
                    }

                    shown = value is IFormattable formattable ? formattable.ToString(null, Inv) : value.ToString()!;
                    break;
            }

            Frame(text, type.FullName!, shown);
            return true;
        }
    }
"""
