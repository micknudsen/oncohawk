# OncoHawk pipeline specification

## Scope of this document

This draft defines OncoHawk's intended use, input and reference boundary, and
reporting boundary. It is a target contract and does not describe implemented
or verified analytical behavior.

OncoHawk currently has no analytical implementation, analytical or scientific
validation, or release. No claim is made that it is clinical-grade or
suitable for patient-care decisions.

## Intended use

OncoHawk is intended to analyze tumor-only whole-genome sequencing data for
acute myeloid leukemia (AML) and myelodysplastic syndromes (MDS). Matched-normal
analysis is outside the current target contract.

The intended final output is a clinician-readable report of genomic findings
selected using approved curated resources for:

- genes associated with AML or MDS;
- known hotspot variants; and
- known recurrent translocations.

These resources will inform prioritization for report inclusion. Their exact
contents, evidence requirements, representation, and inclusion logic remain
open.

## Input boundary

The target contract accepts tumor-only whole-genome sequencing input as
standard gzip-compressed, paired-end FASTQ files (`.fastq.gz`). Each input
record must provide separate, non-interleaved R1 and R2 files. SPRING-compressed
FASTQ is outside the current target contract and may be considered in a later
increment.

One submitted sample represents one tumor specimen. Multiple library and lane
records may refer to that sample. The future sample-sheet contract will have
one row per library and lane and require these fields:

- `case_id`;
- `sample_id`;
- `specimen_id`;
- `library_id`;
- `lane_id`;
- `read_group_id`;
- `fastq_r1`; and
- `fastq_r2`.

This document does not define identifier content, data-governance rules, or
whether an identifier is pseudonymous. It requires only the listed fields.

The contract does not require a separate, full-file preflight scan to establish
read-name or pair consistency before processing begins. It does require that
each input record provide both members of the stated paired-end file set.

The target contract is developed with Illumina paired-end data in mind. Paired-
end data from other platforms may be accepted, but their use is unvalidated and
no performance claim is made for them. Read length and insert size are not
constrained by this contract.

Matched-normal inputs and non-whole-genome inputs are outside the target
contract and are to be rejected. Aligned reads and other non-FASTQ input forms
are also outside the target contract.

## Reference contract

The target reference is the NCBI GCA_000001405.15 GRCh38 no-alt analysis set
with UCSC-style sequence identifiers:

- [GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz](https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz),
  NCBI MD5 `a08035b6a6e31780e96a34008ff21bd6`;
- [GCA_000001405.15_GRCh38_GRC_exclusions.bed](https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_GRC_exclusions.bed),
  NCBI MD5 `bf5c011e0342f355422144eb3547b5d0`.

The reference used by a future implementation must be derived by replacing
each interval in the exclusions BED with `N` bases in the source FASTA. This
masking preserves the source GRCh38 coordinate system. The downloaded source
artifacts must be verified against the pinned checksums, and the checksum of
the derived masked reference must be recorded for each reference build.

## Reporting boundary

The final report is intended for clinicians. It is not intended to be a
technical report for bioinformatics specialists.

The report will not provide:

- a diagnosis;
- a prognosis;
- a treatment recommendation; or
- patient-specific clinical interpretation.

The project does not define or validate downstream clinical review, sign-out,
or decision-making workflows.

## Open matters

This document does not yet decide:

- supported variant classes or analytical methods;
- the contents, evidence hierarchy, provenance, release process, or retirement
  process for curated resources;
- transcript or annotation requirements;
- reporting thresholds, prioritization rules, or the report schema;
- technical, audit, or downstream machine-readable outputs;
- runtime or execution architecture;
- engineering-test requirements;
- analytical and scientific validation requirements;
- regulatory and quality-management requirements; or
- release criteria.
