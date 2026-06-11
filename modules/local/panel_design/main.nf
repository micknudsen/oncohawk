process PANEL_DESIGN {

    tag "$meta.id"
    label 'process_low'
    conda "${moduleDir}/environment.yml"
    container "python:3.11-slim"

    input:
    tuple val(meta), path(gtf)
    path config_json
    path script

    output:
    tuple val(meta), path("panel.bed"), emit: bed
    tuple val(meta), path("panel.log"), emit: panel_log
    path "versions.yml"                , emit: versions
    
    script:
    """
    set -euo pipefail

    pip install -q pyranges pandas

    python ${script} \
        --gtf ${gtf} \
        --config ${config_json} \
        --out panel.bed \
        > panel.log 2>&1

    cat > versions.yml << EOF
    "${task.process}":
        python: \$(python --version | cut -d' ' -f2)
        pyranges: \$(python -c "import pyranges; print(pyranges.__version__)")
        pandas: \$(python -c "import pandas; print(pandas.__version__)")
    EOF
    """
}