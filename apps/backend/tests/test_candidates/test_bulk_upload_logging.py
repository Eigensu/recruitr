"""The uploaded filename must never be handed to a logger.

It comes straight from the client, so a newline in it lets the uploader forge
whole log entries (pythonsecurity:S5145). The failure is still reported back to
the caller by name in BulkUploadFailure — it just never reaches a log line,
which is what actually keeps the tainted value out.

Asserted against the source rather than by driving the endpoint: the two
logging branches sit behind nested `except Exception` handlers that swallow
anything raised earlier, so an execution test would have to reach them through
several layers of unrelated error handling.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

from app.modules.recruitment.controller import candidates

TAINTED = {"filename"}


def _tree() -> ast.AST:
    return ast.parse(textwrap.dedent(inspect.getsource(candidates.bulk_upload_resumes)))


def _log_calls(tree: ast.AST) -> list[ast.Call]:
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if (
                isinstance(fn, ast.Attribute)
                and isinstance(fn.value, ast.Name)
                and fn.value.id == "_log"
            ):
                calls.append(node)
    return calls


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def test_bulk_upload_still_logs_on_failure():
    # Guard the guard: if the logging is refactored away, the assertion below
    # must not start passing vacuously.
    assert _log_calls(_tree()), "expected bulk_upload_resumes to log on failure"


def test_no_log_call_receives_the_filename():
    for call in _log_calls(_tree()):
        for arg in call.args:
            leaked = _names_in(arg) & TAINTED
            assert not leaked, f"logger receives client-controlled {leaked}: {ast.unparse(call)}"


def test_failures_still_report_the_filename_to_the_caller():
    # Dropping it from the log must not drop it from the response, or callers
    # lose the only signal telling them which file failed.
    assert "filename=filename" in inspect.getsource(candidates.bulk_upload_resumes)
