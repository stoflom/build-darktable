# Content-hash identifiers for darktable sidecars

To keep track of a large number of images, a BLAKE3 content-hash identifier is
added to the **Notes** field of every darktable XMP sidecar. This allows the
original image file to be identified and verified independently of file path
and date-time stamps. (The darktable team considered a built-in content hash
but rejected it on the ground of the import performance penalty.)

## Where the identifier lives

**Field:** Notes — the XMP tag `Xmp.acdsee.notes`.

> Note: earlier drafts of this document referred to "Xmp.darktable.notes".
> That tag does not exist in darktable. The tag behind the Notes metadata
> field (metadata editor) and the Lua `image.notes` property is
> `Xmp.acdsee.notes`, in the ACDSee namespace
> `http://ns.acdsee.com/iptc/1.0/`. This was confirmed against the darktable
> source (`src/common/database.c`, the built-in metadata field table) and
> against Exiv2 0.28.x — the version darktable is built with — which reads
> the tag back as `Xmp.acdsee.notes`.

Why Notes:

- It is an internal, free-form text buffer, rarely used for public
  cataloging, so there is zero conflict with standard Dublin Core schema.
- Unlike a hash placed in `dc:subject`, it does **not** clutter the tags
  module with thousands of unique tags.
- In **Preferences → Metadata Editor** the field can be set **Hidden** and
  **Private** so it stays out of the UI and is stripped from JPEG/TIFF
  exports.

In the sidecar file the value is stored as an attribute on the main
`<rdf:Description>` element:

```xml
xmlns:acdsee="http://ns.acdsee.com/iptc/1.0/"
...
acdsee:notes="hash:b1079c52f2150e74fb14e12cdba308ea1d53fd989aa5af55aef64b63d318e171"
```

## Identifier format

```
hash:<hex>
```

`<hex>` is the BLAKE3 digest of the companion **image file** (for
`IMG.PEF.xmp`, the file `IMG.PEF`) computed with `b3sum -l 32`:

- default: the full 64-hex-character digest (self-verifying);
- `--length 16` gives the 16-hex (64-bit) short form, which is sufficient
  as a unique key for tens of thousands of photos (birthday-bound
  collision probability is negligible) but is *not* sufficient to verify
  file content on its own.

The identifier is stored **on its own line** inside the Notes value. Any
existing user note text in the field is preserved; only previous identifier
lines are replaced when the image content has changed.

## The script: `add_content_hash.py`

```
./add_content_hash.py [OPTIONS] PATH [PATH ...]
```

`PATH` may be a directory (searched recursively for `*.xmp`), an image file,
or a sidecar file.

The script works in two phases: first it hashes all companion image files
in **batched `b3sum` invocations** (chunks sized to fit the OS command-line
limit; `b3sum` runs one rayon thread per file and so saturates all cores by
itself — no per-file process spawning), then it applies the sidecar edits in
a thread pool. This stays efficient for very large trees (multi-TB).

| Option         | Effect                                                            |
| -------------- | ----------------------------------------------------------------- |
| `--dry-run`    | Report what would change; write nothing                           |
| `--check`      | Verify existing identifiers against recomputed hashes; exit 1 on any mismatch or error |
| `--length N`   | Identifier length in hex chars, 1–64 (default 64)                 |
| `--prefix P`   | Identifier prefix (default `hash:`)                               |
| `--force`      | Replace the whole Notes field with the identifier (discards other note text) |
| `--threads N`  | Worker threads for the sidecar edit phase (default: number of CPUs; 1 = serial) |
| `--no-recurse` | Do not recurse into subdirectories                                |
| `-q, --quiet`  | Only print errors and the summary                                 |

Exit code 0 on success (or a clean dry-run/check), 1 if any file was
reported as `error` or `mismatch`. A `--check` run does not fail on
sidecars that simply lack an identifier yet — darktable creates new
sidecars on import, and they are stamped on the next script run; they are
reported as `missing` for information only.

Safety properties:

- **Surgical edit**: only the `acdsee:notes` attribute (and the
  `xmlns:acdsee` declaration, if absent) is changed. All of darktable's
  internal data — history, masks, iop order, timestamps — is
  byte-identical in the result. (ExifTool was considered and rejected for
  the write step: it restructures the whole XML document.)
- **Idempotent**: files already holding the current identifier are left
  completely untouched (mtime preserved), so re-runs are free.
- **Atomic write**: writes a temp file in the same directory, validates the
  result is well-formed XML, then replaces the original.
- **Does not touch `darktable:change_timestamp`** and **never writes to the
  darktable library database**. The sidecar's mtime simply becomes "now",
  which is exactly what darktable needs to recognise it as externally
  modified.
- Orphan sidecars (no companion image file) and unreadable files are
  skipped and reported, never clobbered. Orphans can be removed with
  `--remove-orphans` (preview first with `--dry-run`). Note that a missing
  image may simply have been moved elsewhere without its sidecar — search
  for it before removing the sidecar.

## Workflow

**0. Back up first — required.** The script modifies `.xmp` sidecars in
place, and a darktable sidecar is the *only* place your edit history,
masks, and presets live. Before the first run, back up the complete
photography tree, **images and sidecars together** (an image without its
sidecar loses all its edits). A plain `rsync`/`tar` copy or your regular
backup system is fine; the test run was done on a scratch copy before ever
touching the real tree.

**1. Close darktable.** Never modify sidecars while darktable has the
library open — darktable will overwrite your changes on its next save.

**2. Preview:**

```bash
./add_content_hash.py --dry-run ~/Pictures
```

**3. Run:**

```bash
./add_content_hash.py ~/Pictures
```

**4. Verify (optional, at any time):**

```bash
./add_content_hash.py --check ~/Pictures   # exit 1 if any image no longer matches
```

`--check` is also the mechanism for the "verify the original image file"
use case: if a renamed or moved file is re-hashed and no longer matches its
stored identifier, it is reported as `mismatch` (the only condition, apart
from operational errors, that makes `--check` fail). Sidecars that darktable
has newly created on import are reported as `missing` until the next script
run, which is normal and does not affect the exit code.

**5. Let darktable re-read the sidecars.** The script does not touch the
library database. Because every updated sidecar now has a newer mtime than
its `darktable:change_timestamp`, darktable sees them as externally
modified the next time the library is opened and offers to reload changed
images (lighttable → *Import → Reload changed images*). Accept the reload
and the Notes field (and hence the library database) is populated from the
sidecars.

## Caveats

- Any user note line that literally begins with the prefix (`hash:`) will
  be treated as an identifier and replaced; rename such notes first or use
  a different `--prefix`.
- Changing `--length` (or re-running after image content changes) updates
  the identifier line in place; user note text is unaffected unless
  `--force` is used.
- The hash identifies the *original image file*, not the sidecar. Editing
  the raw/CR3 file itself will change the hash; normal darktable processing
  does not.
- Keep the Notes field **Hidden** and **Private** in
  Preferences → Metadata Editor (see above) so the identifier stays out of
  the UI and out of exported files.
