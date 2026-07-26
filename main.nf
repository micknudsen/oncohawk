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

workflow {
    selectedWorkflow = validateWorkflowParameters()

    if( selectedWorkflow == 'analyze' ) {
        VALIDATE_SAMPLESHEET(params.input)
    }
    else {
        error "Workflow '${selectedWorkflow}' is not implemented"
    }
}
