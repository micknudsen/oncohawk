# Oncohawk — milestone 1 requirements

Fresh design session started 2026-11-01. This file records the restart brief and decisions accepted in this session. Proposals belong in [design.md](design.md).

Q1–Q8 and the execution-environment clarification establish the agreed milestone scope. The [implementation plan](implementation-plan.md) proposes the build sequence and acceptance checks for review.

The [public workflow architecture review](design.md#public-workflow-architecture-review--2026-11-10), confirmed on 2026-11-10, updates the required entrypoints and output organization below. At the design checkpoint, the migration was accepted but implementation had not been authorized or started. Later that day, the user authorized sequential implementation, PR creation, correction of CI failures, and merging after all CI tests pass. The first implementation slice, [#26](https://github.com/micknudsen/oncohawk/issues/26), replaces the pipeline-directory interfaces with the root dispatcher while temporarily retaining flat BAM/index publication under `alignments`. The final output organization below remains the accepted requirement, delivered by #27 and #28.

The implementation-ready architecture specification is [GitHub issue #25](https://github.com/micknudsen/oncohawk/issues/25).

The synthesized milestone specification is published as [GitHub issue #1](https://github.com/micknudsen/oncohawk/issues/1).

## Scope

Oncohawk is a Nextflow workflow for tumor-only short-read DNA WGS analysis of blood cancers. Milestone 1 prepares a reusable reference bundle containing only alignment assets and produces a usable alignment from sequencing inputs. Include only the preprocessing, validation, provenance, and modest synthetic execution tests needed for that path. The alignment path requires no knowledge bundle.

## Architecture

- **`prepare_reference_bundle`:** prepares reusable reference assets and tool indexes with provenance.
- **`prepare_knowledge_bundle`:** compiles human-authored biological/reporting knowledge against a reference bundle. Deferred beyond milestone 1; selecting it must immediately fail with a clear not-yet-implemented error until it exists.
- **`oncohawk`:** consumes sequencing data and prepared bundles, maps reads, analyzes variants, and produces a report for expert review. Only its alignment portion is in milestone 1, requiring no knowledge bundle yet.

A shared root `main.nf` selects exactly one workflow per invocation. `--workflow` selects among these three names; omission defaults to `oncohawk`. Bundle preparation is explicit and is not automatically chained into analysis. The root dispatcher replaces the standalone reference/alignment entrypoints without compatibility wrappers.

Each workflow has its own implementation under `workflows/`. Root `nextflow.config` selects shared and workflow-specific settings from `conf/`, preserving process-selector isolation. Modules remain shared and upstream nf-core modules remain pristine. Reference source provenance includes relevant shared sources while excluding analysis-only sources.

The intended later topology is mapping followed by parallel SNV/INDEL, SV, and CNA branches, then report generation. Each variant branch supports one or more callers, reconciles results into a consistent output for its class, and annotates that output. VEP is an example to consider; downstream callers, reconciliation, annotations, schemas, and report content remain open.

## Alignment

Use **bwa-mem2** for milestone 1 and include its reference indexes in the reference bundle. Use the suitable upstream nf-core indexing and mapping modules under the development constraints below. Accepted in [Q1](design.md#q1--aligner-for-milestone-1).

Enable `-Y` for supplementary soft clipping and supply each FASTQ pair's read-group header through `-R`; otherwise retain default mapping settings. Supplementary records retain the complete read supplied after preprocessing. Accepted in [Q8](design.md#q8--mapping-settings).

### Reference preparation

Use these exact NCBI resources, selected in [Q2](design.md#q2--reference-for-milestone-1):

- [GRCh38 no-ALT analysis-set FASTA, UCSC sequence IDs](https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz).
- [Matching GRC exclusions BED](https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_GRC_exclusions.bed).

Hard-mask the exclusion intervals with `N` bases before generating alignment indexes. The bundle's alignment FASTA and bwa-mem2 indexes must represent the same masked sequence. Preserve sequence names, lengths, and coordinates. Skip exclusions BED entries whose contig is absent from the FASTA and record every skipped entry in `omitted_exclusions_bed_entries` with reason `"Contig missing in FASTA"`. Malformed intervals and out-of-bounds coordinates on existing contigs remain errors. The GENCODE FASTA proposal was not adopted.

### Sequencing inputs

Accept one sample sheet with one row per gzipped paired-end FASTQ pair. Each row supplies R1/R2 paths, sample ID, library ID, flowcell, and lane. Each pair contains reads belonging to one read group; multiple rows may belong to the same sample. Accepted in [Q3](design.md#q3--sequencing-input-interface).

An optional `options` column contains semicolon-separated `key=value` entries. Initially supported keys are `r1_adapter` and `r2_adapter`. Blank cells are allowed; malformed entries, unknown keys, and repeated keys fail validation. Accepted in [Q4](design.md#q4--optional-row-settings).

### Read preprocessing

Process every input pair through one shared, pristine nf-core Cutadapt step. Remove explicitly supplied regular 3′ adapters: `r1_adapter` applies to R1 and `r2_adapter` to R2; either may be supplied alone. Skip adapter removal when neither is supplied. Do not infer adapter sequences automatically. Accepted in [Q5](design.md#q5--adapter-removal).

After optional adapter removal, require both mates to be at least 15 bp. Discard the whole pair if either mate is shorter; exactly 15 bp passes. Apply this rule to all inputs, including already-trimmed reads and rows without adapter settings. The shared Cutadapt step performs length filtering alone when no adapters are supplied. Do not add quality trimming in milestone 1. Accepted in [Q6](design.md#q6--minimal-read-filtering).

### Alignment output

Produce one coordinate-sorted, indexed BAM per sample, combining the sample's rows and preserving read groups. Mark duplicates per library: consider reads across lanes/read groups of the same library together, and keep distinct libraries separate for duplicate detection. Retain duplicate reads with their flags set. Accepted in [Q7](design.md#q7--alignment-deliverable).

The confirmed architecture migration makes `results` the default analysis output root, overridable with `--outdir`. Publish `<sample>.bam` and `<sample>.bam.bai` under `results/samples/<sample>/alignments/`. Future sample-specific variants and reports belong within the same sample directory; any enabled run-wide diagnostics or summaries belong under `results/execution/`. This organization does not introduce new diagnostic generation or empty placeholder directories. Reference preparation retains its default `reference` destination.

## Execution environments

- **Development:** local Mac with Docker. Use small synthetic reference sequences, a matching exclusion BED, and synthetic paired reads. Local development and tests must fit the Mac's memory; do not require full-human-reference bwa-mem2 indexing or alignment locally.
- **Production:** SLURM HPC with Apptainer. Support preparation of the full selected NCBI reference bundle and full-reference alignment here.

Use the same workflow logic and pristine modules in both environments, with execution profiles supplying environment-specific settings and test fixtures supplying the smaller local data. Conda execution is unsupported. Clarified directly by the user on 2026-11-01.

Formal acceptance uses compact synthetic tests on the development Mac with Docker and in required CI. The user checks SLURM/Apptainer operation informally during development and reports problems. HPC execution, access, run evidence, or explicit sign-off must never be required for ticket acceptance, merging, or milestone completion. In the absence of reported problems, continue without an HPC blocker; this is not a claim that the agent verified an HPC run. Clarified directly by the user during ticket planning on 2026-11-01.

## Development constraints

- Prefer suitable nf-core modules installed through the nf-core CLI, with pinned revisions. Keep upstream modules pristine; configure and compose them externally.
- Propose custom modules only when suitable upstream modules and supported composition cannot meet the milestone's requirements.
- Prioritize correctness and testability. Optimize only when measurements justify it; do not fuse separate modules into custom Unix pipelines for runtime or I/O optimization. Existing pipes inside upstream modules are permitted.
- Use protected `master`, focused feature branches and PRs, required passing GitHub Actions checks, squash merges, and linear history. Verify actual enforcement as required checks evolve.
- Exercise real reference preparation and mapping with modest synthetic data and meaningful assertions.
- Test the public reference-preparation and alignment workflow boundaries, plus one end-to-end composition test. Assert observable artifacts and error behavior rather than private helper structure. These testing boundaries were confirmed during spec synthesis.
- Follow the development/production split above and limit environment work to this milestone.

## Session boundary

Work in English, one focused question at a time. Stop planning when the inputs, outputs, necessary tools, and acceptance checks support a small implementation plan. Research and documentation are authorized; implementation and repository-setting changes require a separate instruction.
