"""What a recorded `mutation` must be: an unfilled placeholder is not evidence (#239, #240).

`status` holds an `implemented` entry to the tests that prove it, and each test to the mutation
that was recorded turning it red. Until this module the rule behind that word was
`isinstance(mutation, str) and mutation.strip()`, so `"mutation": "PENDING"` was evidence -- for a
test nobody had run. #239 closed that on the engine side, in the gate recipe every `factory
produce` vendors. This closes it here, in the checker a **published map package carries** (0015)
and the one `scripts/validate.sh` runs over this repository's own maps, neither of which any
engine's gate stands in front of.

The rule, in full, is `placeholder_problem()` below. Three refusals, in order, all applied to the
mutation after `normalise()` -- NFKD, combining marks and format characters (Unicode Mn, Me, Cf)
removed, whitespace collapsed, punctuation, symbols and spaces stripped from both ends by Unicode
category, and casefolded, so `TODO`, `ＴＯＤＯ`, `"TODO"`, `TO<zero-width space>DO` and `TÓDO` are
one word:

  * a **placeholder**: the whole mutation is one of the set, or every distinct word in it is;
  * **one word repeated**: two or more words, all the same word;
  * **too short**: fewer than MINIMUM_WORDS words, counted with repeats, or fewer than
    MINIMUM_CHARACTERS characters.

Words are counted with repeats, and distinctness is only ever the placeholder rule's business:
``Increment `increment`; fails.`` is honest evidence about a variable named `increment`, and a
floor counting distinct words refused it. "One word repeated" is what refuses `TODO TODO TODO`
when the copies are spelled in a script the placeholder set does not contain -- a Cyrillic `О` for
a Latin `O`, say. **Confusable (homoglyph) mapping is deliberately not done**: it needs a versioned
table of confusables kept current against Unicode, which belongs to the whole factory and not to
one check, and a homoglyph here is deliberate evasion, which this floor does not claim to stop in
any case. So the claim is exactly this and no more: *repeating one spelling is refused whatever
script the spelling is in; mixing spellings to evade -- `TODO TОDO TODО`, three different ones --
is not something this floor stops.*

This refuses **unfilled placeholders**, and nothing more. It cannot tell whether the edit was
made, whether the test went red, whether the mutation was a good one, or whether the sentence was
copied from another entry; `not yet recorded` passes it. Nothing a string can be read for can do
otherwise, and every refusal says so, because a reader told only "that is not a mutation" will
read the passing case as "this test was watched failing". The threshold is set far below any real
mutation on purpose: refusing an honest mutation blocks honest work and teaches people to pad,
which is worse than a placeholder slipping through. The shortest mutation in either engine the
factory has built (faa-part-107, tax-121-principal-residence) is 20 words and 159 characters, an
order of magnitude above the floor.

**This is a deliberate duplicate of `placeholder_problem()` in
`tools/factory/recipe/map-overlay.py`, not a shared module, and the copy is held to the original
by a test.** The recipe is vendored into a produced engine, where it is a standard-library script
beside an engine's own sources with no factory, no `mapcontract` and no `mapvalidator` on the
path; it may therefore import nothing of this repository's, and 0032 forbids the reverse import
just as firmly -- the map's verifier does not read the factory's consumer code. Extracting the
rule into `mapcontract` would not help either: `mapcontract` states what a field means and judges
nothing, and this judges. So there are two copies on purpose, and what keeps them in step is
`tools/tests/test_placeholder_mutation_is_one_rule.py`, which loads both and asserts every
constant and every verdict is the same over one shared table of strings. A change to either copy
alone turns that test red and names the constant or the string that diverged.
"""
import unicodedata


# The placeholder set (#239). Each of these is a word someone types to get past a check they mean
# to come back to, and every one of them has been seen in a `mutation` field or is one keystroke
# from one. `scratch` is here deliberately: the factory's own tools/validate-engine.py wrote
# `"mutation": "scratch"` in its scratch-engine overlays, which is exactly the habit this refuses.
PLACEHOLDERS = frozenset((
    "pending", "tbd", "todo", "none", "n/a", "na", "scratch", "placeholder", "xxx",
    "unknown", "later", "fixme", "wip", "",
))

# The floor. A mutation is a sentence: it names what was changed and says what the test then did,
# and neither fits in two words. Counted with repeats -- a word may legitimately appear twice, as
# in ``Increment `increment`; fails.`` Set an order of magnitude below any real mutation, because
# refusing an honest mutation is worse than letting a placeholder through. Not a quality bar.
MINIMUM_WORDS = 3
MINIMUM_CHARACTERS = 12

# Combining marks and format characters. Removed outright, not stripped from the ends: a
# zero-width space inside `TO<zwsp>DO` hides the word, and seven of them pad `1 2 3` past a
# character floor.
INVISIBLE = ("Mn", "Me", "Cf")

# What a placeholder is decorated with -- "TODO.", "-- pending --", "?", "n/a!", curly quotes --
# taken by Unicode category rather than an ASCII set, so it is not only ASCII punctuation. This is
# also how the empty-after-punctuation case ("...", "-", "()") becomes the empty string.
EDGE_CATEGORIES = ("P", "S", "Z")


def an_edge(character):
    return unicodedata.category(character)[0] in EDGE_CATEGORIES or character.isspace()


def strip_edges(text):
    """`text` without leading and trailing punctuation, symbols and whitespace."""
    start, end = 0, len(text)
    while start < end and an_edge(text[start]):
        start += 1
    while end > start and an_edge(text[end - 1]):
        end -= 1
    return text[start:end]


def normalise(mutation):
    """The mutation as it is matched. See the docstring: NFKD, invisibles gone, whitespace
    collapsed, ends stripped by category, casefolded."""
    text = unicodedata.normalize("NFKD", mutation)
    text = "".join(c for c in text if unicodedata.category(c) not in INVISIBLE)
    text = unicodedata.normalize("NFC", text)
    return strip_edges(" ".join(text.split())).casefold()


def words(normalised):
    """The tokens that carry meaning: whitespace-separated, at least one letter or digit each,
    with their own punctuation off. In order, with repeats: the floor counts these."""
    return [strip_edges(w) for w in normalised.split() if any(c.isalnum() for c in w)]


def placeholder_problem(mutation):
    """Why this mutation is not evidence, or None. The whole rule, in one place (#239, #240)."""
    normalised = normalise(mutation)
    tokens = words(normalised)
    distinct = set(tokens)
    if normalised in PLACEHOLDERS or (distinct and distinct <= PLACEHOLDERS):
        return f"{mutation.strip()!r}, which is a placeholder, not a mutation"
    if len(tokens) > 1 and len(distinct) == 1:
        return f"{mutation.strip()!r}, which is one word repeated, not a mutation"
    if len(tokens) < MINIMUM_WORDS or len(normalised) < MINIMUM_CHARACTERS:
        return (f"{mutation.strip()!r}, which is too short to be a mutation: at least "
                f"{MINIMUM_WORDS} words and {MINIMUM_CHARACTERS} characters are asked "
                f"for, and this is {len(tokens)} and {len(normalised)}")
    return None
