import gzip
import io
import json

import pytest

from loglens.__main__ import main
from loglens.analyze import analyze
from loglens.report import render_json


def log(path, status=200):
    return f'192.0.2.1 - - [05/Oct/2026:09:00:00 -0500] "GET {path} HTTP/1.1" {status} 10 "-" "Browser"\n'


def test_json_schema_privacy_and_top_limit():
    report = render_json(analyze(io.StringIO(log("/one?token=secret", 500) + log("/two"))), top=1)
    data = json.loads(report)
    assert data["schema_version"] == 1
    assert data["valid_requests"] == 2 and data["response_bytes"] == 20
    assert data["statuses"] == {"200": 1, "500": 1}
    assert data["top_paths"] == [{"path": "/one", "requests": 1}]
    assert data["top_error_paths"] == [{"path": "/one", "errors": 1}]
    assert data["hours_utc"] == {"2026-10-05 14:00 UTC": 2}
    assert all(value not in report for value in ["192.0.2.1", "secret", "Browser", "token"])


def test_empty_summary_is_valid_json():
    data = json.loads(render_json(analyze(io.StringIO(""))))
    assert data["top_paths"] == [] and data["statuses"] == {}


def test_gzip_json_cli_refuses_overwrite(tmp_path):
    source = tmp_path / "access.gz"
    source.write_bytes(gzip.compress(log("/jobs").encode()))
    output = tmp_path / "report.json"
    args = ["analyze", str(source), "--format", "json", "--output", str(output)]
    main(args)
    original = output.read_bytes()
    assert json.loads(original)["valid_requests"] == 1
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 1 and output.read_bytes() == original


def test_json_default_extension(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "access.txt"
    source.write_text(log("/jobs"), encoding="utf-8")
    main(["analyze", str(source), "--format", "json"])
    assert json.loads((tmp_path / "output/report.json").read_text())["valid_requests"] == 1
