# Oncohawk

Oncohawk is a Nextflow workflow for tumor-only short-read DNA WGS analysis. It prepares a reusable **reference bundle** and aligns gzipped FASTQ pairs to produce one coordinate-sorted, indexed BAM per sample with duplicates marked and retained. A sample sheet can combine multiple samples, libraries, lanes, and FASTQ chunks, with optional adapter settings for each mate in each row. Read groups are preserved, and duplicate detection combines lanes within each library while keeping distinct libraries separate. Downstream analysis remains deferred.

The [milestone 1 acceptance record](docs/milestone-1-acceptance.md) maps the completed scope to tests, merged implementation PRs, and recorded local/CI results as of 2026-11-01.

Use Nextflow **26.10.4**, Java **21.0.13+9**, Python **3.12** for tests, and a running Docker installation for local development. Containers supply the bioinformatics tools; Conda execution is unsupported. The [reference-bundle guide](docs/reference-bundle.md) and [alignment guide](docs/alignment.md) describe inputs, outputs, runtime pins, and production use.

Run the compact acceptance tests from the checkout:

```bash
python3 -m unittest discover -s tests -v
```

These tests run real reference preparation, alignment, and their composition with Docker through the public workflow interfaces. The `docker,test` profiles limit execution to compact fixtures; full-human-reference runs belong on the production cluster.

Each pipeline has its own entrypoint and process configuration under `pipelines/`; modules and execution-environment settings are shared. Default output directories are `reference` and `alignments`, respectively. Override either with `--outdir`.

Reference URLs use a persistent, integrity-checked download store, defaulting to `downloads` in the launch directory. Set `--downloads_dir /persistent/path` to share it across runs independently of Nextflow work directories and `-resume`. See [persistent downloads](docs/reference-bundle.md#persistent-downloads) for integrity, concurrency, and cluster setup.

Before the first official pipeline release, every commit may break functionality; backward compatibility is not maintained.

Prepare a bundle from your own small fixture:

```bash
nextflow run pipelines/reference -profile docker,test \
  --fasta /path/to/small.fa.gz \
  --exclusions_bed /path/to/exclusions.bed \
  --outdir /path/to/new-bundle
```

Align small paired-end fixtures against that prepared bundle:

```bash
nextflow run pipelines/alignment -profile docker,test \
  --input /path/to/samples.csv \
  --reference_bundle /path/to/new-bundle \
  --outdir /path/to/new-alignments
```

Use the [sample-sheet examples](docs/alignment.md#sample-sheet) for one pair or multiple samples and a fresh output directory. All pairs pass through Cutadapt; after optional row-local adapter removal, both mates must be at least 15 bp. Each input FASTQ may appear only once in the sheet.

The production `slurm` profile uses Apptainer and the same workflow and pristine nf-core modules. See the [site configuration example](conf/site.example.config) and [cluster instructions](docs/reference-bundle.md#production-with-slurm-and-apptainer). Formal acceptance uses local Docker and required CI; HPC checks are informal and never gate ticket or milestone completion.

Project scope and accepted decisions are in [requirements](docs/requirements.md), [design](docs/design.md), and the root [glossary](GLOSSARY.md).
