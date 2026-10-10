#!/usr/bin/env python3
"""Post-session visualization for the breath tracking task.

Generates a 6-panel summary figure from a session CSV or Respyra XDF, helping
experimenters evaluate participant performance and verify task operation.

Usage
-----
    python scripts/plot_session.py data/recording.xdf --no-show
    python scripts/plot_session.py data/session.csv --no-show

The figure is saved as ``{input_stem}_summary.png`` alongside the input.
XDF targets/errors use recorded sample times, not the CSV's display-frame times.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# -- Colors ----------------------------------------------------------------

PHASE_COLORS = {
    "range_cal": "#3d2a2a",  # dark warm (one-time calibration)
    "baseline": "#2a2a3d",  # dark indigo
    "countdown": "#2a3340",  # dark teal
    "tracking": "#1a1a2e",  # near-black (no shading — trace stands out)
}
CONDITION_COLORS = {
    "normal": "#5b9bd5",  # steel blue
    "deep": "#ed7d31",  # warm orange
    "shallow": "#e05cda",  # magenta
    "normal_no_feedback": "#6FBD68",
    "deep_no_feedback": "#7132A5",
    "shallow_no_feedback": "#E6D220",
}
CONDITION_SHORT = {
    "normal": "NF",
    "deep": "DF",
    "shallow": "SF",
    "normal_no_feedback": "NN",
    "deep_no_feedback": "DN",
    "shallow_no_feedback": "SN",
}
FORCE_COLOR = "#00e676"  # lime green (matches live trace)
TARGET_COLOR = "#ffa726"  # orange
ERROR_POS_COLOR = "#ef5350"  # red
ZERO_LINE_COLOR = "#666666"


# -- Data loading ----------------------------------------------------------

PHASE_ORDER = {"range_cal": 0, "baseline": 1, "countdown": 2, "tracking": 3}


class NoSessionSamples(ValueError):
    """A recording ended before any calibration/trial samples were captured."""


def load_session(csv_path: str | Path) -> pd.DataFrame:
    """Read CSV or XDF into the common plotting table, with elapsed session time.

    Parameters
    ----------
    csv_path : str
        Path to an original sample CSV or a native Respyra XDF recording.

    Returns
    -------
    pd.DataFrame
        CSV rows use reconstructed phase order; XDF rows use synchronized
        sample timestamps. ``signal_unit`` in attrs supplies N or g labels.
    """
    if Path(csv_path).suffix.lower() == ".xdf":
        return load_xdf_session(csv_path)
    if Path(csv_path).suffix.lower() != ".csv":
        raise ValueError("Expected a session .csv or Respyra .xdf file")
    df = pd.read_csv(csv_path)
    unit = "g" if "signal_g" in df.columns else "N"
    df = df.rename(columns={"signal_g": "force_n", "target_signal_g": "target_force",
                            "error_g": "error", "compensated_error_g": "compensated_error"})
    required = {"timestamp", "force_n", "target_force", "error", "phase", "condition", "trial_num"}
    if not required.issubset(df.columns) or df.empty:
        raise ValueError("No session samples; use the sample CSV, not the self-assessment CSV")
    df["condition"] = df["condition"].fillna("")

    # Numeric columns (empty strings → NaN)
    for col in ("timestamp", "frame", "force_n", "target_force", "error", "feedback_gain"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "trial_num" in df.columns:
        df["trial_num"] = pd.to_numeric(df["trial_num"], errors="coerce").astype("Int64")

    # Sort chronologically: trial → phase order → timestamp.
    # Frame numbers and timestamps both reset per trial, so we need the
    # phase ordering to reconstruct the correct session sequence.
    df["_phase_ord"] = df["phase"].map(PHASE_ORDER).fillna(9)
    df = df.sort_values(
        ["trial_num", "_phase_ord", "timestamp"],
    ).reset_index(drop=True)
    df = df.drop(columns=["_phase_ord"])

    # Build a monotonic session_time for the full-session trace.
    df["session_time"] = _build_session_time(df)
    df.attrs["signal_unit"] = unit

    return df


def _field(info, key, default=""):
    """Read one value from PyXDF's XML lists."""
    values = info.get(key) or [default]
    return values[0] if values[0] is not None else default


def load_xdf_session(path: str | Path) -> pd.DataFrame:
    """Reconstruct the selected study input and phases from XDF alone.

    Keep clock synchronization but disable nominal-rate timestamp smoothing.
    Pair raw values with the selected derived outlet's accepted timestamps;
    comparison outlets and invalid Polar samples cannot enter the summary.
    The existing target generator owns target reconstruction. No CSV sidecar
    or assumptions about stream display names/channel order are needed.
    """
    import pyxdf

    streams, _ = pyxdf.load_xdf(str(path), synchronize_clocks=True, dejitter_timestamps=False)
    marker_streams = [s for s in streams if
                      _field(_field(s["info"], "desc", {}), "schema") == "respyra-event-markers-v1"]
    if len(marker_streams) != 1:
        raise ValueError("Expected exactly one Respyra study marker stream in XDF")
    markers = marker_streams[0]
    events = [(float(t), json.loads(row[0])) for t, row in
              zip(markers["time_stamps"], markers["time_series"], strict=True)]
    events.sort(key=lambda item: item[0])
    run_ids = {e.get("run_id") for _, e in events}
    if len(run_ids) != 1 or None in run_ids:
        raise ValueError("XDF markers must identify one Respyra run")
    run_id = next(iter(run_ids))
    if not any(e["event"] in {"calibration.attempt.started", "baseline.started",
                              "countdown.started", "tracking.started"} for _, e in events):
        raise NoSessionSamples("XDF contains no recorded calibration or trial phase samples")

    def unique_stream(source_id):
        matches = [s for s in streams if _field(s["info"], "source_id") == source_id]
        if len(matches) != 1 or not len(matches[0]["time_stamps"]):
            raise ValueError(f"Missing or ambiguous selected XDF stream: {source_id}")
        return matches[0]

    selected = unique_stream(f"respyra-breathing-{run_id}")
    desc = _field(selected["info"], "desc", {})
    raw = unique_stream(_field(desc, "raw_source_id"))
    raw_desc = _field(raw["info"], "desc", {})
    channels = _field(raw_desc, "channels", {}).get("channel", [])
    polar = _field(desc, "input_contract") in {"respyra-polar-pca/1", "respyra-polar-phan-signed/1"}
    unit = "g" if polar else "N"
    indices = [i for i, c in enumerate(channels) if _field(c, "unit") == unit and
               (polar or (_field(c, "sensor_number") == "1" and _field(c, "type") == "RawMeasurement"))]
    if len(indices) != 1:
        raise ValueError("Selected raw XDF input has no unique study signal channel")
    calibration = next((e for _, e in events if e["event"] == "calibration.completed"), {})
    setup_events = [e for _, e in events]
    for _, event in events:
        if event["event"] == "recording.started":
            setup_events = event.get("pre_recording_events", []) + setup_events
    direction = next((e for e in reversed(setup_events) if e["event"] == "source.polarity.set"), {})
    if polar and not calibration and not direction:
        raise ValueError("Polar XDF is missing the selected input polarity")
    polarity = (calibration.get("input_polarity", -1 if direction.get("enabled") else 1)
                if polar else 1)
    if polarity not in (-1, 1):
        raise ValueError("Polar XDF is missing the selected input polarity")

    raw_times = np.asarray(raw["time_stamps"], dtype=float)
    values = np.asarray(raw["time_series"], dtype=float)[:, indices[0]] * polarity
    order = np.argsort(raw_times, kind="stable")
    raw_times, values = raw_times[order], values[order]
    times = np.asarray(selected["time_stamps"], dtype=float)
    if not np.isfinite(raw_times).all() or not np.isfinite(times).all():
        raise ValueError("XDF has nonfinite signal timestamps")
    right = np.searchsorted(raw_times, times).clip(0, len(raw_times) - 1)
    left = (right - 1).clip(0)
    nearest = np.where(abs(raw_times[left] - times) <= abs(raw_times[right] - times), left, right)
    periods = np.diff(raw_times)
    periods = periods[periods > 0]
    # Allow clock-fit error, but never pair across half a sample interval.
    tolerance = min(0.01, float(np.median(periods)) * 0.45) if len(periods) else 0.001
    paired = abs(raw_times[nearest] - times) <= tolerance
    values = values[nearest]

    phase_starts = {"calibration.attempt.started": "range_cal", "baseline.started": "baseline",
                    "countdown.started": "countdown", "tracking.started": "tracking"}
    phase_ends = {"calibration.attempt.ended", "baseline.ended", "countdown.ended", "tracking.ended"}
    terminal = {"run.aborted", "run.completed", "display.closed", "recording.finalizing"}
    intervals = []
    active = None
    for stamp, event in events:
        name = event["event"]
        if active is not None and (name in phase_starts or name in phase_ends or name in terminal):
            intervals.append((*active, stamp))
            active = None
        if name in phase_starts:
            active = (stamp, event, phase_starts[name])
    if active is not None:
        intervals.append((*active, float(times.max()) + np.finfo(float).eps * abs(times.max())))

    frames = []
    for start, event, phase, end in intervals:
        mask = (times >= start) & (times < end)
        if not paired[mask].all():
            raise ValueError("Cannot pair selected study samples with recorded raw timestamps")
        elapsed, signal = times[mask] - start, values[mask]
        if not np.isfinite(signal).all():
            raise ValueError("Selected study samples contain nonfinite raw values")
        gain = float(event.get("feedback_gain", 1))
        target = np.full(len(signal), np.nan)
        compensated = target.copy()
        if phase == "tracking":
            from respyra.core.target_generator import ConditionDef, SegmentDef, TargetGenerator

            center = event.get("target_center_value", event.get("target_center_n"))
            amplitude = event.get("target_amplitude_value", event.get("target_amplitude_n"))
            segments = [SegmentDef(float(s["freq_hz"]), int(s["n_cycles"])) for s in event.get("segments", [])]
            if (center is None or amplitude is None or not np.isfinite([center, amplitude, gain]).all()
                    or amplitude <= 0 or not segments
                    or any(not np.isfinite(s.freq_hz) or s.freq_hz <= 0 or s.n_cycles <= 0 for s in segments)):
                raise ValueError("Tracking marker lacks valid target parameters")
            generator = TargetGenerator(ConditionDef(event["condition"], segments), center, amplitude)
            target = np.array([generator.get_target(t) for t in elapsed])
            compensated = target - (center + gain * (signal - center))
        frames.append(pd.DataFrame({"timestamp": elapsed, "frame": np.nan, "force_n": signal,
                                    "target_force": target, "error": target - signal,
                                    "compensated_error": compensated, "phase": phase,
                                    "condition": event.get("condition") or "",
                                    "trial_num": event.get("trial") or 0, "feedback_gain": gain,
                                    "session_time": times[mask]}))
    if not frames or not any(len(frame) for frame in frames):
        raise NoSessionSamples("XDF contains no recorded calibration or trial phase samples")
    df = pd.concat(frames, ignore_index=True).sort_values("session_time").reset_index(drop=True)
    df["trial_num"] = df["trial_num"].astype("Int64")
    df["session_time"] -= intervals[0][0]
    df.attrs.update(signal_unit=unit, source_format="XDF")
    baseline_cal = [{"trial_num": e["trial"], "condition": e.get("condition") or "",
                     "center": e.get("center_value", e.get("center_n")),
                     "amplitude": e.get("amplitude_value", e.get("amplitude_n"))}
                    for _, e in events if e["event"] == "baseline.calculated"]
    if baseline_cal:
        df.attrs["baseline_calibration"] = baseline_cal
    return df


def save_xdf_summary(path: str | Path) -> Path | None:
    """Save a headless six-panel PNG from the closed XDF; skip pre-study stops."""
    import matplotlib
    matplotlib.use("Agg", force=True)
    try:
        df = load_xdf_session(path)
    except NoSessionSamples:
        return None
    output = Path(path).with_name(Path(path).stem + "_summary.png")
    fig = plot_session(df, str(path))
    try:
        fig.savefig(output, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    finally:
        plt.close(fig)
    return output


def _build_session_time(df: pd.DataFrame) -> pd.Series:
    """Reconstruct monotonic session time from per-phase timestamps.

    The df must already be sorted by (trial_num, phase_order, timestamp).
    """
    session_time = np.zeros(len(df))
    offset = 0.0
    prev_phase = None
    prev_trial = None

    for i in range(len(df)):
        row = df.iloc[i]
        phase = row.get("phase", "")
        trial = row.get("trial_num", np.nan)
        ts = row.get("timestamp", 0.0)
        if pd.isna(ts):
            ts = 0.0

        # Detect phase/trial boundary → bump offset past previous max
        if phase != prev_phase or trial != prev_trial:
            if i > 0:
                offset = session_time[i - 1] + 0.5
            prev_phase = phase
            prev_trial = trial

        session_time[i] = offset + ts

    return pd.Series(session_time, index=df.index)


# -- Per-trial statistics --------------------------------------------------


def compute_trial_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-trial summary statistics from the tracking phase.

    Parameters
    ----------
    df : pd.DataFrame
        Session dataframe as returned by :func:`load_session`.

    Returns
    -------
    pd.DataFrame
        One row per trial with columns: ``trial_num``, ``condition``,
        ``mae`` (mean absolute error in the input unit), ``mae_sd``,
        ``rmse``, and ``n_samples``.  Empty if no tracking data exists.
    """
    tracking = df[df["phase"] == "tracking"].dropna(subset=["error"]).copy()
    if tracking.empty:
        return pd.DataFrame()

    tracking["abs_error"] = tracking["error"].abs()

    stats = (
        tracking.groupby(["trial_num", "condition"])
        .agg(
            mae=("abs_error", "mean"),
            mae_sd=("abs_error", "std"),
            rmse=("error", lambda x: np.sqrt((x**2).mean())),
            n_samples=("error", "count"),
        )
        .reset_index()
    )

    return stats


def compute_baseline_cal(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-trial baseline calibration (center and amplitude).

    Parameters
    ----------
    df : pd.DataFrame
        Session dataframe as returned by :func:`load_session`.

    Returns
    -------
    pd.DataFrame
        One row per trial with columns: ``trial_num``, ``condition``,
        ``force_min``, ``force_max``, ``force_mean``, ``center``
        (midpoint of min/max), and ``amplitude`` (half-range, minimum 0.5 N
        or 1e-5 g). XDF uses the study's baseline.calculated markers for
        center/amplitude when present. Empty if no baseline data exists.
    """
    if "baseline_calibration" in df.attrs:
        # These markers report the actual samples used by the study, including
        # samples consumed just before the first baseline display flip.
        return pd.DataFrame(df.attrs["baseline_calibration"]).dropna(subset=["center", "amplitude"])
    baseline = df[df["phase"] == "baseline"].dropna(subset=["force_n"])
    if baseline.empty:
        return pd.DataFrame()

    cal = (
        baseline.groupby(["trial_num", "condition"])
        .agg(
            force_min=("force_n", "min"),
            force_max=("force_n", "max"),
            force_mean=("force_n", "mean"),
        )
        .reset_index()
    )

    cal["center"] = (cal["force_max"] + cal["force_min"]) / 2
    minimum = 1e-5 if df.attrs.get("signal_unit") == "g" else 0.5
    cal["amplitude"] = ((cal["force_max"] - cal["force_min"]) / 2).clip(lower=minimum)

    return cal


# -- Plotting --------------------------------------------------------------


def plot_session(df: pd.DataFrame, csv_path: str) -> plt.Figure:
    """Create a 6-panel summary figure for one session.

    Panels: (1) full session force trace with target overlay,
    (2) signed tracking error per trial, (3) per-trial MAE bar chart,
    (4) error distribution by condition, (5) baseline calibration stability,
    (6) summary statistics text.

    Parameters
    ----------
    df : pd.DataFrame
        Session dataframe as returned by :func:`load_session`.
    csv_path : str
        Original CSV path, used for the figure title.

    Returns
    -------
    matplotlib.figure.Figure
        The completed figure (not yet saved or shown).
    """
    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    fig.patch.set_facecolor("#0e0e1a")

    trial_stats = compute_trial_stats(df)
    baseline_cal = compute_baseline_cal(df)
    tracking = df[df["phase"] == "tracking"].copy()
    unit = df.attrs.get("signal_unit", "N")

    _plot_full_trace(axes[0, 0], df, unit)
    _plot_error_timeseries(axes[0, 1], tracking, unit)
    _plot_trial_mae_bars(axes[1, 0], trial_stats, unit)
    _plot_error_distribution(axes[1, 1], tracking, trial_stats, unit)
    _plot_baseline_stability(axes[2, 0], baseline_cal, unit)
    _plot_summary_text(axes[2, 1], df, trial_stats, baseline_cal, csv_path)

    fig.suptitle(
        f"Session Summary — {Path(csv_path).stem}",
        color="white",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


def _style_ax(ax, title, xlabel="", ylabel=""):
    """Apply dark-theme styling to an axes."""
    ax.set_facecolor("#1a1a2e")
    ax.set_title(title, color="white", fontsize=11, fontweight="bold", pad=8)
    ax.set_xlabel(xlabel, color="#aaaaaa", fontsize=9)
    ax.set_ylabel(ylabel, color="#aaaaaa", fontsize=9)
    ax.tick_params(colors="#aaaaaa", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#333333")
    ax.grid(True, alpha=0.15, color="white")


# -- Panel 1: Full session force trace + target ----------------------------


def _plot_full_trace(ax, df, unit="N"):
    _style_ax(ax, "Full Session Trace", "Session time (s)", f"Breathing signal ({unit})")

    trials = sorted(df["trial_num"].dropna().unique())

    # Phase background shading
    labeled_trials = set(trials[::max(1, int(np.ceil(len(trials) / 12)))])
    for trial_num in trials:
        for phase_name, color in PHASE_COLORS.items():
            mask = (df["trial_num"] == trial_num) & (df["phase"] == phase_name)
            subset = df[mask]
            if subset.empty:
                continue
            t0 = subset["session_time"].iloc[0]
            t1 = subset["session_time"].iloc[-1]
            ax.axvspan(t0, t1, color=color, alpha=0.4)

    # Actual breathing trace
    valid = df.dropna(subset=["force_n"])
    ax.plot(
        valid["session_time"],
        valid["force_n"],
        color=FORCE_COLOR,
        linewidth=0.6,
        alpha=0.85,
        label="Breathing",
    )

    # Target overlay (tracking only)
    target_data = df[(df["phase"] == "tracking") & df["target_force"].notna()]
    if not target_data.empty:
        ax.plot(
            target_data["session_time"],
            target_data["target_force"],
            color=TARGET_COLOR,
            linewidth=1.0,
            linestyle="--",
            alpha=0.8,
            label="Target",
        )

    ax.legend(
        loc="upper right", fontsize=8, facecolor="#1a1a2e", edgecolor="#333333", labelcolor="white"
    )

    # Trial boundary lines + labels (placed after data so ylim is set)
    ymin, ymax = ax.get_ylim()
    for trial_num in trials:
        trial_data = df[df["trial_num"] == trial_num]
        if trial_data.empty:
            continue
        t0 = trial_data["session_time"].iloc[0]
        ax.axvline(t0, color="#555555", linewidth=0.5, linestyle="--")
        if trial_num not in labeled_trials:
            continue
        cond = (
            trial_data["condition"].dropna().iloc[0]
            if trial_data["condition"].notna().any()
            else ""
        )
        cond_short = CONDITION_SHORT.get(
            cond, cond[:2].upper() if isinstance(cond, str) and cond else "??"
        )
        gain = (
            trial_data["feedback_gain"].iloc[0] if "feedback_gain" in trial_data.columns else 1.0
        )
        gain_str = f" g={gain}" if pd.notna(gain) and gain != 1.0 else ""
        ax.text(
            t0 + 0.3,
            ymax - (ymax - ymin) * 0.03,
            "Cal" if trial_num == 0 else f"T{int(trial_num)} {cond_short}{gain_str}",
            color="#aaaaaa",
            fontsize=7,
            va="top",
            fontweight="bold",
        )


# -- Panel 2: Signed tracking error per trial -----------------------------


def _plot_error_timeseries(ax, tracking, unit="N"):
    _style_ax(ax, "Tracking Error Over Time", "Time in phase (s)", f"Error ({unit})")

    if tracking.empty:
        ax.text(
            0.5,
            0.5,
            "No tracking data",
            transform=ax.transAxes,
            color="#666666",
            ha="center",
            va="center",
            fontsize=12,
        )
        return

    ax.axhline(0, color=ZERO_LINE_COLOR, linewidth=1.0)
    if unit == "N":
        ax.axhline(1.0, color=ERROR_POS_COLOR, linewidth=0.7, linestyle=":", alpha=0.5)
        ax.axhline(-1.0, color=ERROR_POS_COLOR, linewidth=0.7, linestyle=":", alpha=0.5)

    trials = sorted(tracking["trial_num"].dropna().unique())
    seen = set()

    for trial_num in trials:
        t_data = tracking[tracking["trial_num"] == trial_num]
        cond = t_data["condition"].iloc[0]
        # Show gain in label when perturbation is active
        gain = t_data["feedback_gain"].iloc[0] if "feedback_gain" in t_data.columns else 1.0
        gain_str = f" g={gain}" if pd.notna(gain) and gain != 1.0 else ""
        ax.plot(
            t_data["timestamp"],
            t_data["error"],
            color=CONDITION_COLORS.get(cond, "#999999"),
            linewidth=0.7,
            alpha=0.8,
            label=f"{cond.replace('_', ' ')}{gain_str}" if cond not in seen else "_nolegend_",
        )
        seen.add(cond)

    ax.legend(
        loc="upper right",
        fontsize=7,
        facecolor="#1a1a2e",
        edgecolor="#333333",
        labelcolor="white",
        ncol=2,
    )


# -- Panel 3: Per-trial MAE bar chart -------------------------------------


def _plot_trial_mae_bars(ax, trial_stats, unit="N"):
    _style_ax(ax, "Per-Trial Mean Absolute Error", "Trial", f"MAE ({unit})")

    if trial_stats.empty:
        ax.text(
            0.5,
            0.5,
            "No tracking data",
            transform=ax.transAxes,
            color="#666666",
            ha="center",
            va="center",
            fontsize=12,
        )
        return

    trials = trial_stats["trial_num"].values
    mae_vals = trial_stats["mae"].values
    colors = [CONDITION_COLORS.get(c, "#999999") for c in trial_stats["condition"]]

    ax.bar(
        range(len(trials)), mae_vals, color=colors, alpha=0.85, edgecolor="white", linewidth=0.3
    )
    positions = range(0, len(trials), max(1, int(np.ceil(len(trials) / 12))))
    ax.set_xticks(positions)
    ax.set_xticklabels([f"T{int(trials[i])}" for i in positions])

    # Overall mean line
    overall_mae = mae_vals.mean()
    ax.axhline(overall_mae, color="white", linewidth=0.8, linestyle="--", alpha=0.6)
    ax.text(
        len(trials) - 0.5,
        overall_mae + 0.02,
        f"mean={overall_mae:.2f}",
        color="white",
        fontsize=7,
        ha="right",
        va="bottom",
    )

    # Legend for conditions
    unique_conds = trial_stats["condition"].unique()
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=CONDITION_COLORS.get(c, "#999")) for c in unique_conds
    ]
    labels = [c.replace("_", " ") for c in unique_conds]
    ax.legend(
        handles,
        labels,
        loc="upper right",
        fontsize=8,
        facecolor="#1a1a2e",
        edgecolor="#333333",
        labelcolor="white",
    )


# -- Panel 4: Error distribution by condition (box plot) -------------------


def _plot_error_distribution(ax, tracking, trial_stats, unit="N"):
    _style_ax(ax, "Error Distribution by Condition", "", f"|Error| ({unit})")

    if tracking.empty:
        ax.text(
            0.5,
            0.5,
            "No tracking data",
            transform=ax.transAxes,
            color="#666666",
            ha="center",
            va="center",
            fontsize=12,
        )
        return

    conditions = sorted(tracking["condition"].dropna().unique())
    box_data = []
    positions = []
    colors = []

    for i, cond in enumerate(conditions):
        cond_errors = tracking[tracking["condition"] == cond]["error"].dropna().abs()
        if not cond_errors.empty:
            box_data.append(cond_errors.values)
            positions.append(i)
            colors.append(CONDITION_COLORS.get(cond, "#999999"))

    if box_data:
        bp = ax.boxplot(
            box_data, positions=positions, widths=0.5, patch_artist=True, showfliers=False
        )

        for patch, color in zip(bp["boxes"], colors, strict=False):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)
            patch.set_edgecolor("white")
        for element in ("whiskers", "caps", "medians"):
            for line in bp[element]:
                line.set_color("white")
                line.set_alpha(0.8)

        # Overlay per-trial means as scatter
        if not trial_stats.empty:
            for i, cond in enumerate(conditions):
                cond_stats = trial_stats[trial_stats["condition"] == cond]
                if not cond_stats.empty:
                    jitter = np.random.default_rng(42).uniform(-0.1, 0.1, len(cond_stats))
                    ax.scatter(
                        i + jitter,
                        cond_stats["mae"],
                        color="white",
                        s=30,
                        zorder=5,
                        edgecolors="none",
                        alpha=0.8,
                        label="Trial MAE" if i == 0 else "",
                    )

    ax.set_xticks(range(len(conditions)))
    ax.set_xticklabels([c.replace("_no_feedback", "\nno feedback") for c in conditions], fontsize=9)

    if box_data:
        ax.legend(
            loc="upper right",
            fontsize=8,
            facecolor="#1a1a2e",
            edgecolor="#333333",
            labelcolor="white",
        )


# -- Panel 5: Baseline calibration stability -------------------------------


def _plot_baseline_stability(ax, baseline_cal, unit="N"):
    _style_ax(ax, "Baseline Calibration Stability", "Trial", f"Breathing signal ({unit})")

    if baseline_cal.empty:
        ax.text(
            0.5,
            0.5,
            "No baseline data",
            transform=ax.transAxes,
            color="#666666",
            ha="center",
            va="center",
            fontsize=12,
        )
        return

    trials = baseline_cal["trial_num"].values
    centers = baseline_cal["center"].values
    amplitudes = baseline_cal["amplitude"].values
    colors = [CONDITION_COLORS.get(c, "#999") for c in baseline_cal["condition"]]

    # Error bars: center ± amplitude
    for i, (_t, c, a, col) in enumerate(zip(trials, centers, amplitudes, colors, strict=False)):
        ax.errorbar(
            i,
            c,
            yerr=a,
            fmt="o",
            color=col,
            markersize=8,
            capsize=6,
            capthick=1.5,
            elinewidth=1.5,
            markeredgecolor="white",
            markeredgewidth=0.5,
        )

    # Connect centers with a line to show drift
    ax.plot(range(len(trials)), centers, color="white", linewidth=0.8, alpha=0.4, linestyle="--")

    positions = range(0, len(trials), max(1, int(np.ceil(len(trials) / 12))))
    ax.set_xticks(positions)
    ax.set_xticklabels([f"T{int(trials[i])}" for i in positions])

    # Legend
    unique_conds = baseline_cal["condition"].unique()
    handles = [
        plt.Line2D(
            [0], [0], marker="o", color=CONDITION_COLORS.get(c, "#999"), linestyle="", markersize=8
        )
        for c in unique_conds
    ]
    labels = [c.replace("_", " ") for c in unique_conds]
    ax.legend(
        handles,
        labels,
        loc="upper right",
        fontsize=8,
        facecolor="#1a1a2e",
        edgecolor="#333333",
        labelcolor="white",
    )


# -- Panel 6: Summary statistics text panel --------------------------------


def _plot_summary_text(ax, df, trial_stats, baseline_cal, csv_path):
    ax.set_facecolor("#1a1a2e")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#333333")
    ax.set_title("Summary Statistics", color="white", fontsize=11, fontweight="bold", pad=8)

    tracking = df[df["phase"] == "tracking"]
    unit = df.attrs.get("signal_unit", "N")
    lines = []

    # Session info
    lines.append(f"File: {Path(csv_path).name}")
    n_trials = int(df.loc[df["trial_num"] > 0, "trial_num"].nunique())
    lines.append(f"Trials: {n_trials} | Samples: {len(df)} | Tracking: {len(tracking)}")
    if df.attrs.get("source_format") == "XDF":
        lines.append("XDF targets/errors reconstructed at sample times.")
        lines.append("CSV display-frame statistics may differ.")
    lines.append("")

    # Overall performance
    if not trial_stats.empty:
        overall_mae = trial_stats["mae"].mean()
        overall_rmse = trial_stats["rmse"].mean()
        best_idx = trial_stats["mae"].idxmin()
        worst_idx = trial_stats["mae"].idxmax()
        best = trial_stats.loc[best_idx]
        worst = trial_stats.loc[worst_idx]

        lines.append(f"Overall MAE: {overall_mae:.3f} {unit}; RMSE: {overall_rmse:.3f} {unit}")
        lines.append(f"Best: T{int(best['trial_num'])} ({best['mae']:.3f} {unit}); "
                     f"worst: T{int(worst['trial_num'])} ({worst['mae']:.3f} {unit})")
        lines.append("")

        # Per-condition
        for cond in sorted(trial_stats["condition"].unique()):
            cond_stats = trial_stats[trial_stats["condition"] == cond]
            c_mae = cond_stats["mae"].mean()
            c_sd = cond_stats["mae"].std()
            c_rmse = cond_stats["rmse"].mean()
            label = cond.replace("_", " ")
            # Show gain if present
            cond_tracking = tracking[tracking["condition"] == cond]
            if "feedback_gain" in cond_tracking.columns:
                gains = cond_tracking["feedback_gain"].dropna()
                gain = gains.iloc[0] if not gains.empty else 1.0
                gain_str = f" (gain={gain})" if gain != 1.0 else ""
            else:
                gain_str = ""
            lines.append(f"{label}{gain_str}: MAE {c_mae:.3f} +/- {c_sd:.3f}; RMSE {c_rmse:.3f} {unit}")
        lines.append("")

    # Baseline calibration
    if not baseline_cal.empty:
        centers = baseline_cal["center"].values
        amps = baseline_cal["amplitude"].values
        lines.append(
            f"Baseline center: {centers.mean():.2f} {unit} "
            f"(range {centers.min():.2f}-{centers.max():.2f})"
        )
        lines.append(
            f"Baseline amplitude: {amps.mean():.2f} {unit} (range {amps.min():.2f}-{amps.max():.2f})"
        )

    text = "\n".join(lines)
    ax.text(
        0.05,
        0.95,
        text,
        transform=ax.transAxes,
        color="white",
        fontsize=8.5,
        fontfamily="monospace",
        verticalalignment="top",
        linespacing=1.05,
    )


# -- CLI -------------------------------------------------------------------


def main() -> None:
    """CLI entry point: parse arguments and generate summary figures.

    Processes session CSV or XDF files, saving each as
    ``{input_stem}_summary.png`` alongside the original.
    """
    parser = argparse.ArgumentParser(
        description="Generate a 6-panel summary figure from a Respyra session CSV or XDF.",
    )
    parser.add_argument(
        "session_path",
        nargs="+",
        help="Path(s) to session .csv or Respyra .xdf file(s).",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Save PNG without displaying interactively.",
    )
    args = parser.parse_args()

    failed = False
    for csv_path in args.session_path:
        if not os.path.isfile(csv_path):
            print(f"File not found: {csv_path}", file=sys.stderr)
            failed = True
            continue

        print(f"Loading {csv_path}...")
        try:
            df = load_session(csv_path)
        except (ValueError, OSError, ImportError, KeyError, TypeError) as exc:
            print(f"Cannot load {csv_path}: {exc}", file=sys.stderr)
            failed = True
            continue

        print(
            f"  {len(df)} rows, "
            f"{df.loc[df['trial_num'] > 0, 'trial_num'].nunique()} trials, "
            f"phases: {sorted(df['phase'].dropna().unique())}"
        )

        fig = plot_session(df, csv_path)

        out_path = str(Path(csv_path).with_suffix("")) + "_summary.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        print(f"  Saved: {out_path}")

        if not args.no_show:
            plt.show()
        else:
            plt.close(fig)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
