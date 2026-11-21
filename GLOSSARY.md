# Oncohawk

Domain language for Oncohawk analysis and its reusable inputs.

## Language

**Oncohawk workflow**:
The analysis workflow for tumor-only short-read DNA whole-genome sequencing of blood cancers, using sequencing inputs and prepared bundles to produce a report for review by clinicians and molecular biologists.
_Avoid_: Report-generation workflow, which understates the analysis included in this workflow.

**Reference bundle**:
A reusable collection of reference sequences, reference annotations, and associated assets for analysis. It includes the assets needed for alignment, variant calling, and consequence annotation.

**Knowledge bundle**:
A prepared collection of human-authored biological and reporting knowledge associated with a reference bundle.

**Alignment reference**:
The reference genome sequence against which reads are aligned and variants are called.

**Annotation reference**:
The reference genome sequence used to determine variant consequences and sequence-relative descriptions. It must be compatible with the coordinates and alleles being annotated.

**Consequence annotation**:
Gene and transcript context and predicted sequence effects associated with a variant, including applicable coding and protein changes. These annotations do not establish somatic origin, pathogenicity, or treatment significance.

**RefSeq consequence**:
A predicted variant effect expressed against an identified RefSeq transcript sequence version. Known coding and noncoding transcripts are distinct from predicted model transcripts.

**MANE metadata**:
The Select or Plus Clinical designation associated with a matched RefSeq and Ensembl transcript pair. It identifies transcript relationships and does not classify a variant or require other transcripts to be discarded.
