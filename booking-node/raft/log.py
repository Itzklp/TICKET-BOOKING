"""Simple in-memory Raft log.

In production systems, this should be replaced with a persistent
Write-Ahead Log (WAL) or durable storage mechanism.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Generator


@dataclass
class LogEntry:
    """Represents a single Raft log entry."""
    index: int
    term: int
    command: bytes


class Log:
    """In-memory log storage for Raft nodes."""

    def __init__(self):
        # Dictionary mapping log index → LogEntry
        self._entries: Dict[int, LogEntry] = {}
        self.last_index: int = 0

    # ------------------------------------------------------------------
    # Log Operations
    # ------------------------------------------------------------------
    def append(self, entry: LogEntry) -> None:
        """Append a new log entry."""
        self._entries[entry.index] = entry
        self.last_index = max(self.last_index, entry.index)

    def get(self, index: int) -> Optional[LogEntry]:
        """Get a log entry by index."""
        return self._entries.get(index)

    def entries_from(self, index: int) -> Generator[LogEntry, None, None]:
        """Iterate over log entries starting from a given index."""
        i = index
        while i <= self.last_index:
            yield self._entries[i]
            i += 1
