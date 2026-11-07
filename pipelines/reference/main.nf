include { GUNZIP } from '../../modules/nf-core/gunzip/main'
include { BEDTOOLS_MASKFASTA } from '../../modules/nf-core/bedtools/maskfasta/main'
include { BWAMEM2_INDEX } from '../../modules/nf-core/bwamem2/index/main'
include { REFERENCE_BUNDLE } from '../../modules/local/reference_bundle'
include { REFERENCE_VALIDATE } from '../../modules/local/reference_validate'
include { REFERENCE_DOWNLOAD } from '../../modules/local/reference_download'

def encoded(value) {
    return groovy.json.JsonOutput.toJson(value).getBytes('UTF-8').encodeBase64().toString()
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

workflow {
    repository = projectDir.parent.parent
    if (file(params.outdir).exists())
        error('Reference bundle output directory already exists; choose a new --outdir')
    ncbi_base = 'https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/'
    official_fasta = params.fasta == ncbi_base + 'GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz'
    official_exclusions_bed = params.exclusions_bed == ncbi_base + 'GCA_000001405.15_GRCh38_GRC_exclusions.bed'
    checksums = [
        fasta: [md5: official_fasta ? 'a08035b6a6e31780e96a34008ff21bd6' : null, sha256: params.fasta_sha256],
        exclusions_bed: [md5: official_exclusions_bed ? 'bf5c011e0342f355422144eb3547b5d0' : null, sha256: params.exclusions_bed_sha256]
    ]
    policy = encoded(checksums)
    identities = [fasta: sourceIdentity(params.fasta_identity, official_fasta),
                  exclusions_bed: sourceIdentity(params.exclusions_bed_identity, official_exclusions_bed)]
    sources = [fasta: params.fasta.toString(), exclusions_bed: params.exclusions_bed.toString()]
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
        proxyEnvironment()
    )
    acquired = REFERENCE_DOWNLOAD.out.source.map { kind, result ->
        [kind, referenceInput(new groovy.json.JsonSlurper().parseText(result.text).path)]
    }.mix(channel.fromList(local.collect { kind, uri -> [kind, referenceInput(uri)] }))
    fasta = acquired.filter { kind, _path -> kind == 'fasta' }.map { _kind, path -> path }
    exclusions_bed = acquired.filter { kind, _path -> kind == 'exclusions_bed' }.map { _kind, path -> path }
    inputs = fasta.branch { path ->
        compressed: path.name.endsWith('.gz')
        plain: true
    }
    GUNZIP(inputs.compressed.map { path -> [[id: 'reference'], path] })
    uncompressed = GUNZIP.out.gunzip.map { _meta, path -> path }.mix(inputs.plain)
    REFERENCE_VALIDATE(uncompressed, exclusions_bed, fasta, policy, file("$repository/bin/validate_reference.py"))
    BEDTOOLS_MASKFASTA(REFERENCE_VALIDATE.out.exclusions_bed.map { path -> [[id: 'reference'], path] }, REFERENCE_VALIDATE.out.fasta)
    BWAMEM2_INDEX(BEDTOOLS_MASKFASTA.out.fasta)
    modules = new groovy.json.JsonSlurper().parseText(file("$repository/modules.json").text)
    source_paths = [
        'pipelines/reference/*.nf', 'pipelines/reference/*.config',
        'conf/common.config', 'conf/slurm.config', 'modules.json',
        'bin/validate_reference.py', 'bin/package_reference.py', 'bin/download_reference.py', 'modules/local/*.nf',
        'modules/nf-core/gunzip/main.nf', 'modules/nf-core/bedtools/maskfasta/main.nf',
        'modules/nf-core/bwamem2/index/main.nf'
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
            .subMap(['gunzip', 'bedtools/maskfasta', 'bwamem2/index'])
    ])
    versions = GUNZIP.out.versions_gunzip
        .mix(BEDTOOLS_MASKFASTA.out.versions_bedtools, BWAMEM2_INDEX.out.versions_bwamem2)
        .collect(flat: false).map { entries -> encoded(entries) }
    REFERENCE_BUNDLE(
        BEDTOOLS_MASKFASTA.out.fasta.map { _meta, path -> path }, BWAMEM2_INDEX.out.index.map { _meta, path -> path },
        REFERENCE_VALIDATE.out.report, metadata, versions, file("$repository/bin/package_reference.py")
    )
}
