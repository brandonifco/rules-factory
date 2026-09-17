"""A check's verdict, and the three ways a check reaches one.

Every check returns a Result. `skip` is the one that needs care: it never becomes `ok`, and a
skip that had subject matter fails the run, because a check that could not look has not passed.
"""


class Result:
    """One check's verdict. `skip` never becomes `ok`; it fails the run if it had work."""

    def __init__(self, status, summary, details=None, had_subject=True):
        self.status = status  # "ok" | "fail" | "skip"
        self.summary = summary
        self.details = details or []
        self.had_subject = had_subject

    @property
    def fatal(self):
        return self.status == "fail" or (self.status == "skip" and self.had_subject)


def ok(summary, details=None):
    return Result("ok", summary, details)


def fail(details, summary):
    return Result("fail", summary, details)


def skip(summary, had_subject=True):
    return Result("skip", "NOT VERIFIED -- " + summary, had_subject=had_subject)


def verdict(details, ok_summary, fail_summary):
    return fail(details, fail_summary) if details else ok(ok_summary)
