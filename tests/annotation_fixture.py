"""Inputs for exercising annotation-ready bundles with existing compact references."""

import gzip
from pathlib import Path

CACHE = Path(__file__).parent / "data/vep116/refseq-cache.tar.gz"


def annotation_arguments(directory, source):
    """Keep the original unmasked bases, with Ensembl primary-contig names."""
    data = gzip.decompress(source) if source.startswith(b"\x1f\x8b") else source
    lines = []
    for line in data.decode().splitlines():
        if line.startswith(">chr"):
            name, *description = line[1:].split(maxsplit=1)
            alias = "MT" if name == "chrM" else name[3:]
            line = ">" + alias + (" " + description[0] if description else "")
        lines.append(line)
    fasta = Path(directory) / "annotation.fa"
    fasta.write_text("\n".join(lines) + "\n")
    return ["--annotation_fasta", str(fasta), "--vep_cache", str(CACHE)]
