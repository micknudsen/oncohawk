# Workflow process names

Both workflows name their processes by responsibility: **subject or role first, action last**. These names appear in the console, trace, reports, DAG, and scheduler jobs. The alignment and annotation references have explicit, parallel names for equivalent operations.

Workflow imports alias the underlying modules. The nf-core module files and their tool names remain unchanged. Use the workflow names below in site configuration selectors, for example `withName: READS_ALIGN`.

## Reference preparation

| Previous process name | Workflow process name | Implementation |
| --- | --- | --- |
| `REFERENCE_DOWNLOAD` | `REFERENCE_DOWNLOAD` | Local source acquisition |
| `GUNZIP` | `ALIGNMENT_FASTA_DECOMPRESS` | gunzip |
| `ANNOTATION_GUNZIP` | `ANNOTATION_FASTA_DECOMPRESS` | gunzip |
| `REFERENCE_VALIDATE` | `REFERENCE_VALIDATE` | Local reference validation |
| `SAMTOOLS_FAIDX` | `ALIGNMENT_FASTA_INDEX` | SAMtools faidx |
| `ANNOTATION_FAIDX` | `ANNOTATION_FASTA_INDEX` | SAMtools faidx |
| `BEDTOOLS_MASKFASTA` | `ALIGNMENT_FASTA_MASK` | BEDTools maskfasta |
| `ANNOTATION_PREPARE` | `ANNOTATION_PREPARE` | Local annotation preparation |
| `BWAMEM2_INDEX` | `ALIGNMENT_MAPPER_INDEX` | bwa-mem2 index |
| `PICARD_CREATESEQUENCEDICTIONARY` | `ALIGNMENT_SEQUENCE_DICTIONARY_CREATE` | Picard CreateSequenceDictionary |
| `REFERENCE_BUNDLE` | `REFERENCE_BUNDLE_ASSEMBLE` | Local bundle packaging |

## Sample analysis

| Previous process name | Workflow process name | Implementation |
| --- | --- | --- |
| `CUTADAPT` | `READS_TRIM` | Cutadapt |
| `BWAMEM2_MEM` | `READS_ALIGN` | bwa-mem2 mem |
| `SAMTOOLS_MERGE` | `SAMPLE_ALIGNMENTS_MERGE` | SAMtools merge |
| `PICARD_MARKDUPLICATES` | `SAMPLE_DUPLICATES_MARK` | Picard MarkDuplicates |
| `SAMTOOLS_INDEX` | `SAMPLE_BAM_INDEX` | SAMtools index |
| `GATK4_MUTECT2` | `VARIANTS_CALL` | GATK Mutect2 |
| `GATK4_FILTERMUTECTCALLS` | `VARIANTS_FILTER` | GATK FilterMutectCalls |
| `ENSEMBLVEP_VEP` | `VARIANT_CONSEQUENCES_ANNOTATE` | Ensembl VEP |

## Updating existing configurations and runs

Update process selectors in your site configuration and any scripts that parse task names using these tables. Fully qualified names retain the workflow prefix, for example `ONCOHAWK:READS_ALIGN` and `PREPARE_REFERENCE_BUNDLE:ANNOTATION_FASTA_INDEX`. To configure both FASTA index tasks, use `withName: 'ALIGNMENT_FASTA_INDEX|ANNOTATION_FASTA_INDEX'`.

Process names contribute to Nextflow task identity, so renamed tasks can rerun when resuming work created before this change. The separate download store retains its existing keys and verified assets. Existing reference bundles remain usable.

These aliases preserve task labels, resource allocations, commands, container pins, and published artifact names. Caller and annotation tool identifiers remain in output names such as `sample.mutect2.vcf.gz` and `sample.mutect2.vep.vcf.gz`. Tool identities remain available through the module imports, commands, and reference-bundle provenance.
