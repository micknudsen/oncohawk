# OncoHawk pipeline specification

## Scope of this document

This draft defines OncoHawk's intended use, workflow-role, dispatch, and bundle
boundary, input and reference boundary, variant-class boundary, reporting
boundary, and initial runtime and engineering-verification boundary. It is a
target contract and does not describe
implemented or verified analytical behavior.

OncoHawk currently has no analytical implementation, analytical or scientific
validation, or release. No claim is made that it is clinical-grade or
suitable for patient-care decisions.

## Intended use

OncoHawk is intended to analyze tumor-only whole-genome sequencing data for
acute myeloid leukemia (AML) and myelodysplastic syndromes (MDS). Matched-normal
analysis is outside the current target contract.

The intended final output is a clinician-readable report of genomic findings
selected using approved curated resources for:

- genes associated with AML or MDS;
- known hotspot variants; and
- known recurrent translocations.

These resources will inform prioritization for report inclusion. Their exact
contents, evidence requirements, representation, and inclusion logic remain
open.

## Workflow architecture

The target architecture has three conceptual workflow roles. These names do
not define current command-line modes or executable workflow entry points, and
they do not describe implemented preparation or analysis behavior.

`prepare_reference_bundle` selects a versioned bundle specification and uses
its pinned reference-genome and annotation assets to produce a versioned
reference bundle with an identity. The bundle contains the derived reference
and the indexes required by later-approved analysis components. The bundle root
contains a machine-readable `manifest.json`. Its `bundle_id` is an opaque,
producer-assigned string. Consumers compare bundle identities by exact string
equality. The exact annotation assets and releases, index contents,
bundle-identifier syntax, and directory layout remain open.

The reference bundle must expose its identity and provenance for its source
genome, exclusions BED, annotation assets, masking transformation, and derived
masked-reference checksum through its manifest.

`prepare_knowledge_bundle` selects a JSON, clinician-oriented knowledge
specification and a reference bundle. It uses
reference-bundle annotation assets, for example a GENCODE GTF, to produce a
versioned, machine-consumable knowledge bundle. The knowledge bundle must
declare the identity of the reference bundle from which it is prepared. The
knowledge bundle must also expose its own identity and the identity of its
approved JSON knowledge specification. It does not duplicate the
individual curated-resource provenance of that specification. Translation
semantics remain open.

The knowledge-bundle root contains a machine-readable `manifest.json` with its
opaque, producer-assigned `bundle_id` and a `source_reference_bundle_id`. The
latter is the `bundle_id` of the reference bundle used to prepare the knowledge
bundle.

Only `analyze` consumes a sample sheet. It requires both a reference bundle and
a knowledge bundle as inputs. It accepts the knowledge bundle only when its
declared source reference-bundle identity exactly matches the supplied
reference-bundle identity. A missing or mismatched identity must fail before
analysis processing begins. Its analysis output set must record the supplied
reference-bundle identity, knowledge-bundle identity, and their compatibility
relationship. Full lineage is resolved through the bundles rather than
duplicated in the analysis output set. The record is a separate
`bundle-compatibility.json` containing `reference_bundle_id`,
`knowledge_bundle_id`, and `knowledge_source_reference_bundle_id` string
fields.

The JSON knowledge specification, compiled knowledge bundle, and
final clinician-readable report are distinct artifacts.

## Top-level workflow-dispatch contract

A future top-level entry point must require exactly one `--workflow` value. It
must be one of:

- `prepare_reference_bundle`;
- `prepare_knowledge_bundle`; or
- `analyze`.

There is no default workflow selection. An omitted or unrecognized
`--workflow` value must cause the entry point to fail before it consumes a
mode-specific input or starts processing, and the failure must identify the
accepted values.

Every workflow requires `--outdir`, which identifies the root directory for
that workflow's output set. The required and optional mode-specific parameters
are:

| `--workflow` value | Required parameters | Optional parameters |
| --- | --- | --- |
| `prepare_reference_bundle` | `--outdir` | `--reference_spec` |
| `prepare_knowledge_bundle` | `--outdir`, `--reference_bundle` | `--knowledge_spec` |
| `analyze` | `--outdir`, `--input`, `--reference_bundle`, `--knowledge_bundle` | None |

For `prepare_reference_bundle`, `--reference_spec` is a path to a local custom
reference-bundle specification. When it is omitted, the workflow uses the
default reference-bundle specification versioned with the selected OncoHawk
release. The selected specification identifies the pinned source assets and
their validation requirements; the workflow downloads those assets. Source
locations and download mechanics remain open.

For `prepare_knowledge_bundle`, `--knowledge_spec` is a path to a local custom
JSON knowledge specification. When it is omitted, the workflow uses
the default knowledge specification versioned with the selected OncoHawk
release. `--reference_bundle` identifies the reference bundle against which
the selected knowledge specification is prepared.

For `analyze`, `--input` identifies the sample sheet, and
`--reference_bundle` and `--knowledge_bundle` identify the input bundles. The
knowledge bundle must declare the exact identity of the supplied reference
bundle as its source reference bundle.

Default and custom specifications must both produce bundles that conform to
the versioned OncoHawk bundle contract. Their resulting manifests must record
the provenance required for their respective bundle type.

A selected workflow accepts only the parameters listed for it, in addition to
`--workflow`. Supplying a parameter intended for another workflow is an error
that must be reported before processing begins. This includes supplying
`--reference_spec` to `prepare_knowledge_bundle` or `analyze`,
`--knowledge_spec` to `prepare_reference_bundle` or `analyze`, or any
bundle-preparation parameter to `analyze` other than its required input-bundle
parameters.

The `--workflow` selector and these parameter boundaries are target-contract
requirements, not implemented behavior.

## JSON specification contracts

This section defines target contracts for selected JSON reference and knowledge
specifications. It does not add a bundled default specification, custom-spec
runtime support, or validation to the current executable workflows.

Every v1 specification has this shared top-level envelope:

```json
{
  "schema_version": 1,
  "spec_id": "producer-assigned-identifier"
}
```

`schema_version` is the JSON number `1`. `spec_id` is a non-empty opaque
string; consumers compare it by exact string equality and do not interpret its
contents. A compiler calculates the selected specification's SHA-256 from the
exact bytes of the selected JSON file. It must not hash a parsed, reformatted,
or otherwise normalized representation. Wherever a specification checksum is
recorded, it is a lowercase 64-character hexadecimal SHA-256 string.

A compiled reference-bundle manifest records the selected specification as:

```json
"source_reference_spec": {
  "spec_id": "producer-assigned-identifier",
  "sha256": "lowercase-64-character-hexadecimal-sha256"
}
```

A compiled knowledge-bundle manifest uses the analogous
`source_knowledge_spec` object. Each object contains exactly its non-empty
`spec_id` and the checksum of the exact selected JSON file bytes. These source
objects are required provenance for future compiled bundles; they do not alter
the identity or compatibility fields of the current executable bundle
manifests.

### Reference specification v1

A reference specification has exactly these top-level fields:

```json
{
  "schema_version": 1,
  "spec_id": "producer-assigned-specification-identifier",
  "bundle_id": "producer-assigned-bundle-identifier",
  "assembly": "assembly-identifier",
  "contig_naming": "contig-naming-identifier",
  "source_fasta": {
    "filename": "source.fna.gz",
    "url": "https://example.invalid/source.fna.gz",
    "md5": "00000000000000000000000000000000"
  },
  "exclusions_bed": {
    "filename": "exclusions.bed",
    "url": "https://example.invalid/exclusions.bed",
    "md5": "00000000000000000000000000000000"
  }
}
```

`bundle_id`, `assembly`, and `contig_naming` are non-empty strings. `bundle_id`
is opaque and may equal `spec_id`. Each source-asset object has exactly
`filename`, `url`, and `md5`: `filename` is a filename only (not a path),
`url` is an absolute HTTPS URL, and `md5` is a lowercase 32-character
hexadecimal string. Unknown fields are invalid at every level of reference
specification v1, including the envelope and both source-asset objects.

### Knowledge specification v1

A knowledge specification has exactly these top-level fields:

```json
{
  "schema_version": 1,
  "spec_id": "producer-assigned-specification-identifier",
  "knowledge": {}
}
```

`knowledge` must be present. Its contents are intentionally unvalidated in
v1: this contract neither constrains nested fields nor defines their
translation into knowledge-bundle artifacts. The strict top-level boundary
preserves the option to define that payload in a later approved contract.

## Analyze output-set boundary

The current executable `analyze` path writes its run-level compatibility
metadata to `metadata/bundle-compatibility.json` beneath `--outdir`. The
metadata directory is reserved for non-report, run-level metadata. This
increment does not define the treatment of other existing contents beneath
`--outdir`, or the future publishing, collision, and resume behavior of
analytical outputs.

The compatibility record is created only after the current bundle and
sample-sheet preflight validations succeed. A failed preflight must create
neither `--outdir` nor its `metadata` directory. If the record already exists,
the workflow accepts it only when its bytes exactly equal the deterministic
record it would produce; a differing record is a failure and is not replaced.
`--outdir` and an existing `metadata` path must each be directories.

The broader analysis output-set layout remains open.

## Analyze input boundary

The `analyze` role, selected with `--workflow analyze`, accepts tumor-only
whole-genome sequencing input as
standard gzip-compressed, paired-end FASTQ files (`.fastq.gz` or `.fq.gz`). Each
input record must provide separate, non-interleaved R1 and R2 files.
SPRING-compressed FASTQ is outside the current target contract and may be
considered in a later increment.

One analysis represents one tumor sample. A single run may include multiple
independent samples from multiple patients. Multiple library, flowcell, and
lane records may refer to one sample.

### Sample-sheet contract

The future `analyze` sample sheet is a headered CSV file with these exact
columns in this order:

```csv
patient_id,sample_id,filetype,info,filepath
```

`patient_id` and `sample_id` are required. A patient may have multiple samples,
including longitudinal samples. Each `sample_id` is globally unique and maps to
exactly one `patient_id`; it may occur in multiple library, flowcell, and lane
rows. This document does not define identifier content or data-governance rules.

`filetype` is required and must be `fastq` in the current target contract. The
field is retained so that a future, separately approved contract may define
other input types. It does not grant current BAM, CRAM, or SPRING support.

`info` is a required, semicolon-separated list of `key:value` entries. It must
contain exactly one of each required key:

- `library_id`;
- `flowcell_id`; and
- `lane`.

It may contain one `platform` entry and one `barcode` entry. If omitted,
`platform` is `ILLUMINA`. A supplied `platform` must be exactly one of the
uppercase SAM values `CAPILLARY`, `DNBSEQ`, `ELEMENT`, `HELICOS`, `ILLUMINA`,
`IONTORRENT`, `LS454`, `ONT`, `PACBIO`, `SINGULAR`, `SOLID`, or `ULTIMA`.
Lowercase and other values are invalid. `barcode` is the demultiplexing sample
barcode, not a UMI or another laboratory identifier. It must be either one
uppercase IUPAC DNA sequence or two such sequences joined by `+` as `i7+i5`.
It is retained exactly as supplied; OncoHawk does not reverse-complement or
otherwise transform it. No other keys are permitted by the current target
contract.

`filepath` is required and contains exactly two semicolon-separated paths: R1
then R2. Both paths must name non-interleaved `.fastq.gz` or `.fq.gz` files. The
first filename must contain a delimited `R1` mate token and the second a
delimited `R2` mate token; delimiters are the start or end of the filename, an
underscore, a period, or a hyphen. Common Illumina names such as
`sample_R1_001.fastq.gz` and `sample_R2_001.fastq.gz` are accepted. Relative
paths are resolved from the directory containing the sample sheet.
Each declared path must exist and resolve to a readable regular file; symlinked
FASTQs are accepted when their targets meet those conditions. R1 and R2 must
resolve to distinct underlying files, including when aliases are created with
symlinks or hard links. Remote and object-store paths are outside this
contract.

The tuple (`sample_id`, `library_id`, `flowcell_id`, `lane`) must be unique.
Structural validation emits normalized records with `barcode`, `read_group_id`,
and `platform_unit` fields. `barcode` is the raw validated value or null when
absent. The future pipeline will set read-group sample (`SM`) from `sample_id`,
library (`LB`) from `library_id`, and platform (`PL`) from the provided or
defaulted platform value.

For `read_group_id`, OncoHawk composes `sample_id`, `library_id`,
`flowcell_id`, and `lane` in that order. For `platform_unit`, it composes
`flowcell_id`, `lane`, and `barcode` when a barcode is present; otherwise it
uses `read_group_id`. Components are joined with `.` after percent-encoding
their UTF-8 bytes. Only `A-Z`, `a-z`, `0-9`, `_`, and `-` remain literal; every
other byte is encoded as uppercase `%HH`. This produces reversible printable
ASCII values without delimiter ambiguity. Generated `read_group_id` and
`platform_unit` values must each be unique within a run; a collision is a
structural validation failure.

The target contract requires preflight validation of the exact headers,
required fields, `filetype`, `info` grammar and keys, path-pair grammar, local
FASTQ-file eligibility, sample to patient mapping, and the unique tuple. It
does not require a FASTQ-content scan.

Valid synthetic example:

```csv
patient_id,sample_id,filetype,info,filepath
patient_001,sample_001,fastq,library_id:lib_A;flowcell_id:FC123;lane:001,fastq/sample_001/lib_A_FC123_L001_R1.fastq.gz;fastq/sample_001/lib_A_FC123_L001_R2.fastq.gz
patient_001,sample_001,fastq,library_id:lib_A;flowcell_id:FC123;lane:002,fastq/sample_001/lib_A_FC123_L002_R1.fastq.gz;fastq/sample_001/lib_A_FC123_L002_R2.fastq.gz
patient_001,sample_002,fastq,library_id:lib_B;flowcell_id:FC456;lane:001;platform:ILLUMINA,fastq/sample_002/lib_B_FC456_L001_R1.fastq.gz;fastq/sample_002/lib_B_FC456_L001_R2.fastq.gz
patient_002,sample_003,fastq,library_id:lib_C;flowcell_id:FC789;lane:001,fastq/sample_003/lib_C_FC789_L001_R1.fastq.gz;fastq/sample_003/lib_C_FC789_L001_R2.fastq.gz
```

Examples of structural failures include a repeated
(`sample_id`, `library_id`, `flowcell_id`, `lane`) tuple; one `sample_id`
mapped to different patients; a missing `library_id`, `flowcell_id`, or `lane`;
an unrecognized `info` key; a non-`fastq` filetype; or a `filepath` value that
does not contain exactly two `.fastq.gz` or `.fq.gz` paths with delimited R1/R2
mate tokens in R1/R2 order.

The contract does not require a separate, full-file preflight scan to establish
read-name or pair consistency before processing begins. It does require that
each input record provide both members of the stated paired-end file set.

The target contract is developed with Illumina paired-end data in mind. Paired-
end data from other platforms may be accepted, but their use is unvalidated and
no performance claim is made for them. Read length and insert size are not
constrained by this contract.

Matched-normal inputs and non-whole-genome inputs are outside the target
contract and are to be rejected. Aligned reads and other non-FASTQ input forms
are also outside the target contract.

## Reference contract

The target reference is the NCBI GCA_000001405.15 GRCh38 no-alt analysis set
with UCSC-style sequence identifiers:

- [GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz](https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz),
  NCBI MD5 `a08035b6a6e31780e96a34008ff21bd6`;
- [GCA_000001405.15_GRCh38_GRC_exclusions.bed](https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_GRC_exclusions.bed),
  NCBI MD5 `bf5c011e0342f355422144eb3547b5d0`.

The reference used by a future implementation must be derived by replacing
each interval in the exclusions BED with `N` bases in the source FASTA. This
masking preserves the source GRCh38 coordinate system. The downloaded source
artifacts must be verified against the pinned checksums, and the checksum of
the derived masked reference must be recorded for each reference build.

The future `prepare_reference_bundle` role will establish this derived masked
reference from those pinned source artifacts. It will also contain pinned
annotation assets, including those used by `prepare_knowledge_bundle`; their
selection and release remain open. Required indexes will be defined when their
dependent analysis components are approved.

### Initial executable reference-bundle boundary

The current `prepare_reference_bundle` path implements only the pinned default
source FASTA and exclusions BED above. It does not yet provide durable download
caching; cache location, collision, and resume behavior remain open.
`--reference_spec` is not yet supported.

The reference bundle root is the directory supplied through `--outdir`. It contains
`manifest.json` and
`fasta/GCA_000001405.15_GRCh38_no_alt_analysis_set.masked.fna`. The manifest
has schema version `1` and declares bundle ID
`oncohawk-reference-hg38-beta-2`. Its `reference` object records the assembly,
UCSC contig naming, source FASTA filename, URL, and verified MD5, plus the
relative path and SHA-256 of the derived masked FASTA. Its `mask` object
records the exclusions BED filename, URL, and verified MD5, and the masking
method, replacement base, and coordinate system. This bundle ID must change
whenever the bundle contents change.

The implementation downloads with a pinned nf-core WGET module, verifies both
source MD5 values, decompresses the source FASTA, and applies the exclusions
BED with `bedtools maskfasta`. BED intervals use standard zero-based, half-open
semantics. Annotation assets and indexes are not represented by this initial
bundle and remain open rather than being represented by placeholder fields.

### Initial executable knowledge-bundle boundary

The current `prepare_knowledge_bundle` path validates that `--reference_bundle`
is a local bundle root with a parseable `manifest.json`, schema version `1`, and
a non-empty string `bundle_id`. It then stops with an unimplemented-workflow
error. It does not yet create a knowledge bundle, interpret a knowledge
specification, or select annotation assets.

### Knowledge-specification contract

The v1 knowledge-specification contract is defined in
[JSON specification contracts](#json-specification-contracts). It does not
describe implemented knowledge-bundle behavior or a schema for the nested
`knowledge` payload. The supplied reference bundle remains the single source
of truth for assembly, contig naming, and annotation identity. Any future
payload contract and translation behavior require separate approval.

### Compiled knowledge-bundle artifacts

The artifacts, payload translation behavior, and validation requirements of a
future compiled knowledge bundle remain open. Their definition is not implied
by the v1 envelope or its manifest provenance fields.

## Variant and MVP reporting boundary

The target contract requires genome-wide calling of single-nucleotide variants
(SNVs), insertions and deletions (indels), and structural variants (SVs).
Genome-wide call sets must be retained so that a sample can be re-analysed
against an updated knowledge bundle without repeating variant calling. The
exact formats and retention requirements for these call sets remain open.

The MVP report contains two finding categories: **Variants** and
**Translocations**. These are biological reporting categories, not partitions
based on variant size or a caller's representation. Report inclusion is limited
to findings matched by rules represented in the input knowledge bundle.

**Variants** contains findings that annotation predicts will affect one gene
and that match an AML/MDS gene or hotspot rule represented in the input
knowledge bundle. This category may include SNVs, indels, and single-gene
events represented by an SV caller. For example, an `FLT3` internal tandem
duplication or a `KMT2A` partial tandem duplication belongs in **Variants**,
irrespective of its underlying caller representation. The exact annotation
consequences, transcript policy, resources, and inclusion rules remain open.

**Translocations** contains events predicted to join gene partners that match
a recurrent-fusion rule represented in the input knowledge bundle. Inclusion
is independent of whether the underlying event is represented as a BND,
deletion, duplication, inversion, or another suitable SV representation.
Genome-wide SV calls are retained, but novel or otherwise potentially
interesting fusions outside the input knowledge bundle are not included in the
MVP report.

Copy-number alterations (CNAs, also called CNVs) are deferred. Reliable
tumor-only CNA analysis requires a separately designed read-depth background,
including an appropriate panel of normals. The panel's construction,
provenance, matching requirements, and validation remain open. Because CNA
analysis is outside the MVP, the MVP report omits a CNA section.

Handling of potentially germline findings is not defined by this variant-class
boundary and remains a separate matter spanning calling and filtering.

## Reporting boundary

The final report is intended for clinicians. It is not intended to be a
technical report for bioinformatics specialists.

The report will not provide:

- a diagnosis;
- a prognosis;
- a treatment recommendation; or
- patient-specific clinical interpretation.

The project does not define or validate downstream clinical review, sign-out,
or decision-making workflows.

Bundle identity, provenance, and compatibility records required for the
analysis output set are separate from the clinician-readable report.

## Runtime and engineering-verification boundary

The initial workflow implementation will use Nextflow DSL2 on Linux. Native
macOS, native Windows, and Windows Subsystem for Linux execution are not initial
support targets; this does not assert that the workflow cannot run on them.

The required Nextflow release is exactly `26.04.6`, the newest stable release
available when this contract was written. A future executable configuration
must set `manifest.nextflowVersion = '!26.04.6'`, and developer and continuous-
integration entry points must select `NXF_VER=26.04.6`. Updating Nextflow
requires a reviewed change that updates both pins and reruns the applicable
engineering tests. No unbounded minimum-version or latest-version declaration
meets this contract.

Fast engineering tests must run on Linux with Nextflow's local executor and
wholly synthetic inputs. They must not require an HPC scheduler, production
storage, protected data, or network access during execution. Slurm with
Apptainer is the required initial HPC compatibility target. Executor profiles,
resource policies, shared-cache and filesystem requirements, Apptainer launch
configuration, and environment-specific integration tests remain for a later
approved increment. Until those tests exist and pass on the target environment,
Slurm and Apptainer compatibility is intended rather than implemented or
verified behavior.

Workflow orchestration will connect channels, workflows, and subworkflows; it
will not embed the command implementation of analytical tools. A process that
wraps an external tool must have one coherent responsibility, declare version-
pinned and reconstructable dependencies, and remain reusable independently of
reporting policy. Future analytical wrappers will use applicable nf-core
component conventions as design guidance. This does not make OncoHawk an
nf-core pipeline or require compliance with the full nf-core pipeline template.
The need for targeted `nf-core modules lint` checks will be decided with the
first analytical module.

Structural input validation must be separately testable and complete before
analytical processes consume a sample-sheet record. The first executable
increment is therefore structural sample-sheet validation, not analytical
processing.

The engineering-test framework is nf-test. Its exact version must be pinned in
the separately approved increment that first adds the dependency. The minimum
engineering-verification layers for executable behavior are:

- native Nextflow linting for the workflow code in scope;
- focused nf-test assertions for functions, processes, or workflows at the
  narrowest useful boundary, including positive and negative cases;
- a local-executor smoke test of the affected end-to-end workflow path; and
- environment-specific integration tests before claiming implemented support
  for an HPC executor or production container runtime.

Tests must use the smallest wholly synthetic fixtures that exercise the stated
contract. Snapshot tests may supplement explicit assertions, but a stored
snapshot alone is not evidence that a result is scientifically correct.
Engineering tests prove only the behavior they assert. They are not analytical
or scientific validation and do not establish clinical readiness, performance,
or suitability for patient-care decisions.

## Open matters

This document does not yet decide:

- analytical methods, tools, or caller-specific representations;
- the contents, evidence hierarchy, source provenance, release process, or
  retirement process for curated resources;
- annotation assets, releases, and HGNC identifier mapping needed in reference
  bundles to resolve transcript targets and gene references;
- translation semantics for transcript exon rules, including transcript
  accession/version resolution, exon semantics, strand, padding expansion, and
  overlap handling;
- coordinate-resolution and VCF-normalization implementation for hotspot
  declarations;
- fusion breakpoint-matching semantics beyond the directional rule and
  endpoint-permutation requirement;
- bundle identifier and versioning schemes, manifest fields beyond the
  required identities and compiled-artifact checksums, or exact tool/index
  contents;
- source locations and download mechanics for default bundle specifications;
- the layout of a workflow output set, including existing-output-directory
  behavior;
- reporting thresholds, prioritization rules, or the report schema;
- technical, audit, or downstream machine-readable outputs other than the
  required recording of input-bundle identity, provenance, and compatibility
  relationship;
- Slurm profiles, resource policies, and site-specific execution configuration;
- production Apptainer image, provenance, cache, and launch requirements;
- cloud and managed-execution support;
- the exact nf-test version and targeted nf-core module checks to use when
  their respective dependencies are first introduced;
- analytical and scientific validation requirements;
- regulatory and quality-management requirements; or
- release criteria.
