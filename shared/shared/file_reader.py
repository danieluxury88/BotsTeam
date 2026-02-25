"""Local file reader for personal bots.

Reads markdown notes, task lists, and CSV habit logs from the local filesystem.
Analogous to git_reader.py but for file-based personal data sources.
"""

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


@dataclass
class FileEntry:
    """A single file read from disk."""
    path: Path
    filename: str
    modified: datetime
    content: str
    word_count: int = 0

    def __post_init__(self):
        if not self.word_count:
            self.word_count = len(self.content.split())


@dataclass
class FileReadResult:
    """Result of reading one or more files."""
    entries: list[FileEntry] = field(default_factory=list)
    total_files: int = 0
    date_range: tuple[datetime, datetime] | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def total_words(self) -> int:
        return sum(e.word_count for e in self.entries)

    @property
    def is_empty(self) -> bool:
        return len(self.entries) == 0


def read_markdown_files(
    directory: Path | str,
    since: date | None = None,
    until: date | None = None,
    max_files: int = 50,
) -> FileReadResult:
    """
    Read .md files from a directory, sorted newest-first.

    Args:
        directory: Path to directory containing markdown files
        since: Only include files modified on or after this date
        until: Only include files modified on or before this date
        max_files: Maximum number of files to read

    Returns:
        FileReadResult with all matching entries
    """
    directory = Path(directory)
    result = FileReadResult()

    if not directory.exists():
        result.errors.append(f"Directory does not exist: {directory}")
        return result

    if not directory.is_dir():
        result.errors.append(f"Path is not a directory: {directory}")
        return result

    # Collect all .md files
    md_files = sorted(directory.glob("**/*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    result.total_files = len(md_files)

    for path in md_files:
        if len(result.entries) >= max_files:
            break

        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)

            # Apply date filters
            if since and mtime.date() < since:
                continue
            if until and mtime.date() > until:
                continue

            content = path.read_text(encoding="utf-8", errors="replace")
            result.entries.append(FileEntry(
                path=path,
                filename=path.name,
                modified=mtime,
                content=content,
            ))
        except Exception as e:
            result.errors.append(f"Could not read {path.name}: {e}")

    if result.entries:
        dates = [e.modified for e in result.entries]
        result.date_range = (min(dates), max(dates))

    return result


def read_task_file(path: Path | str) -> FileReadResult:
    """
    Read a task list file or directory.

    Supports:
    - Markdown checkboxes: - [ ] task / - [x] done
    - todo.txt format (one task per line, priority codes like (A))
    - Plain text (one item per line)
    - If path is a directory, reads all .md files in it

    Returns:
        FileReadResult with the task content
    """
    path = Path(path)
    result = FileReadResult()

    if path.is_dir():
        return read_markdown_files(path)

    if not path.exists():
        result.errors.append(f"Task file does not exist: {path}")
        return result

    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        content = path.read_text(encoding="utf-8", errors="replace")
        result.entries.append(FileEntry(
            path=path,
            filename=path.name,
            modified=mtime,
            content=content,
        ))
        result.total_files = 1
        result.date_range = (mtime, mtime)
    except Exception as e:
        result.errors.append(f"Could not read {path}: {e}")

    return result


def read_habit_file(path: Path | str) -> FileReadResult:
    """
    Read a habit tracking file.

    Supports:
    - CSV files: first column is date, remaining columns are habit names
    - Markdown files: tables or daily logs

    Returns:
        FileReadResult with the habit content formatted for LLM consumption
    """
    path = Path(path)
    result = FileReadResult()

    if not path.exists():
        result.errors.append(f"Habit file does not exist: {path}")
        return result

    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime)

        if path.suffix.lower() == ".csv":
            content = _format_csv_for_llm(path)
        else:
            content = path.read_text(encoding="utf-8", errors="replace")

        result.entries.append(FileEntry(
            path=path,
            filename=path.name,
            modified=mtime,
            content=content,
        ))
        result.total_files = 1
        result.date_range = (mtime, mtime)
    except Exception as e:
        result.errors.append(f"Could not read {path}: {e}")

    return result


def _format_csv_for_llm(path: Path) -> str:
    """Convert a CSV habit log to a readable text format for the LLM."""
    lines = ["Habit tracking data:\n"]
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return "No habit data found."

        headers = list(rows[0].keys())
        lines.append(f"Habits tracked: {', '.join(headers[1:])}")
        lines.append(f"Total days logged: {len(rows)}\n")

        # Show recent rows (last 30)
        recent = rows[-30:]
        lines.append("Recent entries:")
        for row in recent:
            parts = [f"{k}: {v}" for k, v in row.items() if v.strip()]
            lines.append("  " + " | ".join(parts))

    except Exception as e:
        return f"Could not parse CSV: {e}"

    return "\n".join(lines)


def format_files_for_llm(
    entries: list[FileEntry],
    max_chars: int = 12000,
    include_filename: bool = True,
) -> str:
    """
    Format file entries into a single text block suitable for LLM prompts.

    Respects max_chars by truncating older entries first (newest are kept).

    Args:
        entries: List of FileEntry objects (sorted newest-first)
        max_chars: Maximum total character count
        include_filename: Whether to include filename headers

    Returns:
        Formatted text string for the LLM
    """
    if not entries:
        return "(no content)"

    sections = []
    total_chars = 0

    for entry in entries:
        header = f"\n--- {entry.filename} ({entry.modified.strftime('%Y-%m-%d')}) ---\n" if include_filename else "\n"
        section = header + entry.content.strip() + "\n"

        if total_chars + len(section) > max_chars:
            # Try to fit a truncated version
            remaining = max_chars - total_chars - len(header) - 50
            if remaining > 200:
                section = header + entry.content[:remaining].strip() + "\n...(truncated)"
                sections.append(section)
            break

        sections.append(section)
        total_chars += len(section)

    return "\n".join(sections).strip()
