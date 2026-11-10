include { CUTADAPT } from '../modules/nf-core/cutadapt/main'
include { BWAMEM2_MEM } from '../modules/nf-core/bwamem2/mem/main'
include { SAMTOOLS_MERGE } from '../modules/nf-core/samtools/merge/main'
include { PICARD_MARKDUPLICATES } from '../modules/nf-core/picard/markduplicates/main'
include { SAMTOOLS_INDEX } from '../modules/nf-core/samtools/index/main'

def inputOptions(value, row_number) {
    def options = [:]
    if (!value?.trim())
        return options
    value.split(';', -1).each { entry ->
        def parts = entry.split('=', -1).collect { it.trim() }
        if (parts.size() != 2 || !parts[0] || !parts[1])
            error("Sample-sheet row ${row_number}: malformed options; expected nonempty key=value entries")
        def (key, sequence) = parts
        if (!(key in ['r1_adapter', 'r2_adapter']))
            error("Sample-sheet row ${row_number}: unknown option '${key}'")
        if (options.containsKey(key))
            error("Sample-sheet row ${row_number}: repeated option '${key}'")
        if (!(sequence ==~ /(?i)[ACGTRYSWKMBDHVN]+/))
            error("Sample-sheet row ${row_number}: ${key} must be a DNA IUPAC sequence")
        options[key] = sequence.toUpperCase()
    }
    return options
}

def fastqInput(value, sheet, field, row_number) {
    if (!value?.trim())
        error("Sample-sheet row ${row_number}: missing ${field}")
    def source = sheet.parent.resolve(value.trim()).normalize()
    if (!(source.name ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/) || !source.name.endsWith('.gz'))
        error("Sample-sheet row ${row_number}: ${field} must name one .gz file with a safe basename")
    def path = file(source, checkIfExists: true)
    if (!path.isFile())
        error("Sample-sheet row ${row_number}: ${field} must be a regular file")
    return path
}

def alignmentReference(value) {
    def root = file(value, checkIfExists: true)
    def manifest = root.resolve('bundle.json')
    if (!manifest.isFile())
        error('Reference bundle must contain bundle.json')
    def bundle = new groovy.json.JsonSlurper().parseText(manifest.text)
    if (!(bundle instanceof Map) || bundle.bundle_format_version != 1)
        error('Unsupported reference-bundle bundle_format_version; expected 1')
    if (bundle.fasta != 'reference.fa' || bundle.bwamem2_index != 'bwamem2/reference.fa')
        error('Reference-bundle artifact paths do not match bundle_format_version 1')
    def artifacts = ['reference.fa'] + ['.0123', '.amb', '.ann', '.bwt.2bit.64', '.pac']
        .collect { suffix -> "bwamem2/reference.fa${suffix}".toString() }
    if (!(bundle.checksums instanceof Map) || bundle.checksums.keySet() != artifacts.toSet())
        error('Reference bundle must checksum its FASTA and all five bwa-mem2 indexes')
    artifacts.each { relative ->
        def path = root.resolve(relative)
        if (!path.isFile())
            error("Reference-bundle artifact missing: ${relative}")
        def digest = java.security.MessageDigest.getInstance('SHA-256')
        new java.security.DigestInputStream(path.newInputStream(), digest).withCloseable { stream ->
            stream.transferTo(java.io.OutputStream.nullOutputStream())
        }
        if (digest.digest().encodeHex().toString() != bundle.checksums[relative])
            error("Reference-bundle checksum mismatch: ${relative}")
    }
    return [root.resolve('reference.fa'), root.resolve('bwamem2')]
}

def sampleInputs(table, sheet) {
    if (!table)
        error('Sample sheet is empty')
    def header = table[0].collect { value -> value.trim() }
    def required = ['sample', 'library', 'flowcell', 'lane', 'fastq_1', 'fastq_2']
    header.each { field ->
        if (header.count(field) != 1)
            error("Duplicate sample-sheet column '${field}'")
        if (!(field in required + ['options']))
            error("Unknown sample-sheet column '${field}'")
    }
    required.each { field ->
        if (!(field in header))
            error("Missing sample-sheet column '${field}'")
    }
    if (table.size() < 2)
        error('Sample sheet must contain at least one data row')
    def used_reads = [:]
    def sample_names = [:]
    table.drop(1).withIndex().collect { values, index ->
        def row_number = index + 2
        if (values.size() != header.size())
            error("Sample-sheet row ${row_number}: expected ${header.size()} columns, found ${values.size()}")
        def row = [header, values].transpose().collectEntries { key, value -> [key, value] }
        ['sample', 'library', 'flowcell', 'lane'].each { field ->
            def value = row[field]?.trim()
            if (!value)
                error("Sample-sheet row ${row_number}: missing ${field}")
            if (!(value ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/))
                error("Sample-sheet row ${row_number}: invalid ${field} identifier '${value}'")
            row[field] = value
        }
        def output_name = row.sample.toLowerCase(java.util.Locale.ROOT)
        if (sample_names.containsKey(output_name) && sample_names[output_name] != row.sample)
            error("Sample-sheet row ${row_number}: sample IDs '${sample_names[output_name]}' and '${row.sample}' differ only by case; output filenames must be distinct on case-insensitive filesystems")
        sample_names[output_name] = row.sample
        def options = inputOptions(row.options, row_number)
        def identity = groovy.json.JsonOutput.toJson([row.sample, row.library, row.flowcell, row.lane])
            .getBytes('UTF-8').encodeBase64().toString().replace('+', '-').replace('/', '_').replace('=', '')
        def platform_unit = "${row.flowcell.replace('.', '%2E')}.${row.lane.replace('.', '%2E')}"
        def group = "@RG\\tID:rg_${identity}\\tSM:${row.sample}\\tLB:${row.library}\\tPU:${platform_unit}"
        def reads = ['fastq_1', 'fastq_2'].collect { field -> fastqInput(row[field], sheet, field, row_number) }
        def real_reads = reads.collect { it.toRealPath().toString() }
        if (real_reads[0] == real_reads[1])
            error("Sample-sheet row ${row_number}: R1 and R2 must be distinct files")
        if (reads[0].name == reads[1].name)
            error("Sample-sheet row ${row_number}: R1 and R2 must have distinct basenames for staging")
        real_reads.each { path ->
            if (used_reads.containsKey(path))
                error("Sample-sheet row ${row_number}: FASTQ file already used in row ${used_reads[path]}; repeated or conflicting read-group assignment")
            used_reads[path] = row_number
        }
        def task_identity = groovy.json.JsonOutput.toJson([identity, real_reads])
        def task_id = java.security.MessageDigest.getInstance('SHA-256')
            .digest(task_identity.getBytes('UTF-8')).encodeHex().toString()
        def task_label = "${row.sample} / ${row.library} / ${row.flowcell} / ${row.lane} / ${task_id.take(12)}"
        [[id: "row_${task_id}".toString(), sample: row.sample, single_end: false, read_group: group,
          task_label: task_label.toString(),
          r1_adapter: options.r1_adapter, r2_adapter: options.r2_adapter],
         reads]
    }
}

workflow ONCOHAWK {
    main:
    if (!params.input || !params.reference_bundle)
        error('Alignment requires --input and --reference_bundle')
    output_path = params._oncohawk_output_path
    if (!(output_path instanceof java.nio.file.Path))
        error('Invalid internal output-directory state; do not override _oncohawk_output_path')
    if (output_path != workflow.outputDir)
        error('Analysis output selection must use --outdir; do not override native outputDir or -output-dir')
    reference = alignmentReference(params.reference_bundle)
    sheet = file(params.input, checkIfExists: true)
    inputs = channel.of(sheet)
        .splitCsv(quote: '"').toList()
        .map { table -> sampleInputs(table, sheet) }
        .flatMap { rows -> rows }
    CUTADAPT(inputs)
    BWAMEM2_MEM(CUTADAPT.out.reads, channel.value([[id: 'reference'], reference[1]]),
                channel.value([[id: 'reference'], reference[0]]), true)
    sample_bams = BWAMEM2_MEM.out.bam
        .map { meta, bam -> [[id: meta.sample, sample: meta.sample], bam] }
        .groupTuple()
        .map { meta, bams -> [meta, bams.sort { it.name }, []] }
    SAMTOOLS_MERGE(sample_bams, channel.value([[:], [], [], []]), '')
    PICARD_MARKDUPLICATES(SAMTOOLS_MERGE.out.bam, channel.value([[:], [], []]))
    SAMTOOLS_INDEX(PICARD_MARKDUPLICATES.out.bam)
    completed = PICARD_MARKDUPLICATES.out.bam.join(SAMTOOLS_INDEX.out.index)

    emit:
    samples = completed
}
