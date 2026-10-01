"""Optional MNE reader for Respyra's BIDS physiology and timed signal tables."""

from __future__ import annotations

import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np


def read_bids_signal(path: str | Path, *, sfreq: float | None = None):
    """Return ``(mne.Raw, original_timestamps)`` for one numeric BIDS signal.

    Fixed-rate physiology needs no rate argument. An irregular ``_beh.tsv``
    requires ``sfreq``; its finite adjacent samples are linearly interpolated
    onto that grid; a lone sample is kept as one sample. Missing values remain
    gaps. All channels are MNE ``misc``
    because LSL physical units can differ from MNE's ECG/RESP voltage units.
    Exact recorded times and channel units remain in the BIDS table and sidecar.
    """
    import mne  # Optional analysis dependency; not needed by the recording app.

    path = Path(path)
    if path.name.endswith("_physio.tsv.gz"):
        metadata_path = path.with_suffix("").with_suffix(".json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        columns = metadata["Columns"]
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle, delimiter="\t"))
        rate = float(metadata["SamplingFrequency"])
        if sfreq is not None:
            raise ValueError("Fixed-rate physiology already has a sampling rate")
    elif path.name.endswith("_beh.tsv"):
        metadata_path = path.with_suffix(".json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, delimiter="\t")
            columns = next(reader)
            rows = list(reader)
        if sfreq is None or not math.isfinite(sfreq) or sfreq <= 0:
            raise ValueError("Irregular samples need an explicit positive sfreq for MNE")
        rate = float(sfreq)
    else:
        raise ValueError("Expected a BIDS _physio.tsv.gz or _beh.tsv signal table")
    if metadata["LSLSource"]["ChannelFormat"] == "string":
        raise ValueError("MNE Raw requires numeric channels")
    if columns[0] != "timestamp" or not rows or any(len(row) != len(columns) for row in rows):
        raise ValueError("Invalid or empty BIDS signal table")
    stamps = np.array([float(row[0]) for row in rows], dtype=float)
    if not np.all(np.isfinite(stamps)) or np.any(np.diff(stamps) <= 0):
        raise ValueError("BIDS signal timestamps must be finite and increasing")
    data = np.array([[float("nan") if cell == "n/a" else float(cell) for cell in row[1:]]
                     for row in rows], dtype=float).T
    if path.name.endswith("_beh.tsv") and len(stamps) > 1:
        grid = stamps[0] + np.arange(math.floor((stamps[-1] - stamps[0]) * rate) + 1) / rate
        sampled = np.full((data.shape[0], len(grid)), np.nan)
        for index, channel in enumerate(data):
            for left in range(len(stamps) - 1):
                if np.isfinite(channel[left]) and np.isfinite(channel[left + 1]):
                    mask = (grid >= stamps[left]) & (grid <= stamps[left + 1])
                    sampled[index, mask] = np.interp(grid[mask], stamps[left:left + 2], channel[left:left + 2])
            for stamp, value in zip(stamps, channel):
                position = round((stamp - stamps[0]) * rate)
                if 0 <= position < len(grid) and abs(grid[position] - stamp) < 1e-9:
                    sampled[index, position] = value
        data = sampled
    names = [metadata.get(column, {}).get("LongName", column) for column in columns[1:]]
    if len(names) != len(set(names)):
        names = columns[1:]
    info = mne.create_info(names, sfreq=rate, ch_types=["misc"] * len(names))
    info["description"] = json.dumps({"LSLSource": metadata["LSLSource"],
                                      "ChannelUnits": {column: metadata.get(column, {}).get("Units", "")
                                                       for column in columns[1:]}})
    return mne.io.RawArray(data, info, verbose="ERROR"), stamps
