#!/usr/bin/env python3
"""Publish the small, versioned alignment reference bundle contract."""

import base64
import hashlib
import json
from pathlib import Path
import shutil
import sys


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


fasta, index, fai, dictionary, validation, annotation, metadata, versions = sys.argv[1:]
metadata = json.loads(base64.b64decode(metadata))
tools = json.loads(base64.b64decode(versions))
bundle = Path("bundle")
(bundle / "bwamem2").mkdir(parents=True)
shutil.copyfile(fasta, bundle / "reference.fa")
for path in Path(index).iterdir():
    shutil.copyfile(path, bundle / "bwamem2" / path.name)
shutil.copyfile(fai, bundle / "reference.fa.fai")
shutil.copyfile(dictionary, bundle / "reference.dict")
shutil.copytree(annotation, bundle / "annotation")
annotation_report = json.loads((bundle / "annotation/resource_metadata.json").read_text())
report = json.loads(Path(validation).read_text())
report["sources"].update(annotation_report["sources"])
metadata.update({
    "annotation": annotation_report["annotation"],
    "fasta": "reference.fa",
    "fasta_index": "reference.fa.fai",
    "sequence_dictionary": "reference.dict",
    "bwamem2_index": "bwamem2/reference.fa",
    "omitted_exclusions_bed_entries": report["omitted_exclusions_bed_entries"],
    "contigs": report["contigs"],
    "tools": [{"process": p, "tool": t, "version": v} for p, t, v in tools],
    "metadata_python": sys.version.split()[0],
    "checksums": {str(p.relative_to(bundle)): checksum(p)
                  for p in sorted(bundle.rglob("*")) if p.is_file()},
})
for key, checksums in report["sources"].items():
    metadata["sources"][key].update(checksums)
manifest = {"bundle_format_version": 3, **metadata}
(bundle / "bundle.json").write_text(json.dumps(manifest, indent=2) + "\n")
