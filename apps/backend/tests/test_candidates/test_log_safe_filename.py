"""An uploaded filename reaches the log, so it must not be able to forge lines."""

from app.modules.recruitment.controller.candidates import _log_safe


def test_strips_newlines_that_would_forge_a_log_entry():
    forged = "cv.pdf\nERROR:root:Bulk upload: granted admin to attacker"
    out = _log_safe(forged)
    assert "\n" not in out
    assert out.startswith("cv.pdf")


def test_strips_carriage_returns_and_control_characters():
    assert "\r" not in _log_safe("a\rb")
    assert "\t" not in _log_safe("a\tb")
    assert _log_safe("a\x00b") == "ab"


def test_caps_length_so_one_upload_cannot_flood_a_line():
    assert len(_log_safe("x" * 5000)) == 120


def test_leaves_an_ordinary_filename_alone():
    assert _log_safe("John_Doe_Resume_2024.pdf") == "John_Doe_Resume_2024.pdf"


def test_falls_back_when_nothing_printable_survives():
    assert _log_safe("\n\r\x00") == "<unnamed>"
    assert _log_safe("") == "<unnamed>"
