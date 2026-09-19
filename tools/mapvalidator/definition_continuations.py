"""The semantic half of a definition continuation: its target and map-level anchor (0046).

The corpus locator checker proves the other half: that the structural anchor resolves to this
entry's passage under the directly defining passage. This check deliberately does not parse a
locator grammar; a locator is evidence-side truth, while this package owns the map contract.
"""
from .diagnostics import skip, verdict
from mapcontract.vocabulary import CONTINUES_DEFINITION_FIELDS, DEFINITION_ANCHOR_FIELDS
from mapcontract.entry import (block, definition_continuation_of, defines_of, entries_of, index,
                               label)


def check_definition_continuations(ctx):
    """Every `continuesDefinition` has one direct defining target and one structural witness.

    The continuation writes no vocabulary or term. Those are inherited from exactly one direct
    `defines` declaration on `definedBy`, which keeps 0045's own-evidence anchor unchanged.
    Chains and multi-term targets are refused until a corpus forces them.
    """
    by_id, bad, carriers = index(ctx["map"]), [], []
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict) or "continuesDefinition" not in entry:
            continue
        name = label(entry, position)
        carriers.append(name)
        declared = entry.get("continuesDefinition")
        if not isinstance(declared, dict):
            bad.append(f"  X  {name}: `continuesDefinition` is not an object")
            continue
        if set(declared) != set(CONTINUES_DEFINITION_FIELDS):
            held = ", ".join(f"`{field}`" for field in sorted(declared)) or "nothing"
            bad.append(f"  X  {name}: continuesDefinition holds {held}; it is exactly "
                       f"`definedBy` and `anchor`, and an unknown key is refused")
            continue
        anchor = declared.get("anchor")
        if not isinstance(anchor, dict):
            bad.append(f"  X  {name}: continuesDefinition.anchor is not a locator object")
            continue
        if set(anchor) != set(DEFINITION_ANCHOR_FIELDS):
            held = ", ".join(f"`{field}`" for field in sorted(anchor)) or "nothing"
            bad.append(f"  X  {name}: continuesDefinition.anchor holds {held}; an anchor is "
                       f"exactly `sourceId` and `citation`")
            continue
        continuation = definition_continuation_of(entry)
        if continuation is None:
            bad.append(f"  X  {name}: continuesDefinition needs non-empty string `definedBy`, "
                       f"`anchor.sourceId`, and `anchor.citation`")
            continue
        target_id, anchor_source, _ = continuation
        if "defines" in entry:
            bad.append(f"  X  {name}: carries both `defines` and `continuesDefinition`; a "
                       f"continuation inherits one direct definition and does not declare another")
        target = by_id.get(target_id)
        if target is None:
            bad.append(f"  X  {name}: continuesDefinition.definedBy names {target_id!r}, which is "
                       f"not an entry in this map")
            continue
        if target_id == entry.get("id"):
            bad.append(f"  X  {name}: continuesDefinition.definedBy names itself")
            continue
        if "continuesDefinition" in target:
            bad.append(f"  X  {name}: continues a definition through {target_id!r}, which is "
                       f"itself a continuation; continuation chains are not supported (0046)")
        target_definitions = defines_of(target)
        if len(target_definitions) != 1:
            bad.append(f"  X  {name}: continues {target_id!r}, which has "
                       f"{len(target_definitions)} direct definition(s); the target has exactly "
                       f"one until a corpus forces multi-term continuation")
        source = block(entry, "locator").get("sourceId")
        target_source = block(target, "locator").get("sourceId")
        if not source or source != target_source:
            bad.append(f"  X  {name}: continuation and directly defining entry are not in the "
                       f"same corpus ({source!r} versus {target_source!r})")
        if anchor_source != source:
            bad.append(f"  X  {name}: continuation anchor names corpus {anchor_source!r}, not "
                       f"the continuation's corpus {source!r}")

    if not carriers:
        return skip("no entry carries `continuesDefinition`, so no continuation was checked",
                    had_subject=False)
    return verdict(bad,
                   f"{len(carriers)} definition continuation(s) have one direct defining target "
                   f"and a same-corpus structural anchor",
                   "a definition continuation is malformed or is not tied to one direct definition")
