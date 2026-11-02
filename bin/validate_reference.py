#!/usr/bin/env python3
"""Validate Oncohawk's FASTA/exclusions BED contract before invoking alignment tools."""

import argparse
import base64
import hashlib
import json
from pathlib import Path


def source_checksums(path, expected, label):
    digests = {algorithm: hashlib.new(algorithm) for algorithm in ["sha256", "md5"]}
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            for digest in digests.values():
                digest.update(block)
    result = {algorithm: digest.hexdigest() for algorithm, digest in digests.items()}
    result["verified_checksum"] = None
    for algorithm, checksum in expected.items():
        if checksum:
            if result[algorithm] != checksum.lower():
                raise ValueError(f"{label} checksum mismatch ({algorithm})")
            result["verified_checksum"] = f"{algorithm}:{checksum.lower()}"
    return result


def validate(fasta, exclusions_bed, archive, policy):
    sources = {
        "fasta": source_checksums(archive, policy["fasta"], "FASTA"),
        "exclusions_bed": source_checksums(exclusions_bed, policy["exclusions_bed"], "Exclusions BED"),
    }
    lengths = {}
    name = None
    with fasta.open() as handle:
        for number, line in enumerate(handle, 1):
            if line.startswith(">"):
                header = line[1:].split()
                if not header:
                    raise ValueError(f"FASTA line {number}: missing sequence name")
                name = header[0]
                if name in lengths:
                    raise ValueError(f"FASTA has repeated contig '{name}'")
                lengths[name] = 0
            elif line.strip():
                if name is None:
                    raise ValueError("FASTA sequence occurs before its first header")
                lengths[name] += len(line.strip())
    if not lengths or any(length == 0 for length in lengths.values()):
        raise ValueError("FASTA must contain nonempty named sequences")
    omitted = []
    with exclusions_bed.open() as source, Path("validated_exclusions.bed").open("w") as target:
        for number, line in enumerate(source, 1):
            if not line.strip() or line.startswith(("#", "track ", "browser ")):
                continue
            fields = line.split()
            if len(fields) < 3:
                raise ValueError(f"Exclusions BED line {number}: expected contig, start, end")
            contig = fields[0]
            try:
                start, end = map(int, fields[1:3])
            except ValueError:
                raise ValueError(f"Exclusions BED line {number}: invalid coordinates; expected integers") from None
            if not 0 <= start < end:
                raise ValueError(f"Exclusions BED line {number}: invalid coordinates {start}:{end}")
            if contig not in lengths:
                omitted.append({"line": number, "contig": contig, "start": start, "end": end,
                                "reason": "Contig missing in FASTA"})
                continue
            if not 0 <= start < end <= lengths[contig]:
                raise ValueError(
                    f"Exclusions BED line {number}: invalid coordinates {start}:{end} "
                    f"for contig '{contig}' of length {lengths[contig]}"
                )
            target.write(f"{contig}\t{start}\t{end}\n")
    Path("validation.json").write_text(json.dumps({
        "contigs": lengths, "omitted_exclusions_bed_entries": omitted, "sources": sources,
    }) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("fasta", type=Path)
    parser.add_argument("exclusions_bed", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("policy")
    args = parser.parse_args()
    try:
        validate(args.fasta, args.exclusions_bed, args.archive, json.loads(base64.b64decode(args.policy)))
    except ValueError as error:
        parser.exit(1, f"Reference input error: {error}\n")
