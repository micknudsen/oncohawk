# oncohawk
Nextflow-based pipeline for tumor-only inference of somatic variation in myeloid malignancies

Calling-region definitions live in `assets/calling_regions/variants.json`.
Generate `assets/calling_regions/variants.bed` with `bash ./bin/update_calling_regions.sh /path/to/gencode.gtf.gz`.
