from types import SimpleNamespace

import pytest

from mpi.event_markers import CATALOG, run_marked_participant_dialog


@pytest.mark.parametrize("button", ["ok", "cancel"])
def test_native_dialog_marks_keys_edits_and_buttons(monkeypatch, button):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PyQt6 import QtCore, QtTest
    from psychopy import gui

    original_dialog = gui.DlgFromDict
    observed = []

    class Collector:
        def emit(self, name, **fields):
            assert name in CATALOG["events"]
            assert set(CATALOG["events"][name]["fields"]) <= fields.keys()
            observed.append((name, fields))

    def make_dialog(*args, **kwargs):
        dialog = original_dialog(*args, **kwargs)
        assert kwargs["show"] is False

        def interact():
            QtTest.QTest.keyClicks(dialog.inputFields[0], "A")
            QtTest.QTest.keyClicks(dialog.inputFields[1], "2")
            (dialog.okBtn if button == "ok" else dialog.cancelBtn).click()

        QtCore.QTimer.singleShot(0, interact)
        return dialog

    monkeypatch.setattr(gui, "DlgFromDict", make_dialog)
    result = run_marked_participant_dialog(SimpleNamespace(name="Test"), Collector())
    names = [name for name, _fields in observed]
    assert names.count("participant.dialog.shown") == 1
    assert names.count("participant.dialog.hidden") == 1
    assert names.count("participant.field.key") >= 2
    assert names.count("participant.field.edited") >= 2
    assert f"participant.button.{button}.clicked" in names
    if button == "ok":
        assert "participant.dialog.accepted" in names
        assert result == {"participant": "A", "session": "0012"}
    else:
        assert "participant.dialog.rejected" in names
        assert result is None


def test_native_dialog_stops_when_marker_publication_fails(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PyQt6 import QtCore, QtTest
    from psychopy import gui

    original_dialog = gui.DlgFromDict

    class FailingCollector:
        def emit(self, name, **_fields):
            if name == "participant.field.key":
                raise RuntimeError("marker recorder disconnected")

    def make_dialog(*args, **kwargs):
        dialog = original_dialog(*args, **kwargs)
        QtCore.QTimer.singleShot(
            0, lambda: QtTest.QTest.keyClicks(dialog.inputFields[0], "A")
        )
        return dialog

    monkeypatch.setattr(gui, "DlgFromDict", make_dialog)
    with pytest.raises(RuntimeError, match="marker recorder disconnected"):
        run_marked_participant_dialog(SimpleNamespace(name="Test"), FailingCollector())
