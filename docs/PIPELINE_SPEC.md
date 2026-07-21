# OncoHawk pipeline specification

## Scope of this document

This draft defines OncoHawk's intended use, input and reference boundary,
variant-class boundary, and reporting boundary. It is a target contract and
does not describe implemented or verified analytical behavior.

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

One analysis represents one tumor sample. A single run may include multiple
independent samples from multiple patients. Multiple library, flowcell, and
lane records may refer to one sample.

### Sample-sheet contract

The future sample sheet is a headered CSV file with these exact columns in this
order:

```csv
patient_id,sample_id,filetype,info,filepath
```

`patient_id` and `sample_id` are required. A patient may have multiple samples,
including longitudinal samples. Each `sample_id` is globally unique and maps to
exactly one `patient_id`; it may occur in multiple library, flowcell, and lane
rows. This document does not define identifier content or data-governance rules.

`filetype` is required and must be `fastq` in the current target contract. The
field is retained so that a future, separately approved contract may define
other input types. It does not grant current BAM, CRAM, or SPRING support.

`info` is a required, semicolon-separated list of `key:value` entries. It must
contain exactly one of each required key:

- `library_id`;
- `flowcell_id`; and
- `lane`.

It may contain one `platform` entry. If omitted, `platform` is `ILLUMINA`.
No other keys are permitted by the current target contract. The platform
vocabulary beyond the default is not decided here; a supplied value must be
non-empty.

`filepath` is required and contains exactly two semicolon-separated paths: R1
then R2. Both paths must name non-interleaved `.fastq.gz` files. Relative paths
are resolved from the directory containing the sample sheet.

The tuple (`sample_id`, `library_id`, `flowcell_id`, `lane`) must be unique.
The sample sheet does not contain a read-group identifier. A future pipeline
will construct GATK-compatible read groups deterministically from the sample,
library, flowcell, lane, and platform metadata. It will set sample (`SM`) from
`sample_id`, library (`LB`) from `library_id`, and platform (`PL`) from the
provided or defaulted platform value. The exact serialization of the generated
read-group ID (`ID`) and platform unit (`PU`) remains an implementation matter.

The target contract requires structural validation of the exact headers,
required fields, `filetype`, `info` grammar and keys, path-pair grammar, sample
to patient mapping, and the unique tuple. It does not require a file-existence,
readability, or FASTQ-content scan.

Valid synthetic example:

```csv
patient_id,sample_id,filetype,info,filepath
patient_001,sample_001,fastq,library_id:lib_A;flowcell_id:FC123;lane:001,fastq/sample_001/lib_A_FC123_L001_R1.fastq.gz;fastq/sample_001/lib_A_FC123_L001_R2.fastq.gz
patient_001,sample_001,fastq,library_id:lib_A;flowcell_id:FC123;lane:002,fastq/sample_001/lib_A_FC123_L002_R1.fastq.gz;fastq/sample_001/lib_A_FC123_L002_R2.fastq.gz
patient_001,sample_002,fastq,library_id:lib_B;flowcell_id:FC456;lane:001;platform:ILLUMINA,fastq/sample_002/lib_B_FC456_L001_R1.fastq.gz;fastq/sample_002/lib_B_FC456_L001_R2.fastq.gz
patient_002,sample_003,fastq,library_id:lib_C;flowcell_id:FC789;lane:001,fastq/sample_003/lib_C_FC789_L001_R1.fastq.gz;fastq/sample_003/lib_C_FC789_L001_R2.fastq.gz
```

Examples of structural failures include a repeated
(`sample_id`, `library_id`, `flowcell_id`, `lane`) tuple; one `sample_id`
mapped to different patients; a missing `library_id`, `flowcell_id`, or `lane`;
an unrecognized `info` key; a non-`fastq` filetype; or a `filepath` value that
does not contain exactly two `.fastq.gz` paths in R1/R2 order.

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

## Variant and MVP reporting boundary

The target contract requires genome-wide calling of single-nucleotide variants
(SNVs), insertions and deletions (indels), and structural variants (SVs).
Genome-wide call sets must be retained so that a sample can be re-analysed
against updated approved resources without repeating variant calling. The exact
formats and retention requirements for these call sets remain open.

The MVP report contains two finding categories: **Variants** and
**Translocations**. These are biological reporting categories, not partitions
based on variant size or a caller's representation. Report inclusion is limited
to findings matched by approved predefined resources.

**Variants** contains findings that annotation predicts will affect one gene
and that match an approved AML/MDS gene or hotspot resource. This category may
include SNVs, indels, and single-gene events represented by an SV caller. For
example, an `FLT3` internal tandem duplication or a `KMT2A` partial tandem
duplication belongs in **Variants**, irrespective of its underlying caller
representation. The exact annotation consequences, transcript policy,
resources, and inclusion rules remain open.

**Translocations** contains events predicted to join gene partners that match
an approved predefined recurrent-fusion resource. Inclusion is independent of
whether the underlying event is represented as a BND, deletion, duplication,
inversion, or another suitable SV representation. Genome-wide SV calls are
retained, but novel or otherwise potentially interesting fusions outside the
predefined resource are not included in the MVP report.

Copy-number alterations (CNAs, also called CNVs) are deferred. Reliable
tumor-only CNA analysis requires a separately designed read-depth background,
including an appropriate panel of normals. The panel's construction,
provenance, matching requirements, and validation remain open. Because CNA
analysis is outside the MVP, the MVP report omits a CNA section.

Handling of potentially germline findings is not defined by this variant-class
boundary and remains a separate matter spanning calling and filtering.

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

- analytical methods, tools, or caller-specific representations;
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
