import sys
import threading
import types

import numpy as np
import pandas as pd
import pytest

from messgraph import progress
from messgraph.progress import Cancelled, Job


def test_sections_nest_and_never_go_back():
    job = Job("a")
    with progress.track(job):
        with progress.section(0.0, 0.5, "lesen"):
            progress.step(0.5)
            assert job.fraction == pytest.approx(0.25) and job.text == "lesen" and not job.indeterminate
            with progress.section(0.5, 1.0):
                progress.step(0.5)
                assert job.fraction == pytest.approx(0.375)
        assert job.fraction == pytest.approx(0.5)
        progress.busy("asammdf")
        assert job.indeterminate and job.text == "asammdf"
        progress.step(0.1)
        assert job.fraction == pytest.approx(0.5)          # nie rückwärts
    assert job.done and progress.current() is None
    progress.step(0.9)  # ohne Job wirkungslos


def test_cancel_raises_at_next_report_and_overall():
    job = Job("a")
    job.cancelled = True
    with pytest.raises(Cancelled), progress.track(job):
        progress.step(0.1)
    assert progress.overall([Job("x"), job]) == pytest.approx(0.5)
    assert progress.overall([]) == 0.0
    assert issubclass(Cancelled, Exception) and progress.thousands(1234567) == "1.234.567"


def test_job_is_bound_per_thread():
    job, seen = Job("a"), []
    with progress.track(job):
        t = threading.Thread(target=lambda: seen.append(progress.current()))
        t.start()
        t.join()
    assert seen == [None]


def fake_pyarrow(monkeypatch, df, batch_rows, on_batch=None):
    class Table:
        def __init__(self, frame):
            self.frame = frame

        def to_pandas(self):
            return self.frame

        @staticmethod
        def from_batches(batches, schema=None):
            return Table(pd.concat([b.frame for b in batches], ignore_index=True))

    class Batch:
        def __init__(self, frame):
            self.frame, self.num_rows = frame, len(frame)

    class ParquetFile:
        def __init__(self, path):
            self.metadata = types.SimpleNamespace(num_rows=len(df))
            self.schema_arrow = None

        def iter_batches(self, batch_size):
            for start in range(0, len(df), batch_rows):
                if on_batch:
                    on_batch(start)
                yield Batch(df.iloc[start:start + batch_rows])

        def read(self):
            return Table(df)

    pa = types.ModuleType("pyarrow")
    pq = types.ModuleType("pyarrow.parquet")
    pq.ParquetFile = ParquetFile
    pa.parquet, pa.Table = pq, Table
    monkeypatch.setitem(sys.modules, "pyarrow", pa)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", pq)


def test_parquet_reads_in_batches_with_progress(tmp_path, monkeypatch):
    from messgraph.loaders import load_file
    n = 10_000
    df = pd.DataFrame({"time": np.arange(n) * 0.01, "v": np.arange(n, dtype=float)})
    seen = []
    job = Job("a.parquet")
    fake_pyarrow(monkeypatch, df, 1000, on_batch=lambda start: seen.append((job.fraction, job.text)))
    p = tmp_path / "a.parquet"
    p.write_bytes(b"x")
    with progress.track(job):
        dataset = load_file(str(p))
    assert dataset.channels[0].y.tolist() == df["v"].tolist()       # Blöcke korrekt zusammengesetzt
    assert len(seen) == 10 and seen[-1][0] == pytest.approx(0.54)   # 9 von 10 Blöcken im Abschnitt 0..0.6
    assert "9.000 von 10.000 Zeilen" in seen[-1][1]
    assert job.fraction == pytest.approx(1.0) and job.done


def test_parquet_cancel_stops_reading(tmp_path, monkeypatch):
    from messgraph.loaders import load_file
    df = pd.DataFrame({"time": np.arange(5000) * 0.01, "v": np.ones(5000)})
    job = Job("a.parquet")
    calls = []

    def batch(start):
        calls.append(start)
        if start == 2000:
            job.cancelled = True
    fake_pyarrow(monkeypatch, df, 1000, on_batch=batch)
    p = tmp_path / "a.parquet"
    p.write_bytes(b"x")
    with pytest.raises(Cancelled), progress.track(job):
        load_file(str(p))
    assert calls == [0, 1000, 2000]


def test_channel_cancel_leaves_channel_unloaded():
    from messgraph.data_model import Channel
    job = Job("k")

    def loader():
        job.cancelled = True        # Abbruch während asammdf liest
        return np.arange(5.0), np.arange(5.0), "V"
    ch = Channel(name="k", source="m.mf4", loader=loader)
    with pytest.raises(Cancelled), progress.track(job):
        ch.load()
    assert not ch.loaded
    ch.load()                        # ohne Job: normal nachladbar
    assert ch.loaded and ch.unit == "V"


def test_session_cancel_closes_loaded_files(tmp_path, monkeypatch):
    from messgraph import session
    from messgraph.data_model import Dataset
    job, closed = Job("Ansicht"), []
    files = []
    for name in ("a.parquet", "b.parquet"):
        (tmp_path / name).write_bytes(b"x")
        files.append({"path": str(tmp_path / name)})

    def fake_load(path, options=None):
        job.cancelled = True
        return Dataset(path=path, closer=lambda: closed.append(path))
    monkeypatch.setattr(session, "load_file", fake_load)
    with pytest.raises(Cancelled), progress.track(job):
        session.open_session({"files": files, "graphs": []}, None)
    assert closed == [str(tmp_path / "a.parquet")]
