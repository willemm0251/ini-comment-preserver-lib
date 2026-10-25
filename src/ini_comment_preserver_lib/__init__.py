"""Package init: re-export public API from core."""

from .core import (
    INIFile,
    Section,
    Key,
    Comment,
    Blank,
    dump,
    loads,
    dumps,
)

__all__ = [
    "INIFile",
    "Section",
    "Key",
    "Comment",
    "Blank",
    "dump",
    "loads",
    "dumps",
]
