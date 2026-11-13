# Align samples from paired FASTQs

The Oncohawk workflow, selected by `nextflow run .` or explicitly by `nextflow run . --workflow oncohawk`, accepts a [prepared reference bundle](reference-bundle.md) and a sample sheet with one row per gzipped FASTQ pair. It applies shared Cutadapt adapter removal and length filtering, maps each pair with bwa-mem2, and combines rows into one coordinate-sorted, indexed BAM per sample. Duplicate detection considers all lanes of each library together, keeps distinct libraries separate, and retains duplicate records with their flags set.

It consumes the prepared reference bundle without running bundle preparation, and it requires no knowledge bundle for this alignment milestone. Relative paths passed to `--input`, `--reference_bundle`, and `--outdir` resolve from the launch directory; paths within the sample sheet follow the rule below. Replace `.` with the checkout path when launching outside it.

## Sample sheet

Use a CSV file with these required columns in any order and at least one data row. A single pair remains supported:

```csv
sample,library,flowcell,lane,fastq_1,fastq_2
S1,L1,FC1,1,/data/S1_R1.fastq.gz,/data/S1_R2.fastq.gz
```

`sample`, `library`, `flowcell`, and `lane` identify the biological and sequencing inputs. Each must match `[A-Za-z0-9][A-Za-z0-9_.-]*`: start with an ASCII letter or digit, followed by letters, digits, underscores, periods, or hyphens. Missing required values and duplicate or unknown column headers fail validation.

Distinct sample IDs must also differ when compared without letter case: `S1` and `s1` cannot coexist in one sheet. This keeps their published BAM and index filenames distinct on case-insensitive filesystems, including the development Mac. Accepted sample names retain their original case; multiple rows with exactly the same sample ID are expected.

`fastq_1` and `fastq_2` identify the corresponding gzipped mate files. Relative paths resolve from the sample-sheet directory, not the launch directory. Each filename must end in `.gz` and match the same safe-character pattern above. Wildcards, using the same file for both mates, and mates with the same basename are rejected. Different rows may use the same basenames in different directories. Missing files and malformed or unusable sequencing inputs fail the workflow.

Each canonical FASTQ path may occur only once anywhere in the sheet, including as the other mate or through a symlink alias. Reusing an input fails even if its metadata is unchanged: this prevents double-counting and assigning the same sequencing input to conflicting samples or read groups. Separate FASTQ chunks with the same sample, library, flowcell, and lane are allowed when their files are distinct.

The optional `options` column contains semicolon-separated `key=value` entries. Only `r1_adapter` and `r2_adapter` are supported; either may be supplied alone. Options apply only to their own row. This example combines two lanes of `S1` library `L1`, a second library for `S1`, and a separate sample that also uses the label `L1`:

```csv
sample,library,flowcell,lane,fastq_1,fastq_2,options
S1,L1,FC1,1,/data/S1_L1_lane1_R1.fastq.gz,/data/S1_L1_lane1_R2.fastq.gz,
S1,L1,FC1,2,/data/S1_L1_lane2_R1.fastq.gz,/data/S1_L1_lane2_R2.fastq.gz,r1_adapter=AGATCGGAAGAGC
S1,L2,FC2,1,/data/S1_L2_R1.fastq.gz,/data/S1_L2_R2.fastq.gz,r2_adapter=CTGTCTCTTATACACATCT
S2,L1,FC3,1,/data/S2_L1_R1.fastq.gz,/data/S2_L1_R2.fastq.gz,r1_adapter=AGATCGGAAGAGC;r2_adapter=CTGTCTCTTATACACATCT
```

| `options` cell | Adapter removal |
| --- | --- |
| `r1_adapter=AGATCGGAAGAGC` | R1 only; R2 sequence is unchanged. |
| `r2_adapter=CTGTCTCTTATACACATCT` | R2 only; R1 sequence is unchanged. |
| `r1_adapter=AGATCGGAAGAGC;r2_adapter=CTGTCTCTTATACACATCT` | Each mate uses its supplied adapter. |
| Blank cell or omitted column | No adapter removal; length filtering still applies. |

Adapter values are nonempty DNA IUPAC sequences (`ACGTRYSWKMBDHVN`, case-insensitive). Whitespace around entries, keys, and values is ignored; whitespace inside a sequence is invalid. Keys are case-sensitive. Empty keys or values, missing or extra `=`, empty entries (including a trailing `;`), unknown keys, and repeated keys fail clearly. Cutadapt syntax such as anchoring (`$`), linked adapters (`...`), adapter files, or extra command-line flags is not accepted as a sequence.

Read-group values are derived consistently from the row:

| SAM field | Value |
| --- | --- |
| `ID` | `rg_` followed by unpadded base64url encoding of the compact JSON array `[sample,library,flowcell,lane]`. |
| `SM` | Sample value. |
| `LB` | Library value. |
| `PU` | Flowcell and lane joined with a period, for example `FC1.1`; literal periods within either component are escaped as `%2E`. |

The same `ID` appears in the header and each read's `RG` tag. The encoded identity keeps sample/library/flowcell/lane boundaries unambiguous. Distinct FASTQ chunks with the same four values share one identical read-group definition; changing any value gives a distinct read-group ID. Library labels are scoped to their sample, so `S1/L1` and `S2/L1` never participate in duplicate detection together.

Internal row identities are hashes of the read-group tuple and canonical mate paths, independent of CSV row order. Internal output names begin with `_`, outside the accepted source-basename and public-identifier namespace. This keeps intermediate outputs from overwriting staged input symlinks or colliding with final sample filenames.

CUTADAPT and BWAMEM2_MEM task labels use `sample / library / flowcell / lane / <12-character hash>` in the console, trace, and execution reports. The suffix is the first 12 characters of the internal row hash, distinguishing separate FASTQ pairs from the same sample/library/flowcell/lane. Both tasks retain the same label for a pair, including when sample-sheet rows are reordered. Display labels are configured separately from the full internal IDs and intermediate filenames; the nf-core modules remain unchanged.

## Local Docker execution

Use the [pinned development runtimes](reference-bundle.md#runtime-pins) and a running Docker installation. Prepare a compact bundle and matching gzipped read pairs, then run from the checkout:

```bash
nextflow run . -profile docker,test \
  --input /path/to/samples.csv \
  --reference_bundle /path/to/prepared-bundle \
  --outdir /path/to/new-results
```

`--reference_bundle` points to the directory containing `bundle.json`, `reference.fa`, and its bwa-mem2 indexes. `--outdir` must be a fresh output directory. The Docker profile selects `linux/amd64` containers, including on Apple Silicon; the test profile limits local execution to two CPUs and 4 GiB total task memory. Use compact references locally and full-human-reference inputs on the production cluster.

Analysis accepts only `workflow`, `input`, `reference_bundle`,
`verify_bundle_checksums`, and `outdir` as pipeline parameter names. Unsupported
names, including reference-preparation parameters, fail before input processing
or task submission. The [strict parameter policy](../README.md) also covers
parameter/configuration files and previously ignored custom parameters. Use
`-profile` with one dash to select a Nextflow profile; `--profile` fails with a
correction. Existing output-directory protection can report an error first.

Before processing reads, alignment validates the bundle manifest's structure,
supported format version 1, artifact paths, and required checksum entries. It
checks that the FASTA and all five index files exist as regular files. Normal
startup does not read artifact contents or calculate checksums. Sample-sheet and
FASTQ path checks also complete before Cutadapt submission; they do not validate
FASTQ contents.

Add `--verify_bundle_checksums` to an `oncohawk` run to verify SHA-256 checksums
of the FASTA and all five index files against the manifest before processing
reads. The option defaults to off; `--verify_bundle_checksums false` explicitly
keeps lightweight validation. Verification streams one file at a time in the
Nextflow launcher on the submission host, with bounded memory, once per invocation
including `-resume`. It is outside individual SLURM task resource allocations.
Any checksum mismatch fails before Cutadapt starts; successful verification
continues into analysis. Default validation does not detect artifact-content
corruption, although downstream tools may reject corrupt inputs. Reference
preparation still generates the bundle's checksums in both cases.

Every pair passes through the same pristine Cutadapt step. Supplied sequences are [regular 3′ adapters](https://cutadapt.readthedocs.io/en/v5.2/guide.html#regular-3-adapters) for the corresponding mate: a full internal match removes the adapter and following sequence, and a partial match at the read's end can also be removed. Cutadapt's default matching rules apply. Adapters are never inferred automatically, and an unconfigured mate receives no adapter removal.

After optional adapter removal, both mates must remain at least **15 bp**: a pair with either mate below 15 bp is discarded, and a pair with both mates exactly 15 bp is retained. Already-trimmed inputs and rows with blank or omitted options receive the same length filtering. No quality trimming is added. A retained short read may remain unmapped.

bwa-mem2 receives the row's read group through `-R` and uses `-Y` supplementary soft clipping. Other mapping settings retain their defaults, apart from configured compute resources. Supplementary alignments retain the complete sequence supplied after preprocessing.

Coordinate-sorted row BAMs are grouped by sample and passed to samtools merge in a stable filename order. Its `-c` setting preserves the shared read-group ID for compatible chunks with identical definitions. Program records remain distinct; `-p` is not enabled. Picard then marks duplicates once per sample using the read groups' `LB` fields, before the final BAM is indexed. This combines lanes within a library without treating matching coordinates from different libraries as duplicates of each other.

## Outputs and failures

The default output root is `results`; use `--outdir` to choose a different fresh destination. Relative overrides resolve from the launch directory. Quote paths containing spaces. Each sample's BAM and index are grouped under `samples/<sample>/alignments/`, retaining the sample ID in both filenames. An override changes only the root; it does not change the sample hierarchy. Existing output roots, including empty directories, are rejected before processing, preserving previous results.

For the two samples in the example, successful completion publishes exactly one BAM and index per sample:

```text
results/
└── samples/
    ├── S1/
    │   └── alignments/
    │       ├── S1.bam
    │       └── S1.bam.bai
    └── S2/
        └── alignments/
            ├── S2.bam
            └── S2.bam.bai
```

For example, `--outdir /path/to/new-results` places S1's BAM at `/path/to/new-results/samples/S1/alignments/S1.bam`. No flat duplicate BAMs or empty variant/report directories are published. With diagnostics disabled, the tree above contains the entire published analysis output; there is no `execution` directory.

Each BAM is coordinate-sorted, contains only that sample's records, preserves its read-group headers and read tags, and retains duplicate reads with duplicate flags set. The final index supports regional BAM queries.

If adapter removal and length filtering leave no pairs for a sample, successful completion still produces a valid header-only BAM and its index. The read-group headers are retained, and regional queries return no records. An empty row can also be combined with nonempty rows of the same sample. These empty results are distinct from a failed tool or invalid input.

Native Nextflow workflow outputs publish each completed BAM and index after indexing succeeds. A failed preprocessing, mapping, merging, duplicate-marking, or indexing task fails the workflow instead of publishing that sample as completed. Other samples may already have completed; a failed run is not an atomic batch publication. Consult the reported task directory and its `.command.err`/`.command.out` files when diagnosing a failure.

Tool logs and Picard duplicate metrics remain in task work directories. Execution diagnostics are separate from the published BAM/index contract and use the native opt-in controls below.

## Execution diagnostics

Enable any combination of Nextflow's trace, execution report, timeline, and DAG using `-with-trace`, `-with-report`, `-with-timeline`, and `-with-dag`. None is enabled by default. For analysis, their native directory settings place generated artifacts under `<outdir>/execution/`, alongside `samples/`; reference preparation retains its own bundle contract and does not load these analysis settings.

Bare flags use Nextflow's default filenames. To choose predictable filenames, supply relative names:

```bash
nextflow run . -profile docker,test \
  --input /path/to/samples.csv \
  --reference_bundle /path/to/prepared-bundle \
  --outdir /path/to/new-results \
  -with-trace trace.tsv \
  -with-report report.html \
  -with-timeline timeline.html \
  -with-dag dag.html
```

For two completed samples, this command publishes:

```text
new-results/
├── execution/
│   ├── trace.tsv
│   ├── report.html
│   ├── timeline.html
│   └── dag.html
└── samples/
    ├── S1/
    │   └── alignments/
    │       ├── S1.bam
    │       └── S1.bam.bai
    └── S2/
        └── alignments/
            ├── S2.bam
            └── S2.bam.bai
```

Use bare flags or relative diagnostic filenames; Nextflow rejects absolute diagnostic filenames when these directory settings are active. Use `--outdir` to choose the analysis output root. Native `-output-dir` or configuration `outputDir` settings that resolve to a different root are rejected because they would bypass the output-root validation. Existing site and resource settings remain configurable through `-c` and `-C`; keep output selection in `--outdir`. Default selection and explicit `--workflow oncohawk` use the same paths, including when launching from outside the checkout.

The selected output root is checked while loading analysis configuration, before native diagnostics can create or replace files. A root that already existed before invocation remains an error, even with diagnostics enabled. A failed invocation may leave execution diagnostics and already completed samples. It still fails overall, and it does not publish a failed sample as completed. Choose a new output root for another invocation instead of reusing the failed run's directory. Engine work directories, caches, and `.nextflow.log` retain their normal locations outside this publication layout.

This check also applies to read-only `nextflow config` inspection. Inspect analysis configuration from a launch directory without an existing `results` directory; inspection creates no output directory. An existing selected root causes a clear error without changing its contents. For example, run `nextflow config /absolute/path/to/oncohawk -profile slurm -flat` from a fresh temporary directory. Workflow selection and site/resource settings remain inspectable through the supported configuration files.

## Production with SLURM and Apptainer

The SLURM profile enables [community-style resource retries](resource-retries.md): one retry with growing resource requests, optional native caps, and standard configuration overrides. First-attempt allocations remain unchanged; ordinary local Docker behavior is unchanged.

Copy [the site example](../conf/site.example.config) and replace its queue/account and shared paths. This file contains only shared cluster settings. For the selected Oncohawk workflow, the `slurm` profile automatically loads [alignment process allocations](../conf/oncohawk_resources.config); copy these separately to customize CPU, memory, and time. Allocations for `CUTADAPT`, `BWAMEM2_MEM`, `SAMTOOLS_MERGE`, `PICARD_MARKDUPLICATES`, and `SAMTOOLS_INDEX` are illustrative, not measured requirements. Inputs, the reference bundle, work directory, output directory, and Apptainer cache must be accessible to the submission host and compute nodes.

```bash
mkdir -p .local
cp conf/site.example.config .local/site.config
cp conf/oncohawk_resources.config .local/alignment-resources.config
# Edit the shared site settings and alignment resource allocations for your cluster.
nextflow run . -profile slurm -c .local/site.config,.local/alignment-resources.config \
  --input /shared/PROJECT/samples.csv \
  --reference_bundle /shared/PROJECT/bundles/grch38-no-alt \
  --outdir /shared/PROJECT/results/run-001
```

SLURM/Apptainer and Docker use the same workflow logic and pristine nf-core modules. Conda execution is unsupported. HPC checks are informal operator checks; HPC access, execution evidence, and sign-off never gate ticket or milestone completion. No production-cluster execution or full-reference resource measurement is claimed here.

## Modules and validation

The alignment modules `cutadapt`, `bwamem2/mem`, `samtools/merge`, `picard/markduplicates`, and `samtools/index` were installed with nf-core CLI **4.2.1**, pinned to upstream revision `20c6e6407f63748003b47f92837b64fb0a53ffa4` in [modules.json](../modules.json). Their upstream scripts and container pins remain unchanged; configuration and composition live outside them.

On 2026-11-01, a real public alignment run succeeded on the ARM64 development Mac using Docker's `linux/amd64` containers. The fixture used a 12-kb synthetic reference and one read pair; production resource sizing remains unmeasured. The executed task environments reported:

| Tool | Observed version |
| --- | --- |
| Cutadapt | 5.2 |
| bwa-mem2 | 2.2.1 |
| samtools in the mapping container | 1.22.1 |
| Picard | 3.5.0 |
| samtools in the final indexing container | 1.25 |

Run `python3 -m unittest discover -s tests -v` to exercise the public reference-preparation and alignment interfaces and their composition with real containers. The **Tests and validation** CI check runs the same suite. Tests assert observable BAM content and input/tool failures rather than private parser helpers.

On 2026-11-08, the readable-task-label regression failed against the old hash-only labels, then passed after the change using Nextflow 26.10.5, Java 21, and the pinned Docker images (65 seconds). It checks both processes' trace labels, distinct chunks sharing one read group, row-reordering stability, and the existing BAM/read-group/duplicate-marking assertions. Both pipeline-configuration tests also passed, along with Nextflow lint (existing deprecation warnings), Python compilation, and whitespace checks. The full suite, CI, and SLURM/Apptainer execution were not run for this change.

Adapter acceptance uses designed read sequences to check R1-only, R2-only, both-mate, omitted, and blank settings in final BAMs. It also checks regular 3′ matching, the 14/15-bp boundary after trimming, mate synchronization, supplementary sequence preservation, empty indexed BAMs, and malformed settings. Multiple-input acceptance covers sample isolation, read-group associations, duplicates across lanes within one library, independent libraries, repeated chunks of one read group, input reuse errors, and mixed row-local adapters through reference preparation and final BAM/index queries.
