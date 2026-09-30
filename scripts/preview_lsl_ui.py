"""Loopback-only live LSL feed for the standalone experiment UI preview."""

from __future__ import annotations

import json
import argparse
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mpi.lsl_force import scan_force_streams  # noqa: E402
from mpi.lsl_viewer import LSLViewer  # noqa: E402


class Discovery:
    def __init__(self):
        self.viewer = LSLViewer("__standalone_preview__")
        self.candidates = {}
        self.error = None
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._scan, daemon=True, name="respyra-preview-scan")
        self.thread.start()

    def _scan(self):
        while not self.stop.is_set():
            try:
                candidates = {candidate.info.uid(): {
                    "compatible": candidate.force_index is not None,
                    "reason": candidate.reason,
                } for candidate in scan_force_streams(wait_time=.2)}
                with self.lock:
                    self.candidates, self.error = candidates, None
            except Exception as exc:
                with self.lock:
                    self.candidates, self.error = {}, str(exc)
            self.wake.wait(3)
            self.wake.clear()

    def snapshot(self):
        with self.lock:
            candidates, scan_error = self.candidates.copy(), self.error
        return {
            "streams": [{**row, **candidates.get(row["uid"], {"compatible": False, "reason": "Checking compatibility…"})}
                        for row in self.viewer.snapshot()],
            "error": self.viewer.error or scan_error,
        }

    def close(self):
        self.stop.set()
        self.wake.set()
        self.thread.join(timeout=3)
        self.viewer.close()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def do_GET(self):
        route = urlsplit(self.path).path
        if route in {"/api/streams", "/api/refresh"}:
            if route == "/api/refresh":
                self.server.discovery.wake.set()
            payload = json.dumps(self.server.discovery.snapshot(), allow_nan=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    port = parser.parse_args().port
    discovery = Discovery()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.discovery = discovery
    try:
        print(f"Live LSL preview: http://127.0.0.1:{server.server_port}/experiment-hub-preview.html", flush=True)
        server.serve_forever()
    finally:
        server.server_close()
        discovery.close()


if __name__ == "__main__":
    main()
