# Oncohawk

Oncohawk is a Nextflow workflow for tumor-only short-read DNA WGS analysis. It prepares a reusable **reference bundle** and aligns one gzipped FASTQ pair to produce a coordinate-sorted, indexed BAM with duplicates marked and retained. This alignment slice supports one sample, library, and read group, with optional per-mate adapter settings; multiple inputs belong to a later slice. Downstream analysis remains deferred.

Use Nextflow **26.10.4**, Java **21.0.13+9**, Python **3.12** for tests, and a running Docker installation for local development. Containers supply the bioinformatics tools; Conda execution is unsupported. The [reference-bundle guide](docs/reference-bundle.md) and [alignment guide](docs/alignment.md) describe inputs, outputs, runtime pins, and production use.

Run the compact acceptance tests from the checkout:

```bash
python3 -m unittest discover -s tests -v
```

These tests run real reference preparation, alignment, and their composition with Docker through the public workflow interfaces. The `docker,test` profiles limit execution to compact fixtures; full-human-reference runs belong on the production cluster.

Prepare a bundle from your own small fixture:

```bash
nextflow run . -profile docker,test \
  --fasta /path/to/small.fa.gz \
  --bed /path/to/exclusions.bed \
  --outdir /path/to/new-bundle
```

Align a small paired-end fixture against that prepared bundle:

```bash
nextflow run alignment.nf -profile docker,test \
  --input /path/to/samples.csv \
  --reference_bundle /path/to/new-bundle \
  --outdir /path/to/new-alignments
```

Use the [single-row CSV example](docs/alignment.md#sample-sheet) and a fresh output directory. All pairs pass through Cutadapt length filtering; both mates must be at least 15 bp.

The production `slurm` profile uses Apptainer and the same workflow and pristine nf-core modules. See the [site configuration example](conf/site.example.config) and [cluster instructions](docs/reference-bundle.md#production-with-slurm-and-apptainer). Formal acceptance uses local Docker and required CI; HPC checks are informal and never gate ticket or milestone completion.

Project scope and accepted decisions are in [requirements](docs/requirements.md), [design](docs/design.md), and the root [glossary](GLOSSARY.md).
