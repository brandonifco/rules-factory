# Decisions

One file per decision that would otherwise be re-litigated or quietly reversed. A record
states what was decided, what the alternatives were, and what follows — not how something
works, which is the code's or the specification's job.

Numbering is sequential and permanent. A superseded record is marked superseded in place and
kept; its number is never reused.

| # | Decision |
|---|----------|
| [0001](0001-the-corpus-map-is-the-interface.md) | The corpus map is the interface, and it comes before the scaffolder |
| [0002](0002-boundary-policy-belongs-to-the-corpus.md) | Boundary policy belongs to the corpus, not to the repository |
| [0003](0003-a-phase-gate-names-a-rule-not-a-condition.md) | A phase gate names a rule, not a condition |
| [0004](0004-adapter-reach-is-a-property-of-the-entry.md) | Adapter reach is a property of the entry, recorded structurally |
| [0005](0005-a-field-earns-its-place-by-being-checkable.md) | A field earns its place by being checkable, not by naming a distinction |
| [0006](0006-the-general-rule-governs-entry-and-full-means-adversely-full.md) | The general rule governs entry, and "full" means adversely full |
| [0007](0007-a-conflict-is-a-question-not-a-pair.md) | A conflict is a question, not a pair |
| [0008](0008-recognising-a-delegated-standard-is-a-procedure-not-a-test.md) | Recognising a delegated standard is a procedure, not a test, and its residue is named |
| [0009](0009-absence-is-a-verdict-with-evidence.md) | Absence is a verdict with evidence, and scope belongs to a rule, never to a section |
| [0010](0010-whose-fact-it-is-does-not-decide-the-kind.md) | Whose fact it is does not decide the kind; the measure the corpus states does |
| [0011](0011-a-gate-has-a-direction.md) | A gate has a direction, and the field it sits in says which (supersedes 0003's polarity paragraph) |
| [0012](0012-a-fact-the-corpus-implies-is-a-derived-entry.md) | A fact the corpus implies and never states is a derived entry, and it cites nothing |
| [0013](0013-verification-posture-belongs-to-the-corpus.md) | How a corpus is verified, and whether a map may quote it, belong to the corpus too (extends 0002) |
| [0014](0014-a-map-is-checked-by-a-blind-second-mapping.md) | A map is checked by a blind second mapping, and every disagreement is resolved against the corpus before it is used |
| [0015](0015-a-map-is-published-as-a-versioned-package.md) | A map is published as a versioned package, checked before it can be a version, and overlaid by its engine on three fields |
| [0016](0016-a-map-package-is-data-not-code.md) | A map package is data, not code: the factory checks it with its own checker and never runs the package's (amends 0015) |
| [0017](0017-a-map-change-carries-a-review-of-its-bytes.md) | A map change carries a review of its exact bytes, and a check refuses one that does not (enforces 0014) |
| [0018](0018-every-file-the-factory-writes-has-one-owner.md) | Every file the factory writes has one owner: generated, managed (factory policy with a recipe version, hand edits refused) or engine-owned |
| [0019](0019-randomness-is-declared-by-the-corpus.md) | Whether an engine may draw random values is declared by the corpus: `randomness: none` or `seeded` (extends 0002 and 0013) |
| [0020](0020-a-section-citation-names-its-lead-in-and-a-section-map-lists-its-extent.md) | A section citation can name its lead-in, and a section-designation map lists its extent; the manifest is never inline, and `definedElsewhere` alone answers a pointer to an unadmitted corpus (extends 0009) |
| [0021](0021-a-gate-outside-the-slice-is-held-by-the-caller.md) | A gate outside the map's slice is a `scope: out` entry, and whether it holds is a fact the caller states and the engine never infers (extends 0003 and 0011) |
| [0022](0022-a-licensed-copy-is-used-locally-by-a-named-operator-and-never-published.md) | **Superseded by 0028, withdrawn.** A licensed `local-copy` corpus may be used locally by a named operator, under an explicit flag and an allowlisted `gh` identity, and a map of one is never published (extends 0013 and 0015) |
| [0023](0023-a-map-package-is-licensed-as-its-corpus-and-the-factory-are.md) | A map package is licensed as its corpus and the factory are: a `LICENCE.txt` it carries, the corpus terms restating the manifest's `licence`, Apache-2.0 for the rest (amends 0015) |
| [0024](0024-a-quote-is-of-the-extraction-and-a-page-extent-can-end-at-a-heading.md) | A quote is verbatim of the extraction the manifest names, an entry the extraction garbles declares its defect and rendered reading, and a page extent can end before a heading on its last page (extends 0004 and 0020) |
| [0025](0025-an-assertion-names-who-asserts-it-and-an-operation-names-what-it-draws.md) | An assertion names who asserts it (`assertedBy`), and an operation names what it draws (`draws`, `ambiguity.affectsDraws`), each anchored in the corpus's words (extends 0005, amends 0019) |
| [0026](0026-a-meaning-the-same-corpus-gives-elsewhere-is-an-entry-and-a-corpus-declares-its-pointers.md) | A meaning the same corpus gives outside the slice is a `scope: out` entry the rule names in `crossReferences` (and `dependsOn` where it modifies the rule), and each corpus declares its `pointerPhrases`; a silent zero fails (extends 0009, 0020 and 0021) |
| [0027](0027-an-owners-ruling-is-held-by-the-engine-and-checked-by-the-factory.md) | An owner's ruling on part of an unresolved question is held in the engine's overlay (`rulings`, with `declines` for the parts still declined, their spans covering the question), never in the map; the factory checks it against the map, generates `Rulings.g.cs` and records it in provenance (extends 0015, amends 0005 C) |
| [0028](0028-the-factory-admits-only-corpora-whose-licence-permits-publishing-them.md) | The factory admits only corpora whose licence permits committing and publishing their text and maps: public domain, or an open licence read from the manifest's `licence`, refused by intake and `pack-map.py` otherwise; `deckard` stays outside the factory, and #3's criterion 1 is a blind rebuild of `hoyle-backgammon` (supersedes 0022, and the licensed-only parts of 0013, 0015 and 0023) |
| [0029](0029-the-rails-are-emitted-by-default-and-vendor-choice-is-engine-owned-configuration.md) | The rails are emitted by default, `AGENTS.md` governs every agent, vendor and label choices live in engine-owned `.github/agent-policy.json`, and GitHub enforcement is applied by an explicit idempotent command (extends 0018 and 0001) |
| [0030](0030-a-repeated-passage-is-identified-by-the-container-its-citation-names.md) | A passage the corpus prints more than once is identified by the container its citation names, and in a page-marked corpus that container is the heading path; a citation the path does not resolve to one printing is refused, never guessed (extends 0024 and 0020) |
| [0031](0031-an-example-that-bounds-a-term-is-recorded-as-a-bound.md) | An example that is the corpus's only authority for a rule no operative sentence states is an entry; an example that bounds a term an operative rule leaves open is `ambiguity.bounds` on that rule, admitted only where the dimension is comparable, and an owner's ruling that contradicts one fails the engine's gate (extends 0005 and 0027) |
| [0032](0032-mapping-validation-and-generation-are-three-subsystems-over-one-contract.md) | Mapping, map validation and engine generation are three sibling subsystems over one map contract, which none of them may bypass and none may import another through; the direction is checked, and the mapper is not yet its own repository (extends 0001 and 0016) |
| [0033](0033-the-validator-is-the-adversary-and-validates-the-uncertainty-too.md) | `checkmap` is `mapvalidator`: the validator is the adversary, it challenges six kinds of truth, what it validates includes the uncertainty, and the three subsystems claim three different determinisms (extends 0032) |
| [0034](0034-a-valid-unresolved-state-is-established-not-asserted.md) | A valid unresolved state is established by records outside the entry, never asserted by it: the map gains no `readings` field, an adjudicated "the corpus does not settle it" must be recorded in the map as ambiguous (`superposition`), an open question returns a reason its own correspondence rows produce (`unresolved-reason`), and a bound names a term the question records as open (`bound-term-open`) (carries out 0033 §3, extends 0014) |
| [0035](0035-a-rule-stated-in-a-table-row-is-cited-by-its-row.md) | A rule stated in a table is cited by its row (`§ 172.101 table 3, row [column 2 = "Acetal"], column 7`), a row is named by `column = value` pairs that must resolve to exactly one row, the extraction of a row is its cells in column order with the empty ones kept, `table-row` is a unit, and an extent that slices a table names the rows it takes and accounts for every table it does not (extends 0020, 0024 and 0030) |
