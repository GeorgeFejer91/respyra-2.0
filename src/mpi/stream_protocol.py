"""Channel roles shared by LSL recording, BIDS export and MNE analysis."""

PROTOCOL = "respyra-stream/1"
DATA_ROLES = {"measurement", "waveform"}
SUPPORT_ROLES = {"quality", "validity", "diagnostic", "event"}


def field(metadata, key, default=""):
    value = metadata.get(key, default)
    return value[0] if isinstance(value, list) and value else (default if value is None else value)


def channel_role(channel, stream_type=""):
    role = field(channel, "role")
    if role:
        if role not in DATA_ROLES | SUPPORT_ROLES:
            raise ValueError(f"Unsupported stream channel role: {role}")
        return role
    kind = field(channel, "type", stream_type)
    return {"SignalQuality": "quality", "RecordingDiagnostics": "diagnostic",
            "Marker": "event", "Markers": "event"}.get(kind, "measurement")


def mne_channel_spec(channel, stream_type=""):
    """Only assign voltage channel types when their units establish the scale."""
    kind = field(channel, "type", stream_type).lower()
    unit = field(channel, "unit")
    scale = {"V": 1.0, "mV": 1e-3, "uV": 1e-6, "µV": 1e-6, "μV": 1e-6}.get(unit)
    voltage_types = {"ecg": "ecg", "eeg": "eeg", "emg": "emg", "eog": "eog",
                     "respiration": "resp", "resp": "resp", "bio": "bio"}
    if scale is not None and kind in voltage_types:
        return voltage_types[kind], scale
    return "misc", 1.0


def waveform_validity_columns(channel, channels, desc):
    """Bind only this variable's readiness, including multi-variable bundles."""
    references = field(channel, "validity_channels")
    if (not references and field(desc, "waveform_channel")
            and field(channel, "metric_id") == field(desc, "waveform_channel")):
        references = field(desc, "validity_channels")
    if references:
        columns = []
        for identity in references.split(","):
            matches = [i for i, c in enumerate(channels) if field(c, "metric_id") == identity
                       and channel_role(c) == "validity"]
            if len(matches) != 1:
                raise ValueError(f"Missing or ambiguous waveform validity channel: {identity}")
            columns.append(f"channel{matches[0] + 1}")
        return columns
    if sum(channel_role(c) == "waveform" for c in channels) == 1:
        return [f"channel{i + 1}" for i, c in enumerate(channels) if channel_role(c) == "validity"]
    if any(channel_role(c) == "validity" for c in channels):
        raise ValueError("Multi-variable waveform streams must declare their own validity channels")
    return []
