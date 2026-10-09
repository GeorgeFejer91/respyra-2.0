from pathlib import Path
from types import SimpleNamespace
import json

from mpi import diagnostics


def test_remembered_mode_and_report_preserve_original_and_cleanup_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert diagnostics.enabled()
    diagnostics.save_enabled(False)
    assert not diagnostics.enabled()
    diagnostics.save_enabled(True)
    source = SimpleNamespace(source_id="test-force", stream_name="Test Force")
    bridge = SimpleNamespace(troubleshooting=True, source=source, recent=[],
        _progress={"event":"tracking.started", "trial":2, "experiment_phase":"tracking"},
        recorder=SimpleNamespace(output=tmp_path, snapshot=lambda: {"phase":"error", "output_file":"partial.xdf"}))
    markers = SimpleNamespace(run_id="test-run")
    try:
        private_answer = "never-copy-my-answer"
        raise TypeError("'str' object is not callable")
    except TypeError as error:
        result = diagnostics.report(error, bridge, markers, OSError("synthetic recorder failure"))
    assert "TypeError: 'str' object is not callable" in result["text"]
    assert "test_diagnostics.py" in result["text"] and "test-force" in result["text"]
    assert '"trial": 2' in result["text"] and "partial.xdf" in result["text"]
    assert "Recording finalization also failed" in result["text"]
    assert private_answer not in result["text"]
    assert Path(result["saved_path"]).read_text(encoding="utf-8") == result["text"]
    bridge.troubleshooting = False
    assert diagnostics.report(RuntimeError("disabled"), bridge, markers) is None
    assert len(list((tmp_path / "diagnostics").glob("*.txt"))) == 1


def test_report_remains_copyable_when_disk_write_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    blocked = tmp_path / "not-a-folder"
    blocked.write_text("sentinel")
    bridge = SimpleNamespace(troubleshooting=True, failure_context={"phase":"baseline"},
        recorder=SimpleNamespace(output=blocked, snapshot=lambda: {}))
    result = diagnostics.report(RuntimeError("original failure"), bridge, SimpleNamespace(run_id="run"))
    assert result["saved_path"] is None
    assert "original failure" in result["text"] and "Could not save report" in result["text"]
    assert blocked.read_text() == "sentinel"
