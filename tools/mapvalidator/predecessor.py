"""A check that had subject matter in the version this map replaces, and has none now (#268).

Not a check: a rule about every check's verdict, applied by the command line after each one has
spoken. It reads the map a published version replaces, which is the one fact a single map cannot
supply about itself.
"""
from .diagnostics import fail


def had_no_subject(result):
    """Whether this verdict is a check declaring it found nothing to look at."""
    return result.status == "skip" and not result.had_subject


def silenced_by_the_change(name, check, result, previous, where):
    """The verdict a check that lost its subject matter gets, or None to leave it alone.

    `check-map.py` reports NOT VERIFIED for a check with no subject matter and, when the check
    declares it had none, **exits 0**. That is right for a corpus that genuinely has no gates and
    no assertions. It is wrong when the subject matter was there a moment ago and the damage is
    what removed it, and both halves were measured: turning a map's only assertion into an
    operation silences `asserted-by`, removing the rule every other entry was suspended by
    silences `gates`, and `tools/mutate-map.py` watched the gate stay green through both.

    The validator cannot know from one map whether a corpus has assertions. It can know that
    *this* map had them: a published map package is a version, and its predecessor is a fact
    (0015). A check that had subject matter in the version being replaced and has none now is a
    claim that the corpus changed, and that claim belongs in the diff a mapper writes rather than
    in a silent skip. `tools/mapper/`'s re-mapping guidance has had this shape since trial 3 --
    diff entry content, never the entry list -- and the validator had nothing.

    What it cannot do:

      * **It says nothing without a predecessor.** A first map has none, and a caller who does not
        pass `--previous` gets exactly the behaviour #268 describes. `tools/mutate-map.py` passes
        it, because the harness holds both versions; `tools/pack-map.py` does not, because the
        publish gate reads the working tree and the previous version is on nuget.org, which is the
        same reason it already states that nothing there compares a version number against the one
        it replaces.
      * **It compares verdicts, not corpora.** That a check went quiet is all it reads; whether
        the corpus really lost its assertions is the mapper's to state, and this refuses the
        silence rather than judging the answer.
      * **It cannot see a check that lost half its subject matter.** An assertion removed from a
        map that has five leaves `asserted-by` looking at four and saying `ok`. Only the last one
        turns this on, which is the same shape as a map whose extent narrows by one page.
    """
    if previous is None or not had_no_subject(result):
        return None
    try:
        before = check(previous)
    except Exception as error:  # a check that raises on the published version has proved nothing
        return fail([f"  X  {name}: {result.summary}, and the same check raised "
                     f"{type(error).__name__} on {where}, so whether this map is the one that "
                     f"silenced it cannot be read (#268)"],
                    "this check has no subject matter here and the version it replaces could not "
                    "be checked")
    if had_no_subject(before):
        return None
    return fail([f"  X  {name}: {result.summary} -- and {where}, the version this map replaces, "
                 f"had subject matter for it: {before.summary}. A corpus that lost its "
                 f"assertions, its gates or its definitions between two versions is a change the "
                 f"map's diff states, not a check that goes quiet (#268)"],
                "this check had subject matter in the version being replaced and has none here")
