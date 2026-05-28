#!/usr/bin/env python3
"""
Generate a tiny, deterministic synthetic dataset for ONCOHAWK local testing.

Creates:
  test/data/reference/chr22_subset.fa
  test/data/reads/sample_A_lane1_R{1,2}.fastq.gz
  test/data/reads/sample_A_lane2_R{1,2}.fastq.gz
  test/data/reads/sample_B_lane1_R{1,2}.fastq.gz

The reference is a single 50 kb contig of pseudo-random A/C/G/T (seed=42) so
the output is reproducible across machines. Reads are 150 bp paired-end with
~300 bp insert size, ~30x average depth, with a low (~1%) error rate.

No external dependencies — pure stdlib.
"""

from __future__ import annotations

import gzip
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REF_DIR = REPO_ROOT / "test" / "data" / "reference"
READ_DIR = REPO_ROOT / "test" / "data" / "reads"

REF_NAME = "chr22_subset"
REF_LENGTH = 50_000  # 50 kb is plenty for index + alignment testing
READ_LENGTH = 150
INSERT_SIZE_MEAN = 300
INSERT_SIZE_SD = 30
ERROR_RATE = 0.005
QUAL_CHAR = "I"  # Phred 40

BASES = "ACGT"
COMPLEMENT = str.maketrans("ACGTN", "TGCAN")


def revcomp(seq: str) -> str:
    return seq.translate(COMPLEMENT)[::-1]


def write_fasta(path: Path, name: str, sequence: str, width: int = 60) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        fh.write(f">{name}\n")
        for i in range(0, len(sequence), width):
            fh.write(sequence[i : i + width] + "\n")


def mutate(seq: str, rng: random.Random) -> str:
    out = []
    for b in seq:
        if rng.random() < ERROR_RATE:
            choices = [x for x in BASES if x != b]
            out.append(rng.choice(choices))
        else:
            out.append(b)
    return "".join(out)


def simulate_reads(
    reference: str,
    n_pairs: int,
    seed: int,
    out_r1: Path,
    out_r2: Path,
    read_name_prefix: str,
) -> None:
    rng = random.Random(seed)
    ref_len = len(reference)
    out_r1.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(out_r1, "wt") as fh1, gzip.open(out_r2, "wt") as fh2:
        for i in range(n_pairs):
            insert = max(
                READ_LENGTH + 10,
                int(rng.gauss(INSERT_SIZE_MEAN, INSERT_SIZE_SD)),
            )
            start = rng.randint(0, ref_len - insert - 1)
            frag = reference[start : start + insert]

            r1_seq = mutate(frag[:READ_LENGTH], rng)
            r2_seq = mutate(revcomp(frag[-READ_LENGTH:]), rng)
            qual = QUAL_CHAR * READ_LENGTH
            name = f"{read_name_prefix}:{i + 1}"

            fh1.write(f"@{name} 1:N:0:CGATGT\n{r1_seq}\n+\n{qual}\n")
            fh2.write(f"@{name} 2:N:0:CGATGT\n{r2_seq}\n+\n{qual}\n")


def main() -> None:
    # ── Reference ───────────────────────────────────────────────────────────
    ref_rng = random.Random(42)
    reference = "".join(ref_rng.choices(BASES, k=REF_LENGTH))
    ref_path = REF_DIR / f"{REF_NAME}.fa"
    write_fasta(ref_path, REF_NAME, reference)
    print(f"Wrote reference: {ref_path} ({REF_LENGTH} bp)")

    # ── Reads ───────────────────────────────────────────────────────────────
    # ~30x coverage over 50 kb with 150bp reads -> ~5000 pairs total per sample
    samples = [
        ("sample_A", "lib_A", "FC1ABCXX", "1", 2500, 1001),
        ("sample_A", "lib_A", "FC1ABCXX", "2", 2500, 1002),
        ("sample_B", "lib_B", "FC1ABCXX", "1", 2500, 2001),
    ]
    for sample, library, flowcell, lane, n_pairs, seed in samples:
        prefix = f"{flowcell}:{lane}"
        r1 = READ_DIR / f"{sample}_L00{lane}_R1.fastq.gz"
        r2 = READ_DIR / f"{sample}_L00{lane}_R2.fastq.gz"
        simulate_reads(reference, n_pairs, seed, r1, r2, prefix)
        print(f"Wrote {n_pairs} read pairs for {sample} lane {lane}: {r1.name}, {r2.name}")


if __name__ == "__main__":
    main()
