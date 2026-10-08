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
        Same(one, new Hashtable { ["b"] = 2, ["a"] = 1 }, "an IDictionary that is not generic");
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

    internal static partial bool IsOver(Counter state) =>
        state.Value >= 10 || (Variant == "ending-drift" && Zero(state) && Replaying(state));

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

        if ((Variant == "decline-allowed" && Affected(state)) || (Variant == "slow" && state.Configuration == "beta"))
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
