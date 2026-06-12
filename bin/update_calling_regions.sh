#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
config_path="${repo_root}/assets/calling_regions/variants.json"
output_path="${repo_root}/assets/calling_regions/variants.bed"
python_bin="${PYTHON_BIN:-python3}"
gtf_path="${1:-${GTF_PATH:-}}"

if [[ -z "${gtf_path}" ]]; then
    echo "Usage: bash ./bin/update_calling_regions.sh <gencode.gtf.gz>" >&2
    echo "   or: GTF_PATH=/path/to/gencode.gtf.gz bash ./bin/update_calling_regions.sh" >&2
    exit 1
fi

"${python_bin}" "${repo_root}/bin/gtf_to_bed.py" \
    --gtf "${gtf_path}" \
    --config "${config_path}" \
    --out "${output_path}"