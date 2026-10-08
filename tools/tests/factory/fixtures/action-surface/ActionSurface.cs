// The adapter of a toy action surface, for tests/factory/test_factory_acceptance.py (decision 0078).
// It is a fixture: a counter that offers +1 and +2 and is over at 10 or more, written against the
// HoyleBackgammon engine that scripts/validate-engine.sh produces. The test copies it, with the
// engine's name, to tests/HoyleBackgammon.Tests/ActionSurface.cs, which is where an engine's own
// adapter lives and which `produce` never writes.
//
// One build serves every case: the environment variable ACTION_SURFACE_FIXTURE names the violation
// to commit, so each invariant is shown red without a rebuild per case. Each violation happens only in
// the runs `Affected` names, so the others still complete and the one invariant under test is the only
// one broken.
global using ActionSurfaceState = HoyleBackgammon.Tests.Counter;
global using ActionSurfaceAction = HoyleBackgammon.Tests.Step;

using System.Collections;
using System.Collections.Immutable;
using System.Numerics;
using RulesKernel.Provenance;
using RulesKernel.Resolution;

namespace HoyleBackgammon.Tests;

/// <summary>A toy state. Not a record, and equal by <see cref="Value"/> alone, as a record that
/// compares its collections by reference would be: its equality cannot tell two replays apart.</summary>
public sealed class Counter : IEquatable<Counter>
{
    private int stamp;

    public Counter(string configuration, int seed, int value, ImmutableArray<int> trail, int stamp)
    {
        Configuration = configuration;
        Seed = seed;
        Value = value;
        Trail = trail;
        this.stamp = stamp;
    }

    public string Configuration { get; }

    public int Seed { get; }

    public int Value { get; }

    public ImmutableArray<int> Trail { get; }

    public ImmutableArray<int> NeverSet { get; }

    public ImmutableDictionary<string, int> Tally { get; init; } = ImmutableDictionary<string, int>.Empty;

    public ImmutableHashSet<int> Seen { get; init; } = [];

    public Func<int> Ignored { get; init; } = () => 0;

    public int Stamp() => stamp;

    // What a call on a state must not do: change a field of the state it was given.
    public void Poke() => stamp++;

    public Counter Next(int by, int stampNow) =>
        new(Configuration, Seed, Value + by, Trail.Add(by), stampNow)
        {
            Tally = Tally.SetItem(by.ToString(), Tally.GetValueOrDefault(by.ToString()) + 1),
            Seen = Seen.Add(by),
        };

    public bool Equals(Counter? other) => other is not null && Value == other.Value;

    public override bool Equals(object? obj) => Equals(obj as Counter);

    public override int GetHashCode() => Value;
}

public readonly record struct Step(int By);

public sealed class Box
{
    public object? Value;
}

/// <summary>Two fields, each of which may hold any value: the field after one is what the one must not reproduce.</summary>
public sealed class Pair(object? first, object? second)
{
    public readonly object? First = first;

    public readonly object? Second = second;
}

public sealed class Node
{
    public string? Label;

    public Node? Next;
}

public enum Colour
{
    Red = 1,
    Green = 2,
}

public enum Shade
{
    Red = 1,
    Green = 2,
}

/// <summary>An engine's own enumerable: a field and items, neither of which the other may stand for.</summary>
public sealed class Labelled(string label, params int[] items) : IEnumerable<int>
{
    private readonly string label = label;

    public IEnumerator<int> GetEnumerator() => ((IEnumerable<int>)items).GetEnumerator();

    IEnumerator IEnumerable.GetEnumerator() => GetEnumerator();
}

/// <summary>An engine's own list: the list's capacity is bookkeeping, and the label is not.</summary>
public sealed class Hand(string label) : List<int>
{
    private readonly string label = label;
}

/// <summary>The structural dump, on paired values that must dump differently (and some that must not).</summary>
public sealed class FixtureDump
{
    private static string Dump(object? value) => ActionSurfaceAcceptance.StructuralDump.Of(value);

    private static void Differ(object? left, object? right, string why) =>
        Xunit.Assert.True(Dump(left) != Dump(right), why + $": both dump as {Dump(left)}");

    private static void Same(object? left, object? right, string why) =>
        Xunit.Assert.True(Dump(left) == Dump(right), why + $": {Dump(left)} then {Dump(right)}");

    [Xunit.Fact]
    public void A_sequence_of_pairs_keeps_its_order_and_only_a_map_is_sorted()
    {
        var ab = new List<KeyValuePair<string, int>> { new("a", 1), new("b", 2) };
        var ba = new List<KeyValuePair<string, int>> { new("b", 2), new("a", 1) };
        Differ(ab, ba, "a list of pairs");
        Differ(ab.ToArray(), ba.ToArray(), "an array of pairs");
        Differ(ab.ToImmutableArray(), ba.ToImmutableArray(), "an immutable array of pairs");
        var one = new Dictionary<string, int> { ["a"] = 1, ["b"] = 2 };
        var other = new Dictionary<string, int> { ["b"] = 2, ["a"] = 1 };
        Same(one, other, "a dictionary does not depend on the order it was filled in");
        Same(one, ImmutableDictionary.CreateRange(other), "a dictionary and an immutable one");
        Differ(one, new Dictionary<string, int> { ["a"] = 1, ["b"] = 3 }, "a dictionary with another value");
    }

    [Xunit.Fact]
    public void A_scalar_carries_its_runtime_type()
    {
        Differ(new Box { Value = 1 }, new Box { Value = 1L }, "a boxed int and a boxed long");
        Differ(new Box { Value = (byte)1 }, new Box { Value = (sbyte)1 }, "a boxed byte and sbyte");
        Differ(new Box { Value = '1' }, new Box { Value = "1" }, "a char and a string");
        Differ(new Dictionary<object, int> { [1] = 1 }, new Dictionary<object, int> { [1L] = 1 }, "the keys 1 and 1L");
        Differ(default(ImmutableArray<int>), default(ImmutableArray<string>), "a default array of ints and of strings");
        Same(new Box { Value = 1 }, new Box { Value = 1 }, "two boxed ints");
    }

    [Xunit.Fact]
    public void Date_time_and_floating_point_values_are_dumped_so_that_they_round_trip()
    {
        Differ(new TimeOnly(12, 0, 1), new TimeOnly(12, 0, 2), "times a second apart");
        Differ(new TimeOnly(12, 0, 1), new TimeOnly(12, 0, 1).Add(TimeSpan.FromTicks(1)), "times a tick apart");
        Differ(new DateOnly(2026, 10, 7), new DateOnly(2026, 10, 8), "dates a day apart");
        var noon = new DateTime(2026, 10, 7, 12, 0, 0, DateTimeKind.Utc);
        Differ(noon, noon.AddTicks(1), "date times a tick apart");
        Differ(noon, DateTime.SpecifyKind(noon, DateTimeKind.Unspecified), "a UTC time and an unspecified one");
        Differ(new DateTimeOffset(noon), new DateTimeOffset(noon.AddTicks(1)), "offset times a tick apart");
        Differ(new DateTimeOffset(2026, 10, 7, 12, 0, 0, TimeSpan.Zero), new DateTimeOffset(2026, 10, 7, 12, 0, 0, TimeSpan.FromHours(1)), "one clock reading, two offsets");
        Differ(TimeSpan.FromTicks(1), TimeSpan.FromTicks(2), "spans a tick apart");
        Differ(0.1 + 0.2, 0.3, "doubles that print alike to fifteen digits");
        Differ(1f, float.BitIncrement(1f), "adjacent floats");
        Differ(0.0, -0.0, "zero and negative zero");
        Same(new TimeOnly(12, 0, 1), new TimeOnly(12, 0, 1), "equal times");
        Same(noon, new DateTime(2026, 10, 7, 12, 0, 0, DateTimeKind.Utc), "equal date times");
    }

    [Xunit.Fact]
    public void An_enumerable_of_the_engines_own_is_its_fields_and_its_items()
    {
        Differ(new Labelled("x", 1, 2), new Labelled("y", 1, 2), "the same items under two labels");
        Differ(new Labelled("x", 1, 2), new Labelled("x", 1, 3), "one label over two items");
        Same(new Labelled("x", 1, 2), new Labelled("x", 1, 2), "equal ones");
        var small = new Hand("x") { 1, 2 };
        var roomy = new Hand("x") { Capacity = 100 };
        roomy.AddRange([1, 2]);
        Same(small, roomy, "a list's capacity is its bookkeeping, not its value");
        Differ(small, new Hand("y") { 1, 2 }, "a derived list's own field");
        Differ(small, new Hand("x") { 1, 3 }, "a derived list's items");
    }

    [Xunit.Fact]
    public void A_system_enumerable_that_is_not_a_known_collection_is_walked_by_its_fields_and_its_items()
    {
        // Second review of 44614be, findings 2 and 3: a System enumerable, and a System IFormattable.
        int[] items = [1, 2, 3];
        var alice = items.GroupBy(_ => "alice").First();
        var bob = items.GroupBy(_ => "bob").First();
        Xunit.Assert.True(alice.SequenceEqual(bob), "the groupings hold the same items");
        Differ(alice, bob, "two groupings with different keys over the same items");
        Same(alice, items.GroupBy(_ => "alice").First(), "two groupings with one key");
    }

    [Xunit.Fact]
    public void A_system_formattable_that_is_not_an_exact_scalar_is_walked_by_its_fields()
    {
        var upper = new Uri("HTTP://EXAMPLE.COM/a");
        var lower = new Uri("http://example.com/a");
        Xunit.Assert.Equal(upper.ToString(), lower.ToString());
        Differ(upper, lower, "two URIs that differ only in the string they were made from");
        var again = new Uri("http://example.com/a");
        Xunit.Assert.Equal(lower.ToString(), again.ToString()); // both have computed what they compute lazily
        Same(lower, again, "two URIs made from one string");
        Differ(new Pair(upper, "x"), new Pair(lower, "x"), "the same, as a field of a state");
    }

    [Xunit.Fact]
    public void A_cycle_is_written_as_a_reference_back_and_is_not_walked_forever()
    {
        static Node Ring(string label)
        {
            var (first, second) = (new Node { Label = label }, new Node { Label = label + "2" });
            (first.Next, second.Next) = (second, first);
            return first;
        }

        Same(Ring("x"), Ring("x"), "two equal rings");
        Differ(Ring("x"), Ring("y"), "two rings with different labels");
        var loop = new Node { Label = "x" };
        loop.Next = loop;
        var pair = new Node { Label = "x", Next = new Node { Label = "x" } };
        Differ(loop, pair, "a node that is its own next, and one that is not");
    }

    [Xunit.Fact]
    public void A_decimal_keeps_its_scale_and_the_sign_of_zero()
    {
        var negative = new decimal(0, 0, 0, true, 0);
        Xunit.Assert.Equal(0m, negative);
        Differ(0m, negative, "zero and negative zero");
        Differ(1.0m, 1.00m, "one at two scales");
        Differ(new Box { Value = 0m }, new Box { Value = negative }, "the same, as a field");
        Same(1.50m, 1.50m, "equal decimals");
    }

    [Xunit.Fact]
    public void Generic_parameters_are_told_apart_and_so_are_equal_names_in_two_enums()
    {
        var list = typeof(List<>).GetGenericArguments()[0];
        var key = typeof(Dictionary<,>).GetGenericArguments()[0];
        var value = typeof(Dictionary<,>).GetGenericArguments()[1];
        Xunit.Assert.Equal(list.GenericParameterPosition, key.GenericParameterPosition);
        Differ(list, key, "T of List<> and TKey of Dictionary<,>");
        Differ(key, value, "TKey and TValue of Dictionary<,>");
        Same(list, typeof(List<>).GetGenericArguments()[0], "the same parameter twice");
        Differ(typeof(List<int>), typeof(List<long>), "two constructed types");
        Differ(typeof(int), typeof(long), "two plain types");
        Differ(Colour.Red, Shade.Red, "enums of two types with one value");
        Differ(Colour.Red, Colour.Green, "enums of one type with two values");
        Differ(new Box { Value = Colour.Red }, new Box { Value = 1 }, "an enum and its underlying value");
    }

    [Xunit.Fact]
    public void Every_scalar_and_string_is_framed_by_its_length_and_cannot_reproduce_a_neighbour()
    {
        // The text of one string is the prefix of the next entry's: only the length tells them apart.
        var left = new Dictionary<string, string> { ["a"] = "b=>System.String:c" };
        var right = new Dictionary<string, string> { ["a=>System.String:b"] = "c" };
        Differ(left, right, "a key and a value that split one text two ways");
        Differ(new Pair("ab", "c"), new Pair("a", "bc"), "two fields that split one text two ways");
        Differ(new Pair("x", "y"), new Pair("x;Second=System.String:y", ""), "a field that carries the next one");
        Xunit.Assert.Contains("System.String[5]:alice", Dump("alice"));
        Xunit.Assert.Contains("System.Int32[2]:42", Dump(42));
        Differ(new[] { "a", "b" }, new[] { "a, System.String[1]:b" }, "two elements, one element");
        Differ(new Pair(new Uri("http://h/a"), "b"), new Pair(new Uri("http://h/a"), "b "), "a trailing space");
        Differ(BigInteger.Parse("12"), BigInteger.Parse("123"), "big integers");
        Same(BigInteger.Parse("12"), BigInteger.Parse("12"), "equal big integers");
    }

    [Xunit.Fact]
    public void An_ending_is_its_fields_and_two_locators_that_split_alike_end_differently()
    {
        // Second review of 44614be, finding 4: a display string cannot tell where the source ends.
        static UnresolvedResult Declined(string source, string citation, string attempted = "the fixture leaves it open",
            UnresolvedReason reason = UnresolvedReason.RequiresInterpretation) =>
            new(reason, attempted, new SourceLocator(source, citation));
        var one = ActionSurfaceAcceptance.Ending.Stopped(Declined("core", "1.2"));
        var split = ActionSurfaceAcceptance.Ending.Stopped(Declined("core-1", "2"));
        Differ(one, split, "two locators that split source and citation differently");
        Same(one, ActionSurfaceAcceptance.Ending.Stopped(Declined("core", "1.2")), "two equal endings");
        Differ(one, ActionSurfaceAcceptance.Ending.Completed(), "a decline and a natural end");
        Differ(one, ActionSurfaceAcceptance.Ending.Stopped(Declined("core", "1.2", reason: UnresolvedReason.OutsideCurrentScope)), "two reasons");
        Differ(one, ActionSurfaceAcceptance.Ending.Stopped(Declined("core", "1.2", "another operation")), "two attempted operations");
        // A locator prints as 'a / b / c' for both of these.
        var (left, right) = (Declined("a", "b / c"), Declined("a / b", "c"));
        Xunit.Assert.Equal(left.Locator.ToString(), right.Locator.ToString());
        Differ(ActionSurfaceAcceptance.Ending.Stopped(left), ActionSurfaceAcceptance.Ending.Stopped(right),
            "locators that print alike and split source and citation differently");
    }
}

public sealed class FixtureEquality
{
    // What the structural dump is for: this state's equality cannot see a private field, so two
    // replays that differ only in it are "equal" to everything but the dump.
    [Xunit.Fact]
    public void Equality_cannot_see_a_private_field()
    {
        var one = new Counter("alpha", 0, 10, [], stamp: 1);
        var other = new Counter("alpha", 0, 10, [], stamp: 2);
        Xunit.Assert.Equal(one, other);
        Xunit.Assert.NotEqual(one.Stamp(), other.Stamp());
    }
}

public sealed partial class ActionSurfaceAcceptance
{
    private static readonly string Variant = Environment.GetEnvironmentVariable("ACTION_SURFACE_FIXTURE") ?? "correct";

    private static int stamps;

    // How many times the first seed of alpha was started: once for the play, twice for its replay.
    private static int zeroStarts;

    private static Counter? shared;

    private static Counter? lastResult;

    // The runs a violation is committed in: a quarter of the alpha configuration's seeds, so the
    // completion fraction the fixture declares still holds.
    private static bool Affected(Counter state) => state.Configuration == "alpha" && state.Seed % 4 == 0 && state.Value >= 6;

    // The first seed of alpha, in its replay.
    private static bool Replaying(Counter state) => state.Configuration == "alpha" && state.Seed == 0 && Volatile.Read(ref zeroStarts) >= 2;

    private static bool Zero(Counter state) => state.Configuration == "alpha" && state.Seed == 0 && state.Value >= 6;

    // What the engine's registry answers for an entry it has not built: UnsupportedRule, a refusal.
    private static Resolution<T> Refusal<T>(string entryId) =>
        Registry.Resolve(entryId, RuleRequest.Empty)
            .Match(_ => throw new InvalidOperationException(entryId + " resolved; the fixture needs a declined entry"),
                   Resolution<T>.FromUnresolved);

    // A reading left open: RequiresInterpretation, at the locator of the entry that documents it.
    private static Resolution<T> Open<T>(string entryId, UnresolvedReason reason = UnresolvedReason.RequiresInterpretation) =>
        Resolution<T>.FromUnresolved(new UnresolvedResult(reason, "the fixture leaves " + entryId + " open", Registry.Entry(entryId).Locator));

    internal static partial ImmutableArray<string> Configurations() => ["alpha", "beta"];

    internal static partial Counter Start(string configuration, int seed)
    {
        if (configuration == "alpha" && seed == 0)
        {
            Interlocked.Increment(ref zeroStarts);
        }

        // One object for every Start, already over, whose private stamp every Start moves on.
        if (Variant == "singleton" && configuration == "alpha" && seed == 0)
        {
            shared ??= new Counter(configuration, seed, 10, [], 0);
            shared.Poke();
            return shared;
        }

        return new(configuration, seed, configuration == "alpha" ? 0 : 4, [],
            Variant == "drift" ? Interlocked.Increment(ref stamps) : 0);
    }

    internal static partial bool IsOver(Counter state)
    {
        // A lazily finalizing IsOver: it caches an incrementing stamp on a terminal state it is asked
        // about, after the harness has dumped that state.
        if (Variant == "isover-cache" && state.Configuration == "alpha" && state.Seed == 0 && state.Value >= 10)
        {
            state.Poke();
        }

        return state.Value >= 10 || (Variant == "ending-drift" && Zero(state) && Replaying(state));
    }

    internal static partial Resolution<ImmutableArray<Step>> LegalActions(Counter state)
    {
        if (Variant == "mutate-legal" && Affected(state))
        {
            state.Poke();
        }

        if (Variant == "decline-history" && Zero(state))
        {
            return Resolution<ImmutableArray<Step>>.FromValue(Replaying(state) ? [new Step(5), new Step(6)] : [new Step(1), new Step(2)]);
        }

        // Off the allowlist in both runs, and the same display in both: 'a b c'. Only the split of the
        // locator into its source and its citation differs between the play and the replay.
        if (Variant == "locator-split" && Zero(state))
        {
            return Resolution<ImmutableArray<Step>>.FromUnresolved(new UnresolvedResult(UnresolvedReason.RequiresInterpretation,
                "the fixture leaves it open", Replaying(state) ? new SourceLocator("a", "b c") : new SourceLocator("a b", "c")));
        }

        if (Variant == "ending-drift" && Zero(state))
        {
            return Open<ImmutableArray<Step>>("rubber-scoring");
        }

        if (Variant == "throw" && Affected(state))
        {
            throw new InvalidOperationException("the fixture throws here");
        }

        if (Variant == "stall" && Affected(state))
        {
            return Resolution<ImmutableArray<Step>>.FromValue([]);
        }

        if (Variant == "decline-outside" && Affected(state))
        {
            return Open<ImmutableArray<Step>>("must-play-whole-throw");
        }

        if (Variant == "decline-reason" && Affected(state))
        {
            return Open<ImmutableArray<Step>>("rubber-scoring", UnresolvedReason.OutsideCurrentScope);
        }

        // Half of alpha's two seeds decline on the allowlisted reading, so only the other half can complete.
        if ((Variant == "half" && state.Configuration == "alpha" && state.Seed == 1)
            || (Variant == "decline-allowed" && Affected(state)) || (Variant == "slow" && state.Configuration == "beta"))
        {
            return Open<ImmutableArray<Step>>("rubber-scoring");
        }

        return Resolution<ImmutableArray<Step>>.FromValue([new Step(1), new Step(2)]);
    }

    internal static partial Resolution<Counter> Apply(Counter state, Step action)
    {
        if (Variant == "mutate" && Affected(state))
        {
            state.Poke();
        }

        if (Variant == "decline-history" && Zero(state))
        {
            return Open<Counter>("rubber-scoring");
        }

        if (Variant == "alias" && state.Configuration == "alpha" && state.Seed == 0)
        {
            // The result of one offered action is changed by the probe of the next: the chosen
            // result must be kept exactly as it was returned.
            lastResult?.Poke();
            var result = state.Next(action.By, state.Stamp());
            lastResult = result;
            return Resolution<Counter>.FromValue(result);
        }

        if (Variant == "transient" && state.Configuration == "alpha" && state.Seed == 0)
        {
            // A stamp that is nowhere in the final state: the runs converge, and differ on the way.
            return Resolution<Counter>.FromValue(state.Next(action.By, state.Value + action.By < 10 ? Interlocked.Increment(ref stamps) : 0));
        }

        if (Variant == "refuse" && Affected(state) && action.By == 2)
        {
            return Refusal<Counter>("player-count");
        }

        if (Variant == "loop" && Affected(state))
        {
            return Resolution<Counter>.FromValue(state.Next(action.By - state.Value, state.Stamp()));
        }

        return Resolution<Counter>.FromValue(state.Next(action.By, state.Stamp()));
    }

    internal static partial string Render(Step action) =>
        Variant == "render-constant" ? "+" : $"+{action.By}" + (Variant == "history-drift" ? "#" + Interlocked.Increment(ref stamps) : "");
}
