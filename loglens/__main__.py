import argparse
from pathlib import Path

from loglens.analyze import analyze
from loglens.report import render


def top_count(value):
    count = int(value)
    if not 1 <= count <= 100:
        raise argparse.ArgumentTypeError("Choose a number between 1 and 100")
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyze Nginx combined logs locally.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    command = subcommands.add_parser("analyze", help="Build an HTML report")
    command.add_argument("input", type=Path)
    command.add_argument("--output", type=Path, default=Path("output/report.html"))
    command.add_argument("--top", type=top_count, default=10)
    args = parser.parse_args(argv)
    try:
        with args.input.open(encoding="utf-8", errors="replace") as stream:
            summary = analyze(stream)
        if not summary.valid:
            parser.exit(
                1, f"No valid combined-log entries found; skipped {summary.skipped} lines.\n"
            )
        report = render(summary, args.top)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as file:
            file.write(report)
    except FileExistsError:
        parser.exit(1, "Output already exists. Choose a new path; nothing was overwritten.\n")
    except (OSError, ValueError):
        parser.exit(
            1, "Could not analyze input or save output. Check paths, format, and file size.\n"
        )
    print(f"Report: {args.output} ({summary.valid} requests, {summary.skipped} skipped lines)")


if __name__ == "__main__":
    main()
