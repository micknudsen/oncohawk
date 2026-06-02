/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    PREPARE_REFERENCE workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Produces an indexed reference for downstream alignment. Modes:

      1. `params.genome_fasta` is set  → use that FASTA as-is, build only
         the indexes that don't already exist alongside it.
      2. otherwise                     → download from `params.genome_url`
         (default: GRCh38 no-alt analysis set), then index.

    Emits a single value channel `ch_reference` containing
        tuple( fasta, bwa_0123, bwa_amb, bwa_ann, bwa_bwt_2bit_64, bwa_pac )

    Following YAGNI: only the bwa-mem2 index is built here. Other indexes
    (faidx, dict, ...) will be added by later workflow phases as the tools
    that need them are introduced.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

include { WGET_GENOME   } from '../modules/local/wget_genome/main'
include { BWAMEM2_INDEX } from '../modules/local/bwamem2/index/main'

workflow PREPARE_REFERENCE {

    main:

    log.info """\

        ╔══════════════════════════════════════════════════════╗
        ║          ONCOHAWK — PREPARE_REFERENCE                ║
        ╚══════════════════════════════════════════════════════╝
        Reference directory : ${params.reference_dir}
        Genome FASTA        : ${params.genome_fasta ?: '(will download)'}
        Genome URL          : ${params.genome_url}
        """.stripIndent()

    ch_versions = Channel.empty()

    // ── Source FASTA: either user-provided or downloaded ────────────────────
    if (params.genome_fasta) {
        ch_fasta = Channel.fromPath(params.genome_fasta, checkIfExists: true)
    } else {
        WGET_GENOME(Channel.value(params.genome_url))
        ch_fasta    = WGET_GENOME.out.fasta
        ch_versions = ch_versions.mix(WGET_GENOME.out.versions)
    }

    // ── bwa-mem2 index ──────────────────────────────────────────────────────
    BWAMEM2_INDEX(ch_fasta)
    ch_versions = ch_versions.mix(BWAMEM2_INDEX.out.versions)

    emit:
    reference = BWAMEM2_INDEX.out.index
    versions  = ch_versions
}
