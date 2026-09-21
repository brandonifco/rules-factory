"""An `ambiguity.question` quotes the passage its two readings turn on (#271).

Beside `ambiguity.py` rather than inside it: the block's own shape, its conflict groups and its
decision records are one module's worth of rules already, and the builder caps a joined module
at 300 lines. What lives here is the anchoring, and the reading of the corpus's words that
anchoring is defined over.
"""
import re
import unicodedata

from .diagnostics import skip, verdict
from mapcontract.entry import block, entries_of, label, quotes_withheld

# The run length, and why three. Every one of the 64 ambiguities the committed maps record
# shares a run of at least three consecutive words with a passage one of those maps quotes; the
# shortest are "miles per hour", "source of fear" and "about 6 seconds". Four refuses seven of
# them. The invented block `tools/mutate-map.py --only clear-to-ambiguous` writes shares three
# words with one map of five -- "between the two", of which the corpus owns not one -- which is
# why an anchoring run must also carry a word outside the closed classes below.
ANCHOR_WORDS = 3
# Words a run can be made of without quoting anybody: articles, pronouns, prepositions,
# conjunctions, auxiliaries and the bare quantifiers. A digit is not among them -- "about 6
# seconds" anchors on the number the corpus prints.
FUNCTION_WORDS = frozenset("""
a an the this that these those each every any all some no none other another same such
i me my we us our you your he him his she her it its they them their who whom whose which what
of in on at to from by for with without within into onto over under above below between among
across through during before after since until up down out off about against per as than
and or but nor so yet if then when where while because although though unless whether either
neither both not only also just more most less least very too here there now
is are was were be been being am do does did done have has had having
will would shall should can could may might must
one two three four five six seven eight nine ten first second third
""".split())
NOT_A_WORD = re.compile(r"[^0-9a-z']+")
# What a quotation of the corpus is read through, so an entry quoting the extraction's curly
# apostrophe and a question typing a straight one are the same words.
FOLDED_PAIRS = (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                ("—", " "), ("–", " "), ("‒", " "))


def corpus_words(text):
    """`text` as the words a quotation of it shares with the corpus.

    Case, spacing, punctuation and the dash-and-quote pairs an extraction prints are the
    typesetter's rather than the corpus's; `crossReferences.cites` is compared after whitespace
    normalisation for the same reason. Nothing else is done -- no stemming, no synonyms -- so a
    run that matches is a run the mapper copied.
    """
    folded = unicodedata.normalize("NFKC", str(text or "")).lower()
    for character, plain in FOLDED_PAIRS:
        folded = folded.replace(character, plain)
    return [word for word in (w.strip("'") for w in NOT_A_WORD.sub(" ", folded).split()) if word]


def runs_of(words, length=ANCHOR_WORDS):
    """Every run of `length` consecutive words, as space-joined strings."""
    return {" ".join(words[at:at + length]) for at in range(len(words) - length + 1)}


def quoted_runs(document):
    """Every run the map's quoted evidence contains, one entry's evidence at a time.

    Per entry, never over the concatenation: a run straddling two entries' evidence is a phrase
    no passage contains, and admitting it would anchor a question to an accident of entry order.
    """
    found = set()
    for entry in entries_of(document):
        if isinstance(entry, dict):
            found |= runs_of(corpus_words(entry.get("evidence")))
    return found


def anchor_of(question, available):
    """The run of the corpus's words this question quotes, or None.

    A run of only function words is not one: that is the question's own grammar meeting the
    corpus's, and it carries no word anybody had to read the passage to write.
    """
    for run in sorted(runs_of(corpus_words(question))):
        if run in available and any(word not in FUNCTION_WORDS for word in run.split()):
            return run
    return None


def check_question_anchor(ctx):
    """An `ambiguity.question` quotes the passage its two readings turn on (#271).

    A `crossReferences` item names a `cites` string that appears verbatim in the entry's own
    evidence: a reference is anchored to the passage that makes it rather than asserted beside
    it. An `ambiguity` on the same entry had no such rule. Its `question` was free prose tied to
    no word of the corpus, so a mapper who invented doubt the corpus settles -- a complete and
    plausible block, with a `fate` and a valid `unresolvedReason` -- passed on 5 of the 5 maps
    `tools/mutate-map.py` attacks.

    The rule is on `question` and not on a new field, because a new field can only be carried by
    a map written after it exists, and the 64 ambiguities this repository has already committed
    are the evidence it had to hold for. A question quotes the corpus: a run of at least
    `ANCHOR_WORDS` consecutive words appearing verbatim in quoted `evidence`, carrying at least
    one word outside `FUNCTION_WORDS`.

    **The anchor is the corpus as this map quotes it, not only this entry's own evidence.** Two
    readings can turn on a passage another entry holds -- hazmat's IB3 row is ambiguous because
    of what § 172.102(b)(4) says, and backgammon's `legal-destination` because of a sentence
    three later -- and five committed ambiguities are exactly that shape. This is the one place
    the rule is weaker than `cross-references`, and it is weaker on purpose.

    What it cannot do, which is the larger half: it does not catch a mapper who invents doubt
    about a real sentence. Nothing structural can. It catches the ambiguity that is about
    nothing in the passage, which is what an invented one usually is, and it makes an invented
    one have to be invented against words the corpus prints.

    Its asymmetric twin stays out of reach and stays measured: `ambiguous-to-clear`, the
    premature collapse, leaves no field to check, and `superposition` (0034) reaches only the
    part of it a second reader recorded.

    A corpus whose `quotation` is `withheld` (0013) quotes nothing for a question to be anchored
    in. Those ambiguities are counted and named as unanchorable rather than passed quietly.
    """
    available, bad, anchored, withheld = quoted_runs(ctx["map"]), [], [], []
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        question = block(entry, "ambiguity").get("question")
        if not isinstance(question, str) or not question.strip():
            continue  # `exclusions` owns the missing question
        name = label(entry, position)
        if quotes_withheld(ctx.get("manifest"), entry):
            withheld.append(name)
            continue
        if anchor_of(question, available) is None:
            bad.append(f"  X  {name}: `ambiguity.question` quotes no passage this map quotes; "
                       f"name the words the two readings turn on, as `crossReferences.cites` "
                       f"names the words a pointer is made in. A question anchored to nothing is "
                       f"a doubt nobody can check against the corpus (#271)")
        else:
            anchored.append(name)
    held = (f"; {len(withheld)} of a corpus whose quotation is withheld, which nothing here can "
            f"anchor" if withheld else "")
    if not anchored and not bad:
        return skip("no entry records an `ambiguity.question` this map could anchor" + held,
                    had_subject=bool(withheld))
    return verdict(bad, f"{len(anchored)} recorded ambiguit{'y' if len(anchored) == 1 else 'ies'}, "
                        f"each quoting a run of the corpus's own words this map holds" + held,
                   "an ambiguity is about no passage this map quotes")
