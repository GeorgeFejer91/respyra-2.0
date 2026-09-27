"""Real embedded runtime import/resource check; does not start a study."""
import importlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys

engine = Path(__file__).resolve().parents[1]
runtime = engine / "python"
assert Path(sys.executable).resolve() == runtime / "python.exe"
assert sys.flags.isolated and sys.flags.no_user_site and sys.flags.dont_write_bytecode and sys.flags.utf8_mode
assert sys.stdout.encoding.lower() == "utf-8"
assert all(Path(path).resolve().is_relative_to(runtime) for path in sys.path), sys.path
for name in ("numpy", "scipy", "pandas", "matplotlib", "pylsl", "psychopy.core", "psychopy.visual",
             "psychopy.data", "psychopy.event", "PyQt6.QtGui", "pythoncom", "pywintypes",
             "mpi.lsl_force", "mpi.event_markers", "mpi.validation_study_jenny", "respyra.core.runner"):
    module = importlib.import_module(name)
    assert Path(module.__file__).resolve().is_relative_to(runtime), (name, module.__file__)
from mpi.event_markers import MarkerOutlet
markers = MarkerOutlet()
assert markers.health_snapshot()["online"]
catalog = runtime / "Lib/site-packages/mpi/event_markers/catalog.json"
assert catalog.is_file()
print(json.dumps({"result": "passed", "isolated": bool(sys.flags.isolated),
                  "python": sys.version.split()[0], "psychopy": metadata.version("psychopy"),
                  "respyra": metadata.version("respyra"), "pylsl": metadata.version("pylsl"),
                  "marker_outlet": markers.health_snapshot()["online"]}))
