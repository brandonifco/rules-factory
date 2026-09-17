# The mapper

The subsystem that turns a corpus into a candidate map, and the record of how it was read.

It is a sibling of map validation and of the factory, over the map contract they share
([0032](decisions/0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md)).
Three different questions, three trust boundaries:

| Subsystem | The question it asks |
|---|---|
| **Mapper** | What does this corpus say, and where does its certainty end? |
| **[Validator](validator.md)** | Has the mapper justified those claims, and is this map safe to rely on? |
| **Factory** | Given an acceptable map, what follows mechanically? |

The mapper is an interpreter, and it is not allowed to certify itself. That is the whole reason
[the validator](validator.md) is a sibling and not a utility hanging off this one.

## What is here and what is in the method

[`docs/method.md`](method.md) is the method: what a mapper does, in what order, and why. It stays
a document, because most of it is judgement a program cannot make — whether a sentence states a
rule, whether two readings are both defensible, whether an example bounds a term or is one.

`tools/mapper/` is the part of it that is mechanical: **the protocol that says how a particular
corpus communicates rules, and the interrogation a protocol obliges.** The method says *walk the
corpus*; the protocol says what walking this corpus means.

## The mapping protocol

`mapping-protocol.json`, beside the map. One per map, and `validate.sh` fails a map without one:
a map with no protocol cannot say how it was read.

It is **not** packed into the map package
([0015](decisions/0015-a-map-is-published-as-a-versioned-package.md)). The package carries the
map, the manifest and the checker, because those are what a consumer needs to judge and build
from the map. The protocol is how the map was *made*, which is the mapper's business and not the
factory's — the factory asks for a valid, certified map and nothing about how it was read.

```json
{
  "protocolVersion": 1,
  "corpus": "srd-5.2.1",
  "units": ["glossary-definition", "heading", "paragraph", "list-item"],
  "pointerMechanisms": [
    { "mechanism": "phrase" },
    { "mechanism": "defined-term-use", "vocabularyFrom": "condition-list" }
  ],
  "requiredSweeps": ["definitions", "vocabulary", "applicability", "exceptions",
                     "undefined-terms", "cross-references", "extent-coverage"],
  "adapterReach": {
    "text": "readable",
    "tables": "rendered-page-required",
    "columns": "rendered-page-required",
    "illustrations": "unsupported"
  }
}
```

Every vocabulary is closed, for the reason every vocabulary in the map is closed: a value
nothing holds to a set means whatever the last writer thought. The sets are in
[`tools/mapper/protocol.py`](../tools/mapper/protocol.py), which is where they are enforced.

| Field | What it says |
|---|---|
| `units` | the shapes this corpus states rules in — what a mapper reads one at a time. The walk is bounded ([method](method.md#phase-2--map-the-corpus)); this says by what |
| `pointerMechanisms` | how this corpus points at a meaning it gives elsewhere ([0026](decisions/0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md)) |
| `requiredSweeps` | the completeness challenge this mapping owes. Declared and **not yet run**: [#250](https://github.com/brandonifco/rules-factory/issues/250) is where each becomes code, and `mapper protocol` says so on every run so a protocol cannot read as though its sweeps had passed |
| `adapterReach` | how far the extraction reaches into each modality ([0004](decisions/0004-adapter-reach-is-a-property-of-the-entry.md), [0024](decisions/0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md)) |

### Why `pointerMechanisms` exists

Because a phrase list was the wrong interrogation mechanism for a corpus and nothing could say
so. [#208](https://github.com/brandonifco/rules-factory/issues/208) measured it: against the
SRD's conditions the declared `pointerPhrases` detect **0** pointers in passages holding **51**
bare condition-name references, leaving 102 of 107 `crossReferences` declarations obliged by
nothing. No regex fixes that, because the corpus points by **naming a defined term**, and the
words of a pointer in one entry are the words of the definition in another.

What separates them is where the sentence is. A naming of a term inside the passage that defines
it is the definition; a naming of it anywhere else is a pointer. The passage is the container the
citation names ([0030](decisions/0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md)),
so two entries citing the same container are inside the same definition.

The vocabulary is read **out of the map**, never out of the protocol: the corpus already states
its defined terms somewhere, that statement is an entry, and its term-anchored `crossReferences`
are already term → defining entry. A second copy in the protocol would be a second definition to
keep in step.

A mechanism is either detected by this subsystem or detected somewhere the protocol checker
names; a mechanism in neither is refused. `phrase` is detected by
`check-map.py --only cross-references`, and `section-designation` by the corpus's own locator
checker. They are declared here anyway, so a protocol is the whole account of how a corpus
points rather than the part this package happens to implement.

## Commands

```bash
python3 tools/mapper protocol <corpus-map.json>   # is this a protocol the mapper can act on?
python3 tools/mapper pointers <corpus-map.json>   # run the interrogation it obliges
```

Four exit codes, the factory's four:

| Exit | Meaning |
|---|---|
| `0` | every declaration held, and something was actually examined |
| `1` | a declaration is wrong, or an interrogation that was declared detected nothing at all |
| `2` | a usage error |
| `3` | **NOT VERIFIED**: the interrogation found what it cannot judge — a pointer the map does not declare. Whether each is owed is decided by reading the corpus (0026), not here |

A silent zero is a failure, not a pass: a corpus that declares a mechanism and on which nothing
fires has either the wrong mechanism declared or a map whose evidence spans do not reach its
pointers. That is the same rule 0026 already applies to phrases, and it is exactly the shape #208
measured.

## What it does not do yet

- **It produces no map.** Mapping is still done by hand, by the method. What this makes checkable
  is that the walk was the walk this corpus requires.
- **No sweep runs** ([#250](https://github.com/brandonifco/rules-factory/issues/250)).
  `requiredSweeps` is held to its vocabulary and to nothing else, and every run says so.
- **Nothing stages a blind second mapping**
  ([#223](https://github.com/brandonifco/rules-factory/issues/223)). The redaction the method
  requires is enforced by nobody, and the one tool that does it lives inside the trial that
  needed it.
- **There is no inventory** — no record of which passages were examined, which were rejected and
  why, and which the adapter could not inspect. `extent` claims coverage and nothing evidences
  it ([#255](https://github.com/brandonifco/rules-factory/issues/255)).
- **The detector reads `evidence`,** which is the corpus's words for one rule and not the whole
  passage, so a naming outside every entry's quoted span is invisible to it. And it matches a
  term exactly, so a corpus that inflects its defined terms needs a mechanism this is not.
