"""Tests for ini_comment_preserver_lib.core.

All tests are deterministic — no wall-clock, no sleeps, no float equality.
"""

import os
import tempfile
import unittest

from ini_comment_preserver_lib.core import (
    INIFile,
    Section,
    Key,
    Comment,
    Blank,
    dump,
    loads,
    dumps,
)


class TestRoundTrip(unittest.TestCase):
    """The core promise: parse then dump equals the original text."""

    def test_round_trip_full(self):
        text = "# top comment\n\n[main]\n; section comment\nkey = value\n\n[other]\nnested=1\n"
        self.assertEqual(dumps(loads(text)), text)

    def test_round_trip_empty_string(self):
        self.assertEqual(dumps(loads("")), "")

    def test_round_trip_no_trailing_newline(self):
        # A file ending without a newline should round-trip exactly.
        text = "[s]\nk=v"
        self.assertEqual(dumps(loads(text)), text)

    def test_round_trip_only_comments(self):
        text = "# a\n; b\n\n#c\n"
        self.assertEqual(dumps(loads(text)), text)


class TestEntryClassification(unittest.TestCase):
    """Verify how each input line is classified."""

    def test_comment_with_hash(self):
        ini = loads("# hello\n")
        self.assertIsInstance(ini.entries[0], Comment)

    def test_comment_with_semicolon(self):
        ini = loads("; hello\n")
        self.assertIsInstance(ini.entries[0], Comment)

    def test_indented_comment(self):
        ini = loads("    ; indented\n")
        self.assertIsInstance(ini.entries[0], Comment)
        self.assertEqual(ini.entries[0].raw, "    ; indented\n")

    def test_blank_line(self):
        ini = loads("\n")
        self.assertIsInstance(ini.entries[0], Blank)

    def test_whitespace_only_line(self):
        ini = loads("   \t  \n")
        self.assertIsInstance(ini.entries[0], Blank)
        self.assertEqual(ini.entries[0].raw, "   \t  \n")

    def test_section_header(self):
        ini = loads("[section]\n")
        self.assertIsInstance(ini.entries[0], Section)
        self.assertEqual(ini.entries[0].raw, "[section]\n")

    def test_key_value_basic(self):
        ini = loads("key=value\n")
        e = ini.entries[0]
        self.assertIsInstance(e, Key)
        self.assertEqual(e.key, "key")
        self.assertEqual(e.value, "value\n")

    def test_key_value_with_spaces(self):
        ini = loads("key = value\n")
        e = ini.entries[0]
        self.assertEqual(e.key, "key ")
        self.assertEqual(e.value, " value\n")

    def test_value_with_equals(self):
        # Single split on first '=': subsequent '=' stays in the value.
        ini = loads("a=b=c\n")
        e = ini.entries[0]
        self.assertEqual(e.key, "a")
        self.assertEqual(e.value, "b=c\n")

    def test_indented_key(self):
        ini = loads("  indented = v\n")
        e = ini.entries[0]
        self.assertEqual(e.key, "  indented ")
        self.assertEqual(e.value, " v\n")

    def test_inline_semicolon_is_not_comment(self):
        # Per documented design: inline ';' is part of the value, not a comment.
        ini = loads("key=value ; not a comment\n")
        e = ini.entries[0]
        self.assertEqual(e.value, "value ; not a comment\n")


class TestBareText(unittest.TestCase):
    """Lines with no '=' are kept verbatim as Key entries."""

    def test_bare_text_round_trips(self):
        text = "[s]\nsome text\nkey=v\n"
        self.assertEqual(dumps(loads(text)), text)

    def test_bare_text_stored_as_key(self):
        ini = loads("bare line\n")
        self.assertIsInstance(ini.entries[0], Key)
        self.assertEqual(ini.entries[0].raw, "bare line\n")


class TestGetSet(unittest.TestCase):
    """Test the get/set convenience API."""

    def test_get_existing(self):
        ini = loads("[main]\nkey = value\n")
        self.assertEqual(ini.get("main", "key "), " value\n")

    def test_get_missing_section(self):
        ini = loads("[main]\nkey=v\n")
        self.assertIsNone(ini.get("other", "key"))

    def test_get_missing_key(self):
        ini = loads("[main]\nkey=v\n")
        self.assertIsNone(ini.get("main", "absent"))

    def test_get_after_other_section(self):
        # get must only return keys under the matching section.
        ini = loads("[a]\nk=1\n[b]\nk=2\n")
        self.assertEqual(ini.get("a", "k"), "1\n")
        self.assertEqual(ini.get("b", "k"), "2\n")

    def test_set_existing_value(self):
        ini = loads("[main]\nkey = value\n")
        ini.set("main", "key ", "newval\n")
        self.assertEqual(ini.get("main", "key "), "newval\n")
        self.assertEqual(dumps(ini), "[main]\nkey =newval\n")

    def test_set_creates_section_and_key(self):
        ini = INIFile()
        ini.set("newsec", "newkey", "newval\n")
        self.assertEqual(dumps(ini), "[newsec]\nnewkey=newval\n")

    def test_set_creates_key_in_existing_section(self):
        ini = loads("[main]\nexisting=v\n")
        ini.set("main", "added", "x\n")
        self.assertEqual(ini.get("main", "added"), "x\n")


class TestDumpToFile(unittest.TestCase):
    """dump() writes to a file and creates parent directories."""

    def test_dump_writes_file(self):
        ini = loads("[s]\nk=v\n")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.ini")
            dump(ini, path)
            with open(path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "[s]\nk=v\n")

    def test_dump_creates_parent_dirs(self):
        ini = loads("[s]\nk=v\n")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "dir", "out.ini")
            dump(ini, path)
            self.assertTrue(os.path.isfile(path))


class TestSyntheticEntries(unittest.TestCase):
    """Entries constructed by hand (no raw) render from component fields."""

    def test_synthetic_key_render(self):
        k = Key(key="name", delimiter=":", value="bob\n")
        self.assertEqual(k.render(), "name:bob\n")

    def test_synthetic_section_render(self):
        s = Section(raw="[sec]\n")
        self.assertEqual(s.render(), "[sec]\n")

    def test_synthetic_comment_render(self):
        c = Comment(raw="# note\n")
        self.assertEqual(c.render(), "# note\n")

    def test_synthetic_blank_render(self):
        b = Blank(raw="\n")
        self.assertEqual(b.render(), "\n")


class TestLineEndingPreservation(unittest.TestCase):
    """Windows-style CRLF line endings are preserved verbatim."""

    def test_crlf_round_trip(self):
        text = "[s]\r\nk=v\r\n"
        self.assertEqual(dumps(loads(text)), text)


if __name__ == "__main__":
    unittest.main()
