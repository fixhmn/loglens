# LogLens

[![Tests](https://github.com/fixhmn/loglens/actions/workflows/tests.yml/badge.svg)](https://github.com/fixhmn/loglens/actions/workflows/tests.yml)

A small local tool for answering basic questions about Nginx access logs: which paths get traffic, where errors happen, and how requests are distributed by hour. It reads the standard combined format and creates a standalone HTML report. No account, API, database, or runtime dependencies are needed.

## Try it

Python 3.11 or newer. From this folder:

```powershell
python -m loglens analyze examples/access.txt --output output/demo.html
```

Open `output/demo.html` in your browser. The sample is entirely synthetic: six requests and one deliberately malformed line. It is not production traffic. Using `.txt` lets the sample be tracked while real `.log` files remain ignored.

For your own combined log:

```powershell
python -m loglens analyze C:/private/access.log --top 20 --output output/report.html
```

Rotated gzip logs work directly too; `.gz` matching is case-insensitive:

```powershell
python -m loglens analyze C:/private/access.log.1.gz --output output/archive-report.html
```

The archive is streamed through the same parser, without unpacking it to disk or changing the input. Invalid or truncated gzip archives fail before a report is created. The existing per-line and distinct-key limits still apply to decompressed text. There is no total decompressed-size or runtime limit, so use trusted local files, not arbitrary uploaded archives.

Existing output files are never replaced. Choose a new output name to rerun. An input with no valid entries exits with an error instead of producing a misleading empty report.

## What's in the report

- Total valid requests, skipped lines, oversized lines, and response bytes
- Counts for each HTTP status
- Most requested paths and paths with the most 4xx/5xx responses
- Request counts per hour, normalized to UTC

Query strings and fragments are removed before paths are counted. IP addresses, referrers, user agents, and raw malformed lines never appear in the report. Paths can still contain names or IDs: this is not an anonymization tool. Keep real logs and generated reports private; don't commit them.

## Decisions and limits

The parser and aggregation are separate from HTML rendering and the CLI. HTML values are escaped; the report has no JavaScript, remote fonts, or external assets. Python's standard library is sufficient for this first version, so a template library would add a dependency without much benefit yet.

Input is read in bounded chunks, with a 65,536-character line limit. Oversized entries are skipped once, not counted as multiple entries. Counters store unique paths and hours; analysis stops beyond 50,000 of either, rather than growing indefinitely. This isn't a constant-memory analyzer.

Only combined-format logs are supported, including quoted escaped characters in referrer/user-agent fields. Plain text and gzip inputs are supported; custom formats, JSON logs, other compression formats, request timing, and live tailing aren't. Timezones come from each entry; hour rows include dates, and hours without traffic are omitted. A `-` response size counts as zero. Results describe the provided file, not necessarily a whole day or unique visitors.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

GitHub Actions runs tests and Ruff on Python 3.11 and 3.12. Next useful improvements: status filters and an optional JSON summary. Real Nginx integration hasn't been verified yet.
