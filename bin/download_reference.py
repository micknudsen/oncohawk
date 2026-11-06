#!/usr/bin/env python3
"""Acquire source bytes in a persistent, integrity-checked download store."""

import argparse
import base64
from contextlib import contextmanager
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import ssl
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid


def hashes(path):
    digests = {name: hashlib.new(name) for name in ("sha256", "md5")}
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            for digest in digests.values():
                digest.update(block)
    return {name: digest.hexdigest() for name, digest in digests.items()}


def check_expected(actual, asset):
    for algorithm, expected in asset["expected"].items():
        if actual[algorithm] != expected:
            raise ValueError(f"{asset['kind']} checksum mismatch ({algorithm}) for {asset['uri']}")


def download(uri, source, ca_bundle=None):
    context = ssl.create_default_context()
    if ca_bundle:
        context.load_verify_locations(cafile=ca_bundle)
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(uri, timeout=60, context=context) as response, source.open("wb") as target:
                shutil.copyfileobj(response, target, length=1024 * 1024)
                length = response.headers.get("Content-Length")
                if length is not None and target.tell() != int(length):
                    raise OSError(f"Incomplete download: expected {length} bytes, received {target.tell()}")
                target.flush()
                os.fsync(target.fileno())
            return
        except (OSError, http.client.HTTPException) as error:
            if isinstance(getattr(error, "reason", error), ssl.SSLCertVerificationError):
                raise OSError(f"TLS certificate verification failed for {uri}: {error}. "
                              "For a private/proxy CA, set --download_ca_bundle to the approved PEM bundle. "
                              "If already configured, check the certificate chain and hostname with your administrator.") from error
            if attempt == 3:
                raise OSError(f"Download failed after 3 attempts for {uri}: {error}. "
                              "Check source availability and compute-node network access, then rerun.") from error
            print(f"Download attempt {attempt}/3 failed for {uri}: {error}; retrying", file=sys.stderr)
            time.sleep(attempt)


@contextmanager
def entry_lock(entry):
    # mkdir coordinates across independent container mounts as well as cluster nodes.
    # Never steal ownership based on age: a live large download can take hours.
    lock = entry / ".lock"
    deadline = time.monotonic() + 3600
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise OSError(f"Timed out waiting for download-store lock {lock}. "
                              "Check owner.json and active jobs; see the guide for stale-lock recovery.")
            time.sleep(1)
    try:
        (lock / "owner.json").write_text(json.dumps({
            "host": socket.gethostname(), "pid": os.getpid(), "started": time.time(),
        }) + "\n")
        yield
    finally:
        shutil.rmtree(lock)


def acquire(store, asset, ca_bundle=None):
    asset["expected"] = {name: value.lower() for name, value in asset["expected"].items() if value}
    for name, value in asset["expected"].items():
        if name not in ("sha256", "md5") or not re.fullmatch(
                r"[0-9a-f]{64}" if name == "sha256" else r"[0-9a-f]{32}", value):
            raise ValueError(f"Invalid expected {name} checksum for {asset['uri']}")
    filename = Path(urllib.parse.urlsplit(asset["uri"]).path).name
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", filename):
        raise ValueError("Reference input filenames must contain only letters, digits, dots, underscores or hyphens")
    key = hashlib.sha256(json.dumps(asset, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    entry = store / key
    entry.mkdir(parents=True, exist_ok=True)
    with entry_lock(entry):
        return acquire_locked(entry, asset, filename, ca_bundle)


def acquire_locked(entry, asset, filename, ca_bundle=None):
    metadata = entry / "metadata.json"
    if metadata.exists():
        try:
            record = json.loads(metadata.read_text())
            if record["asset"] != asset or record["store_format_version"] != 1:
                raise ValueError("stored asset identity or format differs")
            generation = record["generation"]
            if not re.fullmatch(r"[0-9a-f]{32}", generation):
                raise ValueError("invalid stored generation")
            source = entry / generation / filename
            actual = hashes(source)
            if actual != record["checksums"] or source.stat().st_size != record["size"]:
                raise ValueError("stored source checksum or size differs")
            check_expected(actual, asset)
            print(f"Verified download-store hit: {asset['uri']}", file=sys.stderr)
            return source
        except (ValueError, KeyError, TypeError, OSError) as error:
            print(f"Corrupt or incomplete download-store entry {entry}: {error}; replacing", file=sys.stderr)

    # Publish a new immutable generation, then atomically commit its metadata.
    # Existing generations remain readable by tasks from other runs.
    temporary = Path(tempfile.mkdtemp(prefix=".partial-", dir=entry))
    try:
        source = temporary / filename
        print(f"Downloading {asset['uri']}", file=sys.stderr)
        download(asset["uri"], source, ca_bundle)
        actual = hashes(source)
        check_expected(actual, asset)
        generation = uuid.uuid4().hex
        record = {"store_format_version": 1, "asset": asset, "generation": generation,
                  "checksums": actual, "size": source.stat().st_size}
        temporary.rename(entry / generation)
        pending_metadata = entry / f".metadata-{generation}.json"
        with pending_metadata.open("w") as handle:
            handle.write(json.dumps(record, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        pending_metadata.replace(metadata)
        return entry / generation / filename
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


if __name__ == "__main__":
    def interrupted(_signum, _frame):
        raise SystemExit("Reference download interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store", type=Path)
    parser.add_argument("asset", help="Base64-encoded JSON asset identity and integrity policy")
    parser.add_argument("--ca-bundle", type=Path, help="Additional trusted CA certificates in PEM format")
    args = parser.parse_args()
    try:
        source = acquire(args.store, json.loads(base64.b64decode(args.asset)), args.ca_bundle)
        Path("download.json").write_text(json.dumps({"path": str(source)}) + "\n")
    except (ValueError, OSError) as error:
        parser.exit(1, f"Reference download error: {error}\n")
