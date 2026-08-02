nextflow.enable.dsl=2

include { VALIDATE_SAMPLESHEET } from './subworkflows/local/validate_samplesheet'
include { PREPARE_REFERENCE_BUNDLE } from './subworkflows/local/prepare_reference_bundle'

def requireValue(String name, Object value) {
    if( value == null || value.toString().trim().isEmpty() ) {
        error "Missing required parameter: --${name}"
    }
}

def validateWorkflowParameters() {
    def workflowParameters = [
        prepare_reference_bundle: [required: [], optional: ['reference_spec']],
        prepare_knowledge_bundle: [required: ['reference_bundle'], optional: ['knowledge_spec']],
        analyze: [required: ['input', 'reference_bundle', 'knowledge_bundle'], optional: []]
    ]
    def selectedWorkflow = params.workflow

    if( selectedWorkflow == null || selectedWorkflow.toString().trim().isEmpty() || !workflowParameters.containsKey(selectedWorkflow) ) {
        error "Missing or invalid required parameter: --workflow <prepare_reference_bundle|prepare_knowledge_bundle|analyze>"
    }

    requireValue('outdir', params.outdir)

    def selectedParameters = workflowParameters[selectedWorkflow]
    selectedParameters.required.each { parameter -> requireValue(parameter, params[parameter]) }

    def allowedParameters = (selectedParameters.required + selectedParameters.optional) as Set
    def modeSpecificParameters = [
        'input', 'reference_bundle', 'knowledge_bundle', 'reference_spec', 'knowledge_spec', 'download_cache',
        'reference_fasta_url', 'reference_fasta_md5', 'reference_exclusions_url', 'reference_exclusions_md5'
    ]
    modeSpecificParameters.findAll { parameter -> !allowedParameters.contains(parameter) && params[parameter] != null }.each { parameter ->
        error "Parameter --${parameter} is not valid for --workflow ${selectedWorkflow}"
    }

    selectedWorkflow
}

def validateReferenceBundleParameters() {
    if( params.reference_spec != null ) {
        error 'Parameter --reference_spec is not yet supported for --workflow prepare_reference_bundle'
    }
}

def readBundleManifest(String parameter, Object bundleRoot) {
    def root = new File(bundleRoot.toString())
    if( !root.isDirectory() ) {
        error "Invalid --${parameter}: expected a local bundle-root directory"
    }

    def manifestFile = new File(root, 'manifest.json')
    if( !manifestFile.isFile() ) {
        error "Invalid --${parameter}: missing manifest.json"
    }

    try {
        new groovy.json.JsonSlurper().parse(manifestFile)
    }
    catch( Exception _ignored ) {
        error "Invalid --${parameter}: malformed manifest.json"
    }
}

def requireManifestIdentity(String parameter, Object manifest, String field) {
    def value = manifest instanceof Map ? manifest[field] : null
    if( !(value instanceof String) || value.trim().isEmpty() ) {
        error "Invalid --${parameter}: manifest.json requires a non-empty string ${field}"
    }

    value
}

def requireManifestSchemaVersion(String parameter, Object manifest) {
    def value = manifest instanceof Map ? manifest['schema_version'] : null
    if( value != 1 ) {
        error "Invalid --${parameter}: manifest.json requires schema_version 1"
    }
}

def validateKnowledgePreparationReferenceBundle() {
    def referenceManifest = readBundleManifest('reference_bundle', params.reference_bundle)
    requireManifestSchemaVersion('reference_bundle', referenceManifest)
    requireManifestIdentity('reference_bundle', referenceManifest, 'bundle_id')
}

def validateAnalyzeBundleCompatibility() {
    def referenceManifest = readBundleManifest('reference_bundle', params.reference_bundle)
    def knowledgeManifest = readBundleManifest('knowledge_bundle', params.knowledge_bundle)
    def referenceBundleId = requireManifestIdentity('reference_bundle', referenceManifest, 'bundle_id')
    def knowledgeSourceReferenceBundleId = requireManifestIdentity('knowledge_bundle', knowledgeManifest, 'source_reference_bundle_id')
    requireManifestIdentity('knowledge_bundle', knowledgeManifest, 'bundle_id')

    if( knowledgeSourceReferenceBundleId != referenceBundleId ) {
        error 'Invalid bundle compatibility: knowledge manifest source_reference_bundle_id does not match reference manifest bundle_id'
    }

    [
        reference_bundle_id: referenceBundleId,
        knowledge_bundle_id: requireManifestIdentity('knowledge_bundle', knowledgeManifest, 'bundle_id'),
        knowledge_source_reference_bundle_id: knowledgeSourceReferenceBundleId
    ]
}

def writeBundleCompatibilityRecord(Map compatibility) {
    def outputDirectory = new File(params.outdir.toString())
    if( !outputDirectory.exists() && !outputDirectory.mkdirs() ) {
        error "Unable to create --outdir: ${outputDirectory}"
    }
    if( !outputDirectory.isDirectory() ) {
        error "Invalid --outdir: expected a directory"
    }

    def metadataDirectory = new File(outputDirectory, 'metadata')
    if( !metadataDirectory.exists() && !metadataDirectory.mkdirs() ) {
        error "Unable to create metadata directory: ${metadataDirectory}"
    }
    if( !metadataDirectory.isDirectory() ) {
        error "Invalid metadata path: expected a directory"
    }

    def compatibilityRecord = new File(metadataDirectory, 'bundle-compatibility.json')
    def expectedContent = groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson(compatibility)) + '\n'
    if( compatibilityRecord.exists() ) {
        if( !compatibilityRecord.isFile() ) {
            error "Invalid bundle compatibility record: expected a file"
        }
        if( compatibilityRecord.getText('UTF-8') != expectedContent ) {
            error "Conflicting bundle compatibility record: ${compatibilityRecord}"
        }
        return
    }

    compatibilityRecord.setText(expectedContent, 'UTF-8')
}

workflow {
    selectedWorkflow = validateWorkflowParameters()

    if( selectedWorkflow == 'analyze' ) {
        def compatibility = validateAnalyzeBundleCompatibility()
        VALIDATE_SAMPLESHEET(params.input).records
            .collect()
            .map { records ->
                writeBundleCompatibilityRecord(compatibility)
                records
            }
    }
    else if( selectedWorkflow == 'prepare_reference_bundle' ) {
        validateReferenceBundleParameters()
        PREPARE_REFERENCE_BUNDLE()
    }
    else {
        validateKnowledgePreparationReferenceBundle()
        error "Workflow '${selectedWorkflow}' is not implemented"
    }
}
