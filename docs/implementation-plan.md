# Milestone 1 — reference preparation and alignment

Originally proposed for review on 2026-11-01. The [accepted requirements](requirements.md) define scope; the proposed build sequence below is retained as planning history. Implementation was subsequently authorized and completed through the four child issues. The [milestone acceptance record](milestone-1-acceptance.md) maps the completed scope to verified evidence.

Published specification: [milestone 1, issue #1](https://github.com/micknudsen/oncohawk/issues/1).

## Deliverables

Two runnable Nextflow entry points: reference preparation and alignment. Alignment is the first part of the future report-generation workflow. It consumes a prepared reference bundle and one sample sheet, producing one sorted, indexed, duplicate-marked BAM per sample, plus standard tool logs/metrics and version information. Knowledge compilation and everything downstream of alignment remain deferred.

## Execution environments

| Purpose | Environment | Data/reference |
| --- | --- | --- |
| Local development | Mac with Docker | Small synthetic FASTA, matching exclusion BED, and paired reads that fit local memory. |
| Required CI | Containerized test runner | The same compact synthetic fixtures; no full-human-reference job. |
| Production and informal user checks | SLURM HPC with Apptainer | The selected NCBI reference bundle and the user's inputs; HPC checks are not acceptance criteria. |

Keep the workflow logic and pristine modules shared. Profiles configure the executor, container backend, resources, and filesystem settings. Full-human-reference preparation and alignment belong on the HPC; local tests use a small reference as well as small read sets.

## Build sequence

### 1. Establish the project and execution path

Create a minimal Nextflow project, a local Docker profile, a production SLURM/Apptainer profile, and a compact synthetic reference/BED/read fixture. Install suitable nf-core modules through the CLI and pin compatible workflow, module, tool/container, and test-tool versions. Keep all changes outside upstream modules.

Check actual Docker execution early on the Mac, including bwa-mem2 indexing and mapping on the tiny synthetic reference. This Mac reports ARM64; [bwa-mem2's upstream build](https://github.com/bwa-mem2/bwa-mem2/blob/master/Makefile) targets x86 SIMD. Successful execution on this Mac must be demonstrated before claiming local support. Set local resource/concurrency limits to fit available memory. Provide configurable SLURM paths and resource settings for the user's cluster; HPC access and actual execution are not completion prerequisites.

Use protected `master`, required GitHub Actions checks, squash-only merging, and linear history, with focused feature PRs for milestone changes. The empty repository's one-time bootstrap commit and documentation publication were separately authorized on 2026-11-01; subsequent changes enter `master` through PRs. Keep required checks appropriate to each stage and verify their enforcement as they evolve.

### 2. Prepare the reference bundle

Develop reference preparation locally against the small synthetic fixture. Support acquiring the exact NCBI FASTA and BED from Q2 and running decompression, exclusion masking, and bwa-mem2 indexing with the production SLURM/Apptainer profile. Use suitable upstream modules, including [gunzip](https://nf-co.re/modules/gunzip), `bedtools/maskfasta`, and `bwamem2/index`; acquisition and compatibility handling are routine implementation work. The user runs the full-reference path on the HPC; its execution is not an acceptance gate.

Validate the supplied BED against its FASTA during reference preparation. Distinguish intentionally absent ALT sequences from unexpected name/coordinate mismatches, recording any excluded BED entries. Publish the masked FASTA, alignment indexes, and a small provenance file with relative artifact paths, source URLs/checksums, and tool/module versions. Test this behavior with compact fixtures, without requiring a full-reference HPC run. Add further reference assets only when a milestone step needs them.

### 3. Connect the sequencing-to-BAM path

Propose CSV columns `sample,library,flowcell,lane,fastq_1,fastq_2,options`. Validate the accepted input/options rules and derive consistent read-group metadata. Keep task/file identities distinct from biological sample IDs; preserve read-group identity when combining rows and reject conflicting definitions.

Compose the verified modules: shared `cutadapt` → `bwamem2/mem` with sorted BAM output → sample-level `samtools/merge` → `picard/markduplicates` → [samtools/index](https://github.com/nf-core/modules/blob/master/modules/nf-core/samtools/index/main.nf). Configure accepted options outside modules. Preserve library grouping and index the final duplicate-marked BAM. Use ordinary workflow failures for malformed inputs or failed tools; do not publish a failed task's output as a completed sample.

### 4. Verify and document the usable path

Run real reference-to-BAM tests locally with Docker and in required CI, using the compact synthetic reference/BED/read fixtures; production defaults remain the chosen NCBI assets. Provide local test and SLURM/Apptainer reference-preparation/alignment examples. The user checks HPC operation informally during development and reports problems; do not require HPC runs, evidence, or sign-off. Record executed test results accurately and proceed without an HPC blocker when no problem is reported.

## Acceptance checks

The confirmed testing boundaries are the public reference-preparation and alignment interfaces, plus one end-to-end composition test. Observe results and input/tool errors through these interfaces rather than introducing public parser/helper seams.

| Area | Evidence required |
| --- | --- |
| Reference | Expected intervals become `N`; names, lengths, coordinates, and unmasked bases are preserved. Indexes are generated from the resulting FASTA and used successfully. |
| Input handling | Valid rows/options work; missing required metadata and malformed, unknown, or repeated option keys fail clearly. Multiple rows retain the correct sample/library/read-group associations. |
| Preprocessing | Expected adapter removal for R1, R2, both, and neither; pairs with a mate below 15 bp are removed, exactly 15 bp passes, and surviving mates remain synchronized. |
| Mapping | Known synthetic reads map to expected loci. A split-read fixture produces supplementary records with soft clipping and the complete preprocessed sequence. Read-group headers/tags match the input metadata. |
| Duplicates | Designed duplicates spanning lanes in one library are flagged; matching coordinates in distinct libraries are not grouped together. Duplicate reads remain in the BAM. |
| Final output | One BAM per sample, coordinate order verified, final index usable for a regional query, and expected records/flags retained. |

Successful exit codes alone do not satisfy these checks. Required CI grows with the staged PRs: scaffold and reference-preparation PRs run their meaningful checks, and the complete reference-to-BAM fixture becomes required when that path is introduced. Every PR must pass all checks required at its stage. HPC/SLURM/Apptainer tests are never formal acceptance criteria for tickets, PRs, or this milestone; the user's informal checks run alongside development.

## Current verification status

At the initial planning checkpoint on 2026-11-01, module interfaces and relevant tool behavior had been researched in [the design record](design.md), but no bioinformatics workflow, container, or cluster execution had occurred. NCBI file retrieval, final version pins, runtime compatibility, and resource sizing remained implementation checks. Subsequent implementation and validation are recorded below.

Repository bootstrap and branch protection were verified on 2026-11-01. Protection includes administrators, requires PRs and passing up-to-date checks, enforces linear history, and prohibits force pushes and deletion; only squash merging is enabled. The initial documentation check covered whitespace only. Reference preparation, single-input alignment, adapter settings, and multiple-input handling were completed through [PR #8](https://github.com/micknudsen/oncohawk/pull/8), [PR #10](https://github.com/micknudsen/oncohawk/pull/10), [PR #11](https://github.com/micknudsen/oncohawk/pull/11), and [PR #12](https://github.com/micknudsen/oncohawk/pull/12).

At the completed implementation snapshot `ef54b748c57414f8a4526877396f15c4718c516f`, the [CI workflow](../.github/workflows/ci.yml) covered public reference preparation, single- and multiple-input alignment, mixed-adapter reference-to-BAM composition, input/tool failures, and pristine pinned-module verification under **Tests and validation**. The final functional suite passed 34 tests locally and in required CI. [The acceptance record](milestone-1-acceptance.md) provides the dated matrix, exact merge and CI links, and the unperformed full-reference/HPC boundary; [the alignment guide](alignment.md) documents the implemented input and output contracts.
