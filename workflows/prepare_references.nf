/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    PREPARE_REFERENCES workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Downloads the GRCh38 no-alt analysis set reference genome and creates all
    indexes required by the pipeline (samtools faidx, bwa-mem2 index).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    WORKFLOW
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow PREPARE_REFERENCES {

    main:

    log.info """\
        ╔══════════════════════════════════════════════════════╗
        ║          ONCOHAWK — PREPARE_REFERENCES               ║
        ╚══════════════════════════════════════════════════════╝
        Reference directory : ${params.reference_dir}
        """.stripIndent()

    // ── Placeholder: modules will be added in Step 2 ────────────────────────
    // WGET_GENOME()
    // SAMTOOLS_FAIDX(WGET_GENOME.out.fasta)
    // BWA_MEM2_INDEX(WGET_GENOME.out.fasta)

    log.warn "PREPARE_REFERENCES workflow is not yet implemented. Coming in Step 2."

}
