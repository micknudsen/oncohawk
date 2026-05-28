/*
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *  Samplesheet parser / validator for ONCOHAWK
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 *  Expected CSV columns (header row required):
 *
 *      sample, library, instrument, flowcell, lane, fastq_1, fastq_2
 *
 *  One row per (sample, library, lane) — a sample sequenced across multiple
 *  lanes will appear on multiple rows and be merged downstream.
 *
 *  The parse(row) method returns a 3-tuple:
 *
 *      [ meta, fastq_1_file, fastq_2_file ]
 *
 *  where `meta` is a LinkedHashMap with:
 *
 *      sample        — sample name (SM)
 *      library       — library name (LB)
 *      instrument    — instrument id (used only for documentation / read names)
 *      flowcell      — flowcell id  (used in PU)
 *      lane          — lane number  (used in PU and RG ID)
 *      id            — unique per-row id: "${sample}.${library}.${flowcell}.${lane}"
 *      read_group    — pre-formatted @RG string ready for `bwa-mem2 mem -R`
 *
 *  Paths in `fastq_1` / `fastq_2` may be absolute or relative to the directory
 *  containing the samplesheet (resolved upstream by Channel.fromPath).
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 */

import nextflow.Nextflow

class Samplesheet {

    // Required columns in the input CSV
    static final List<String> REQUIRED_COLUMNS = [
        'sample',
        'library',
        'instrument',
        'flowcell',
        'lane',
        'fastq_1',
        'fastq_2',
    ]

    /**
     * Parse a single CSV row (already split into a Map<String,String> by
     * `splitCsv(header: true)`) into a [meta, r1, r2] tuple.
     *
     * If `samplesheet_dir` is non-null, relative `fastq_1` / `fastq_2` paths
     * are resolved against it (the directory containing the samplesheet).
     * Absolute paths are used as-is.
     */
    static List parse(Map row, Object samplesheet_dir = null) {


        // ── Validate required columns are present ───────────────────────────
        def missing = REQUIRED_COLUMNS.findAll { !row.containsKey(it) }
        if (missing) {
            Nextflow.error("Samplesheet is missing required column(s): ${missing.join(', ')}. " +
                           "Required columns: ${REQUIRED_COLUMNS.join(', ')}")
        }

        // ── Validate non-empty required values ──────────────────────────────
        def empty = REQUIRED_COLUMNS.findAll { !row[it]?.toString()?.trim() }
        if (empty) {
            Nextflow.error("Samplesheet row has empty value(s) for required column(s): " +
                           "${empty.join(', ')} (row: ${row})")
        }

        def sample     = row.sample.toString().trim()
        def library    = row.library.toString().trim()
        def instrument = row.instrument.toString().trim()
        def flowcell   = row.flowcell.toString().trim()
        def lane       = row.lane.toString().trim()
        def fastq_1    = row.fastq_1.toString().trim()
        def fastq_2    = row.fastq_2.toString().trim()

        // ── Basic format validation ─────────────────────────────────────────
        if (!(lane ==~ /\d+/)) {
            Nextflow.error("Samplesheet 'lane' must be an integer, got '${lane}' for sample '${sample}'")
        }

        // ── Build a unique row id and a canonical @RG string ────────────────
        def id = "${sample}.${library}.${flowcell}.${lane}".toString()
        def rg_id = "${flowcell}.${lane}".toString()
        def rg_pu = "${flowcell}.${lane}.${sample}".toString()
        def read_group = "@RG\\tID:${rg_id}\\tSM:${sample}\\tLB:${library}\\tPL:ILLUMINA\\tPU:${rg_pu}".toString()

        def meta = [
            id         : id,
            sample     : sample,
            library    : library,
            instrument : instrument,
            flowcell   : flowcell,
            lane       : lane,
            read_group : read_group,
        ]

        // ── Resolve FASTQ paths (relative paths resolved against samplesheet dir) ──
        def r1 = resolvePath(fastq_1, samplesheet_dir)
        def r2 = resolvePath(fastq_2, samplesheet_dir)

        return [ meta, r1, r2 ]
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

