/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ONCOHAWK workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

include { TRIM_AND_MAP_FASTQ } from '../modules/local/trim_and_map_fastq/main'
include { MERGE_LANE_BAMS } from '../modules/local/merge_lane_bams/main'
include { MARK_DUPLICATES } from '../modules/local/mark_duplicates/main'

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
    TRIM_AND_MAP_FASTQ(ch_reads, ch_reference)
    ch_versions = ch_versions.mix(TRIM_AND_MAP_FASTQ.out.versions)

    // ── Merge lane-level BAMs to one BAM per sample ────────────────────────
    ch_bams_by_sample = TRIM_AND_MAP_FASTQ.out.bam
        .map { meta, bam ->
            def sample_meta = [
                id    : meta.sample,
                sample: meta.sample,
            ]
            tuple(sample_meta, bam)
        }
        .groupTuple()

    MERGE_LANE_BAMS(ch_bams_by_sample)
    ch_versions = ch_versions.mix(MERGE_LANE_BAMS.out.versions)

    // ── Duplicate marking with sambamba ────────────────────────────────────
    MARK_DUPLICATES(MERGE_LANE_BAMS.out.bam)
    ch_versions = ch_versions.mix(MARK_DUPLICATES.out.versions)

    emit:
    bam      = MARK_DUPLICATES.out.bam
    bai      = MARK_DUPLICATES.out.bai
    markdup  = MARK_DUPLICATES.out.bam
    versions = ch_versions
}
