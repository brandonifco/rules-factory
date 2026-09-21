"""The phase registry: every check by name, in the order it runs, and the overlay rule that
decides which of them an engine re-runs on its merged map (0015).
"""
from .schema import check_required_fields, check_schema, check_unique_ids, check_vocabulary
from .extent import check_extent
from .relations import check_derived, check_gates, check_no_cycles, check_references
from .manifest import check_manifest, check_postures
from .extraction import check_extraction
from .ambiguity import (check_conflicts, check_decision_records, check_exclusions,
                        check_inherited_reason, check_unresolved_reason)
from .anchors import check_question_anchor
from .applicability import check_applicability_reach
from .bounds import check_bound_term_open, check_bounds
from .status import check_absent, check_status
from .inputs import check_asserted_by, check_draws
from .crossrefs import check_cross_references
from .defines import check_defines
from .definition_continuations import check_definition_continuations
from .correspondence import check_correspondence
from .epistemic import check_superposition


# --- where each check runs (0015) ------------------------------------------------------
#
# A map is published as a package, and a map that fails any check here never becomes a
# version (`--phase publish`, the default, runs every check). The engine consuming it does
# not re-run them: the package's bytes are what passed. What it does run is the subset whose
# verdict its own overlay can change. An overlay sets exactly OVERLAY_FIELDS on the entries it
# names and nothing else (0015, from #17), so a check that reads none of them is discharged at
# publish, and a check that reads any of them is re-run by the consumer against
# merge(package, overlay) with `--phase consumer`.
#
# The split is read from here, not maintained beside it. `test_check_map.py` holds it to its
# word both ways: every check outside STATUS_DEPENDENT gives the same verdict whatever the
# overlay fields hold, and every check inside it can be turned by them.

OVERLAY_FIELDS = ("status", "implementedIn", "tests")

STATUS_DEPENDENT = {
    "vocabulary",      # `status` is one of the closed vocabularies
    "status",          # implementedIn exactly when implemented; tests, each with its mutation
    "absent",          # an absentFrom entry is `status: declined`
    "correspondence",  # rows 2 and 5 branch on status; `declined` owes a runtime row
}

PHASES = ("publish", "consumer")


CHECKS = [
    ("schema", check_schema),
    ("required-fields", check_required_fields),
    ("vocabulary", check_vocabulary),
    ("unique-ids", check_unique_ids),
    ("extent", check_extent),
    ("references", check_references),
    ("no-cycles", check_no_cycles),
    ("gates", check_gates),
    ("applicability-reach", check_applicability_reach),
    ("derived", check_derived),
    ("manifest", check_manifest),
    ("postures", check_postures),
    ("extraction", check_extraction),
    ("exclusions", check_exclusions),
    ("status", check_status),
    ("decision-records", check_decision_records),
    ("conflicts", check_conflicts),
    ("bounds", check_bounds),
    ("absent", check_absent),
    ("asserted-by", check_asserted_by),
    ("draws", check_draws),
    ("cross-references", check_cross_references),
    ("defines", check_defines),
    ("definition-continuations", check_definition_continuations),
    ("correspondence", check_correspondence),
    # The epistemic checks (0034). None reads `status`, `implementedIn` or `tests`, and
    # none may: an overlay must not be able to turn a verdict about whether the corpus
    # settles a question, because the corpus is the same either way.
    ("unresolved-reason", check_unresolved_reason),
    # #226: the same rule across a `dependsOn` edge. Reads no overlay field, so it belongs here.
    ("inherited-reason", check_inherited_reason),
    # #271: an ambiguity is anchored in the corpus's words, as a cross-reference is. It reads
    # `evidence` and `ambiguity` and no overlay field, so it belongs here and not in
    # STATUS_DEPENDENT: whether the corpus settles a question is the same either way.
    ("question-anchor", check_question_anchor),
    ("bound-term-open", check_bound_term_open),
    ("superposition", check_superposition),
]
