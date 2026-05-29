/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ONCOHAWK workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

include { CUTADAPT    } from '../modules/local/cutadapt/main'
include { BWAMEM2_MEM } from '../modules/local/bwamem2/mem/main'

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
        Genome FASTA : ${params.ref_data_genome_fasta ?: '(not set)'}
        BWA-MEM2 idx : ${params.ref_data_genome_bwamem2_index ?: '(not set)'}
        """.stripIndent()

    // ── Validate required params ─────────────────────────────────────────────
    if (!params.input) {
        error "No samplesheet provided. Please specify --input <samplesheet.csv>"
    }
    if (!params.ref_data_genome_fasta) {
        error "params.ref_data_genome_fasta is not set. " +
              "Run --workflow prepare_reference first, then set this param in your config."
    }
    if (!params.ref_data_genome_bwamem2_index) {
        error "params.ref_data_genome_bwamem2_index is not set. " +
              "Run --workflow prepare_reference first, then set this param in your config."
    }

    // ── Reference channel (value channel — reused by all alignment tasks) ────
    ch_reference = Channel.value([
        file(params.ref_data_genome_fasta,         checkIfExists: true),
        file(params.ref_data_genome_bwamem2_index, checkIfExists: true),
    ])

    // ── Parse samplesheet ────────────────────────────────────────────────────
    def samplesheet_file = file(params.input, checkIfExists: true)
    def samplesheet_dir  = samplesheet_file.parent

    ch_reads = Channel
        .fromPath(samplesheet_file)
        .splitCsv(header: true, strip: true)
        .map { row -> Samplesheet.parse(row, samplesheet_dir) }

    ch_versions = Channel.empty()

    // ── Adapter trimming ─────────────────────────────────────────────────────
    CUTADAPT(ch_reads)
    ch_versions = ch_versions.mix(CUTADAPT.out.versions)

    // ── Alignment (bwa-mem2 mem | samtools sort) ─────────────────────────────
    BWAMEM2_MEM(CUTADAPT.out.reads, ch_reference)
    ch_versions = ch_versions.mix(BWAMEM2_MEM.out.versions)

    // ── Placeholder: downstream subworkflows added in subsequent phases ──────
    // MARK_DUPLICATES(BWAMEM2_MEM.out.bam)

    emit:
    bam      = BWAMEM2_MEM.out.bam
    versions = ch_versions
}
