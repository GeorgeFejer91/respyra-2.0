"""Display-only LSL subscriptions. The native recorder retains full-rate samples."""
from __future__ import annotations

import math
import threading
import time
from xml.etree import ElementTree as ET


class LSLViewer:
    def __init__(self, marker_id):
        self.marker_id = marker_id
        self._snapshot = []
        self.error = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="respyra-lsl-viewer")
        self._thread.start()

    def snapshot(self):
        return self._snapshot

    def close(self):
        self._stop.set()
        self._thread.join(timeout=3)

    def _run(self):
        from pylsl import ContinuousResolver, StreamInlet, cf_string, proc_clocksync
        resolver = ContinuousResolver(forget_after=3)
        streams = {}
        try:
            while not self._stop.wait(.1):
                visible = {info.uid(): info for info in resolver.results()
                           if info.source_id() != self.marker_id}
                for uid in list(streams):
                    if uid not in visible:
                        streams.pop(uid)[0].close_stream()
                for uid, info in visible.items():
                    if self._stop.is_set():
                        break
                    if uid in streams:
                        continue
                    inlet = StreamInlet(info, max_buflen=2, processing_flags=proc_clocksync, recover=False)
                    try:
                        full = inlet.info(timeout=.2)
                        metadata = ET.fromstring(full.as_xml()).findall("./desc/channels/channel")
                        channels = []
                        for index in range(full.channel_count()):
                            channel = metadata[index] if index < len(metadata) else None
                            channels.append({"index": index,
                                "label": (channel.findtext("label") if channel is not None else None) or f"Channel {index + 1}",
                                "unit": channel.findtext("unit", "") if channel is not None else "", "value": None})
                        streams[uid] = (inlet, {"uid": uid, "source_id": full.source_id(),
                            "name": full.name(), "type": full.type(), "numeric": full.channel_format() != cf_string,
                            "channels": channels, "lsl_time": None}, None)
                    except Exception:
                        inlet.close_stream()  # Retry metadata while the outlet remains discoverable.
                rows = []
                for uid, (inlet, row, received) in list(streams.items()):
                    row = {**row, "channels": [dict(channel) for channel in row["channels"]]}
                    try:
                        samples, timestamps = inlet.pull_chunk(timeout=0, max_samples=1024)
                        if timestamps:
                            received = time.monotonic()
                            row["lsl_time"] = timestamps[-1]
                            for channel, value in zip(row["channels"], samples[-1]):
                                channel["value"] = (float(value) if row["numeric"] and math.isfinite(value)
                                                    else None if row["numeric"] else str(value))
                        age = time.monotonic() - received if received is not None else float("inf")
                        row["signal"] = "live" if age <= 1 else "stale" if age <= 3 else "waiting"
                    except Exception:
                        row["signal"] = "lost"
                    streams[uid] = (inlet, row, received)
                    rows.append(row)
                self._snapshot = sorted(rows, key=lambda row: (row["name"].casefold(), row["uid"]))
        except Exception as exc:
            self.error = f"LSL display unavailable: {exc}"
        finally:
            for inlet, _, _ in streams.values():
                inlet.close_stream()
