import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlsplit

QUOTED = r'"(?:[^"\\]|\\.)*"'
LINE = re.compile(
    rf'^\S+ \S+ \S+ \[(?P<date>[^\]]+)\] "(?P<request>(?:[^"\\]|\\.)*)" '
    rf"(?P<status>[1-5]\d{{2}}) (?P<size>\d+|-) {QUOTED} {QUOTED}\s*$"
)
MAX_LINE = 65536
MAX_KEYS = 50000


@dataclass
class Summary:
    valid: int = 0
    skipped: int = 0
    oversized: int = 0
    bytes_sent: int = 0
    statuses: Counter = field(default_factory=Counter)
    paths: Counter = field(default_factory=Counter)
    errors: Counter = field(default_factory=Counter)
    hours: Counter = field(default_factory=Counter)


def parse_line(line):
    match = LINE.fullmatch(line)
    if not match:
        raise ValueError("Not a combined access-log entry")
    # English month names are fixed by the log format, not the machine's locale.
    date = match["date"]
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    parts = date.split("/")
    if len(parts) != 3 or parts[1] not in months:
        raise ValueError("Invalid log timestamp")
    numeric_date = f"{parts[0]}/{months.index(parts[1]) + 1:02d}/{parts[2]}"
    timestamp = datetime.strptime(numeric_date, "%d/%m/%Y:%H:%M:%S %z").astimezone(UTC)
    request = match["request"].split()
    if len(request) != 3 or not request[2].startswith("HTTP/"):
        raise ValueError("Invalid HTTP request")
    target = request[1]
    if target == "*":
        path = "*"
    else:
        parsed = urlsplit(target)
        if not target.startswith("/") and parsed.scheme not in {"http", "https"}:
            raise ValueError("Unsupported request target")
        path = parsed.path or "/"
    return timestamp, path, int(match["status"]), int(match["size"]) if match["size"] != "-" else 0


def analyze(stream):
    result = Summary()
    while line := stream.readline(MAX_LINE + 1):
        if len(line) > MAX_LINE:
            while not line.endswith("\n"):
                line = stream.readline(MAX_LINE + 1)
                if not line:
                    break
            result.skipped += 1
            result.oversized += 1
            continue
        try:
            timestamp, path, status, size = parse_line(line)
        except ValueError:
            result.skipped += 1
            continue
        hour = timestamp.strftime("%Y-%m-%d %H:00 UTC")
        if (path not in result.paths and len(result.paths) >= MAX_KEYS) or (
            hour not in result.hours and len(result.hours) >= MAX_KEYS
        ):
            raise ValueError("Too many distinct paths or hours; analyze a smaller log file")
        result.valid += 1
        result.bytes_sent += size
        result.statuses[status] += 1
        result.paths[path] += 1
        result.hours[hour] += 1
        if status >= 400:
            result.errors[path] += 1
    return result
