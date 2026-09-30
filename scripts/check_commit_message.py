#!/usr/bin/env python3
"""Reject co-author trailers without exposing the commit message."""
from pathlib import Path
import re
import sys


COAUTHOR = re.compile(r"^[ \t]*Co-Authored-By[ \t]*:", re.IGNORECASE)


def coauthor_lines(message: str) -> list[int]:
    return [number for number, line in enumerate(message.splitlines(), 1) if COAUTHOR.match(line)]


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_commit_message.py MESSAGE_FILE", file=sys.stderr)
        return 2
    try:
        message = Path(sys.argv[1]).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        print("Commit guard: cannot read the UTF-8 message file", file=sys.stderr)
        return 2
    if lines := coauthor_lines(message):
        print("Commit guard: remove co-author trailers on lines " + ", ".join(map(str, lines)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
