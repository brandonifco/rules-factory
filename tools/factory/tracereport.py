"""The trace as one HTML page a person can read (#580).

  python3 tools/factory trace --engine <engine dir> --html <report.html>

A renderer and nothing else. `render(trace)` takes the plain data `trace.build` returns -- the same
data `--json` prints -- and lays it out. It reads no file, imports nothing of the factory's, and
cannot add a fact, so the page cannot say anything the JSON does not. What it may do is group,
order and link: an index of entries, an anchor per entry, a summary that counts, and filters made of
CSS alone.

**Every relationship wears its evidence class.** RECORDED, DERIVED, INFERRED and UNKNOWN are four
badges that look different, and the basis, mechanism or reason the trace gives is printed beside
each one. An inferred implementation candidate sits in a dashed box, so it cannot be mistaken for
the recorded test evidence printed above it in a solid one.

**Words no stronger than the evidence.** The page's own text says recorded, derived, inferred and
unknown. It never says that something proves, implements or verifies a rule, because no class the
trace has supports that. The summary counts classes and gaps, and gives no score and no verdict:
a count of unknowns is a list of what to look at, not a grade.

**As private as the engine.** The engine's distribution is the first thing on the page, and a
private engine's page says that it is as private as the engine, because names and mutations can
quote the corpus.

Self-contained and deterministic: CSS embedded, no script, no external asset, no clock. The same
trace gives the same bytes. Standard library only.
"""
import html
import json

CLASSES = ("recorded", "derived", "inferred", "unknown")

CSS = """
:root { --fg: #1d1d1f; --bg: #ffffff; --muted: #5f6368; --rule: #d9d9de; --panel: #f6f6f8;
  --recorded: #1b6e3a; --derived: #1f4f8f; --inferred: #8a5a00; --unknown: #a3261f; }
@media (prefers-color-scheme: dark) {
  :root { --fg: #ececf0; --bg: #16161a; --muted: #a0a0aa; --rule: #34343c; --panel: #202026;
    --recorded: #5fcf8a; --derived: #7fb0f0; --inferred: #f0b54a; --unknown: #ff7b72; } }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 16px 64px; background: var(--bg); color: var(--fg);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1100px; margin: 0 auto; }
h1 { font-size: 24px; margin: 0 0 4px; } h2 { font-size: 18px; margin: 32px 0 8px; }
h3 { font-size: 16px; margin: 0 0 8px; overflow-wrap: anywhere; }
code, .value { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; overflow-wrap: anywhere; }
.muted, .why { color: var(--muted); font-size: 13px; }
.banner { border: 1px solid var(--rule); background: var(--panel); padding: 8px 12px; margin: 12px 0; }
.banner.private { border-color: var(--unknown); }
table { border-collapse: collapse; width: 100%; margin: 8px 0; display: block; overflow-x: auto; }
th, td { text-align: left; vertical-align: top; border-bottom: 1px solid var(--rule); padding: 6px 8px; }
th { font-weight: 600; white-space: nowrap; }
.badge { display: inline-block; font: 600 11px/1 system-ui, sans-serif; letter-spacing: .04em;
  padding: 3px 6px; border-radius: 3px; border: 1px solid currentColor; white-space: nowrap; }
.b-recorded { color: var(--recorded); }
.b-derived { color: var(--derived); }
.b-inferred { color: var(--inferred); border-style: dashed; }
.b-unknown { color: var(--unknown); border-style: dotted; }
.fact { margin: 2px 0 6px; }
section.entry { border: 1px solid var(--rule); padding: 12px 14px; margin: 12px 0; scroll-margin-top: 12px; }
.test { border: 1px solid var(--rule); padding: 8px 10px; margin: 6px 0; }
.candidate { border: 1px dashed var(--inferred); padding: 8px 10px; margin: 6px 0; }
.candidate.none { border: 1px dotted var(--unknown); }
.gaps li { margin: 2px 0; }
.label { font-weight: 600; margin-top: 10px; }
.filters { margin: 8px 0; }
.filters > label { cursor: pointer; margin: 0 14px 0 4px; }
.filters > .entries { margin-top: 8px; }
"""


def esc(text):
    return html.escape(str(text), quote=True)


def shown(value):
    """A value as the page prints it: strings as they are, everything else as compact JSON."""
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def badge(evidence):
    return f'<span class="badge b-{esc(evidence)}">{esc(evidence.upper())}</span>'


def fact(node):
    """One relationship: its badge, its value, and how the trace knows it."""
    evidence = node.get("evidence")
    how = node.get("basis") or node.get("mechanism") or node.get("why") or ""
    word = {"recorded": "recorded in", "derived": "derived by", "inferred": "inferred by",
            "unknown": "unknown:"}.get(evidence, "")
    value = "" if evidence == "unknown" else f' <span class="value">{esc(shown(node.get("value")))}</span>'
    return (f'<div class="fact" data-evidence="{esc(evidence)}">{badge(evidence)}{value} '
            f'<span class="why">{esc(word)} {esc(how)}</span></div>')


def row(label, node):
    return f"<tr><th>{esc(label)}</th><td>{fact(node)}</td></tr>"


def nested_rows(prefix, mapping):
    out = []
    for key, node in mapping.items():
        if isinstance(node, dict) and "evidence" in node:
            out.append(row(f"{prefix}{key}", node))
        elif isinstance(node, dict):
            out += nested_rows(f"{prefix}{key}.", node)
    return out


def anchor(entry_id):
    return "entry-" + "".join(c if c.isalnum() or c in "-_." else "_" for c in str(entry_id))


def status_of(entry):
    """An entry's status as the page names it: the trace's value, shown, whatever its type."""
    return shown((entry.get("status") or {}).get("value"))


def statuses(entries):
    """{status as shown: its position}, in first-seen order. A filter and an entry's class are named by
    the position and never by the value, so no two statuses can share a name and no value reaches CSS."""
    found = {}
    for entry in entries:
        found.setdefault(status_of(entry), len(found))
    return found


def classes_of(entry, gaps_by_subject, positions):
    names = ["entry", f"st-{positions[status_of(entry)]}"]
    if gaps_by_subject.get(f"entry:{entry['id']['value']}"):
        names.append("has-gaps")
    return " ".join(names)


def render_entry(entry, gaps_by_subject, positions):
    entry_id = entry["id"]["value"]
    parts = [f'<section class="{classes_of(entry, gaps_by_subject, positions)}" id="{esc(anchor(entry_id))}">',
             f'<h3><a href="#{esc(anchor(entry_id))}">{esc(entry_id)}</a></h3>', "<table>"]
    for label in ("id", "name", "package", "locator", "corpus", "segment", "status", "implementedIn", "handler"):
        if label in entry:
            parts.append(row(label, entry[label]))
    parts.append("</table>")
    parts.append(f'<div class="label">Named tests ({len(entry.get("tests") or [])})</div>')
    for test in entry.get("tests") or []:
        parts.append('<div class="test">' + fact(test["name"]) + '<div class="muted">mutation the test was '
                     'watched catching:</div>' + fact(test["mutation"]) + "</div>")
    if not entry.get("tests"):
        parts.append('<div class="muted">none named</div>')
    parts.append('<div class="label">Implementation candidates</div>')
    for candidate in entry.get("implementation") or []:
        none = " none" if candidate.get("evidence") == "unknown" else ""
        parts.append(f'<div class="candidate{none}">{fact(candidate)}</div>')
    own = gaps_by_subject.get(f"entry:{entry_id}") or []
    if own:
        parts.append(f'<div class="label">Gaps ({len(own)})</div><ul class="gaps">')
        parts += [f"<li><code>{esc(g['relationship'])}</code> — {esc(g['why'])}</li>" for g in own]
        parts.append("</ul>")
    parts.append("</section>")
    return "\n".join(parts)


def filters(positions):
    """Radio buttons and the CSS that hides what they rule out: a filter with no script."""
    choices = [("all", "all", None), ("gaps", "with gaps", ".entry:not(.has-gaps)")]
    for status, position in positions.items():
        choices.append((f"st-{position}", f"status {status}", f".entry:not(.st-{position})"))
    inputs, rules = [], []
    for position, (key, label, hides) in enumerate(choices):
        checked = " checked" if position == 0 else ""
        inputs.append(f'<input type="radio" name="filter" id="f-{esc(key)}"{checked}>'
                      f'<label for="f-{esc(key)}">{esc(label)}</label>')
        if hides:
            rules.append(f"#f-{key}:checked ~ .entries {hides} {{ display: none; }}")
    return inputs, rules


def render(trace):
    """The page, as a string. A function of `trace` alone."""
    engine = trace.get("engine") or {}
    name = shown((engine.get("name") or {}).get("value"))
    distribution = (engine.get("distribution") or {}).get("value")
    entries = trace.get("entries") or []
    gaps = trace.get("gaps") or []
    gaps_by_subject = {}
    for gap in gaps:
        gaps_by_subject.setdefault(gap.get("subject"), []).append(gap)
    summary = trace.get("summary") or {}
    positions = statuses(entries)
    inputs, rules = filters(positions)

    out = ["<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           f"<title>Trace of {esc(name)}</title>", "<style>" + CSS + "\n".join(rules) + "</style>", "</head>",
           "<body>", "<main>", f"<h1>Trace of {esc(name)}</h1>",
           f'<div class="muted">factory trace, format {esc(trace.get("traceFormat"))}. Every relationship '
           f"below is labelled with how it is known.</div>"]
    # Fails closed: only a record that says `public` gets the public wording.
    private = distribution != "public"
    out.append(f'<div class="banner{" private" if private else ""}">Distribution: <strong>{esc(shown(distribution))}'
               f"</strong>. " + ("This page is as private as the engine: entry names and mutations can quote "
                                 "the corpus, so it goes only where the engine's own files may go."
                                 if private else "Entry names and mutations can quote the corpus.") + "</div>")
    out.append('<h2>How to read it</h2><table>')
    meanings = {
        "recorded": "an existing artifact states it; the artifact and field are named",
        "derived": "it follows from recorded facts through an existing factory reader, which is named",
        "inferred": "deterministic analysis suggests it and nothing records it; the analysis is named",
        "unknown": "nothing establishes it; the reason is given, and it is listed as a gap",
    }
    out += [f"<tr><th>{badge(c)}</th><td>{esc(meanings[c])}</td></tr>" for c in CLASSES]
    out.append("</table>")

    out.append("<h2>Summary</h2><table>")
    out.append(f"<tr><th>entries</th><td>{esc(summary.get('entries'))}</td></tr>")
    for evidence, count in (summary.get("evidence") or {}).items():
        out.append(f"<tr><th>{badge(evidence)}</th><td>{esc(count)} relationship(s)</td></tr>")
    for relationship, count in (summary.get("gaps") or {}).items():
        out.append(f"<tr><th>gap</th><td>{esc(count)} × <code>{esc(relationship)}</code></td></tr>")
    out.append("</table>")

    out.append("<h2>Engine</h2><table>")
    out += nested_rows("", engine)
    topology = trace.get("topology") or {}
    out += nested_rows("topology.", {k: v for k, v in topology.items() if isinstance(v, dict)})
    out.append(f"<tr><th>topology.agrees</th><td><code>{esc(shown(topology.get('agrees')))}</code> "
               f'<span class="why">no class of its own: the trace\'s comparison of the two rows above, which '
               f"no artifact states</span></td></tr>")
    out.append("</table>")
    engine_gaps = [g for g in gaps if not str(g.get("subject", "")).startswith("entry:")]
    if engine_gaps:
        out.append(f'<div class="label">Gaps ({len(engine_gaps)})</div><ul class="gaps">')
        out += [f"<li><code>{esc(g['subject'])}</code> <code>{esc(g['relationship'])}</code> — "
                f"{esc(g['why'])}</li>" for g in engine_gaps]
        out.append("</ul>")

    out.append("<h2>Map packages</h2>")
    for package in trace.get("maps") or []:
        out.append("<table>" + "".join(nested_rows("", package)) + "</table>")
    out.append("<h2>Corpora</h2>")
    for corpus in trace.get("corpora") or []:
        out.append("<table>" + "".join(nested_rows("", corpus)) + "</table>")

    # The radios come first, then the index and the entries as their siblings: one choice filters both.
    out.append('<h2>Entries</h2><div class="filters"><span class="muted">show:</span>' + "".join(inputs))
    out.append('<table class="entries index"><tr><th>entry</th><th>status</th><th>named tests</th><th>gaps</th></tr>')
    for entry in entries:
        entry_id = entry["id"]["value"]
        status = entry.get("status") or {}
        out.append(f'<tr class="{classes_of(entry, gaps_by_subject, positions)}">'
                   f'<td><a href="#{esc(anchor(entry_id))}"><code>{esc(entry_id)}</code></a></td>'
                   f"<td>{badge(status.get('evidence', 'unknown'))} {esc(status_of(entry))}</td>"
                   f"<td>{len(entry.get('tests') or [])}</td>"
                   f"<td>{len(gaps_by_subject.get(f'entry:{entry_id}') or [])}</td></tr>")
    out.append("</table>")
    out.append('<div class="entries">')
    out += [render_entry(entry, gaps_by_subject, positions) for entry in entries]
    out.append("</div></div>")
    out += ["</main>", "</body>", "</html>"]
    return "\n".join(out) + "\n"
