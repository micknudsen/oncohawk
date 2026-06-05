/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ONCOHAWK workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

include { CUTADAPT              } from '../modules/nf-core/cutadapt/main'
include { BWAMEM2_MEM           } from '../modules/nf-core/bwamem2/mem/main'
include { SAMTOOLS_MERGE        } from '../modules/nf-core/samtools/merge/main'
include { PICARD_MARKDUPLICATES } from '../modules/nf-core/picard/markduplicates/main'

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

    // ── Reference channels (value channels — reused by all alignment tasks) ──
    // ch_bwamem2_index: the bwamem2/ directory produced by BWAMEM2_INDEX
    ch_bwamem2_index = Channel.value([
        [id: 'genome'],
        file(params.ref_data_genome_bwamem2_index, checkIfExists: true),
    ])
    // ch_fasta: only needed for CRAM output; unused here but required by BWAMEM2_MEM
    ch_fasta = Channel.value([[id: 'genome'], []])

    // ── Parse samplesheet ────────────────────────────────────────────────────
    def samplesheet_file = file(params.input, checkIfExists: true)
    def samplesheet_dir  = samplesheet_file.parent

    // Samplesheet.parse emits [meta, r1, r2]; reshape to [meta, [r1, r2]] for CUTADAPT
    ch_reads = Channel
        .fromPath(samplesheet_file)
        .splitCsv(header: true, strip: true)
        .map { row -> Samplesheet.parse(row, samplesheet_dir) }
        .map { meta, r1, r2 -> [meta, [r1, r2]] }

    // ── Step 1: Adapter trimming (one task per lane) ──────────────────────
    CUTADAPT(ch_reads)

    // ── Step 2: Alignment + coordinate sort (one task per lane) ──────────
    // sort_bam = true  →  samtools sort is used inside the module
    BWAMEM2_MEM(CUTADAPT.out.reads, ch_bwamem2_index, ch_fasta, true)

    // ── Step 3: Merge lane-level BAMs to one BAM per sample ──────────────
    ch_bams_by_sample = BWAMEM2_MEM.out.bam
        .map { meta, bam ->
            def sample_meta = [
                id        : meta.sample,
                sample    : meta.sample,
                single_end: false,
            ]
            tuple(sample_meta, bam)
        }
        .groupTuple()
        .map { meta, bams -> [meta, bams, []] }   // no index files needed for BAM merge

    // No fasta reference needed for BAM merge (only required for CRAM)
    ch_merge_ref = Channel.value([[id: 'null'], [], [], []])

    SAMTOOLS_MERGE(ch_bams_by_sample, ch_merge_ref)

    // ── Step 4: Duplicate marking with Picard MarkDuplicates ─────────────
    // No fasta reference needed for BAM output
    ch_markdup_ref = Channel.value([[id: 'null'], [], []])

    PICARD_MARKDUPLICATES(SAMTOOLS_MERGE.out.bam, ch_markdup_ref)

    emit:
    bam     = PICARD_MARKDUPLICATES.out.bam
    bai     = PICARD_MARKDUPLICATES.out.bai
    metrics = PICARD_MARKDUPLICATES.out.metrics
}
