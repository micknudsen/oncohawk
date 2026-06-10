/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ONCOHAWK workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

include { CUTADAPT              } from '../modules/nf-core/cutadapt/main'
include { SPRING_DECOMPRESS     } from '../modules/nf-core/spring/decompress/main'
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

    def genome_fasta = params.ref_data_genome_fasta ?: params.genome_fasta
    def genome_bwamem2_index = params.ref_data_genome_bwamem2_index ?: params.genome_bwamem2_index

    log.info """\
        ╔══════════════════════════════════════════════════════╗
        ║                  ONCOHAWK                            ║
        ╚══════════════════════════════════════════════════════╝
        Samplesheet  : ${params.input}
        Output dir   : ${params.outdir}
        Genome FASTA : ${genome_fasta ?: '(not set)'}
        BWA-MEM2 idx : ${genome_bwamem2_index ?: '(not set)'}
        """.stripIndent()

    // ── Validate required params ─────────────────────────────────────────────
    if (!params.input) {
        error "No samplesheet provided. Please specify --input <samplesheet.csv>"
    }
    if (!genome_fasta) {
        error "Reference FASTA not set. Use --genome_fasta (or --ref_data_genome_fasta), " +
              "or run --workflow prepare_reference first and set it in config."
    }
    if (!genome_bwamem2_index) {
        error "BWA-MEM2 index path not set. Use --genome_bwamem2_index (or --ref_data_genome_bwamem2_index), " +
              "or run --workflow prepare_reference first and set it in config."
    }

    // ── Reference channels (value channels — reused by all alignment tasks) ──
    // ch_bwamem2_index: the bwamem2/ directory produced by BWAMEM2_INDEX
    ch_bwamem2_index = Channel.value([
        [id: 'genome'],
        file(genome_bwamem2_index, checkIfExists: true),
    ])
    // ch_fasta: only needed for CRAM output; unused here but required by BWAMEM2_MEM
    ch_fasta = Channel.value([[id: 'genome'], []])

    // ── Parse samplesheet ────────────────────────────────────────────────────
    def samplesheet_file = file(params.input, checkIfExists: true)
    def samplesheet_dir  = samplesheet_file.parent

    // Samplesheet.parse emits [meta, input_type, reads].
    ch_samples = Channel
        .fromPath(samplesheet_file)
        .splitCsv(header: true, strip: true)
        .map { row -> Samplesheet.parse(row, samplesheet_dir) }

    ch_reads_fastq = ch_samples
        .filter { _meta, input_type, _reads -> input_type == 'fastq' }
        .map { meta, _input_type, reads -> [meta, reads] }

    ch_reads_spring = ch_samples
        .filter { _meta, input_type, _reads -> input_type == 'spring' }
        .map { meta, _input_type, spring_file -> [meta, spring_file] }

    SPRING_DECOMPRESS(ch_reads_spring, false)

    ch_reads_spring_fastq = SPRING_DECOMPRESS.out.fastq
        .map { meta, reads -> [meta, reads.sort { read_file -> read_file.name }] }

    ch_reads = ch_reads_fastq.mix(ch_reads_spring_fastq)

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
