#!/usr/bin/env python3
"""Prepare immutable offline annotation assets and validate reference compatibility."""

import argparse
import base64
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile

from validate_reference import source_checksums


CACHE_ROOT = PurePosixPath("homo_sapiens_refseq/116_GRCh38")
IUPAC_BASES = {
    ord(code): frozenset(bases) for code, bases in {
        "A": "A", "C": "C", "G": "G", "T": "T", "R": "AG", "Y": "CT",
        "S": "CG", "W": "AT", "K": "GT", "M": "AC", "B": "CGT", "D": "AGT",
        "H": "ACT", "V": "ACG", "N": "ACGT",
    }.items()
}
DNA_ALPHABET = bytes(IUPAC_BASES)


def fasta_index(path):
    """Record byte spans without retaining chromosome-sized sequence strings."""
    records = {}
    name = None
    with path.open("rb") as source:
        while True:
            offset = source.tell()
            line = source.readline(1024 * 1024)
            if not line:
                if name is not None:
                    records[name]["end"] = offset
                break
            if line.startswith(b">"):
                if name is not None:
                    records[name]["end"] = offset
                header = line[1:].split()
                if not header or not line.endswith(b"\n"):
                    raise ValueError(f"invalid FASTA header in {path.name}")
                name = header[0].decode("ascii")
                if name in records:
                    raise ValueError(f"repeated FASTA contig '{name}' in {path.name}")
                records[name] = {"start": source.tell(), "length": 0}
            else:
                sequence = b"".join(line.split()).upper()
                if sequence:
                    if name is None:
                        raise ValueError(f"FASTA sequence before first header in {path.name}")
                    invalid = sequence.translate(None, DNA_ALPHABET)
                    if invalid:
                        coordinate = records[name]["length"] + sequence.index(invalid[:1]) + 1
                        raise ValueError(f"invalid DNA IUPAC symbol {invalid[:1]!r} at {name}:{coordinate} in {path.name}")
                    records[name]["length"] += len(sequence)
    if not records or any(not record["length"] for record in records.values()):
        raise ValueError(f"FASTA must contain nonempty sequences: {path.name}")
    return records


def sequence_chunks(path, record):
    with path.open("rb") as source:
        source.seek(record["start"])
        remaining = record["end"] - record["start"]
        buffer = b""
        while remaining:
            raw = source.read(min(65536, remaining))
            remaining -= len(raw)
            buffer += raw.translate(None, b" \t\r\n\v\f").upper()
            while len(buffer) >= 65536:
                yield buffer[:65536]
                buffer = buffer[65536:]
        if buffer:
            yield buffer


def annotation_name(name):
    if re.fullmatch(r"chr(?:[1-9]|1[0-9]|2[0-2]|X|Y)", name):
        return name[3:]
    if name == "chrM":
        return "MT"
    scaffold = re.fullmatch(r"chr(?:Un|[1-9]|1[0-9]|2[0-2]|X|Y)_((?:GL|KI)\d+)v(\d+)(?:_random)?", name)
    return f"{scaffold[1]}.{scaffold[2]}" if scaffold else name


def compare_references(source_path, masked_path, annotation_path):
    source_index = fasta_index(source_path)
    masked_index = fasta_index(masked_path)
    annotation_index = fasta_index(annotation_path)
    if source_index.keys() != masked_index.keys():
        raise ValueError("masked alignment reference must retain every source contig")
    masking = {}
    for name, record in source_index.items():
        if record["length"] != masked_index[name]["length"]:
            raise ValueError(f"masked alignment reference changed contig length: '{name}'")
        masking[name] = 0
        for source, masked in zip(sequence_chunks(source_path, record),
                                  sequence_chunks(masked_path, masked_index[name])):
            if source != masked:
                for (original, final), count in Counter(zip(source, masked)).items():
                    if original != final:
                        if final != ord("N"):
                            raise ValueError(f"masked alignment reference changed a base without N masking: '{name}'")
                        masking[name] += count
    aliases = {}
    contigs = []
    for name, record in source_index.items():
        candidates = {name, annotation_name(name)} & annotation_index.keys()
        if len(candidates) > 1:
            raise ValueError(f"ambiguous contig aliases for '{name}'")
        if not candidates:
            continue
        target = candidates.pop()
        if target in aliases.values():
            raise ValueError(f"ambiguous contig aliases: more than one alignment contig maps to '{target}'")
        aliases[name] = target
        if record["length"] != annotation_index[target]["length"]:
            raise ValueError(f"contig length mismatch for '{name}' and '{target}'")
        counts = {"alignment": name, "annotation": target, "length": record["length"],
                  "matching_known_bases": 0, "compatible_ambiguous_bases": 0, "source_gap_bases": 0,
                  "annotation_gap_bases": 0, "shared_gap_bases": 0}
        offset = 0
        for source, annotation in zip(sequence_chunks(source_path, record),
                                      sequence_chunks(annotation_path, annotation_index[target])):
            if source == annotation:
                shared = source.count(b"N")
                ambiguous = len(source.translate(None, b"ACGTN"))
                counts["shared_gap_bases"] += shared
                counts["compatible_ambiguous_bases"] += ambiguous
                counts["matching_known_bases"] += len(source) - shared - ambiguous
            else:
                for (left, right), count in Counter(zip(source, annotation)).items():
                    if IUPAC_BASES[left].isdisjoint(IUPAC_BASES[right]):
                        coordinate = offset + next(index for index, pair in enumerate(zip(source, annotation))
                                                   if pair == (left, right)) + 1
                        raise ValueError(f"unexplained genomic-base disagreement at {name}:{coordinate} ({target}:{coordinate})")
                    if left == right == ord("N"):
                        category = "shared_gap_bases"
                    elif left == ord("N"):
                        category = "source_gap_bases"
                    elif right == ord("N"):
                        category = "annotation_gap_bases"
                    elif left == right and left in b"ACGT":
                        category = "matching_known_bases"
                    else:
                        category = "compatible_ambiguous_bases"
                    counts[category] += count
            offset += len(source)
        contigs.append(counts)
    if not aliases:
        raise ValueError("alignment and annotation references have no matching contigs")
    return {
        "aliases": aliases,
        "contigs": contigs,
        "alignment_masked_bases": masking,
        "unmatched_alignment_contigs": {name: record["length"] for name, record in source_index.items()
                                        if name not in aliases},
        "unmatched_annotation_contigs": {name: record["length"] for name, record in annotation_index.items()
                                         if name not in aliases.values()},
        "assembly_gap_policy": "N denotes an unknown assembly base. Source, annotation and shared N positions are counted as gaps. Other IUPAC codes must share a possible base. Compatible ambiguous positions are counted separately from exact A/C/G/T matches.",
    }


def extract_cache(archive_path, destination):
    transcript_blocks = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            relative = PurePosixPath(member.name)
            if (relative.is_absolute() or ".." in relative.parts or
                    not (relative == CACHE_ROOT or CACHE_ROOT in relative.parents or
                         relative == CACHE_ROOT.parent)):
                raise ValueError("expected a human RefSeq cache at homo_sapiens_refseq/116_GRCh38")
            if not (member.isfile() or member.isdir()):
                raise ValueError(f"cache archive must contain only regular files and directories: {member.name}")
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                if len(relative.parts) == 4 and re.fullmatch(r"\d+-\d+\.gz", relative.name):
                    transcript_blocks += 1
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
    info = destination.joinpath(*CACHE_ROOT.parts, "info.txt")
    if not info.is_file():
        raise ValueError("RefSeq cache is missing info.txt; supply a complete release-116 cache")
    metadata = {}
    for line in info.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("\t")
        if not separator or not key or not value or key in metadata:
            raise ValueError("RefSeq cache info.txt contains malformed or repeated metadata")
        metadata[key] = value
    if metadata.get("species") != "homo_sapiens" or metadata.get("assembly") != "GRCh38":
        raise ValueError("cache metadata must identify homo_sapiens / GRCh38")
    if not transcript_blocks:
        raise ValueError("RefSeq cache contains no transcript blocks")
    return metadata


def prepare(source_fasta, masked_fasta, annotation_fasta, annotation_fai,
            annotation_archive, cache_archive, policy):
    sources = {
        "annotation_fasta": source_checksums(annotation_archive, policy["annotation_fasta"], "Annotation FASTA"),
        "vep_cache": source_checksums(cache_archive, policy["vep_cache"], "VEP cache"),
    }
    compatibility = compare_references(source_fasta, masked_fasta, annotation_fasta)
    output = Path("annotation")
    cache_info = extract_cache(cache_archive, output / "cache")
    if not cache_info.get("source_refseq"):
        raise ValueError("RefSeq cache metadata must declare its source_refseq data version")
    shutil.copyfile(annotation_fasta, output / "reference.fa")
    shutil.copyfile(annotation_fai, output / "reference.fa.fai")
    (output / "chr_synonyms.txt").write_text("".join(f"{target}\t{name}\n" for name, target in compatibility["aliases"].items()))
    (output / "compatibility.json").write_text(json.dumps(compatibility, indent=2) + "\n")
    metadata = {
        "software_version": "116.3",
        "container": "community.wave.seqera.io/library/ensembl-vep_perl-math-cdf_htslib_gzip_tar@sha256:2294ff1ab149218bb9337722d3fbde0844a290874c7adec6121ff92d856c3729",
        "module_revision": "20c6e6407f63748003b47f92837b64fb0a53ffa4",
        "cache_version": 116,
        "species": "homo_sapiens_refseq",
        "assembly": "GRCh38",
        "refseq_version": cache_info["source_refseq"],
        "mane_version": "MANE v1.5",
        "mane_version_source": "https://ftp.ensembl.org/pub/release-116/mysql/homo_sapiens_core_116_38/meta.txt.gz",
        "mane_version_source_sha256": "b4755176b563f043c12770ece6e27d7dba729579101d76144732917732b0686e",
        "mane_version_basis": "Ensembl release-116 core metadata; cache info.txt does not declare MANE version",
        "cache_source_versions": {key.removeprefix("source_"): value for key, value in cache_info.items()
                                  if key.startswith("source_")},
        "fasta": "annotation/reference.fa",
        "fasta_index": "annotation/reference.fa.fai",
        "cache": "annotation/cache",
        "synonyms": "annotation/chr_synonyms.txt",
        "compatibility": "annotation/compatibility.json",
    }
    (output / "resource_metadata.json").write_text(json.dumps({
        "annotation": metadata, "sources": sources,
    }, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source_fasta", "masked_fasta", "annotation_fasta", "annotation_fai",
                 "annotation_archive", "cache_archive"):
        parser.add_argument(name, type=Path)
    parser.add_argument("policy", help="Base64-encoded source checksum policy")
    args = parser.parse_args()
    try:
        prepare(args.source_fasta, args.masked_fasta, args.annotation_fasta, args.annotation_fai,
                args.annotation_archive, args.cache_archive,
                json.loads(base64.b64decode(args.policy)))
    except (ValueError, OSError, tarfile.TarError) as error:
        parser.exit(1, f"Annotation input error: {error}\n")
