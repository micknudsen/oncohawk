include { ENSEMBLVEP_VEP as VARIANT_CONSEQUENCES_ANNOTATE } from '../modules/nf-core/ensemblvep/vep/main'
include { CUTADAPT as READS_TRIM } from '../modules/nf-core/cutadapt/main'
include { BWAMEM2_MEM as READS_ALIGN } from '../modules/nf-core/bwamem2/mem/main'
include { SAMTOOLS_MERGE as SAMPLE_ALIGNMENTS_MERGE } from '../modules/nf-core/samtools/merge/main'
include { PICARD_MARKDUPLICATES as SAMPLE_DUPLICATES_MARK } from '../modules/nf-core/picard/markduplicates/main'
include { GATK4_MUTECT2 as VARIANTS_CALL } from '../modules/nf-core/gatk4/mutect2/main'
include { GATK4_FILTERMUTECTCALLS as VARIANTS_FILTER } from '../modules/nf-core/gatk4/filtermutectcalls/main'
include { SAMTOOLS_INDEX as SAMPLE_BAM_INDEX } from '../modules/nf-core/samtools/index/main'

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

def alignmentReference(value, verify_checksums) {
    def root = file(value, checkIfExists: true)
    def manifest = root.resolve('bundle.json')
    if (!manifest.isFile())
        error('Reference bundle must contain bundle.json')
    def bundle
    try {
        bundle = new groovy.json.JsonSlurper().parseText(manifest.text)
    } catch (Exception ignored) {
        error('Reference bundle has malformed bundle.json; rebuild explicitly with --workflow prepare_reference_bundle')
    }
    if (!(bundle instanceof Map) || bundle.bundle_format_version != 3)
        error('Unsupported reference-bundle bundle_format_version; expected 3. Rebuild explicitly with --workflow prepare_reference_bundle to include annotation resources')
    def annotation = bundle.annotation
    if (!(annotation instanceof Map) || annotation.software_version != '116.3' ||
        annotation.cache_version != 116 || annotation.species != 'homo_sapiens_refseq' ||
        annotation.assembly != 'GRCh38')
        error('Reference bundle requires compatible VEP 116.3 / RefSeq cache 116 for human GRCh38; rebuild with --workflow prepare_reference_bundle')
    if (bundle.fasta != 'reference.fa' || bundle.bwamem2_index != 'bwamem2/reference.fa' ||
        bundle.fasta_index != 'reference.fa.fai' || bundle.sequence_dictionary != 'reference.dict')
        error('Reference-bundle artifact paths do not match bundle_format_version 3')
    if (annotation.fasta != 'annotation/reference.fa' || annotation.fasta_index != 'annotation/reference.fa.fai' ||
        annotation.cache != 'annotation/cache' || annotation.synonyms != 'annotation/chr_synonyms.txt' ||
        annotation.compatibility != 'annotation/compatibility.json' ||
        !(annotation.refseq_version instanceof String) || !annotation.refseq_version.trim() ||
        !(annotation.mane_version instanceof String) || !annotation.mane_version.trim())
        error('Reference-bundle annotation paths or data versions are malformed; rebuild with --workflow prepare_reference_bundle')
    def artifacts = ['reference.fa', 'reference.fa.fai', 'reference.dict'] + ['.0123', '.amb', '.ann', '.bwt.2bit.64', '.pac']
        .collect { suffix -> "bwamem2/reference.fa${suffix}".toString() }
    artifacts += ['annotation/reference.fa', 'annotation/reference.fa.fai', 'annotation/chr_synonyms.txt',
                  'annotation/compatibility.json', 'annotation/resource_metadata.json',
                  'annotation/cache/homo_sapiens_refseq/116_GRCh38/info.txt']
    if (!(bundle.checksums instanceof Map) || !bundle.checksums.keySet().containsAll(artifacts) ||
        bundle.checksums.any { relative, checksum ->
            !(relative instanceof String) || !(checksum instanceof String) || !(checksum ==~ /[0-9a-f]{64}/) ||
            relative.startsWith('/') || relative.tokenize('/').any { it in ['.', '..'] } || relative.contains('\\')
        })
        error('Reference bundle must checksum its FASTA, FASTA index, sequence dictionary and all five bwa-mem2 indexes, plus every annotation asset')
    bundle.checksums.keySet().each { relative ->
        def path = root.resolve(relative)
        if (!path.isFile())
            error("Reference-bundle artifact missing: ${relative}")
        if (verify_checksums) {
            def digest = java.security.MessageDigest.getInstance('SHA-256')
            new java.security.DigestInputStream(path.newInputStream(), digest).withCloseable { stream ->
                stream.transferTo(java.io.OutputStream.nullOutputStream())
            }
            if (digest.digest().encodeHex().toString() != bundle.checksums[relative])
                error("Reference-bundle checksum mismatch: ${relative}")
        }
    }
    def cache = root.resolve('annotation/cache/homo_sapiens_refseq/116_GRCh38')
    if (!cache.isDirectory())
        error('Reference-bundle RefSeq cache missing; rebuild with --workflow prepare_reference_bundle')
    def cache_files = java.nio.file.Files.walk(cache).withCloseable { paths ->
        paths.filter { java.nio.file.Files.isRegularFile(it) }.map { root.relativize(it).toString() }.toList()
    }
    if (!cache_files.any { it.endsWith('.gz') } || bundle.checksums.keySet() != (artifacts + cache_files).toSet())
        error('Reference-bundle cache contents do not match its checksum inventory; rebuild with --workflow prepare_reference_bundle')
    return [alignment_fasta: root.resolve('reference.fa'), bwamem2: root.resolve('bwamem2'),
            alignment_fai: root.resolve('reference.fa.fai'), alignment_dictionary: root.resolve('reference.dict'),
            annotation_fasta: root.resolve('annotation/reference.fa'), annotation_fai: root.resolve('annotation/reference.fa.fai'),
            annotation_cache: root.resolve('annotation/cache'), annotation_synonyms: root.resolve('annotation/chr_synonyms.txt')]
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
    if (!(output_path instanceof java.net.URI))
        error('Invalid internal output-directory state; do not override _oncohawk_output_path')
    if (java.nio.file.Path.of(output_path) != workflow.outputDir)
        error('Analysis output selection must use --outdir; do not override native outputDir or -output-dir')
    reference = alignmentReference(params.reference_bundle, params.verify_bundle_checksums.toString().toBoolean())
    sheet = file(params.input, checkIfExists: true)
    inputs = channel.of(sheet)
        .splitCsv(quote: '"').toList()
        .map { table -> sampleInputs(table, sheet) }
        .flatMap { rows -> rows }
    READS_TRIM(inputs)
    READS_ALIGN(READS_TRIM.out.reads, channel.value([[id: 'reference'], reference.bwamem2]),
                channel.value([[id: 'reference'], reference.alignment_fasta]), true)
    sample_bams = READS_ALIGN.out.bam
        .map { meta, bam -> [[id: meta.sample, sample: meta.sample], bam] }
        .groupTuple()
        .map { meta, bams -> [meta, bams.sort { it.name }, []] }
    SAMPLE_ALIGNMENTS_MERGE(sample_bams, channel.value([[:], [], [], []]), '')
    SAMPLE_DUPLICATES_MARK(SAMPLE_ALIGNMENTS_MERGE.out.bam, channel.value([[:], [], []]))
    SAMPLE_BAM_INDEX(SAMPLE_DUPLICATES_MARK.out.bam)
    completed = SAMPLE_DUPLICATES_MARK.out.bam.join(SAMPLE_BAM_INDEX.out.index)

    VARIANTS_CALL(
        completed.map { meta, bam, bai -> [meta, [bam], [bai], []] },
        channel.value([[:], reference.alignment_fasta]), channel.value([[:], reference.alignment_fai, []]),
        channel.value([[:], reference.alignment_dictionary]), [], [], [], [], [], []
    )
    calls = VARIANTS_CALL.out.vcf.join(VARIANTS_CALL.out.tbi).join(VARIANTS_CALL.out.stats)
    VARIANTS_FILTER(
        calls.map { meta, vcf, tbi, stats -> [meta, vcf, tbi, stats, [], [], [], 0] },
        channel.value([[:], reference.alignment_fasta]), channel.value([[:], reference.alignment_fai]),
        channel.value([[:], reference.alignment_dictionary])
    )

    filtered = VARIANTS_FILTER.out.vcf.join(VARIANTS_FILTER.out.tbi)
    VARIANT_CONSEQUENCES_ANNOTATE(
        filtered.map { meta, vcf, _tbi -> [meta, vcf, []] },
        'GRCh38', 'homo_sapiens', '116', channel.value([[:], reference.annotation_cache]),
        channel.value([[:], reference.annotation_fasta]), channel.value([reference.annotation_fai, reference.annotation_synonyms]), [[], []]
    )

    emit:
    samples = completed
    variants = filtered.mix(VARIANT_CONSEQUENCES_ANNOTATE.out.vcf.join(VARIANT_CONSEQUENCES_ANNOTATE.out.tbi))
}
