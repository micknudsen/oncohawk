/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ONCOHAWK workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

include { CUTADAPT_BWAMEM2_MEM } from '../modules/local/bwamem2/mem/main'
include { SAMTOOLS_MERGE } from '../modules/local/samtools/merge/main'
include { SAMBAMBA_MARKDUP } from '../modules/local/sambamba/markdup/main'

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

    // ── Adapter trimming + alignment (streamed) ───────────────────────────
    CUTADAPT_BWAMEM2_MEM(ch_reads, ch_reference)
    ch_versions = ch_versions.mix(CUTADAPT_BWAMEM2_MEM.out.versions)

    // ── Merge lane-level BAMs to one BAM per sample ────────────────────────
    ch_bams_by_sample = CUTADAPT_BWAMEM2_MEM.out.bam
        .map { meta, bam ->
            def sample_meta = [
                id    : meta.sample,
                sample: meta.sample,
            ]
            tuple(sample_meta, bam)
        }
        .groupTuple()

    SAMTOOLS_MERGE(ch_bams_by_sample)
    ch_versions = ch_versions.mix(SAMTOOLS_MERGE.out.versions)

    // ── Duplicate marking with sambamba ────────────────────────────────────
    SAMBAMBA_MARKDUP(SAMTOOLS_MERGE.out.bam)
    ch_versions = ch_versions.mix(SAMBAMBA_MARKDUP.out.versions)

    emit:
    bam      = SAMBAMBA_MARKDUP.out.bam
    bai      = SAMBAMBA_MARKDUP.out.bai
    markdup  = SAMBAMBA_MARKDUP.out.bam
    versions = ch_versions
}
