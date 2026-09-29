#!/usr/bin/env python3
"""
add_content_hash.py — stamp a BLAKE3 content-hash identifier into darktable XMP sidecars.

Per HASH.md "Option 1", the identifier is stored in the Notes field
(Xmp.acdsee.notes — the real XMP tag behind darktable's "Notes" metadata
field and the Lua `image.notes` property; written as the acdsee:notes
attribute in namespace http://ns.acdsee.com/iptc/1.0/).

For each sidecar file  <IMAGE>.<ext>.xmp  the BLAKE3 hash of the companion
image file  <IMAGE>.<ext>  is computed and the identifier line

    hash:<hex>

is merged into the notes attribute:
  * an existing identifier line is replaced (image content may have changed),
  * any other user note text is preserved (identifier goes on its own line),
  * files already holding the current identifier are left untouched (mtime
    preserved, idempotent re-runs).

The edit is surgical (only the notes attribute / xmlns declaration is
changed), so darktable's internal tags, masks and history are byte-identical.
darktable:change_timestamp is NOT touched: because the file mtime becomes
"now", darktable sees the sidecar as externally modified and offers to
re-read it the next time the library is opened. Nothing is written to the
library database by this script.

Usage:
  add_content_hash.py [OPTIONS] PATH [PATH ...]

  PATH may be a directory (searched recursively for *.xmp), an image file,
  or a sidecar file.

Options:
  --dry-run        report what would change, write nothing
  --check          verify existing identifiers instead of writing; exit 1
                   on mismatch or error (sidecars without an identifier yet
                   are reported as missing but not treated as failures)
  --remove-orphans prune sidecars whose companion image file does not exist
                   (default: report them as orphans only). This is a
                   standalone mode: it never opens, hashes or rewrites any
                   image or sidecar that has a live companion, so it is
                   cheap even for multi-TB trees. Combine with --dry-run to
                   list the orphans without removing anything. The
                   identifier options (--length, --prefix, --force) and
                   --threads have no effect here.
  --length N       identifier length in hex chars (default 64 = full BLAKE3;
                   use 16 to match the short form in HASH.md)
  --prefix P       identifier prefix (default "hash:")
  --force          replace the whole notes field with the identifier
                   (discards any other note text)
  --threads N      worker threads for the sidecar edit phase (default:
                   number of CPUs); 1 = serial. The hashing phase always
                   uses a single b3sum process per file chunk, which runs
                   one rayon thread per file and so saturates all cores.
  --no-recurse     do not recurse into subdirectories
  --wait           block while a face-review scan is running, instead of only
                   warning (see SCAN LOCK below)
  --wait-timeout S with --wait, give up waiting after S seconds (default:
                   wait indefinitely)
  --no-lock-check  skip the scan-lock check entirely
  -q, --quiet      only print errors and the summary

SCAN LOCK
  The face-review app (~/Workspace/face_recognition) takes
  ~/.cache/facerec/scan.lock while it detects faces, and it reads the same
  ~/Pictures this job hashes. The two are the heaviest readers of that disk, so
  running them together slows both down and can make a scan time out. This
  script therefore warns when the lock is held. Use --wait to block until the
  scan finishes instead, which is what a nightly run should do.

  The lock format and the staleness rule are deliberately identical to
  ScanLock in face_recognition/app/src-tauri/src/scan.rs, so the two can read
  each other's lock. This copy is self-contained on purpose: this script has no
  dependency on the face_recognition workspace. The canonical reader, and the
  parity tests for both, are scripts/scan_lock.py and scripts/test_scan_lock.py
  there -- change both sides together if the format ever moves.

How it works (two phases):
  1. All companion image files are hashed in batched b3sum invocations
     (chunks sized to fit the command-line limit; b3sum parallelises
     across the files in each chunk), which is efficient even for very
     large trees (multi-TB).
  2. The sidecar XML edits are applied in a thread pool.

--remove-orphans skips both phases: an os.path.isfile() test plus, for the
ones that fail it, os.unlink() — threaded over the same worker pool, so a
prune over a multi-TB tree is a metadata-only walk.

Exit codes: 0 = ok (or dry-run/check passed), 1 = errors/mismatches, 2 = usage.
A --check run does not fail on sidecars that simply lack an identifier yet
(darktable creates new sidecars on import); it fails only on hash
mismatches or operational errors.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

ACDSEE_NS = "http://ns.acdsee.com/iptc/1.0/"
ATTR_RE = re.compile(r'(\bacdsee:notes=)"((?:[^"\\]|\\.)*)"')
ELEM_RE = re.compile(r"(<acdsee:notes[^>]*>)(.*?)(</acdsee:notes>)", re.S)
DESC_RE = re.compile(r"<rdf:Description\b[^>]*>")


def hash_images(paths, quiet=False):
    """Batch-hash image files with b3sum; returns {path: digest}.

    b3sum runs one rayon thread per input file (pool = logical cores),
    so each invocation already saturates the machine. Chunks are kept
    small enough to stay under the OS argument-length limit.
    """
    CHUNK_BYTES = 1_000_000  # well under Linux ARG_MAX (~2 MB)
    chunks, cur, cur_len = [], [], 0
    for p in paths:
        if cur and cur_len + len(p) > CHUNK_BYTES:
            chunks.append(cur)
            cur, cur_len = [], 0
        cur.append(p)
        cur_len += len(p)
    if cur:
        chunks.append(cur)

    digests = {}
    for i, chunk in enumerate(chunks, 1):
        if not quiet:
            print(
                "hashing chunk %d/%d (%d files)..."
                % (i, len(chunks), len(chunk)),
                file=sys.stderr,
            )
        out = subprocess.run(
            ["b3sum", "-l", "32", "--"] + chunk,
            capture_output=True, text=True,
        )
        for line in out.stdout.splitlines():
            digest, sep, path = line.partition("  ")
            if sep:
                digests[path] = digest.strip().lower()
        if out.returncode != 0:
            # individual unreadable files are reported per file below;
            # only die if b3sum itself failed outright
            if not digests:
                raise RuntimeError("b3sum failed: %s" % out.stderr.strip()[:300])
    return digests


def xml_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def get_note(text):
    """Return the current notes value (attribute form preferred), or None."""
    m = ATTR_RE.search(text)
    if m:
        return m.group(2)
    m = ELEM_RE.search(text)
    if m:
        return m.group(2)
    return None


def set_note(text, value):
    """Replace or insert the notes value, minimally touching the XML."""
    m = ATTR_RE.search(text)
    if m:
        return text[: m.start(2)] + xml_escape(value) + text[m.end(2):], True

    m = ELEM_RE.search(text)
    if m:
        return (
            text[: m.start(2)] + xml_escape(value) + text[m.end(2):],
            True,
        )

    # Insert as attribute on the first rdf:Description opening tag.
    m = DESC_RE.search(text)
    if not m:
        return None, False
    tag = m.group(0)
    if "xmlns:acdsee" not in text:
        tag = tag.replace(
            "<rdf:Description",
            '<rdf:Description xmlns:acdsee="%s"' % ACDSEE_NS,
            1,
        )
    new_tag = tag[:-1] + ' acdsee:notes="%s"' % xml_escape(value) + ">"
    return text[: m.start()] + new_tag + text[m.end():], False


def merge_note(old, ident, force, prefix):
    """Build the new notes value from the old value and the identifier."""
    lines = []
    if old is not None and not force:
        for line in old.splitlines():
            line = line.strip()
            if line.startswith(prefix):
                continue  # drop stale identifier line
            if line:
                lines.append(line)
    lines.append(ident)
    return "\n".join(lines)


def extract_ident(note, prefix):
    if note is None:
        return None
    for line in note.splitlines():
        line = line.strip()
        if line.startswith(prefix):
            return line
    return None


def progress(done, total, args):
    """Overwrite a single progress line on a TTY stderr (no-op otherwise)."""
    if not args.quiet and sys.stderr.isatty():
        sys.stderr.write("\r  %d/%d sidecars" % (done, total))
        sys.stderr.flush()


def prune(xmp_path, args, _payload=None):
    """Remove (or list) a sidecar whose companion image is gone.

    Touches nothing else: no hashing, no XML edits, and sidecars that do
    have a live companion are reported as kept and left alone.
    """
    img_path = xmp_path[: -len(".xmp")]
    if os.path.isfile(img_path):
        return "kept", None, ""
    if args.dry_run:
        return "would-remove", None, "orphan: %s" % img_path
    try:
        os.unlink(xmp_path)
    except OSError as e:
        return "error", None, "orphan remove failed: %s" % e
    return "removed", None, "orphan: %s" % img_path


def process(xmp_path, args, digest):
    """Return (status, ident, detail); digest may be None on hash failure."""
    if digest is None:
        img_path = xmp_path[: -len(".xmp")]
        if not os.path.isfile(img_path):
            # vanished between the stat pass and here
            return "orphan", None, "no companion image: %s" % img_path
        return "error", None, "no hash for %s" % img_path

    ident = "%s%s" % (args.prefix, digest[: args.length])

    try:
        with open(xmp_path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return "error", None, "read failed: %s" % e

    old = get_note(text)
    if args.check:
        cur = extract_ident(old, args.prefix)
        if cur is None:
            return "missing", ident, "no identifier in notes"
        if cur == ident:
            return "ok", ident, ""
        return "mismatch", ident, "found %s" % cur

    new = merge_note(old, ident, args.force, args.prefix)
    if new == old:
        return "up-to-date", ident, ""

    if args.dry_run:
        return "would-update", ident, ""

    new_text, _ = set_note(text, new)
    if new_text is None:
        return "error", ident, "no rdf:Description found"
    try:
        ET.fromstring(new_text)  # sanity: still well-formed XML
    except ET.ParseError as e:
        return "error", ident, "resulting XML invalid: %s" % e

    d = os.path.dirname(xmp_path) or "."
    st = os.stat(xmp_path)
    fd, tmp = tempfile.mkstemp(prefix=".xmp-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_text)
        os.chmod(tmp, st.st_mode & 0o777)
        os.replace(tmp, xmp_path)
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return "error", ident, "write failed: %s" % e
    return "updated", ident, ""


# --- scan lock (§14 item 10) -----------------------------------------------
# See the SCAN LOCK section of the module docstring. Deliberately a small,
# conservative copy of face_recognition/scripts/scan_lock.py: this script must
# stay runnable without the face_recognition workspace on disk. Both sides must
# be changed together if the lock format moves; scripts/test_scan_lock.py in
# that workspace checks this file still consults the lock.
SCAN_LOCK_PATH = os.path.join(
    os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
    "facerec",
    "scan.lock",
)


def _pid_alive(pid):
    # Without /proc we cannot tell, and "still running" is the answer that
    # avoids two jobs fighting over the same disk.
    return pid != 0 and (not sys.platform.startswith("linux")
                         or os.path.exists("/proc/%d" % pid))


def scan_lock_state(path=None):
    """(is_running, why). Never raises; an unreadable lock means "not running"."""
    path = path or SCAN_LOCK_PATH
    try:
        with open(path) as fh:
            txt = fh.read()
    except OSError:
        return False, None
    pid, tree, started = 0, "", ""
    for line in txt.splitlines():
        if line.startswith("pid="):
            try:
                pid = int(line[4:].strip())
            except ValueError:
                pid = 0
        elif line.startswith("tree="):
            tree = line[5:].strip()
        elif line.startswith("started_at="):
            started = line[11:].strip()
    if pid == 0:
        return False, None                      # released
    if not _pid_alive(pid):
        return False, "stale scan lock from pid %d" % pid
    return True, "a face-review scan of %s is running (pid %d, since %s)" % (
        tree or "the pictures", pid, started or "unknown")


def check_scan_lock(args):
    """Warn, or block with --wait. Returns False only if it gave up waiting."""
    if args.no_lock_check:
        return True
    running, why = scan_lock_state()
    if not running:
        if why and not args.quiet:
            print("note: %s; ignoring it" % why, file=sys.stderr)
        return True
    if not args.wait:
        # Warn and carry on: a scan in flight is not a reason to refuse work
        # that has not actually started, and this job may be the thing keeping
        # the pictures warm. --wait is the opt-in for "actually serialise".
        print("warning: %s" % why, file=sys.stderr)
        print("warning: this job hashes the same ~/Pictures; pass --wait to block "
              "until the scan finishes", file=sys.stderr)
        return True
    if not args.quiet:
        print("waiting for the face-review scan to finish...", file=sys.stderr)
    deadline = None if args.wait_timeout is None else time.time() + args.wait_timeout
    while True:
        time.sleep(2)
        running, why = scan_lock_state()
        if not running:
            if not args.quiet:
                print("scan lock cleared; continuing", file=sys.stderr)
            return True
        if deadline is not None and time.time() >= deadline:
            print("error: gave up waiting after %gs: %s" % (args.wait_timeout, why),
                  file=sys.stderr)
            return False


def collect(paths, recurse=True):
    out = []
    for p in paths:
        if os.path.isdir(p):
            if recurse:
                out.extend(
                    os.path.join(root, f)
                    for root, _, files in os.walk(p)
                    for f in files
                    if f.endswith(".xmp")
                )
            else:
                out.extend(
                    os.path.join(p, f)
                    for f in os.listdir(p)
                    if f.endswith(".xmp")
                    and os.path.isfile(os.path.join(p, f))
                )
        elif p.endswith(".xmp"):
            out.append(p)
        else:
            out.append(p + ".xmp")
    return out


def main(argv):
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[1], formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="+", metavar="PATH")
    ap.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    ap.add_argument("--check", action="store_true", help="verify existing identifiers; exit 1 on mismatch or error")
    ap.add_argument("--remove-orphans", action="store_true",
                    help="standalone prune mode: remove sidecars whose companion image "
                         "does not exist; no image is opened, hashed or rewritten "
                         "(use --dry-run to only list them)")
    ap.add_argument("--length", type=int, default=64, metavar="N", help="identifier length in hex chars, 1-64 (default 64)")
    ap.add_argument("--prefix", default="hash:", metavar="P", help="identifier prefix (default 'hash:')")
    ap.add_argument("--force", action="store_true", help="replace the whole notes field (discards other note text)")
    ap.add_argument("--threads", type=int, default=0, metavar="N",
                    help="worker threads, default = number of CPUs; 1 = serial")
    ap.add_argument("--no-recurse", action="store_true", help="do not recurse into subdirectories")
    ap.add_argument("--wait", action="store_true",
                    help="block while a face-review scan holds the scan lock, "
                         "instead of only warning (see SCAN LOCK below)")
    ap.add_argument("--wait-timeout", type=float, default=None, metavar="SECONDS",
                    help="with --wait, give up waiting after SECONDS "
                         "(default: wait indefinitely)")
    ap.add_argument("--no-lock-check", action="store_true",
                    help="skip the scan-lock check entirely")
    ap.add_argument("-q", "--quiet", action="store_true", help="only print errors and the summary")
    args = ap.parse_args(argv)
    if not 1 <= args.length <= 64:
        ap.error("--length must be between 1 and 64")
    if args.threads < 0:
        ap.error("--threads must be at least 1 (0 = number of CPUs)")
    if args.remove_orphans and args.check:
        ap.error("--check and --remove-orphans are mutually exclusive")
    if args.wait_timeout is not None and not args.wait:
        ap.error("--wait-timeout only has an effect with --wait")
    if not args.remove_orphans and not shutil_which("b3sum"):
        sys.exit("error: b3sum (BLAKE3) not found in PATH")

    # Before anything reads ~/Pictures: the whole point is not to hash the same
    # files the app is decoding right now.
    if not check_scan_lock(args):
        sys.exit(1)

    files = collect(args.paths, recurse=not args.no_recurse)
    if not files:
        sys.exit("error: no .xmp sidecars found")

    missing = [p for p in args.paths if not os.path.exists(p)]
    if missing:
        for p in missing:
            print("error: no such file or directory: %s" % p, file=sys.stderr)
        sys.exit(2)

    if args.remove_orphans:
        # Prune mode: stat + unlink only, no image access whatsoever.
        if not args.quiet:
            print("scanning %d sidecars..." % len(files), file=sys.stderr)
        work, fn = [(xmp, None) for xmp in files], prune
    else:
        # Phase 1: hash all companion images in batched b3sum invocations.
        images = [x[:-4] for x in files if os.path.isfile(x[:-4])]
        if images and not args.quiet:
            print("hashing %d image files..." % len(images), file=sys.stderr)
        digests = hash_images(images, quiet=args.quiet) if images else {}
        # Phase 2: apply the sidecar edits in a thread pool.
        if not args.quiet:
            print("processing %d sidecars..." % len(files), file=sys.stderr)
        work = [(xmp, digests.get(xmp[:-4])) for xmp in files]
        fn = process

    counts = {}
    bad = 0
    for xmp, (status, ident, detail) in run_files(work, fn, args):
        counts[status] = counts.get(status, 0) + 1
        if status in ("error", "mismatch"):
            bad += 1
        if not args.quiet:
            msg = xmp
            if detail:
                msg += "  [%s] %s" % (status, detail)
            elif status in ("updated", "would-update", "up-to-date"):
                msg += "  [%s] %s" % (status, ident)
            print(msg)
    if not args.quiet and sys.stderr.isatty():
        print(file=sys.stderr)  # terminate the progress line

    print(
        "summary: %s — %s"
        % (
            ", ".join("%d %s" % (v, k) for k, v in sorted(counts.items())),
            "DRY RUN" if args.dry_run else ("CHECK" if args.check else ""),
        )
    )
    return 1 if bad else 0


def shutil_which(name):
    import shutil

    return shutil.which(name) is not None


def run_files(work, fn, args):
    """Run fn(xmp, args, payload) over work in parallel; results in input order.

    fn signatures must match: (xmp_path, args, payload).
    """
    workers = args.threads if args.threads > 0 else (os.cpu_count() or 1)
    if workers == 1 or len(work) == 1:
        for i, (xmp, payload) in enumerate(work):
            progress(i, len(work), args)
            yield xmp, fn(xmp, args, payload)
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [(xmp, pool.submit(fn, xmp, args, p)) for xmp, p in work]
        for i, (xmp, fut) in enumerate(futures):
            progress(i, len(futures), args)
            yield xmp, fut.result()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
