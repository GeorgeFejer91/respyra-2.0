"""LSL selection controls in the existing participant/session startup dialog."""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor

from mpi.event_markers import run_marked_participant_dialog
from mpi.lsl_force import (
    LSLForceError, LSLForceSource, connect_force_source, load_force_selection,
    open_force_source, save_force_selection, scan_force_streams,
)


def run_source_setup(cfg, markers):
    """Return participant values and a live, validated source; remember accepted input."""
    from PyQt6 import QtCore, QtWidgets

    source = None
    pending = None
    timer = None
    values = None
    handed_off = False
    fatal = None
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="respyra-lsl-setup")

    def configure(dialog, publish):
        nonlocal timer, pending, source, fatal
        status = QtWidgets.QLabel("No breathing input selected. Use Add LSL Stream.")
        status.setWordWrap(True)
        add = QtWidgets.QPushButton("Add LSL Stream…")
        use = QtWidgets.QPushButton("Use Selected Stream")
        table = QtWidgets.QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Stream", "Type", "Input", "Compatibility"])
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.setMinimumWidth(700)
        table.hide()
        use.hide()
        candidates = []
        row = dialog.irow
        dialog.layout.addWidget(QtWidgets.QLabel("Breathing input"), row, 0)
        dialog.layout.addWidget(status, row, 1)
        dialog.layout.addWidget(add, row + 1, 0)
        dialog.layout.addWidget(use, row + 1, 1)
        dialog.layout.addWidget(table, row + 2, 0, 1, 2)
        dialog.irow += 3
        dialog.okBtn.setText("Start Experiment")
        original_validate = dialog.validate

        def show_status(message):
            current = (f"Current input: {source.stream_name} — Force (N)\n"
                       if source is not None else "No accepted breathing input.\n")
            status.setText(current + message)

        def guarded(action):
            def callback(*_args):
                nonlocal fatal
                try:
                    action()
                except Exception as exc:
                    fatal = exc
                    publish("source.setup.failed", message=str(exc))
                    dialog.reject()
            return callback

        def selected():
            index = table.currentRow()
            return candidates[index] if 0 <= index < len(candidates) else None

        def validate():
            original_validate()
            dialog.okBtn.setEnabled(dialog.okBtn.isEnabled() and source is not None and pending is None)
            add.setEnabled(pending is None)
            candidate = selected()
            use.setEnabled(pending is None and candidate is not None and candidate.force_index is not None)

        dialog.validate = validate

        def submit(kind, action, identity=""):
            nonlocal pending
            pending = (executor.submit(action), kind, identity)
            validate()

        def begin_scan():
            publish("source.ui.add.clicked")
            table.show()
            use.show()
            show_status("Scanning available LSL streams…")
            publish("source.scan.started")
            submit("scan", scan_force_streams)

        def selection_changed():
            candidate = selected()
            if candidate is not None:
                publish("source.ui.selection.changed", source_id=candidate.info.source_id(),
                        stream_name=candidate.info.name(), compatible=candidate.force_index is not None)
            validate()

        def use_selected():
            candidate = selected()
            if candidate is None or candidate.force_index is None:
                return
            identity = candidate.info.source_id()
            publish("source.ui.use.clicked", source_id=identity, stream_name=candidate.info.name())
            publish("source.connection.started", source_id=identity, origin="selection")
            show_status("Checking channel metadata and live Force samples…")
            submit("selection", lambda: open_force_source(candidate.info), identity)

        def poll():
            nonlocal pending, source, candidates
            if source is not None:
                try:
                    source.get_all()  # keep the inlet current while the operator enters details
                except LSLForceError as exc:
                    source.stop()
                    source = None
                    publish("source.lost", message=str(exc))
                    publish("source.disconnected")
                    show_status(f"{exc}\nUse Add LSL Stream to reconnect.")
                    validate()
            if pending is None or not pending[0].done():
                return
            future, kind, identity = pending
            pending = None
            try:
                result = future.result()
                if kind == "selection":
                    try:
                        save_force_selection(result)
                    except Exception:
                        result.stop()
                        raise
            except Exception as exc:
                show_status(f"{exc}\nUse Add LSL Stream to scan or retry.")
                if kind == "scan":
                    publish("source.scan.failed", message=str(exc))
                else:
                    publish("source.connection.failed", source_id=identity, origin=kind, message=str(exc))
                validate()
                return
            if kind == "scan":
                candidates = result
                table.blockSignals(True)
                table.clearSelection()
                table.setCurrentCell(-1, -1)
                table.setRowCount(len(candidates))
                for index, candidate in enumerate(candidates):
                    labels = [candidate.info.name(), candidate.info.type(),
                              f"Force (N), channel {candidate.force_index + 1}" if candidate.force_index is not None else "—",
                              candidate.reason]
                    for column, label in enumerate(labels):
                        item = QtWidgets.QTableWidgetItem(label)
                        item.setToolTip(candidate.info.source_id())
                        table.setItem(index, column, item)
                table.blockSignals(False)
                eligible = sum(item.force_index is not None for item in candidates)
                show_status(f"Found {len(candidates)} streams; {eligible} compatible. Select a row and use it."
                               if eligible else "No compatible raw Force (N) stream. Start Vernier Stream Mini, then scan again.")
                publish("source.scan.completed", streams=[
                    {"source_id": item.info.source_id(), "stream_name": item.info.name(),
                     "stream_type": item.info.type(), "compatible": item.force_index is not None,
                     "reason": item.reason} for item in candidates
                ])
            else:
                previous, source = source, result
                if previous is not None:
                    previous.stop()
                    publish("source.disconnected")
                show_status("Ready for this experiment.")
                publish("source.connected", source_id=source.source_id, stream_name=source.stream_name,
                        force_channel_index=source.force_index)
                publish("source.connection.accepted", source_id=source.source_id, origin=kind)
                if kind == "selection":
                    publish("source.memory.saved", source_id=source.source_id, stream_name=source.stream_name)
            validate()

        add.clicked.connect(guarded(begin_scan))
        use.clicked.connect(guarded(use_selected))
        table.itemSelectionChanged.connect(guarded(selection_changed))
        timer = QtCore.QTimer(dialog)
        timer.timeout.connect(guarded(poll))
        timer.start(25)

        try:
            saved = load_force_selection()
        except LSLForceError as exc:
            saved = None
            show_status(str(exc))
            publish("source.memory.invalid", message=str(exc))
        if saved:
            publish("source.memory.loaded", source_id=saved["source_id"], stream_name=saved["stream_name"])
        identity = os.environ.get("RESPYRA_LSL_SOURCE_ID") or (saved["source_id"] if saved else None)
        if identity:
            origin = "environment" if os.environ.get("RESPYRA_LSL_SOURCE_ID") else "memory"
            show_status("Reconnecting the previously configured LSL source…")
            publish("source.connection.started", source_id=identity, origin=origin)
            submit(origin, lambda: connect_force_source(source_id=identity), identity)
        validate()

    try:
        values = run_marked_participant_dialog(cfg, markers, configure=configure)
        if fatal is not None:
            raise fatal
        if values is not None:
            if source is None:
                raise LSLForceError("No accepted LSL Force source; experiment cannot start")
            try:
                source.get_all()  # recheck health after participant entry
            except Exception as exc:
                markers.emit("source.lost", message=str(exc))
                raise
            handed_off = True
        return values, source if values is not None else None
    finally:
        active_error = sys.exc_info()[1]
        if timer is not None:
            timer.stop()
        executor.shutdown(wait=True, cancel_futures=True)
        to_close = []
        final_events = []
        if pending is not None and not pending[0].cancelled():
            future, kind, identity = pending
            if future.exception() is None and isinstance(future.result(), LSLForceSource):
                to_close.append(future.result())
        if pending is not None:
            _future, kind, identity = pending
            final_events.append(("source.scan.cancelled", {}) if kind == "scan" else (
                "source.connection.cancelled", {"source_id": identity, "origin": kind}))
        if not handed_off and source is not None:
            to_close.append(source)
            final_events.append(("source.disconnected", {}))
        cleanup_error = None
        for closing in to_close:
            try:
                closing.stop()
            except Exception as exc:
                cleanup_error = cleanup_error or exc
        for name, fields in final_events:
            try:
                markers.emit(name, **fields)
            except Exception as exc:
                cleanup_error = cleanup_error or exc
        if cleanup_error is not None and active_error is None:
            raise cleanup_error
