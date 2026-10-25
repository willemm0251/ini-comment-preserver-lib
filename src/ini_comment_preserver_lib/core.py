"""Parse and emit INI files while preserving comments, key ordering, and inline whitespace.

Design decisions (stated plainly so tests and users know exactly what to expect):

1. Each entry type (section header, key=value, comment, blank line) is a distinct class.
   A comment is *only* a line whose first non-whitespace character is '#' or ';'.
   This matches what configparser would have treated as a comment.

2. We preserve leading and trailing whitespace on key=value lines exactly as written.
   We do NOT try to "align" or "normalize" indentation — whatever the file had is what
   round-trips back out. This avoids the compromise-and-fail trap of trying to honour three
   different indentation conventions at once.

3. Key parsing uses a *single split on the first '='*. This means 'a = b = c' has key 'a ',
   value ' b = c', and delimiter ' = '. We keep the exact text around the first equals sign
   so round-tripping is lossless. If a line contains no '=' at all, we treat it as bare text
   (stored verbatim, survives round-trip, but is awkward to edit via the API).

4. A line like '  ; just a comment' is a Comment, not a Key. A line like 'key ; value' is a
   Key whose value is ' ; value' — inline semicolons are part of the value, not comments.
   We deliberately do NOT support inline comments after values, because every INI flavour
   disagrees on the delimiter (';', '#', or both). Picking one interpretation avoids the
   version-comparator-style failure of trying to honour two conflicting rules.

5. Section names keep their surrounding brackets and any interior text verbatim. So
   '[a section]' is stored as '[a section]', not 'a section'. This avoids ambiguity about
   whether to strip brackets.

6. Multi-line values (continuation lines starting with whitespace) are NOT supported.
   We parse and emit them as independent Blank or Key entries (depending on content),
   preserving the raw text either way. Real multi-line support would require deciding
   whether leading whitespace or the absence of '=' is the continuation marker, and
   different INI flavours disagree.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _ensure_newline(s: str) -> str:
    """Return s guaranteed to end with a single newline."""
    if s.endswith("\n"):
        return s
    return s + "\n"


@dataclass
class Key:
    """A key=value line, preserving exact raw text and the split point.

    `raw` is the full original line including newline (or None if synthesised).
    `key`, `delimiter`, `value` come from a single split on the first '='.
    """

    raw: str | None = None
    key: str = ""
    delimiter: str = "="
    value: str = ""

    def render(self) -> str:
        if self.raw is not None:
            return self.raw
        return f"{self.key}{self.delimiter}{_ensure_newline(self.value)}"


@dataclass
class Section:
    """A '[section]' header line, stored verbatim."""

    raw: str | None = None

    def render(self) -> str:
        return self.raw if self.raw is not None else "[]\n"


@dataclass
class Comment:
    """A standalone comment line (first non-whitespace char is '#' or ';')."""

    raw: str | None = None

    def render(self) -> str:
        return self.raw if self.raw is not None else "#\n"


@dataclass
class Blank:
    """A line that is empty or contains only whitespace."""

    raw: str | None = None

    def render(self) -> str:
        return self.raw if self.raw is not None else "\n"


@dataclass
class INIFile:
    """Ordered list of parsed entries with convenience accessors.

    The `entries` list is the source of truth: round-tripping is `obj.dumps()` and
    equals the original text modulo whatever edits you made to entries.
    """

    entries: list = field(default_factory=list)

    def append(self, entry) -> None:
        self.entries.append(entry)

    def get(self, section_name: str, key_name: str) -> str | None:
        """Return the *value text* of a key under a section, or None if absent.

        Section matching is literal against the bracketed form, e.g. '[main]'.
        Key matching is literal against the stored key text (which includes any
        trailing whitespace from the original 'key =' line).
        """
        target_section = f"[{section_name}]"
        in_section = False
        for entry in self.entries:
            if isinstance(entry, Section):
                in_section = entry.raw is not None and entry.raw.strip() == target_section
            elif isinstance(entry, Key) and in_section:
                if entry.key == key_name:
                    return entry.value
        return None

    def set(self, section_name: str, key_name: str, value: str) -> None:
        """Set a key's value text, creating section/key if missing.

        New entries use delimiter '=' and end with a newline. Existing entries
        have only their `value` updated; `raw` is cleared so `render()` emits from
        the component fields.
        """
        target_section = f"[{section_name}]"
        in_section = False
        for entry in self.entries:
            if isinstance(entry, Section):
                in_section = entry.raw is not None and entry.raw.strip() == target_section
            elif isinstance(entry, Key) and in_section and entry.key == key_name:
                entry.value = value
                entry.raw = None
                return
        if not in_section:
            self.entries.append(Section(raw=target_section + "\n"))
        self.entries.append(Key(key=key_name, delimiter="=", value=value))

    def render(self) -> str:
        return "".join(entry.render() for entry in self.entries)


def _is_comment(line: str) -> bool:
    """True if the line's first non-whitespace character is '#' or ';'."""
    stripped = line.lstrip()
    return bool(stripped) and stripped[0] in ("#", ";")


def _is_blank(line: str) -> bool:
    """True if the line is empty or contains only whitespace."""
    return line.strip() == ""


def _is_section(line: str) -> bool:
    """True if the first non-whitespace character is '['.

    We do not require a matching ']' — a malformed line like '[unclosed' still
    round-trips as a Section. This avoids inventing a parsing rule not in scope.
    """
    stripped = line.lstrip()
    return bool(stripped) and stripped[0] == "["


def _has_equals(line: str) -> bool:
    """True if the line contains at least one '=' character."""
    return "=" in line


def _parse_key(line: str) -> Key:
    """Split on the first '=' to build a Key preserving exact text around it."""
    idx = line.index("=")
    key = line[:idx]
    value = line[idx + 1:]
    return Key(raw=line, key=key, delimiter="=", value=value)


def loads(text: str) -> INIFile:
    """Parse INI text into an INIFile preserving comments, ordering, and whitespace.

    The input text should end with a trailing newline for clean round-tripping;
    if it does not, the final line is still parsed (its `raw` simply lacks a newline).
    """
    lines = text.splitlines(keepends=True)
    ini = INIFile()
    for line in lines:
        if _is_blank(line):
            ini.append(Blank(raw=line))
        elif _is_comment(line):
            ini.append(Comment(raw=line))
        elif _is_section(line):
            ini.append(Section(raw=line))
        elif _has_equals(line):
            ini.append(_parse_key(line))
        else:
            # A line with content but no '=' is bare text. Keep it verbatim as a Key
            # so it survives round-tripping, even though it's awkward to edit.
            ini.append(Key(raw=line, key=line, delimiter="", value=""))
    return ini


def dumps(ini: INIFile) -> str:
    """Serialise an INIFile back to text, preserving all stored formatting."""
    return ini.render()


def dump(ini: INIFile, path: str) -> None:
    """Write the INIFile to `path`, creating parent directories if needed."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(dumps(ini))
