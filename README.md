# ini-comment-preserver-lib

Reads and writes INI files while preserving comments, key ordering, and inline whitespace lost by configparser.

```python
from ini_comment_preserver_lib import loads, dumps, INIFile

ini = loads("# config\n[main]\nkey = value\n")
print(dumps(ini))  # verbatim original

ini.set("main", "key ", " new\n")
print(dumps(ini))  # "[main]\nkey = new\n"
```

## Why this exists

`configparser` discards comments, collapses inline whitespace around the `=`, and reorders keys alphabetically. This library keeps the original line structure as a list of typed entries (`Section`, `Key`, `Comment`, `Blank`) so that `dumps(loads(text))` is the identity function and edits stay surgical.

The trade-off: there is no dict-like view of sections. You get an ordered list and accessor methods (`get`/`set`) that match sections and keys by their literal text. That is enough for "change this one value and save without wrecking the file."

## Edge you will hit

Inline comments after values are **not** supported. A line like `key=value ; note` parses with value `value ; note` — the `;` is part of the value, not stripped as a comment. This is deliberate: INI flavours disagree on whether `;`, `#`, or both start inline comments, and trying to honour more than one rule leads to contradictions. If you need inline comments, strip them yourself before calling `loads`.

Multi-line continuation values are also not supported — continuation lines parse as independent entries (Blank or bare-text Key) and round-trip verbatim, but `get` will not assemble them into one value.

## Exports

- `INIFile` — container with `entries`, `get`, `set`, `render`, `append`
- `Section`, `Key`, `Comment`, `Blank` — entry classes with `raw` and `render()`
- `loads(text) -> INIFile`
- `dumps(ini) -> str`
- `dump(ini, path)` — writes to file, creating parent directories

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

