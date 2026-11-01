# Oncohawk — alignment milestone design

Fresh session started 2026-11-01. The [requirements](requirements.md) contain the accepted restart brief. This document tracks only decisions needed for milestone 1.

**Status: milestone-1 scope decisions complete through Q8.** The [implementation plan](implementation-plan.md) is ready for review. No further interview question is pending; implementation is not yet authorized.

The milestone spec is published as [GitHub issue #1](https://github.com/micknudsen/oncohawk/issues/1), with the confirmed workflow-level testing boundaries.

The user's subsequent [execution-environment clarification](#execution-environment-clarification--2026-11-01) is also accepted.

## Minimal path

```text
NCBI FASTA + GRC exclusions BED -> mask reference -> prepare bwa-mem2 indexes -> reference bundle
Sequencing inputs -> Cutadapt (optional adapters + length filtering) -> mapping with reference bundle
  -> combine sample rows -> library-aware duplicate marking -> coordinate-sorted, indexed BAM per sample
```

The aligner, reference inputs, sequencing-input layout, preprocessing, mapping settings, and alignment deliverable are settled in Q1–Q8. The implementation plan groups the remaining routine choices and concrete acceptance checks.

## Decision dependencies

- Reference and aligner choices determine reference-bundle assets.
- Input and read-group requirements determine necessary preprocessing and mapping inputs.
- Alignment output requirements determine finishing steps and acceptance assertions.

Discuss one consequential unresolved decision at a time. Stop when this path is actionable; routine implementation details do not need individual questions.

## Q1 — Aligner for milestone 1

**Status: accepted on 2026-11-01.**

Should we use **bwa-mem2** for milestone 1?

Decision: use bwa-mem2. nf-core provides [reference indexing](https://nf-co.re/modules/bwamem2_index) and [mapping](https://github.com/nf-core/modules/blob/master/modules/nf-core/bwamem2/mem/main.nf) modules, providing a path that can use pristine upstream modules. The initial reference bundle will contain bwa-mem2 indexes.

Module support was checked against primary sources on 2026-11-01. Local Mac/Docker execution has not been tested. Q2 settles the reference inputs, Q7 the output contract, and Q8 the mapping settings.

## Q2 — Reference for milestone 1

**Status: accepted with the user's replacement on 2026-11-01.**

Decision: use the exact NCBI GRCh38 no-ALT analysis-set FASTA and matching GRC exclusions BED linked in [requirements](requirements.md#reference-preparation). Hard-mask the excluded regions with `N` bases before indexing, preserving sequence names, lengths, and coordinates. The masked sequence is the alignment reference.

The user replaced the proposed GENCODE primary-assembly FASTA with these explicit resources. No GENCODE reference was accepted. Both sources use the GRCh38 assembly, but different reference distributions must not be assumed interchangeable.

The earlier proposal was based on [GENCODE's primary-assembly download](https://www.gencodegenes.org/human/release_49.html). Reference preparation remains limited to alignment assets; no annotation resources are added.

Implementation evidence checked on 2026-11-01: [nf-core bedtools/maskfasta](https://nf-co.re/modules/bedtools_maskfasta/) accepts FASTA and BED inputs. [Bedtools documentation](https://bedtools.readthedocs.io/en/latest/content/tools/maskfasta.html) specifies `N` replacement as the default, with matching sequence IDs required. This supplies a suitable upstream step before index generation; no module was installed or run.

Reference evidence: [UCSC's support discussion reproducing NCBI's README](https://groups.google.com/a/soe.ucsc.edu/g/genome/c/RI7uDc7oG80) describes existing analysis-set masking, including chrY pseudoautosomal regions. The requested GRC exclusions add corrections for false duplications and contamination ([GRC explanation](https://genomeref.blogspot.com/2021/07/one-of-these-things-doest-belong.html)); the [U2AF1 study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8950341/) documents applying this mask with bedtools and reindexing. These corrections are separate from the analysis set's existing masks.

Verification limit: direct NCBI FTP access was unavailable during research. No full FASTA download, sequence-level comparison with GENCODE, BED-byte inspection, or checksum validation was performed. Check actual BED sequence membership when preparing the bundle: GRC's broader correction description includes an ALT scaffold that a no-ALT reference may omit.

## Q3 — Sequencing-input interface

**Status: accepted on 2026-11-01.**

Should milestone 1 accept a single sample sheet with one row per gzipped paired-end FASTQ pair and its read-group metadata?

Decision: use one sample sheet. Each row identifies R1/R2 files, sample, library, flowcell, and lane. Multiple rows may belong to the same sample. Each pair must contain reads belonging to one read group. This provides the mapping inputs and grouping information together; the exact sheet syntax and derived read-group values can be specified in the implementation plan.

The user also suggested an optional key-value column for additional row settings, such as adapter sequences. Q4 makes that suggestion concrete without selecting trimming behavior.

## Q4 — Optional row settings

**Status: accepted on 2026-11-01.**

Should we add an optional `options` column containing semicolon-separated `key=value` entries and accepting only documented keys?

Decision: add the optional `options` column. Initially support `r1_adapter` and `r2_adapter`. Allow blank cells; reject malformed entries, unknown keys, and repeated keys. An illustrative cell is:

```text
r1_adapter=AGATCGGAAGAGC;r2_adapter=AGATCGGAAGAGC
```

This decision settles serialization and basic validation only; Q5 settles adapter removal and per-mate settings. Q6 settles read filtering. Routine parser details belong in the implementation plan rather than separate interview questions.

## Q5 — Adapter removal

**Status: accepted on 2026-11-01.**

Should we use Cutadapt for adapter removal only when adapter sequences are supplied in the sample sheet?

Decision: use the pristine nf-core Cutadapt module. Treat `r1_adapter` and `r2_adapter` as regular 3′ adapter sequences for their respective mates. Either may be supplied alone. Remove the supplied adapters; when neither is supplied, skip adapter removal. Do not infer adapter sequences automatically. Q6 separately defines length and quality-filtering policy and confirms that the shared Cutadapt step still runs without adapters.

Primary sources checked on 2026-11-01: the [nf-core module](https://github.com/nf-core/modules/blob/master/modules/nf-core/cutadapt/main.nf) forwards configurable arguments and adds no length/quality filter by default. [Cutadapt's paired-end documentation](https://cutadapt.readthedocs.io/en/stable/guide.html#trimming-paired-end-reads) supports `-a` for R1 and `-A` for R2, including either alone. [Filtering documentation](https://cutadapt.readthedocs.io/en/stable/guide.html#filtering-reads) confirms that adapter removal alone retains reads even when trimmed to zero length. No filtering threshold or exact tool/module version is selected by this decision.

## Q6 — Minimal read filtering

**Status: accepted on 2026-11-01.**

Should we require both mates to be at least **15 bp** after optional adapter removal, with no additional quality trimming in milestone 1?

Decision: discard the whole pair if either mate is shorter than 15 bp; exactly 15 bp passes. Apply the same rule to every input pair, including already-trimmed reads and rows without adapter settings. Use one shared, pristine nf-core Cutadapt step for all rows. This removes empty/very short reads and keeps preprocessing consistent while preserving pairs. Do not add quality trimming in milestone 1.

Implementation evidence checked on 2026-11-01: [Cutadapt's guide](https://cutadapt.readthedocs.io/en/stable/guide.html#filtering-reads) documents length filtering after read modifications and pair removal with `-m 15 --pair-filter=any`; quality trimming requires a separate option. Filtering without adapters is supported ([official changelog](https://cutadapt.readthedocs.io/en/stable/changes.html#v1-7-2014-11-25)). The 15 bp threshold is the accepted workflow policy, not a Cutadapt requirement or an established optimal threshold.

The user asked whether inputs without adapters could share the same step. Yes: configure the module's supported `task.ext.args` per row, always including `-m 15 --pair-filter=any` and adding `-a`/`-A` only for supplied adapters. The [upstream module source](https://github.com/nf-core/modules/blob/master/modules/nf-core/cutadapt/main.nf) supports this without modification or a custom preprocessing module. Illustrative adapter-free command:

```sh
cutadapt -m 15 --pair-filter=any \
  -o R1.filtered.fastq.gz -p R2.filtered.fastq.gz \
  R1.fastq.gz R2.fastq.gz
```

This is a documented command shape, not an executed test. The nf-core module supplies threads, output names, and logging.

## Q7 — Alignment deliverable

**Status: accepted on 2026-11-01.**

Should milestone 1 produce one coordinate-sorted, indexed BAM per sample, with duplicates marked per library?

Decision: combine the sample's rows while preserving read groups. Detect duplicates across lanes/read groups belonging to the same library, keep different libraries separate for duplicate detection, and retain duplicate reads with their flags set. Produce one coordinate-sorted, indexed BAM per sample. This defines the sample-level alignment endpoint.

Primary sources checked on 2026-11-01: nf-core provides [samtools/merge](https://nf-co.re/modules/samtools_merge) and [picard/markduplicates](https://nf-co.re/modules/picard_markduplicates). [Picard's library-ID implementation](https://github.com/broadinstitute/picard/blob/master/src/main/java/picard/sam/markduplicates/util/LibraryIdGenerator.java) uses read-group `LB` values to identify libraries. Duplicate marking must see all relevant reads from a library together; exact module composition remains an implementation detail.

## Q8 — Mapping settings

**Status: accepted on 2026-11-01.**

Should mapping enable supplementary soft clipping with `-Y`, assign each FASTQ pair's read-group header with `-R`, and otherwise use bwa-mem2's default mapping settings?

Decision: enable `-Y`, supply read-group headers through `-R`, and otherwise use default mapping settings. Soft clipping retains the complete read supplied to the aligner in supplementary records, including clipped bases. Here that means the preprocessed read, after any adapter removal. Read-group headers carry the agreed sample/library metadata into the BAM. Resource settings and supported module configuration remain implementation details.

Primary sources checked on 2026-11-01: [bwa-mem2's options](https://github.com/bwa-mem2/bwa-mem2/blob/master/src/fastmap.cpp#L588-L603) document `-Y` and `-R`; the [nf-core mapping module](https://github.com/nf-core/modules/blob/master/modules/nf-core/bwamem2/mem/main.nf#L24-L44) accepts both through `task.ext.args`. No module modification is needed. The next step is review of the small implementation plan, rather than more routine option questions.

## Execution-environment clarification — 2026-11-01

The user clarified that development takes place locally on a Mac using Docker and synthetic data; the Mac lacks memory for bwa-mem2 on the entire human reference. Production runs on a SLURM HPC with Apptainer. Recorded this directly in [requirements](requirements.md#execution-environments) and the [plan](implementation-plan.md#execution-environments), without reopening the interview.

Local tests use a small synthetic reference, matching BED, and reads. Full NCBI reference preparation and alignment target the HPC. Workflow logic and upstream modules stay shared, with profiles and test inputs providing the environment/data differences. ARM64 container compatibility remains an early local check independent of the reduced-reference memory footprint.

## Testing-boundary confirmation — 2026-11-01

During the explicitly requested to-spec synthesis, the user confirmed two public testing boundaries: reference inputs to a prepared reference bundle, and a prepared bundle plus sample sheet/FASTQs to final BAMs. Add one end-to-end composition test and assert observable outputs/errors rather than private helper structure. This confirms the testing approach without reopening the milestone interview or selecting implementation internals.

## HPC acceptance clarification — 2026-11-01

During ticket planning, the user specified that they will check SLURM/Apptainer operation informally along the way and report problems. HPC tests must never be formal acceptance criteria. Removed the proposed standalone HPC-verification ticket; production profiles and usage instructions belong to the reference-preparation and alignment slices.

Formal workflow acceptance remains based on compact synthetic tests with Docker locally and in required CI. Do not wait for HPC access, results, or sign-off to complete tickets or the milestone. No reported HPC problem means no HPC blocker; record actual evidence accurately without calling silence a verified run. This clarification supersedes the earlier proposal for a required full-reference HPC verification run.

## Deferred

Knowledge compilation, variant calling, variant reconciliation, annotation, reporting, and their resources remain outside this milestone.
