import gzip
import io
from datetime import UTC, datetime
from pathlib import Path

import pytest

from loglens.__main__ import main
from loglens.analyze import MAX_LINE, analyze, parse_line
from loglens.report import render


def entry(path="/jobs?token=secret", status=200, date="05/Oct/2026:09:00:00 -0500", size="128"):
    return f'192.0.2.1 - - [{date}] "GET {path} HTTP/1.1" {status} {size} "-" "TestBrowser"\n'


def test_parser_strips_query_and_normalizes_time():
    when, path, status, size = parse_line(entry())
    assert when == datetime(2026, 10, 5, 14, tzinfo=UTC)
    assert (path, status, size) == ("/jobs", 200, 128)


@pytest.mark.parametrize(
    "line",
    ["broken", entry(status=999), entry(date="31/Feb/2026:09:00:00 +0000"), entry(path="bad")],
)
def test_invalid_entries(line):
    with pytest.raises(ValueError):
        parse_line(line)


def test_counts_and_privacy():
    summary = analyze(io.StringIO(entry() + entry(status=500) + "broken\n"))
    assert (summary.valid, summary.skipped, summary.bytes_sent) == (2, 1, 256)
    assert summary.paths == {"/jobs": 2}
    assert summary.errors == {"/jobs": 1}
    report = render(summary)
    assert "token" not in report and "192.0.2.1" not in report
    assert "TestBrowser" not in report and "broken" not in report


def test_html_escaped_and_no_remote_assets():
    report = render(analyze(io.StringIO(entry(path="/<script>alert(1)</script>"))))
    assert "<script>" not in report and "&lt;script&gt;" in report
    assert "default-src 'none'" in report


def test_oversized_line_is_counted_once():
    summary = analyze(io.StringIO("x" * (MAX_LINE * 3) + "\n" + entry()))
    assert (summary.valid, summary.skipped, summary.oversized) == (1, 1, 1)


def test_unknown_size_absolute_url_and_escaped_quotes():
    line = entry(path="https://example.com/jobs?q=secret#fragment", size="-")
    line = line.replace('"TestBrowser"', r'"Test\"Browser"')
    assert parse_line(line)[1:] == ("/jobs", 200, 0)


def test_hours_from_different_offsets_are_merged():
    summary = analyze(io.StringIO(entry() + entry(date="05/Oct/2026:14:00:00 +0000")))
    assert summary.hours == {"2026-10-05 14:00 UTC": 2}


def test_distinct_path_limit(monkeypatch):
    monkeypatch.setattr("loglens.analyze.MAX_KEYS", 1)
    with pytest.raises(ValueError, match="Too many"):
        analyze(io.StringIO(entry(path="/one") + entry(path="/two")))


def test_cli_sample_and_no_overwrite(tmp_path):
    sample = Path(__file__).parents[1] / "examples" / "access.txt"
    output = tmp_path / "report.html"
    main(["analyze", str(sample), "--output", str(output)])
    original = output.read_bytes()
    assert b"6 valid requests" in original
    with pytest.raises(SystemExit) as error:
        main(["analyze", str(sample), "--output", str(output)])
    assert error.value.code == 1
    assert output.read_bytes() == original


def test_cli_empty_input_does_not_create_report(tmp_path):
    output = tmp_path / "empty.html"
    with pytest.raises(SystemExit) as error:
        main(["analyze", __file__, "--output", str(output)])
    assert error.value.code == 1
    assert not output.exists()


def test_cli_gzip_matches_plain_report_and_keeps_input(tmp_path):
    text = entry() + entry(status=500) + "broken\n"
    plain = tmp_path / "access.txt"
    compressed = tmp_path / "access.log.gz"
    plain.write_text(text, encoding="utf-8")
    original = gzip.compress(text.encode("utf-8"))
    compressed.write_bytes(original)
    plain_report = tmp_path / "plain.html"
    gzip_report = tmp_path / "compressed.html"
    main(["analyze", str(plain), "--output", str(plain_report)])
    main(["analyze", str(compressed), "--output", str(gzip_report)])
    assert gzip_report.read_bytes() == plain_report.read_bytes()
    assert compressed.read_bytes() == original
    assert "secret" not in gzip_report.read_text(encoding="utf-8")


@pytest.mark.parametrize("payload", [b"not a gzip archive", gzip.compress(entry().encode())[:-8]])
def test_cli_bad_gzip_has_clear_error_and_no_partial_report(tmp_path, capsys, payload):
    compressed = tmp_path / "broken.gz"
    compressed.write_bytes(payload)
    output = tmp_path / "report.html"
    with pytest.raises(SystemExit) as error:
        main(["analyze", str(compressed), "--output", str(output)])
    assert error.value.code == 1
    assert "archive integrity" in capsys.readouterr().err
    assert not output.exists()


def test_cli_empty_gzip_does_not_create_report(tmp_path):
    compressed = tmp_path / "empty.gz"
    compressed.write_bytes(gzip.compress(b""))
    output = tmp_path / "report.html"
    with pytest.raises(SystemExit) as error:
        main(["analyze", str(compressed), "--output", str(output)])
    assert error.value.code == 1
    assert not output.exists()


def test_cli_gzip_keeps_oversized_line_limit(tmp_path):
    compressed = tmp_path / "access.GZ"
    text = "x" * (MAX_LINE * 3) + "\n" + entry()
    compressed.write_bytes(gzip.compress(text.encode("utf-8")))
    output = tmp_path / "report.html"
    main(["analyze", str(compressed), "--output", str(output)])
    report = output.read_text(encoding="utf-8")
    assert "1 valid requests" in report
    assert "x" * 100 not in report


@pytest.mark.parametrize("top", ["0", "101", "wrong"])
def test_cli_invalid_top(top):
    with pytest.raises(SystemExit) as error:
        main(["analyze", "missing", "--top", top])
    assert error.value.code == 2
