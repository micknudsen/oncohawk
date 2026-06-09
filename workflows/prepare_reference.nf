/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    PREPARE_REFERENCE workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Produces an indexed reference for downstream alignment. Modes:

      1. `params.genome_fasta` is set  → use that FASTA as-is, build only
         the index if it doesn't already exist.
      2. otherwise                     → download from `params.genome_url`
         (default: GRCh38 no-alt analysis set), then index.

    Emits a single value channel `ch_reference` containing
        tuple( meta, path("bwamem2") )   — the bwa-mem2 index directory

    The index is published to `params.reference_dir/bwamem2/`.
    After running this workflow, set `params.ref_data_genome_bwamem2_index`
    to `<reference_dir>/bwamem2` in your profile config.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

include { WGET as WGET_GENOME_FASTA } from '../modules/nf-core/wget/main'
include { GUNZIP as GUNZIP_GENOME_FASTA } from '../modules/nf-core/gunzip/main'
include { BWAMEM2_INDEX } from '../modules/nf-core/bwamem2/index/main'

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

    // ── Source FASTA: either user-provided or downloaded ────────────────────
    if (params.genome_fasta) {
        ch_fasta = Channel
            .fromPath(params.genome_fasta, checkIfExists: true)
            .map { fasta -> [[id: fasta.baseName], fasta] }
    } else {
        def downloaded_name = params.genome_url.tokenize('/').last()
        def ext_idx = downloaded_name.lastIndexOf('.')
        if (ext_idx <= 0) {
            error "Genome URL must include a file extension: '${params.genome_url}'"
        }
        def downloaded_prefix = downloaded_name[0..<ext_idx]
        def downloaded_suffix = downloaded_name[(ext_idx + 1)..-1]

        WGET_GENOME_FASTA(Channel.value([[id: downloaded_prefix], params.genome_url, downloaded_suffix]))
        GUNZIP_GENOME_FASTA(WGET_GENOME_FASTA.out.outfile)
        ch_fasta = GUNZIP_GENOME_FASTA.out.gunzip
    }

    // ── bwa-mem2 index ──────────────────────────────────────────────────────
    // Output: tuple(meta, path("bwamem2")) — a directory named "bwamem2"
    // containing all index files under the genome prefix.
    BWAMEM2_INDEX(ch_fasta)

    emit:
    reference = BWAMEM2_INDEX.out.index
}
