/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ONCOHAWK workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

include { CUTADAPT } from '../modules/local/cutadapt/main'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    WORKFLOW
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow ONCOHAWK {

    main:

    log.info """\
        ╔══════════════════════════════════════════════════════╗
        ║                  ONCOHAWK                            ║
        ╚══════════════════════════════════════════════════════╝
        Samplesheet  : ${params.input}
        Output dir   : ${params.outdir}
        Reference    : ${params.genome_fasta ?: '(not set)'}
        """.stripIndent()

    // ── Validate input ───────────────────────────────────────────────────────
    if (!params.input) {
        error "No samplesheet provided. Please specify --input <samplesheet.csv>"
    }

    // Path object for the samplesheet, used to resolve relative FASTQ paths.
    def samplesheet_file = file(params.input, checkIfExists: true)
    def samplesheet_dir  = samplesheet_file.parent

    // ── Parse samplesheet ────────────────────────────────────────────────────
    ch_reads = Channel
        .fromPath(samplesheet_file)
        .splitCsv(header: true, strip: true)
        .map { row -> Samplesheet.parse(row, samplesheet_dir) }

    ch_versions = Channel.empty()

    // ── Adapter trimming ─────────────────────────────────────────────────────
    CUTADAPT(ch_reads)
    ch_versions = ch_versions.mix(CUTADAPT.out.versions)

    // ── Placeholder: downstream subworkflows added in subsequent phases ──────
    // READ_ALIGNMENT(CUTADAPT.out.reads, ch_reference)
    // MARK_DUPLICATES(READ_ALIGNMENT.out.bam)

    emit:
    reads_trimmed = CUTADAPT.out.reads
    versions      = ch_versions
}

