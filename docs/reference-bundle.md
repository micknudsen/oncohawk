# Prepare an alignment reference bundle

The reference-preparation entry point, `nextflow run pipelines/reference`, validates reference inputs, decompresses a gzipped FASTA, hard-masks BED intervals with `N`, and builds bwa-mem2 indexes from that exact masked sequence. It publishes the reusable bundle after successful validation and tool execution. Knowledge compilation and sample alignment are outside this entry point.

## Runtime pins

Use Java **21.0.13+9** and [Nextflow **26.10.4**](https://github.com/nextflow-io/nextflow/releases/tag/v26.10.4). The standalone release asset `nextflow-26.10.4-dist` has SHA256 `2cbda6e7fdbbb1e7a413973eff549653f566ba6bb7bdfbb58eb78d0f831fdec4`; the required CI workflow verifies this digest before execution. Python **3.12** runs the standard-library acceptance tests. Docker supplies local task execution; production requires SLURM and Apptainer.

The modules were installed with nf-core CLI **4.2.1** at upstream revision `20c6e6407f63748003b47f92837b64fb0a53ffa4`, recorded in [modules.json](../modules.json). `gunzip`, `bedtools/maskfasta`, and `bwamem2/index` remain unchanged, including their upstream container pins. Actual Docker execution reported gzip **1.13**, bedtools **2.31.1**, and bwa-mem2 **2.2.1**. The upstream bwa-mem2 Conda environment declares 2.3, but that environment is not executed: Conda is unsupported. The manifest records executed versions rather than inferring them from unused environment metadata.

The custom validation and packaging steps implement Oncohawk's input and bundle contracts; their runtime is Python **3.12.16** (Bookworm), pinned as `python@sha256:a5bab0ff300f91231c2e68bf73a8a8d60762ac39ce1c50eaf6803e4c38a9062b`. The digest-only reference works with Docker and Apptainer; combining a tag and digest is rejected by Apptainer. Bioinformatics operations remain in the pristine upstream modules. Executed tool versions and workflow source hashes are recorded in each bundle.

Required CI checks every installed module file against its pinned upstream Git object, including missing or added files. Upstream snapshots contain trailing whitespace, so `.gitattributes` exempts only `modules/nf-core/` from whitespace formatting checks; the stricter upstream integrity check protects those bytes. Project code and documentation retain whitespace checks.

## Inputs and masking

| Parameter | Meaning |
| --- | --- |
| `--fasta` | Local `.fa`/`.fa.gz` or a downloadable FASTA URL. Defaults to the selected NCBI no-ALT analysis set below. |
| `--exclusions_bed` | Local exclusions BED or downloadable BED URL. Defaults to the matching NCBI exclusions below. |
| `--outdir` | New directory for the completed bundle; default `reference`. Choose a fresh destination for each bundle. |
| `--fasta_sha256`, `--exclusions_bed_sha256` | Optional expected SHA256 values for custom source files, checked before preparation. For `.gz` input, hash the compressed source bytes. |

The production defaults are the [GRCh38 no-ALT analysis-set FASTA with UCSC IDs](https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz) and [GRC exclusions BED](https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_GRC_exclusions.bed). Their [NCBI checksum metadata](https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/md5checksums.txt), verified on 2026-11-01, gives FASTA MD5 `a08035b6a6e31780e96a34008ff21bd6` and BED MD5 `bf5c011e0342f355422144eb3547b5d0`. Default acquisition verifies these values.

Exclusions BED coordinates are zero-based, half-open. Masking preserves sequence names, lengths, coordinates, and unmasked bases. If a contig in the exclusions BED is absent from the FASTA, its intervals are skipped and each is recorded in `omitted_exclusions_bed_entries` with its line number, contig, coordinates, and reason `"Contig missing in FASTA"`. This applies to all inputs, including the default NCBI files. Malformed intervals and coordinates outside an existing contig still cause an error.

Input filenames may contain letters, digits, dots, underscores, and hyphens; parent directory paths may contain spaces. Each input identifies one file, not a wildcard collection. Existing output directories are rejected to prevent mixed or overwritten bundles. Source checksums are verified after decompression and before masking/indexing.

## Local Docker example

Start Docker, put the pinned Nextflow executable on `PATH`, and select the pinned Java runtime. From the repository root, create an illustrative small input:

```bash
python3 - <<'PY'
import gzip
from pathlib import Path
example = Path('.local/reference-example')
example.mkdir(parents=True, exist_ok=True)
with gzip.open(example / 'small.fa.gz', 'wt') as handle:
    handle.write('>chr1\nACGTACGTACGTACGTACGT\n>chr2\nTTTTCCCCAAAAGGGG\n')
(example / 'exclusions.bed').write_text('chr1\t4\t8\nchr2\t0\t2\n')
PY
nextflow run pipelines/reference -profile docker,test \
  --fasta .local/reference-example/small.fa.gz \
  --exclusions_bed .local/reference-example/exclusions.bed \
  --outdir .local/reference-example/bundle
```

The `docker` profile uses `--platform=linux/amd64`, including on Apple Silicon. The `test` profile limits local execution to two CPUs and 4 GiB total task memory, with at most one task per process; the indexing task requests 2 GiB. These settings serve compact fixtures, not the human reference.

On 2026-11-01, an initial real masking/indexing/provenance test passed under Docker 29.9.2 on an ARM64 Mac with a 10-CPU, approximately 7.75-GiB Docker VM. That observation establishes execution of the compact path; it is not a peak-resource measurement or full-reference benchmark. Run the public acceptance suite with `python3 -m unittest discover -s tests -v`; the required CI job runs the same command on Linux with real containers.

A subsequent trace of the 36-base fixture on the same date measured 19.8 MB peak RSS for indexing (1.1 GB peak virtual memory) and at most 35.6 MB peak RSS across these five tasks. The test harness retains per-run logs and traces under `.local/tests/`. These fixture measurements do not estimate human-reference requirements.

## Production with SLURM and Apptainer

Copy [conf/site.example.config](../conf/site.example.config) to a local site configuration, then replace its partition, optional account, and shared paths. The submission host and compute nodes must see the work directory, input files, output destination, and Apptainer cache. The shared site file contains no process-name selectors. The `slurm` profile automatically loads [reference process allocations](../pipelines/reference/resources.config). These are starting allocations, not measured cluster requirements. To customize them, copy that resource file and pass it as a second configuration file; keep it specific to reference preparation.

```bash
mkdir -p .local
cp conf/site.example.config .local/site.config
cp pipelines/reference/resources.config .local/reference-resources.config
# Edit the shared site settings and reference resource allocations for your cluster.
nextflow run pipelines/reference -profile slurm -c .local/site.config,.local/reference-resources.config \
  --outdir /shared/PROJECT/oncohawk/bundles/grch38-no-alt
```

Omitting `--fasta` and `--exclusions_bed` selects the checksum-verified NCBI sources. To use local copies, provide both paths. The `slurm` profile enables Apptainer automatic mounts and uses the same workflow and modules as Docker. See Nextflow's [executor guidance](https://docs.seqera.io/nextflow/executor) and [container guidance](https://docs.seqera.io/nextflow/container).

HPC execution is checked informally by the operator. HPC access, runs, evidence, and sign-off never gate formal acceptance or completion. No cluster run is claimed here.

## Published bundle

```text
reference/
├── reference.fa
├── bwamem2/
│   ├── reference.fa.0123
│   ├── reference.fa.amb
│   ├── reference.fa.ann
│   ├── reference.fa.bwt.2bit.64
│   └── reference.fa.pac
└── bundle.json
```

`bundle.json` starts with `bundle_format_version: 1`, identifying the format of the entire reference bundle, followed by relative `fasta` and `bwamem2_index` paths, SHA256 artifact checksums, source URIs and checksums under `sources.fasta` and `sources.exclusions_bed`, sequence lengths, omitted BED entries, tool/module versions, and workflow identity/source hashes. Source hashes use repository-relative paths and cover reference-preparation sources and shared files used by preparation, excluding alignment-only sources. The repository commit is recorded separately. The index path is a prefix; all five index files accompany it. Keep the manifest and artifacts together when moving a bundle. A process failure is a failed preparation, not a completed bundle; inspect the Nextflow task log before retrying into a new output destination.
