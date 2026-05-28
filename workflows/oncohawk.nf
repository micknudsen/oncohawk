/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ONCOHAWK workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

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

    // ── Log parsed samples (debug visibility) ────────────────────────────────
    ch_reads.view { meta, r1, r2 ->
        "  Parsed: ${meta.id}  | sample=${meta.sample} library=${meta.library} " +
        "lane=${meta.lane} flowcell=${meta.flowcell}\n" +
        "          R1=${r1.name}\n" +
        "          R2=${r2.name}\n" +
        "          RG=${meta.read_group}"
    }

    // ── Placeholder: downstream subworkflows added in subsequent phases ──────
    // PREPARE_INPUTS(ch_reads)
    // READ_ALIGNMENT(PREPARE_INPUTS.out.reads, ch_reference)
    // MARK_DUPLICATES(READ_ALIGNMENT.out.bam)

}
