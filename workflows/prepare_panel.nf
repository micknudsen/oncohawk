/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    PREPARE_PANEL workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Design genomic panel from GENCODE GTF and gene selection JSON config.
    
    Input:
      - params.panel_genes_config: JSON file with genes/transcripts to include
      - params.panel_gencode_gtf: GENCODE GTF file
    
    Output:
      - panel.bed: BED file with selected CDS regions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

include { PANEL_DESIGN } from '../modules/local/panel_design/main'

workflow PREPARE_PANEL {

    main:

    log.info """\

        ╔══════════════════════════════════════════════════════╗
        ║          ONCOHAWK — PREPARE_PANEL                    ║
        ╚══════════════════════════════════════════════════════╝
        Panel genes config : ${params.panel_genes_config ?: '(not set)'}
        GENCODE GTF        : ${params.panel_gencode_gtf ?: '(not set)'}
        """.stripIndent()

    // ── Validate required parameters ────────────────────────────────────────
    if (!params.panel_genes_config) {
        error "Panel genes config not set. Use --panel_genes_config <config.json>"
    }
    if (!params.panel_gencode_gtf) {
        error "GENCODE GTF not set. Use --panel_gencode_gtf <gencode.gtf.gz>"
    }

    // ── Load inputs ─────────────────────────────────────────────────────────
    def config_file = file(params.panel_genes_config, checkIfExists: true)
    def gtf_file = file(params.panel_gencode_gtf, checkIfExists: true)

    // Metadata for the panel (single meta)
    def panel_meta = [id: 'panel']

    // Get the Python script from bin directory
    def panel_builder_script = file("${projectDir}/bin/gtf_panel_builder.py", checkIfExists: true)

    // ── Run PANEL_DESIGN ────────────────────────────────────────────────────
    ch_panel = channel.value([panel_meta, gtf_file])

    PANEL_DESIGN(ch_panel, config_file, panel_builder_script)

    emit:
    bed      = PANEL_DESIGN.out.bed
    panel_log = PANEL_DESIGN.out.panel_log
    versions = PANEL_DESIGN.out.versions
}
