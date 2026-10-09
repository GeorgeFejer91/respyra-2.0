"""Remember troubleshooting mode and retain bounded, local failure reports."""
from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import tempfile
import traceback
from uuid import uuid4


def settings_path():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config")) / "Respyra" / "troubleshooting.json"


def enabled():
    try:
        saved = json.loads(settings_path().read_text(encoding="utf-8"))
        return saved.get("enabled") is not False
    except (OSError, ValueError, AttributeError):
        return True


def save_enabled(value):
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump({"version": 1, "enabled": value}, handle)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def context(bridge, markers):
    source = getattr(bridge, "source", None)
    progress = getattr(bridge, "_progress", None) or {}
    comparisons = getattr(source, "comparisons", None)
    return {
        "run_id": markers.run_id,
        "last_event": progress.get("event"),
        "trial": progress.get("trial"), "condition": progress.get("condition"),
        "phase": progress.get("experiment_phase"), "screen": progress.get("screen"),
        "selected_source": {key: getattr(source, key, None) for key in
                            ("source_id", "stream_name", "contract_id")},
        "comparison_sources": [item.source_id for item in comparisons.sources] if comparisons else [],
        "recent_events": list(getattr(bridge, "recent", [])),
    }


def report(error, bridge, markers, finalization_error=None):
    """No signal samples, questionnaire answers, frame locals or remote grants."""
    if not bridge.troubleshooting:
        return None
    runtime = {"Python": platform.python_version(), "OS": platform.platform()}
    for name in ("respyra", "psychopy", "pylsl", "pyxdf"):
        try:
            runtime[name] = version(name)
        except PackageNotFoundError:
            runtime[name] = "unavailable"
    manifest = Path(os.environ.get("RESPYRA_ENGINE_MANIFEST", ""))
    try:
        build = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        build = {}
    recorder = getattr(bridge, "recorder", None)
    state = recorder.snapshot() if recorder else {}
    details = {
        "UTC": datetime.now(timezone.utc).isoformat(),
        "app_version": os.environ.get("RESPYRA_APP_VERSION", "development"),
        "source_revision": build.get("source_revision", "development"),
        "runtime": runtime,
        "failure_context": getattr(bridge, "failure_context", None) or context(bridge, markers),
        "recording": {key: state.get(key) for key in ("phase", "output_file", "error", "streams")},
    }
    text = "Respyra troubleshooting report\n" + json.dumps(details, indent=2, ensure_ascii=False)
    text += "\n\nOriginal exception and traceback:\n" + "".join(traceback.format_exception(type(error), error, error.__traceback__))
    if finalization_error is not None and finalization_error is not error:
        text += "\nRecording finalization also failed:\n" + "".join(traceback.format_exception(
            type(finalization_error), finalization_error, finalization_error.__traceback__))
    text = text.replace(str(Path.home()), "<user>")
    text = text[:65536] if len(text) <= 65536 else text[:60000] + "\n[Report shortened]\n" + text[-5000:]
    result = {"id": uuid4().hex, "text": text, "saved_path": None}
    try:
        folder = Path(recorder.output if recorder else settings_path().parent) / "diagnostics"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / ("error-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + result["id"] + ".txt")
        path.write_text(text, encoding="utf-8")
        result["saved_path"] = str(path)
    except OSError as exc:
        result["text"] += "\nCould not save report: " + str(exc)
    return result
