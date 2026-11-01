#!/usr/bin/env python3
"""Verify every installed nf-core file against the pinned upstream Git tree."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


PROJECT = Path(__file__).resolve().parents[1]
lock = json.loads((PROJECT / "modules.json").read_text())
checked = 0
verified_paths = set()
with tempfile.TemporaryDirectory(prefix="oncohawk-upstream-") as directory:
    def git(*arguments):
        return subprocess.check_output(["git", "-C", directory, *arguments])

    git("init", "--quiet")
    for remote, repository in lock["repos"].items():
        for namespace, modules in repository["modules"].items():
            fetched = set()
            for name, metadata in modules.items():
                revision = metadata["git_sha"]
                if revision not in fetched:
                    git("fetch", "--quiet", "--filter=blob:none", "--depth=1", remote, revision)
                    fetched.add(revision)
                prefix = f"modules/{namespace}/{name}"
                entries = git("ls-tree", "-rz", revision, "--", prefix).decode().split("\0")
                expected = {}
                for entry in filter(None, entries):
                    properties, path = entry.split("\t", 1)
                    mode, kind, object_id = properties.split()
                    if kind != "blob":
                        raise SystemExit(f"Unexpected upstream object: {path}")
                    expected[path] = object_id
                actual = {str(path.relative_to(PROJECT)) for path in (PROJECT / prefix).rglob("*")
                          if path.is_file()}
                if not expected or actual != set(expected):
                    raise SystemExit(f"Module file set differs from upstream: {prefix}")
                for path, object_id in expected.items():
                    data = (PROJECT / path).read_bytes()
                    digest = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
                    if digest != object_id:
                        raise SystemExit(f"Modified upstream module file: {path}")
                    checked += 1
                verified_paths.update(expected)
installed_paths = {str(path.relative_to(PROJECT)) for path in (PROJECT / "modules/nf-core").rglob("*")
                   if path.is_file()}
if installed_paths != verified_paths:
    raise SystemExit("Installed module files are missing from modules.json")
print(f"{checked} installed module files exactly match their pinned upstream revisions")
