# Mapper notes: blind map, hoyle-1909 BACKGAMMON pp. 271-280

## Files read
All in `/tmp/claude-1000/blind-hoyle-95/bundle`:
- `SLICE.md`, `method.md`, `corpus-map.md`, `corpus-manifest.json`: read in full.
- `hoyle.txt`: lines 8195-8494 (end of the preceding chapter, all of BACKGAMMON, the start of BAGATELLE) and lines 14800-14824 (footnotes [64]-[69]). I also ran `grep` inside it to find page markers and footnotes, and a small Python search of the extent for the candidate absence terms.
- Written: `out/build.py` (builds and self-checks the map), `out/blind-map.json`, this file.

## Isolation
I followed the rules. I read and listed only inside the bundle directory (one `ls` of the bundle itself). I did not touch the parent directory, other `/tmp` paths, home, `~/.claude` or `/home/brandon/rules-factory`. I ran no git or gh and used no network. I spawned no agents. The session's primary working directory is a rules-factory worktree, but I never read or listed it; every command used absolute bundle paths. Hash verified: `5d505fa9...645e` matches SLICE.md.

## Unclear points in the method/schema, and what I did
- **Section heading for the untitled opening of the chapter.** The locator grammar wants `<section heading>`, but pp. 271-273 have none before PLAYING. I used `(introduction)`.
- **Evidence from footnotes.** Footnotes lie outside the extent, and their pages would not match the extent. I made no entries from them. [65], [66] and [67] are pronunciation or advice, recorded in notes. [68] (a further-reading pointer to *The Book of Card and Table Games*) is recorded as a `crossReferences` item with `unmapped` on `hints-two-apart`, because the manifest has no `references` to name. Someone may prefer to add it to the manifest as not admitted. I did not edit the manifest.
- **The closed list of pointer phrases is not given.** I declared every pointer I saw (see Fig. 1/2, "hereafter stated", "as in the earlier stage", "as at starting", "Of the above throws", "above-mentioned", "first-mentioned", "last mentioned", [68]).
- **Absence search semantics** (substring or word, case). I assumed case-insensitive substring. So I avoided `faces` ('surfaces'), `sides` ('both sides'), `turn` ('in turn') and `alternate` ('alternately'), and said so in the notes.
- **Ambiguity on a derived entry.** Nothing forbids it. `game-value-coverage` is derived and ambiguous, because the overlap and gap exist only between the three definitions.
- **Scope of a player's choice.** Choosing between stated moves (adopt the opening throw or re-throw; how to split doublets while bearing off) is not an open term, so these are `operation`, not `assertion`. The one assertion is the backgammon multiplier "either thrice or four times (as may have been agreed)", a fixed set fixed by agreement. The agreed stake is a parameter (no entry).
- **Granularity of advice.** I gave each opening-throw heading its own declined entry, so the comparison can go entry by entry, and mapped the heading list itself as the in-scope `possible-throws`, the only place the die range is fixed.
- **beyondAdapter status.** I gave `fig1-orientation` `scope: in`, `status: declined` (MissingRulesData, row 4), since the task lists `declined` only for out/absent entries and the schema's `status` says declined covers "the rule is unreadable".

## Main readings a comparison should look at
- Conflict `entry-onto-own-point`: `landing-restriction` (own-occupied points allowed) against `bar-entry` ("a vacant point or blot" only).
- Unresolved gaps: the order of playing the two dice; doublets as an "aggregate extent" against four moves; which die when only one can be played; whether closed-table suspension needs a man on the bar; turn alternation only presupposed; the stake a hit pays; bearing off after a man is hit; gammon/backgammon overlap plus an uncovered case; the rubber undefined.
- `rubber-scoring` is in scope although it sits in HINTS FOR PLAY.

## Possible leaks
None found. The worked examples in `method.md` and `corpus-map.md` come from FAA Part 107, leases, a sports/overtime example and a generic rulebook. None mentions backgammon, Hoyle, dice games or this chapter's vocabulary. The phrase "a player serving a penalty takes no part in play" and the overtime examples illustrate gates generically. They resemble this chapter's bar suspension only in shape.
