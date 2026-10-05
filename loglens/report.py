import json
from html import escape


def render_json(summary, top=10):
    """A versioned summary for scripts, with the same omissions as the HTML report."""
    return (
        json.dumps(
            {
                "schema_version": 1,
                "valid_requests": summary.valid,
                "skipped_lines": summary.skipped,
                "oversized_lines": summary.oversized,
                "response_bytes": summary.bytes_sent,
                "statuses": {str(key): value for key, value in sorted(summary.statuses.items())},
                "top_paths": [
                    {"path": path, "requests": count}
                    for path, count in summary.paths.most_common(top)
                ],
                "top_error_paths": [
                    {"path": path, "errors": count}
                    for path, count in summary.errors.most_common(top)
                ],
                "hours_utc": dict(sorted(summary.hours.items())),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


def table(title, headings, rows):
    header = "".join(f"<th scope='col'>{escape(str(value))}</th>" for value in headings)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>"
        for row in rows
    )
    if not body:
        body = f"<tr><td colspan='{len(headings)}'>No data</td></tr>"
    return (
        f"<section><h2>{escape(title)}</h2><table><thead><tr>{header}</tr></thead>"
        f"<tbody>{body}</tbody></table></section>"
    )


def render(summary, top=10):
    sections = [
        table("HTTP statuses", ("Status", "Requests"), sorted(summary.statuses.items())),
        table("Most requested paths", ("Path", "Requests"), summary.paths.most_common(top)),
        table("Paths with errors (4xx + 5xx)", ("Path", "Errors"), summary.errors.most_common(top)),
        table("Requests by hour (UTC)", ("Hour", "Requests"), sorted(summary.hours.items())),
    ]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy"
content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'">
<title>LogLens report</title>
<style>
body {{ font: 16px/1.6 system-ui, sans-serif; color: #223047; background: #f4f6f9; margin: 0; }}
main {{ max-width: 960px; margin: 40px auto; padding: 0 24px; }}
h1 {{ margin-bottom: 0; }} .subtitle {{ color: #536176; }}
.summary, section {{ background: white; border: 1px solid #dde3ec; border-radius: 8px;
padding: 20px; margin: 20px 0; overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #e6eaf0;
overflow-wrap: anywhere; }}
th {{ background: #f4f6f9; }} h2 {{ font-size: 20px; }}
</style></head><body><main>
<h1>LogLens</h1><p class="subtitle">Nginx combined access-log summary · generated locally</p>
<div class="summary"><strong>{summary.valid:,} valid requests</strong>
· {summary.skipped:,} skipped lines
({summary.oversized:,} oversized) · {summary.bytes_sent:,} response bytes</div>
{"".join(sections)}
<p class="subtitle">IP addresses, query strings, referrers, user agents, and raw lines are omitted.
Paths can still contain private information. Keep this report private. Hours are normalized to UTC;
missing hours are not filled with zeros. A '-' response size counts as zero.</p>
</main></body></html>
"""
