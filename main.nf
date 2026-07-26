nextflow.enable.dsl=2

include { VALIDATE_SAMPLESHEET } from './subworkflows/local/validate_samplesheet'

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
    def modeSpecificParameters = ['input', 'reference_bundle', 'knowledge_bundle', 'reference_spec', 'knowledge_spec']
    modeSpecificParameters.findAll { parameter -> !allowedParameters.contains(parameter) && params[parameter] != null }.each { parameter ->
        error "Parameter --${parameter} is not valid for --workflow ${selectedWorkflow}"
    }

    selectedWorkflow
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

def validateAnalyzeBundleCompatibility() {
    def referenceManifest = readBundleManifest('reference_bundle', params.reference_bundle)
    def knowledgeManifest = readBundleManifest('knowledge_bundle', params.knowledge_bundle)
    def referenceBundleId = requireManifestIdentity('reference_bundle', referenceManifest, 'bundle_id')
    def knowledgeSourceReferenceBundleId = requireManifestIdentity('knowledge_bundle', knowledgeManifest, 'source_reference_bundle_id')
    requireManifestIdentity('knowledge_bundle', knowledgeManifest, 'bundle_id')

    if( knowledgeSourceReferenceBundleId != referenceBundleId ) {
        error 'Invalid bundle compatibility: knowledge manifest source_reference_bundle_id does not match reference manifest bundle_id'
    }
}

workflow {
    selectedWorkflow = validateWorkflowParameters()

    if( selectedWorkflow == 'analyze' ) {
        validateAnalyzeBundleCompatibility()
        VALIDATE_SAMPLESHEET(params.input)
    }
    else {
        error "Workflow '${selectedWorkflow}' is not implemented"
    }
}
