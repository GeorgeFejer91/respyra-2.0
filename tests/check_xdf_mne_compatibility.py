"""Open a recorded XDF directly with PyXDF and MNE, without BIDS export files."""

import argparse
import json
import math
from pathlib import Path

import mne
import numpy as np
import pyxdf


def check(path: Path, resample_hz: float, require_metadata: bool,
          require_run_metadata: bool, mnelab: bool):
    streams, _ = pyxdf.load_xdf(str(path), dejitter_timestamps=False)
    assert streams, "XDF has no streams"
    opened = 0
    resampled = 0
    samples = 0
    events = []
    marker_stream = None
    for stream in streams:
        info = stream["info"]
        stamps = np.asarray(stream["time_stamps"], dtype=float)
        if not len(stamps):
            continue
        assert np.isfinite(stamps).all() and np.all(np.diff(stamps) > 0)
        samples += len(stamps)
        kind = info["channel_format"][0]
        if kind == "string":
            if (info.get("source_id") or [""])[0].startswith("respyra-events-"):
                marker_stream = stream
                events.extend((float(stamp), json.loads(row[0]))
                              for stamp, row in zip(stamps, stream["time_series"]))
            continue
        data = np.asarray(stream["time_series"], dtype=float)
        count = int(info["channel_count"][0])
        assert data.shape == (len(stamps), count)
        channels = (((info.get("desc") or [{}])[0] or {}).get("channels") or [{}])[0].get("channel", [])
        if require_metadata:
            assert len(channels) == count, info["name"][0]
            assert all(channel.get("label", [""])[0] and channel.get("unit", [""])[0]
                       for channel in channels), info["name"][0]
        labels = [channels[index].get("label", [f"channel{index + 1}"])[0]
                  if index < len(channels) else f"channel{index + 1}" for index in range(count)]
        assert len(labels) == len(set(labels)), info["name"][0]
        nominal = float(info["nominal_srate"][0])
        regular = nominal > 0 and len(stamps) > 1 and np.all(
            np.abs(np.diff(stamps) - 1 / nominal) <= 0.02 / nominal)
        if regular:
            sfreq = nominal
            values = data.T
        else:
            assert resample_hz > 0, "Irregular XDF streams need an explicit analysis rate"
            sfreq = resample_hz
            grid = stamps[0] + np.arange(math.floor((stamps[-1] - stamps[0]) * sfreq) + 1) / sfreq
            values = np.vstack([np.interp(grid, stamps, column) for column in data.T])
            right = np.searchsorted(stamps, grid, side="right")
            inside = (right > 0) & (right < len(stamps))
            gap = np.zeros(len(grid), dtype=bool)
            gap[inside] = (stamps[right[inside]] - stamps[right[inside] - 1]) > 2 / sfreq
            values[:, gap] = np.nan
            resampled += 1
        raw = mne.io.RawArray(values, mne.create_info(labels, sfreq, ch_types="misc"), verbose="ERROR")
        assert raw.get_data().shape == values.shape and raw.ch_names == labels
        assert raw.info["sfreq"] == sfreq
        if regular:
            np.testing.assert_allclose(raw.get_data(), data.T, equal_nan=True)
        opened += 1
    if require_run_metadata:
        assert events, "XDF has no Respyra event stream"
    if events:
        names = [event["event"] for _, event in events]
        assert "recording.started" in names and "recording.finalizing" in names
        origin = events[0][0]
        annotations = mne.Annotations([stamp - origin for stamp, _ in events],
                                      [0] * len(events), names)
        assert len(annotations) == len(events)
        if require_run_metadata:
            start = next(event for _, event in events if event["event"] == "recording.started")
            assert start["subject"] and start["session"] and start["task"] == "respyra"
            assert isinstance(start["variables"], list)
    mnelab_opened = False
    if mnelab:
        from mnextend.io.xdf import read_raw_xdf

        assert events and marker_stream is not None
        start = next(event for _, event in events if event["event"] == "recording.started")
        selected = next(stream for stream in streams
                        if (stream["info"].get("source_id") or [""])[0] == start["source_ids"][0])
        nominal = float(selected["info"]["nominal_srate"][0])
        raw = read_raw_xdf(str(path), stream_ids=[selected["info"]["stream_id"]],
                           marker_ids=[marker_stream["info"]["stream_id"]],
                           fs_new=resample_hz if nominal == 0 else None)
        assert raw.n_times > 0 and len(raw.annotations) == len(events)
        mnelab_opened = True
    assert opened, "XDF contains no numeric signal MNE can open"
    print(json.dumps({"result": "passed", "xdf": str(path), "streams": len(streams),
                      "samples": samples, "mne_raw_opened": opened,
                      "resampled_streams": resampled, "respyra_events": len(events),
                      "mnelab_opened": mnelab_opened}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xdf", required=True, type=Path)
    parser.add_argument("--resample-hz", required=True, type=float)
    parser.add_argument("--require-metadata", action="store_true")
    parser.add_argument("--require-run-metadata", action="store_true")
    parser.add_argument("--mnelab", action="store_true", help="Also open the selected raw stream and events via MNELAB's importer")
    args = parser.parse_args()
    check(args.xdf, args.resample_hz, args.require_metadata, args.require_run_metadata, args.mnelab)
