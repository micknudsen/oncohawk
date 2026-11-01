# Align one FASTQ pair

The public `alignment.nf` entry point accepts a [prepared reference bundle](reference-bundle.md) and one sample-sheet row. It runs shared Cutadapt adapter removal and length filtering, bwa-mem2 mapping, duplicate marking, and final BAM indexing. The single-input path from [issue #4](https://github.com/micknudsen/oncohawk/issues/4) supports per-mate adapter settings from [issue #5](https://github.com/micknudsen/oncohawk/issues/5): one sample, one library, and one read group. Multiple rows remain a subsequent slice and produce an explicit unsupported-input error.

## Sample sheet

Use a CSV file with these required columns in any order and exactly one data row:

```csv
sample,library,flowcell,lane,fastq_1,fastq_2
S1,L1,FC1,1,/data/S1_R1.fastq.gz,/data/S1_R2.fastq.gz
```

`sample`, `library`, `flowcell`, and `lane` identify the biological and sequencing inputs. Each must match `[A-Za-z0-9][A-Za-z0-9_.-]*`: start with an ASCII letter or digit, followed by letters, digits, underscores, periods, or hyphens. Missing required values and duplicate or unknown column headers fail validation.

`fastq_1` and `fastq_2` identify the corresponding gzipped mate files. Relative paths resolve from the sample-sheet directory, not the launch directory. Each filename must end in `.gz` and match the same safe-character pattern above. Wildcards, using the same file for both mates, and distinct files with the same basename are rejected. Missing files and malformed or unusable sequencing inputs fail the workflow.

The optional `options` column contains semicolon-separated `key=value` entries. Only `r1_adapter` and `r2_adapter` are supported; either may be supplied alone. For both mates:

```csv
sample,library,flowcell,lane,fastq_1,fastq_2,options
S1,L1,FC1,1,/data/S1_R1.fastq.gz,/data/S1_R2.fastq.gz,r1_adapter=AGATCGGAAGAGC;r2_adapter=CTGTCTCTTATACACATCT
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

The same `ID` appears in the header and each read's `RG` tag. The encoded identity keeps sample/library/flowcell/lane boundaries unambiguous.

## Local Docker execution

Use the [pinned development runtimes](reference-bundle.md#runtime-pins) and a running Docker installation. Prepare a compact bundle and matching gzipped read pairs, then run from the checkout:

```bash
nextflow run alignment.nf -profile docker,test \
  --input /path/to/samples.csv \
  --reference_bundle /path/to/prepared-bundle \
  --outdir /path/to/new-alignments
```

`--reference_bundle` points to the directory containing `bundle.json`, `reference.fa`, and its bwa-mem2 indexes. `--outdir` must be a fresh output directory. The Docker profile selects `linux/amd64` containers, including on Apple Silicon; the test profile limits local execution to two CPUs and 4 GiB total task memory. Use compact references locally and full-human-reference inputs on the production cluster.

Before processing reads, alignment validates bundle format version 1 and streams SHA256 checks of the FASTA and all five index files against the manifest. These checks run once on the submission host, without loading entire files into memory, and reject altered or incomplete bundles.

Every pair passes through the same pristine Cutadapt step. Supplied sequences are [regular 3′ adapters](https://cutadapt.readthedocs.io/en/v5.2/guide.html#regular-3-adapters) for the corresponding mate: a full internal match removes the adapter and following sequence, and a partial match at the read's end can also be removed. Cutadapt's default matching rules apply. Adapters are never inferred automatically, and an unconfigured mate receives no adapter removal.

After optional adapter removal, both mates must remain at least **15 bp**: a pair with either mate below 15 bp is discarded, and a pair with both mates exactly 15 bp is retained. Already-trimmed inputs and rows with blank or omitted options receive the same length filtering. No quality trimming is added. A retained short read may remain unmapped.

bwa-mem2 receives the row's read group through `-R` and uses `-Y` supplementary soft clipping. Other mapping settings retain their defaults, apart from configured compute resources. Supplementary alignments retain the complete sequence supplied after preprocessing.

## Outputs and failures

For sample `S1`, successful completion publishes:

```text
new-alignments/
├── S1.bam
└── S1.bam.bai
```

The BAM is coordinate-sorted, preserves the input read group, and retains duplicate reads with duplicate flags set. Duplicate detection uses the library metadata. The final index supports regional BAM queries.

If adapter removal and length filtering leave no pairs, successful completion still produces a valid header-only BAM and its index. The read-group header is retained, and regional queries return no records. This empty result is distinct from a failed tool or invalid input.

Native Nextflow workflow outputs publish the completed BAM and index after indexing succeeds. A failed preprocessing, mapping, duplicate-marking, or indexing task fails the workflow instead of publishing that sample as completed. Consult the reported task directory and its `.command.err`/`.command.out` files when diagnosing a failure.

Tool logs and Picard duplicate metrics remain in task work directories. Add `-with-trace` to record a Nextflow run trace. These diagnostics are separate from the published BAM/index contract.

## Production with SLURM and Apptainer

Copy [the site example](../conf/site.example.config), replace its queue/account and shared paths, and adjust CPU, memory, and time for your cluster. Its named allocations for `CUTADAPT`, `BWAMEM2_MEM`, `PICARD_MARKDUPLICATES`, and `SAMTOOLS_INDEX` are illustrative, not measured requirements. Inputs, the reference bundle, work directory, output directory, and Apptainer cache must be accessible to the submission host and compute nodes.

```bash
cp conf/site.example.config .local/site.config
# Edit .local/site.config for your cluster before running.
nextflow run alignment.nf -profile slurm -c .local/site.config \
  --input /shared/PROJECT/samples.csv \
  --reference_bundle /shared/PROJECT/bundles/grch38-no-alt \
  --outdir /shared/PROJECT/alignments/run-001
```

SLURM/Apptainer and Docker use the same workflow logic and pristine nf-core modules. Conda execution is unsupported. HPC checks are informal operator checks; HPC access, execution evidence, and sign-off never gate ticket or milestone completion. No production-cluster execution or full-reference resource measurement is claimed here.

## Modules and validation

The alignment modules `cutadapt`, `bwamem2/mem`, `picard/markduplicates`, and `samtools/index` were installed with nf-core CLI **4.2.1**, pinned to upstream revision `20c6e6407f63748003b47f92837b64fb0a53ffa4` in [modules.json](../modules.json). Their upstream scripts and container pins remain unchanged; configuration and composition live outside them.

On 2026-11-01, a real public alignment run succeeded on the ARM64 development Mac using Docker's `linux/amd64` containers. The fixture used a 12-kb synthetic reference and one read pair; production resource sizing remains unmeasured. The executed task environments reported:

| Tool | Observed version |
| --- | --- |
| Cutadapt | 5.2 |
| bwa-mem2 | 2.2.1 |
| samtools in the mapping container | 1.22.1 |
| Picard | 3.5.0 |
| samtools in the final indexing container | 1.25 |

Run `python3 -m unittest discover -s tests -v` to exercise the public reference-preparation and alignment interfaces and their composition with real containers. The **Tests and validation** CI check runs the same suite. Tests assert observable BAM content and input/tool failures rather than private parser helpers.

Adapter acceptance uses designed read sequences to check R1-only, R2-only, both-mate, omitted, and blank settings in final BAMs. It also checks regular 3′ matching, the 14/15-bp boundary after trimming, mate synchronization, supplementary sequence preservation, empty indexed BAMs, and malformed settings. Mixed settings across multiple rows belong to the multiple-input slice in [issue #6](https://github.com/micknudsen/oncohawk/issues/6).
