#!/usr/bin/env python3
"""The `run:` steps of one job of a GitHub workflow, read from the file as written (no YAML library).

    python3 tools/tests/workflow_steps.py <workflow.yml> <job> <out dir> [EXPR=VALUE ...]

writes each step with a `run: |` block to `<out dir>/NN.sh` and its name to `<out dir>/NN.name`, in
order, with every `${{ EXPR }}` given replaced by VALUE. A step whose run block still holds a
`${{ ... }}` expression afterwards is left out and named on stderr, since it cannot run outside
Actions. scripts/validate-engine.sh runs a licensed-copy engine's CI checks this way (decision 0028),
and tools/tests/test_local_map.py reads the same steps.
"""
import os
import re
import sys
import textwrap


def job_section(text, job):
    """The lines of `job` under `jobs:`."""
    match = re.search(rf"^  {re.escape(job)}:\s*$", text, re.M)
    if not match:
        raise KeyError(f"no job {job!r}")
    rest = text[match.end():]
    end = re.search(r"^  [A-Za-z0-9_-]+:\s*$", rest, re.M)
    return rest[:end.start()] if end else rest


def steps(text, job):
    """[(name, run script or None)] for every step of `job`, in order."""
    lines = job_section(text, job).splitlines()
    found = []
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)- name: (.*)$", line)
        if not match:
            continue
        indent = len(match.group(1))
        body = []
        for later in lines[index + 1:]:
            if later.strip() and len(later) - len(later.lstrip()) <= indent:
                break
            body.append(later)
        block = "\n".join(body) + "\n"
        run = re.search(r"^(\s*)run: \|\n((?:\1  .*\n|\s*\n)+)", block, re.M)
        single = re.search(r"^\s*run: (?!\|)(.+)$", block, re.M)
        script = textwrap.dedent(run.group(2)) if run else (single.group(1) + "\n" if single else None)
        found.append((match.group(2).strip().strip('"'), script))
    return found


def main(argv):
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    path, job, out = argv[:3]
    values = dict(item.split("=", 1) for item in argv[3:])
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    os.makedirs(out, exist_ok=True)
    number = 0
    for name, script in steps(text, job):
        if script is None:
            continue
        for expression, value in values.items():
            script = script.replace("${{ " + expression + " }}", value)
        if "${{" in script:
            print(f"left out (it needs GitHub Actions): {name}", file=sys.stderr)
            continue
        number += 1
        with open(os.path.join(out, f"{number:02d}.sh"), "w", encoding="utf-8") as handle:
            handle.write(script)
        with open(os.path.join(out, f"{number:02d}.name"), "w", encoding="utf-8") as handle:
            handle.write(name + "\n")
    return 0 if number else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
