/*
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *  Samplesheet parser / validator for ONCOHAWK
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 *  Expected CSV columns (header row required):
 *
 *      sample_id, filetype, info, filepath
 *
 *  `info` must include `library_id` and `lane`.
 *  `filepath` must contain either one spring archive path or two FASTQ paths
 *  separated by ';'.
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
 *      - filetype=fastq with two paths in filepath separated by ';'
 *      - filetype=spring with one archive path in filepath
 *
 *  Paths may be absolute or relative to directory containing samplesheet
 *  (resolved upstream by Channel.fromPath).
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 */

import nextflow.Nextflow

class Samplesheet {

    static final List<String> REQUIRED_COLUMNS = [
        'sample_id',
        'filetype',
        'info',
        'filepath',
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
        def missing = REQUIRED_COLUMNS.findAll { !row.containsKey(it) }
        if (missing) {
            Nextflow.error("Samplesheet is missing required column(s): ${missing.join(', ')}. " +
                           "Required columns: ${REQUIRED_COLUMNS.join(', ')}")
        }

        def empty = REQUIRED_COLUMNS.findAll { !row[it]?.toString()?.trim() }
        if (empty) {
            Nextflow.error("Samplesheet row has empty value(s) for required column(s): " +
                           "${empty.join(', ')} (row: ${row})")
        }

        def sample = row.sample_id.toString().trim()
        def filetype = row.filetype.toString().trim().toLowerCase()
        def info = parseInfo(row.info.toString().trim())
        def filepath = row.filepath.toString().trim()

        def library = firstNonBlank(info.library_id)
        def lane = firstNonBlank(info.lane)
        def flowcell = 'NA'
        def fastq_1 = ''
        def fastq_2 = ''
        def spring = ''

        if (!library) {
            Nextflow.error("Samplesheet row must include library_id in info (row: ${row})")
        }
        if (!lane) {
            Nextflow.error("Samplesheet row must include lane in info (row: ${row})")
        }

        if (filetype == 'fastq') {
            def paths = filepath.split(/\s*;\s*/).findAll { it }
            if (paths.size() != 2) {
                Nextflow.error("Samplesheet row with filetype 'fastq' must provide exactly two paths in filepath separated by ';' (row: ${row})")
            }
            fastq_1 = paths[0]
            fastq_2 = paths[1]
        }
        else if (filetype == 'spring') {
            spring = filepath
        }
        else {
            Nextflow.error("Unsupported filetype '${filetype}' in samplesheet row: ${row}")
        }

        // ── Basic format validation ─────────────────────────────────────────
        if (!(lane ==~ /\d+/)) {
            Nextflow.error("Samplesheet 'lane' must be an integer, got '${lane}' for sample '${sample}'")
        }

        def has_fastq = fastq_1 && fastq_2
        def has_partial_fastq = (fastq_1 && !fastq_2) || (!fastq_1 && fastq_2)
        def has_spring = spring as boolean

        if (has_partial_fastq) {
            Nextflow.error("Samplesheet row with filetype 'fastq' must provide exactly two paths in filepath separated by ';' (row: ${row})")
        }
        if (has_fastq && has_spring) {
            Nextflow.error("Samplesheet row must specify either filetype=fastq or filetype=spring, not both (row: ${row})")
        }
        if (!has_fastq && !has_spring) {
            Nextflow.error("Samplesheet row must specify one input type via filetype=fastq or filetype=spring (row: ${row})")
        }

        // ── Build a unique row id and a canonical @RG string ────────────────
        def id = "${sample}.${library}.${lane}".toString()
        def rg_id = "${sample}.${library}.${lane}".toString()
        def rg_pu = "${sample}.${library}.${lane}".toString()
        def read_group = "@RG\\tID:${rg_id}\\tSM:${sample}\\tLB:${library}\\tPL:ILLUMINA\\tPU:${rg_pu}".toString()

        def meta = [
            id         : id,
            sample     : sample,
            library    : library,
            flowcell   : flowcell,
            lane       : lane,
            filetype   : filetype,
            read_group : read_group,
            single_end : false,
        ]

        if (has_fastq) {
            def r1 = resolvePath(fastq_1, samplesheet_dir)
            def r2 = resolvePath(fastq_2, samplesheet_dir)
            return [ meta, 'fastq', [r1, r2] ]
        }

        def spring_file = resolvePath(spring, samplesheet_dir)
        return [ meta, 'spring', spring_file ]
    }

    private static String firstNonBlank(Object... values) {
        for (def value in values) {
            def text = value?.toString()?.trim()
            if (text) {
                return text
            }
        }
        return null
    }

    private static Map parseInfo(String info) {
        def parsed = [:]
        if (!info) {
            return parsed
        }

        info.split(/\s*;\s*/).each { entry ->
            if (!entry) {
                return
            }

            def parts = entry.split(/\s*:\s*/, 2)
            if (parts.size() == 2 && parts[0]) {
                parsed[parts[0].trim()] = parts[1].trim()
            }
        }

        return parsed
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

