import csv
import gzip
import json
import runpy
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from mpi import time_reference as timing
from mpi.bids_export import export_bids
from respyra.core.data_logger import DataLogger


def test_reference_probes_failure_freeze_dst_and_sample_order(monkeypatch, tmp_path):
    instant = datetime(2026, 10, 25, 0, 59, 59, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(timing.time, "time", lambda: instant)
    reference = timing.TimeReference(clock=lambda: 100.0)
    before = reference.fields(100.0)
    after = reference.fields(102.0)
    assert before["berlin_time"].endswith("+02:00")
    assert after["berlin_time"].endswith("+01:00")
    assert before["utc_time"] == "2026-10-25T00:59:59.000000+00:00"
    assert after["utc_time"] == "2026-10-25T01:00:01.000000+00:00"
    monkeypatch.setattr(timing.time, "time", lambda: instant + 3600)
    assert reference.fields(102.0) == after  # OS clock jumps cannot change a run.

    class Response:
        status = 200
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, _limit):
            return b'{"dateTime":"2026-10-25T00:59:59.1234567","timeZone":"UTC"}'

    calls = []
    def request(req, timeout):
        calls.append(req.full_url)
        assert timeout == 1.5 and req.full_url == timing.API_URL
        assert req.get_header("Cache-control") == "no-cache"
        return Response()
    monkeypatch.setattr(timing, "urlopen", request)
    stamps = iter([100, 100, 101, 101.4, 102, 102.2, 103, 103.6])
    online = timing.TimeReference(clock=lambda: next(stamps))
    online._probe()
    state = online.freeze()
    assert len(calls) == 3 and state["source"] == "timeapi.io"
    assert state["lsl_anchor_s"] == pytest.approx(102.1)
    assert state["round_trip_s"] == pytest.approx(.2)
    assert state["utc_anchor"] == "2026-10-25T00:59:59.123456+00:00"

    for body, headers in [(b'{}', {}), (b'not JSON', {}),
                          (Response().read(8193), {"Age": "60"}),
                          (Response().read(8193), {"Age": "NaN"})]:
        invalid = timing.TimeReference(clock=lambda: 100)
        response = Response()
        response.headers = headers
        response.read = lambda _limit, body=body: body
        monkeypatch.setattr(timing, "urlopen", lambda *_args, **_kwargs: response)
        invalid._probe()
        assert invalid.freeze()["source"] == "system"
        assert invalid.freeze()["api_status"] == "unavailable"

    entered, release = threading.Event(), threading.Event()
    def unavailable(*_args, **_kwargs):
        entered.set()
        release.wait(2)
        raise TimeoutError("offline")
    monkeypatch.setattr(timing, "urlopen", unavailable)
    offline = timing.TimeReference(clock=lambda: 100)
    offline.start()
    assert entered.wait(1)
    frozen = offline.freeze()  # Must return while HTTP is still blocked.
    assert frozen["source"] == "system" and not release.is_set()
    release.set()
    offline._worker.join(2)
    assert not offline._worker.is_alive() and offline.freeze() == frozen

    logger = timing.TimedCSVLogger(DataLogger(str(tmp_path / "samples.csv"),
        ["timestamp", "force_n", *timing.TIME_COLUMNS]), reference, sample_rows=True)
    source = SimpleNamespace(get_all=lambda: [(100.0, 1), (100.02, 2)])
    original = source.get_all
    with logger.observe_samples(source):
        source.get_all()  # An idle drain must not accumulate stale timestamps.
        for _stamp, value in source.get_all():
            logger.log_row(timestamp=0.1, force_n=value)
        with pytest.raises(ValueError, match="corresponding LSL"):
            logger.log_row(timestamp=.1, force_n=9)
    assert source.get_all is original
    logger.close()
    with (tmp_path / "samples.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [float(row["lsl_time_s"]) for row in rows] == [100, 100.02]
    assert [row["timestamp"] for row in rows] == ["0.1", "0.1"]
    assert json.loads((tmp_path / "samples.csv.json").read_text())["TimestampBasis"] == "accepted_sample"


def test_bids_absolute_times_share_the_synchronized_marker_clock(monkeypatch, tmp_path):
    reference = timing.TimeReference(clock=lambda: 100).freeze()
    def stream(identity, stamps, rows, kind="float32", rate="10"):
        return {"info": {"source_id": [identity], "channel_format": [kind],
                "channel_count": ["1"], "nominal_srate": [rate]},
                "time_stamps": stamps, "time_series": rows}
    raw = stream("raw", [110, 110.1], [[1], [2]])
    derived = stream("derived", [110, 110.1], [[0], [.5]])
    irregular = stream("counter", [110.05], [[2**53 + 1]], "int64", "0")
    markers = stream("respyra-events-test", [110.02], [[json.dumps({"event": "recording.started",
        "lsl_time": 100.02, "clock_reference": reference})]], "string", "0")
    shifted = timing.recorded_reference(markers)
    assert shifted["lsl_anchor_s"] == pytest.approx(110)
    monkeypatch.setattr("pyxdf.load_xdf", lambda *_a, **_k: ([raw, markers, derived, irregular], {}))
    directory = export_bids(tmp_path / "run.xdf", tmp_path, ("raw", "respyra-events-test", "derived"), "P002", "001")
    physio = next(directory.glob("*recording-raw_physio.tsv.gz"))
    metadata = json.loads(physio.with_suffix("").with_suffix(".json").read_text())
    with gzip.open(physio, "rt") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    columns = metadata["Columns"]
    assert columns[:2] == ["timestamp", "channel1"]
    assert float(rows[0][columns.index("utc_unix_s")]) == reference["unix_anchor_s"]
    assert float(rows[1][columns.index("lsl_time_s")]) == 110.1
    assert metadata["ClockReference"]["source"] == "system"
    assert metadata["TimeOriginBerlin"] == timing.iso_time(reference["unix_anchor_s"], timing.BERLIN)
    with next(directory.glob("*events.tsv")).open() as handle:
        event = next(csv.DictReader(handle, delimiter="\t"))
    assert event["utc_time"] == timing.timestamp_fields(shifted, 110.02)["utc_time"]
    table = next(directory.glob("*acq-lsl01*_beh.tsv"))
    with table.open() as handle:
        row = next(csv.DictReader(handle, delimiter="\t"))
    assert int(row["channel1"]) == 2**53 + 1
    assert float(row["lsl_time_s"]) == 110.05

    for item in (raw, derived, irregular, markers):
        item['info']['name'] = item['info']['source_id']
    export_csv = runpy.run_path(str(Path(__file__).parents[1] / 'scripts/xdf_to_csv.py'))['export']
    folder = export_csv(tmp_path / 'run.xdf')
    with next(folder.glob('*raw.csv')).open() as handle:
        sample = next(csv.DictReader(handle))
    assert sample['utc_time'] == timing.timestamp_fields(shifted, 110)['utc_time']
    assert sample['berlin_time'] == timing.timestamp_fields(shifted, 110)['berlin_time']
    assert sample['time_reference'] == 'system'
    assert len(list(folder.glob('*.json'))) == 4
    markers['time_series'] = [[json.dumps({'event': 'recording.started'})]]
    older = export_csv(tmp_path / 'old.xdf')
    with next(older.glob('*raw.csv')).open() as handle:
        sample = next(csv.DictReader(handle))
    assert list(sample) == ['lsl_time_s', 'ch1_value_1']
    assert not list(older.glob('*.json'))
