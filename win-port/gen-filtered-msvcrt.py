#!/usr/bin/env python3
"""Build the filtered msvcrt.lib from the toolchain's own msvcrt.lib.

The zig (mingw) CRT and MSVC's msvcrt.lib both define the TLS and Control
Flow Guard support objects (__dyn_tls_init, __guard_* ...), which clash at
link time. This script removes exactly those object members from the
Microsoft library installed on the build machine, so no prebuilt binary has
to be shipped in the repository.

msvcrt-reference-symbols.txt lists every symbol the filtered library must
still export. Using the archive's own symbol index (the first linker
member, the same table the linker reads), a member is removed when it
exports a symbol outside that list. As a guard against toolchain drift,
every removed symbol must look like TLS/CFG machinery and at most
MAX_REMOVED members may go; anything else fails the build loudly instead of
producing a silently broken library.

Usage: python gen-filtered-msvcrt.py <lib.exe> <msvcrt.lib> <reference.txt> <out.lib>
"""

import re
import struct
import subprocess
import sys

MAX_REMOVED = 20
CLASH_PATTERN = re.compile(r"tls|guard", re.IGNORECASE)
HEADER_SIZE = 60


def read_header(data, offset):
    header = data[offset:offset + HEADER_SIZE]
    if len(header) != HEADER_SIZE or header[58:60] != b"`\n":
        raise ValueError("bad archive member header at offset %d" % offset)
    return header[:16].decode("latin1").rstrip(), int(header[48:58])


def symbol_index(data):
    """Map member offset -> exported symbols, from the first linker member."""
    if data[:8] != b"!<arch>\n":
        raise ValueError("not a COFF archive")
    name, size = read_header(data, 8)
    if name != "/":
        raise ValueError("archive has no linker member")
    body = data[8 + HEADER_SIZE:8 + HEADER_SIZE + size]
    count = struct.unpack_from(">I", body, 0)[0]
    offsets = struct.unpack_from(">%dI" % count, body, 4)
    names = body[4 + 4 * count:].split(b"\0")[:count]
    index = {}
    for offset, sym in zip(offsets, names):
        index.setdefault(offset, set()).add(sym.decode("latin1"))
    return index


def long_names(data):
    """Return the '//' long-name table of an MS archive (b'' if absent)."""
    offset = 8
    while offset + HEADER_SIZE <= len(data):
        name, size = read_header(data, offset)
        if name == "//":
            return data[offset + HEADER_SIZE:offset + HEADER_SIZE + size]
        if name != "/":
            return b""
        offset += HEADER_SIZE + size + (size & 1)
    return b""


def member_name(data, offset, longnames):
    raw, _ = read_header(data, offset)
    if raw.startswith("/") and raw[1:].isdigit():
        start = int(raw[1:])
        return longnames[start:longnames.find(b"\0", start)].decode("latin1")
    return raw.rstrip("/")


def select_removals(data, reference):
    """Return {member name: symbols outside the reference}, or fail."""
    longnames = long_names(data)
    removals = {}
    for offset, syms in symbol_index(data).items():
        extra = syms - reference
        if extra:
            removals.setdefault(member_name(data, offset, longnames), set()).update(extra)
    unexpected = sorted(s for syms in removals.values() for s in syms if not CLASH_PATTERN.search(s))
    if unexpected or len(removals) > MAX_REMOVED:
        raise SystemExit("refusing to filter: %d members, unexpected symbols %s" % (len(removals), unexpected))
    return removals


def check_unique(data, removals):
    longnames = long_names(data)
    all_names = [member_name(data, off, longnames) for off in symbol_index(data)]
    for name in removals:
        if all_names.count(name) != 1:
            raise SystemExit("member name %r is not unique, cannot remove it safely" % name)


def main(argv):
    if len(argv) != 5:
        raise SystemExit(__doc__)
    lib_exe, source, reference_path, out = argv[1:]
    with open(reference_path, encoding="utf-8") as f:
        reference = {line.strip() for line in f if line.strip()}
    with open(source, "rb") as f:
        data = f.read()
    removals = select_removals(data, reference)
    check_unique(data, removals)
    for name, syms in sorted(removals.items()):
        print("REMOVE %s: %s" % (name, ", ".join(sorted(syms))))
    cmd = [lib_exe, "/NOLOGO", "/OUT:" + out] + ["/REMOVE:" + n for n in sorted(removals)] + [source]
    subprocess.run(cmd, check=True)
    with open(out, "rb") as f:
        kept = set().union(*symbol_index(f.read()).values())
    removed = set().union(*removals.values()) if removals else set()
    if removed & kept:
        raise SystemExit("filtered lib still exports %s" % sorted(removed & kept))
    missing = sorted(reference - kept)
    print("filtered msvcrt.lib: removed %d members, %d symbols kept, %d reference symbols absent: %s"
          % (len(removals), len(kept), len(missing), missing[:20]))


if __name__ == "__main__":
    main(sys.argv)
