/*
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *  Samplesheet parser / validator for ONCOHAWK
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 *  Expected CSV columns (header row required):
 *
 *      sample, library, flowcell, lane, fastq_1, fastq_2, spring
 *
 *  One row per (sample, library, lane) — a sample sequenced across multiple
 *  lanes will appear on multiple rows and be merged downstream.
 *
 *  The parse(row) method returns a 3-tuple:
 *
 *      [ meta, input_type, reads ]
 *
 *  where `meta` is a LinkedHashMap with:
 *
 *      sample        — sample name (SM)
 *      library       — library name (LB)
 *      flowcell      — flowcell id  (used in @RG ID and PU)
 *      lane          — lane number  (used in @RG ID and PU)
 *      id            — unique per-row id: "${sample}.${library}.${flowcell}.${lane}"
 *      read_group    — pre-formatted @RG string ready for `bwa-mem2 mem -R`

 *
 *  Exactly one input type must be provided per row:
 *      - FASTQ pair via fastq_1 + fastq_2
 *      - SPRING archive via spring
 *
 *  Paths may be absolute or relative to directory containing samplesheet
 *  (resolved upstream by Channel.fromPath).
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 */

import nextflow.Nextflow

class Samplesheet {

    // Required columns in the input CSV
    static final List<String> REQUIRED_COLUMNS = [
        'sample',
        'library',
        'flowcell',
        'lane',
    ]

    static final List<String> INPUT_COLUMNS = [
        'fastq_1',
        'fastq_2',
        'spring',
    ]


    /**
    * Parse a single CSV row (already split into a Map<String,String> by
    * `splitCsv(header: true)`) into a [meta, input_type, reads] tuple.
     *
    * If `samplesheet_dir` is non-null, relative input paths are resolved
    * against it (the directory containing the samplesheet).
     * Absolute paths are used as-is.
     */
    static List parse(Map row, Object samplesheet_dir = null) {


        // ── Validate required columns are present ───────────────────────────
        def missing = REQUIRED_COLUMNS.findAll { !row.containsKey(it) }
        if (missing) {
            Nextflow.error("Samplesheet is missing required column(s): ${missing.join(', ')}. " +
                           "Required columns: ${REQUIRED_COLUMNS.join(', ')}")
        }

        def missing_input_cols = INPUT_COLUMNS.findAll { !row.containsKey(it) }
        if (missing_input_cols) {
            Nextflow.error("Samplesheet is missing required input column(s): ${missing_input_cols.join(', ')}. " +
                           "Required input columns: ${INPUT_COLUMNS.join(', ')}")
        }

        // ── Validate non-empty required values ──────────────────────────────
        def empty = REQUIRED_COLUMNS.findAll { !row[it]?.toString()?.trim() }
        if (empty) {
            Nextflow.error("Samplesheet row has empty value(s) for required column(s): " +
                           "${empty.join(', ')} (row: ${row})")
        }

        def sample     = row.sample.toString().trim()
        def library    = row.library.toString().trim()
        def flowcell   = row.flowcell.toString().trim()
        def lane       = row.lane.toString().trim()
        def fastq_1    = row.fastq_1?.toString()?.trim() ?: ''
        def fastq_2    = row.fastq_2?.toString()?.trim() ?: ''
        def spring     = row.spring?.toString()?.trim() ?: ''

        // ── Basic format validation ─────────────────────────────────────────
        if (!(lane ==~ /\d+/)) {
            Nextflow.error("Samplesheet 'lane' must be an integer, got '${lane}' for sample '${sample}'")
        }
        // ── Build a unique row id and a canonical @RG string ────────────────
        def id = "${sample}.${library}.${flowcell}.${lane}".toString()
        def rg_id = "${flowcell}.${lane}".toString()
        def rg_pu = "${flowcell}.${lane}.${library}".toString()
        def read_group = "@RG\\tID:${rg_id}\\tSM:${sample}\\tLB:${library}\\tPL:ILLUMINA\\tPU:${rg_pu}".toString()

        def meta = [
            id         : id,
            sample     : sample,
            library    : library,
            flowcell   : flowcell,
            lane       : lane,
            read_group : read_group,
            single_end : false,
        ]

        def has_fastq = fastq_1 && fastq_2
        def has_partial_fastq = (fastq_1 && !fastq_2) || (!fastq_1 && fastq_2)
        def has_spring = spring as boolean

        if (has_partial_fastq) {
            Nextflow.error("Samplesheet row must include both fastq_1 and fastq_2 when using FASTQ input (row: ${row})")
        }
        if (has_fastq && has_spring) {
            Nextflow.error("Samplesheet row must specify either FASTQ columns (fastq_1, fastq_2) or spring, not both (row: ${row})")
        }
        if (!has_fastq && !has_spring) {
            Nextflow.error("Samplesheet row must specify one input type: FASTQ pair (fastq_1, fastq_2) or spring (row: ${row})")
        }

        if (has_fastq) {
            def r1 = resolvePath(fastq_1, samplesheet_dir)
            def r2 = resolvePath(fastq_2, samplesheet_dir)
            return [ meta, 'fastq', [r1, r2] ]
        }

        def spring_file = resolvePath(spring, samplesheet_dir)
        return [ meta, 'spring', spring_file ]
    }

    /**
     * Resolve a possibly-relative path against the samplesheet directory.
     * Absolute paths (and URIs like s3://, https://) are returned as-is.
     */
    private static Object resolvePath(String path, Object samplesheet_dir) {
        if (samplesheet_dir == null) {
            return Nextflow.file(path, checkIfExists: true)
        }
        // Absolute path or remote URI → use directly
        if (path.startsWith('/') || path =~ /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//) {
            return Nextflow.file(path, checkIfExists: true)
        }
        // Relative path → resolve against the samplesheet's directory
        return Nextflow.file("${samplesheet_dir}/${path}".toString(), checkIfExists: true)
    }
}

