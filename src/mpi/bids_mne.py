"""Optional MNE reader for Respyra's BIDS physiology and timed signal tables."""

from __future__ import annotations

import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np
from mpi.stream_protocol import PROTOCOL, DATA_ROLES, channel_role


def _read_table(path):
    if path.name.endswith("_physio.tsv.gz"):
        metadata = json.loads(path.with_suffix("").with_suffix(".json").read_text(encoding="utf-8"))
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle, delimiter="\t"))
        return metadata, metadata["Columns"], rows
    if path.name.endswith("_beh.tsv"):
        metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, delimiter="\t")
            return metadata, next(reader), list(reader)
    raise ValueError("Expected a BIDS _physio.tsv.gz or _beh.tsv signal table")


def _variable_data(path, metadata, columns, rows, include_support):
    signal_columns = [column for column in columns[1:] if column.startswith("channel")]
    signal_columns = [column for column in signal_columns if include_support or
                      channel_role({"role": metadata.get(column, {}).get("ChannelRole", "measurement")}) in DATA_ROLES]
    if not signal_columns:
        raise ValueError("No experimental data channels; use include_support=True to read diagnostics")
    indices = [columns.index(column) for column in signal_columns]
    data = np.array([[float("nan") if row[index] == "n/a" else float(row[index]) for index in indices]
                     for row in rows], dtype=float).T
    if metadata.get("SupportTable"):
        support_name = metadata["SupportTable"]
        if not isinstance(support_name, str) or Path(support_name).name != support_name or "\\" in support_name:
            raise ValueError("Invalid BIDS support table reference")
        support_metadata, support_columns, support_rows = _read_table(path.parent / support_name)
        if len(support_rows) != len(rows) or any(a[0] != b[0] for a, b in zip(rows, support_rows)):
            raise ValueError("BIDS support timestamps do not match the data variables")
        for index, column in enumerate(signal_columns):
            flags = metadata.get(column, {}).get("ValidityColumns", [])
            if flags:
                flag_indices = [support_columns.index(flag) for flag in flags]
                valid = [all(value != "n/a" and math.isfinite(float(value)) and float(value) >= 0.5
                             for value in (row[i] for i in flag_indices)) for row in support_rows]
                data[index, ~np.array(valid)] = np.nan
        if include_support:
            supporting = [c for c in support_columns if c.startswith("channel")]
            extra = np.array([[float("nan") if row[support_columns.index(c)] == "n/a" else
                               float(row[support_columns.index(c)]) for c in supporting]
                              for row in support_rows], dtype=float).T
            data = np.vstack((data, extra))
            signal_columns.extend(supporting)
            metadata.update({c: support_metadata[c] for c in supporting})
    return data, signal_columns


def _resample_signal(data, stamps, rate, metadata, signal_columns):
    grid = stamps[0] + np.arange(math.floor((stamps[-1] - stamps[0]) * rate) + 1) / rate
    sampled = np.full((data.shape[0], len(grid)), np.nan)
    max_gap = (3 * float(np.median(np.diff(stamps)))
               if metadata.get("StreamProtocol") == PROTOCOL else float("inf"))
    for index, channel in enumerate(data):
        for left in range(len(stamps) - 1):
            if (np.isfinite(channel[left]) and np.isfinite(channel[left + 1])
                    and stamps[left + 1] - stamps[left] <= max_gap):
                mask = (grid >= stamps[left]) & (grid <= stamps[left + 1])
                sampled[index, mask] = (channel[left] if metadata.get(signal_columns[index], {}).get("Interpolation") == "previous"
                                        else np.interp(grid[mask], stamps[left:left + 2], channel[left:left + 2]))
        for stamp, value in zip(stamps, channel):
            position = round((stamp - stamps[0]) * rate)
            if 0 <= position < len(grid) and abs(grid[position] - stamp) < 1e-9:
                sampled[index, position] = value
    return sampled


def read_bids_signal(path: str | Path, *, sfreq: float | None = None, include_support=False):
    """Return ``(mne.Raw, original_timestamps)`` for one numeric BIDS signal.

    Fixed-rate physiology needs no rate argument. An irregular ``_beh.tsv``
    requires ``sfreq``; its finite adjacent samples are linearly interpolated
    onto that grid; a lone sample is kept as one sample. Missing values remain
    gaps. Experimental variables are selected by role; supporting channels
    require ``include_support=True``. Declared voltage channels use MNE's SI
    units; Force, ACC and dimensionless breathing remain ``misc``.
    Exact recorded times and channel units remain in the BIDS table and sidecar.
    """
    import mne  # Optional analysis dependency; not needed by the recording app.

    path = Path(path)
    metadata, columns, rows = _read_table(path)
    if path.name.endswith("_physio.tsv.gz"):
        rate = float(metadata["SamplingFrequency"])
        if sfreq is not None:
            raise ValueError("Fixed-rate physiology already has a sampling rate")
    elif path.name.endswith("_beh.tsv"):
        if sfreq is None or not math.isfinite(sfreq) or sfreq <= 0:
            raise ValueError("Irregular samples need an explicit positive sfreq for MNE")
        rate = float(sfreq)
    if metadata["LSLSource"]["ChannelFormat"] == "string":
        raise ValueError("MNE Raw requires numeric channels")
    if columns[0] != "timestamp" or not rows or any(len(row) != len(columns) for row in rows):
        raise ValueError("Invalid or empty BIDS signal table")
    stamps = np.array([float(row[0]) for row in rows], dtype=float)
    if not np.all(np.isfinite(stamps)) or np.any(np.diff(stamps) <= 0):
        raise ValueError("BIDS signal timestamps must be finite and increasing")
    data, signal_columns = _variable_data(path, metadata, columns, rows, include_support)
    if path.name.endswith("_beh.tsv") and len(stamps) > 1:
        data = _resample_signal(data, stamps, rate, metadata, signal_columns)
    names = [metadata.get(column, {}).get("LongName", column) for column in signal_columns]
    if metadata.get("StreamProtocol") == PROTOCOL:
        names = [f"{metadata['LSLSource']['Name']}:{name}" for name in names]
    if len(names) != len(set(names)):
        names = ([f"{metadata['LSLSource']['Name']}:{column}" for column in signal_columns]
                 if metadata.get("StreamProtocol") == PROTOCOL else signal_columns)
    kinds = [metadata.get(column, {}).get("MNEType", "misc") for column in signal_columns]
    scales = np.array([metadata.get(column, {}).get("MNEValueScale", 1.0) for column in signal_columns], dtype=float)
    if not np.all(np.isfinite(scales)) or np.any(scales <= 0):
        raise ValueError("Invalid MNE unit scale")
    data *= scales[:, np.newaxis]
    info = mne.create_info(names, sfreq=rate, ch_types=kinds)
    info["description"] = json.dumps({"LSLSource": metadata["LSLSource"],
                                      "OriginalChannelUnits": {column: metadata.get(column, {}).get("Units", "")
                                                       for column in signal_columns},
                                      "MNEValueScale": dict(zip(signal_columns, scales.tolist()))})
    return mne.io.RawArray(data, info, verbose="ERROR"), stamps
