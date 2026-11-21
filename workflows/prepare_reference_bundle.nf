include { GUNZIP as ANNOTATION_GUNZIP } from '../modules/nf-core/gunzip/main'
include { SAMTOOLS_FAIDX as ANNOTATION_FAIDX } from '../modules/nf-core/samtools/faidx/main'
include { ANNOTATION_PREPARE } from '../modules/local/annotation_prepare'
include { GUNZIP } from '../modules/nf-core/gunzip/main'
include { BEDTOOLS_MASKFASTA } from '../modules/nf-core/bedtools/maskfasta/main'
include { SAMTOOLS_FAIDX } from '../modules/nf-core/samtools/faidx/main'
include { PICARD_CREATESEQUENCEDICTIONARY } from '../modules/nf-core/picard/createsequencedictionary/main'
include { BWAMEM2_INDEX } from '../modules/nf-core/bwamem2/index/main'
include { REFERENCE_BUNDLE } from '../modules/local/reference_bundle'
include { REFERENCE_VALIDATE } from '../modules/local/reference_validate'
include { REFERENCE_DOWNLOAD } from '../modules/local/reference_download'

def encoded(value) {
    return groovy.json.JsonOutput.toJson(value).getBytes('UTF-8').encodeBase64().toString()
}

def referenceLabel(fasta) {
    def source = fasta.toString()
    def path = source ==~ /(?i)^(https?|ftp|file):\/\/.*/ ? new java.net.URI(source).path : source
    return new java.io.File(path).name
}

def proxyEnvironment() {
    return ['http', 'https', 'no'].collectEntries { scheme ->
        // Match urllib: a present lowercase value wins, even when explicitly empty.
        def value = System.getenv("${scheme}_proxy")
        if (value == null) {
            // Preserve urllib's protection against CGI-injected HTTP_PROXY headers.
            value = scheme == 'http' && System.getenv('REQUEST_METHOD') != null ?
                '' : System.getenv("${scheme.toUpperCase()}_PROXY")
        }
        // Export the resolved value under both spellings for a consistent task environment.
        return [("${scheme}_proxy".toString()): value ?: '',
                ("${scheme.toUpperCase()}_PROXY".toString()): value ?: '']
    }
}

def referenceInput(value) {
    def path = file(value, checkIfExists: true)
    if (path instanceof List)
        error('Reference inputs must each identify one file, not a wildcard collection')
    if (!(path.name ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/))
        error('Reference input filenames must contain only letters, digits, dots, underscores or hyphens')
    return path
}

def sourceIdentity(value, official) {
    def identity = value instanceof Map ? value : new groovy.json.JsonSlurper().parseText(value.toString())
    if (!(identity instanceof Map) || identity.any { key, item ->
        !(key in ['dataset', 'release', 'assembly']) || !(item instanceof String) || !item.trim()
    })
        error('Source identity must be a JSON object with nonempty dataset, release or assembly strings')
    if (official) {
        if (identity)
            error('Official NCBI source identity is fixed; do not supply an identity override')
        return [dataset: 'NCBI no-ALT analysis set with UCSC IDs', release: 'GCA_000001405.15', assembly: 'GRCh38']
    }
    return identity
}

workflow PREPARE_REFERENCE_BUNDLE {
    main:
    repository = projectDir
    if (workflow.outputDir.exists())
        error('Reference bundle output directory already exists; choose a new --outdir')
    ncbi_base = 'https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/'
    official_fasta = params.fasta == ncbi_base + 'GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz'
    official_exclusions_bed = params.exclusions_bed == ncbi_base + 'GCA_000001405.15_GRCh38_GRC_exclusions.bed'
    ensembl_base = 'https://ftp.ensembl.org/pub/release-116/'
    official_annotation = params.annotation_fasta == ensembl_base + 'fasta/homo_sapiens/dna/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz'
    official_cache = params.vep_cache == ensembl_base + 'variation/indexed_vep_cache/homo_sapiens_refseq_vep_116_GRCh38.tar.gz'
    reference_label = referenceLabel(params.fasta)
    checksums = [
        fasta: [md5: official_fasta ? 'a08035b6a6e31780e96a34008ff21bd6' : null, sha256: params.fasta_sha256],
        exclusions_bed: [md5: official_exclusions_bed ? 'bf5c011e0342f355422144eb3547b5d0' : null, sha256: params.exclusions_bed_sha256],
        annotation_fasta: [sha256: official_annotation ? 'd8c3af0094a7bba6125763bad779ec18a81483c739c6ed122094bdf86c187b92' : params.annotation_fasta_sha256],
        vep_cache: [sha256: official_cache ? '0427dd48d05d15be2486ceffff047be8153ea5e7b65391918d25efcb054f7f77' : params.vep_cache_sha256]
    ]
    if (official_annotation && params.annotation_fasta_sha256 &&
        params.annotation_fasta_sha256.toString().toLowerCase() != checksums.annotation_fasta.sha256)
        error('Official Ensembl annotation FASTA checksum is fixed; do not override it')
    if (official_cache && params.vep_cache_sha256 &&
        params.vep_cache_sha256.toString().toLowerCase() != checksums.vep_cache.sha256)
        error('Official Ensembl RefSeq cache checksum is fixed; do not override it')
    policy = encoded(checksums)
    identities = [fasta: sourceIdentity(params.fasta_identity, official_fasta),
                  exclusions_bed: sourceIdentity(params.exclusions_bed_identity, official_exclusions_bed)]
    identities.annotation_fasta = sourceIdentity(params.annotation_fasta_identity, false)
    identities.vep_cache = sourceIdentity(params.vep_cache_identity, false)
    if ((official_annotation && identities.annotation_fasta) || (official_cache && identities.vep_cache))
        error('Official Ensembl source identity is fixed; do not supply an identity override')
    if (official_annotation)
        identities.annotation_fasta = [dataset: 'Ensembl unmasked primary assembly', release: '116', assembly: 'GRCh38']
    if (official_cache)
        identities.vep_cache = [dataset: 'Ensembl RefSeq-only VEP cache', release: '116', assembly: 'GRCh38']
    sources = [fasta: params.fasta.toString(), exclusions_bed: params.exclusions_bed.toString(),
               annotation_fasta: params.annotation_fasta.toString(), vep_cache: params.vep_cache.toString()]
    remote = sources.findAll { _kind, uri -> uri ==~ /(?i)^(https?|ftp):\/\/.*/ }
    local = sources.findAll { kind, _uri -> !remote.containsKey(kind) }
    if (local.any { _kind, uri -> uri ==~ /(?i)^(?!file:)[a-z][a-z0-9+.-]*:\/\/.*/ })
        error('Downloadable reference inputs must use HTTP, HTTPS or FTP; otherwise provide local files')
    downloads = file(params.downloads_dir).toAbsolutePath().normalize()
    if (downloads.toUri().scheme != 'file' || downloads.toString() =~ /[:\r\n,]/)
        error('--downloads_dir must be a local/shared filesystem directory without colons, commas or newlines')
    ca_bundle = params.download_ca_bundle ? file(params.download_ca_bundle, checkIfExists: true) : []
    if (params.download_ca_bundle && (ca_bundle instanceof List ||
            ca_bundle.toUri().scheme != 'file' || !ca_bundle.isFile()))
        error('--download_ca_bundle must identify one local/shared PEM file')
    if (remote)
        downloads.mkdirs()
    assets = remote.collect { kind, uri ->
        [kind, encoded([kind: kind, uri: uri, expected: checksums[kind], identity: identities[kind]])]
    }
    REFERENCE_DOWNLOAD(
        channel.fromList(assets), downloads.toString(), file("$repository/bin/download_reference.py"), ca_bundle,
        proxyEnvironment(), reference_label
    )
    acquired = REFERENCE_DOWNLOAD.out.source.map { kind, result ->
        [kind, referenceInput(new groovy.json.JsonSlurper().parseText(result.text).path)]
    }.mix(channel.fromList(local.collect { kind, uri -> [kind, referenceInput(uri)] }))
    fasta = acquired.filter { kind, _path -> kind == 'fasta' }.map { _kind, path -> path }
    exclusions_bed = acquired.filter { kind, _path -> kind == 'exclusions_bed' }.map { _kind, path -> path }
    annotation_archive = acquired.filter { kind, _path -> kind == 'annotation_fasta' }.map { _kind, path -> path }
    cache_archive = acquired.filter { kind, _path -> kind == 'vep_cache' }.map { _kind, path -> path }
    annotation_inputs = annotation_archive.branch { path ->
        compressed: path.name.endsWith('.gz')
        plain: true
    }
    ANNOTATION_GUNZIP(annotation_inputs.compressed.map { path -> [[id: 'annotation', reference_label: reference_label], path] })
    annotation_fasta = ANNOTATION_GUNZIP.out.gunzip.map { _meta, path -> path }.mix(annotation_inputs.plain)
    inputs = fasta.branch { path ->
        compressed: path.name.endsWith('.gz')
        plain: true
    }
    GUNZIP(inputs.compressed.map { path -> [[id: 'reference', reference_label: reference_label], path] })
    uncompressed = GUNZIP.out.gunzip.map { _meta, path -> path }.mix(inputs.plain)
    REFERENCE_VALIDATE(uncompressed, exclusions_bed, fasta, policy, file("$repository/bin/validate_reference.py"), reference_label)
    ANNOTATION_FAIDX(annotation_fasta.combine(REFERENCE_VALIDATE.out.report).map { path, _report ->
        [[id: 'annotation', reference_label: reference_label], path, []]
    }, false)
    BEDTOOLS_MASKFASTA(REFERENCE_VALIDATE.out.exclusions_bed.map { path ->
        [[id: 'reference', reference_label: reference_label], path]
    }, REFERENCE_VALIDATE.out.fasta)
    ANNOTATION_PREPARE(
        REFERENCE_VALIDATE.out.fasta, BEDTOOLS_MASKFASTA.out.fasta.map { _meta, path -> path },
        annotation_fasta, ANNOTATION_FAIDX.out.fai.map { _meta, path -> path },
        annotation_archive, cache_archive, policy,
        [file("$repository/bin/prepare_annotation.py"), file("$repository/bin/validate_reference.py")], reference_label
    )
    BWAMEM2_INDEX(BEDTOOLS_MASKFASTA.out.fasta)
    SAMTOOLS_FAIDX(BEDTOOLS_MASKFASTA.out.fasta.map { meta, path -> [meta, path, []] }, false)
    PICARD_CREATESEQUENCEDICTIONARY(BEDTOOLS_MASKFASTA.out.fasta)
    modules = new groovy.json.JsonSlurper().parseText(file("$repository/modules.json").text)
    source_paths = [
        'main.nf', 'nextflow.config', 'workflows/prepare_reference_bundle.nf',
        'conf/prepare_reference_bundle.config', 'conf/prepare_reference_bundle_resources.config',
        'conf/common.config', 'conf/slurm.config',
        'bin/validate_reference.py', 'bin/package_reference.py', 'bin/download_reference.py', 'bin/prepare_annotation.py',
        'modules/local/annotation_prepare.nf', 'modules/local/reference_validate.nf', 'modules/local/reference_bundle.nf', 'modules/local/reference_download.nf',
        'modules/nf-core/gunzip/main.nf', 'modules/nf-core/bedtools/maskfasta/main.nf',
        'modules/nf-core/bwamem2/index/main.nf',
        'modules/nf-core/samtools/faidx/main.nf', 'modules/nf-core/picard/createsequencedictionary/main.nf'
    ]
    source_hashes = source_paths.collectMany { pattern -> files("$repository/$pattern") }
        .collectEntries { path ->
            [repository.relativize(path).toString(), java.security.MessageDigest.getInstance('SHA-256').digest(path.bytes).encodeHex().toString()]
        }
    metadata = encoded([
        sources: sources.collectEntries { kind, uri -> [kind, [uri: uri, identity: identities[kind]]] },
        workflow: [repository: workflow.manifest.name, version: workflow.manifest.version,
                   nextflow: nextflow.version.toString(), commit: workflow.commitId, source_sha256: source_hashes],
        modules: modules.repos['https://github.com/nf-core/modules.git'].modules['nf-core']
            .subMap(['gunzip', 'bedtools/maskfasta', 'bwamem2/index', 'samtools/faidx', 'picard/createsequencedictionary'])
    ])
    versions = GUNZIP.out.versions_gunzip
        .mix(BEDTOOLS_MASKFASTA.out.versions_bedtools, BWAMEM2_INDEX.out.versions_bwamem2,
             SAMTOOLS_FAIDX.out.versions_samtools, PICARD_CREATESEQUENCEDICTIONARY.out.versions_picard,
             ANNOTATION_GUNZIP.out.versions_gunzip, ANNOTATION_FAIDX.out.versions_samtools)
        .collect(flat: false).map { entries -> encoded(entries) }
    REFERENCE_BUNDLE(
        BEDTOOLS_MASKFASTA.out.fasta.map { _meta, path -> path }, BWAMEM2_INDEX.out.index.map { _meta, path -> path },
        SAMTOOLS_FAIDX.out.fai.map { _meta, path -> path },
        PICARD_CREATESEQUENCEDICTIONARY.out.reference_dict.map { _meta, path -> path },
        REFERENCE_VALIDATE.out.report, ANNOTATION_PREPARE.out.assets, metadata, versions, file("$repository/bin/package_reference.py"), reference_label
    )

    emit:
    bundle = REFERENCE_BUNDLE.out
}
