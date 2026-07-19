# OncoHawk pipeline specification

## Scope of this document

This draft defines only OncoHawk's intended use and reporting boundary. It is a
target contract and does not describe implemented or verified analytical
behavior.

OncoHawk currently has no analytical implementation, analytical or scientific
validation, or release. No claim is made that it is clinical-grade or
suitable for patient-care decisions.

## Intended use

OncoHawk is intended to analyze tumor-only whole-genome sequencing data for
acute myeloid leukemia (AML) and myelodysplastic syndromes (MDS). Matched-normal
analysis is outside the current target contract.

The intended final output is a clinician-readable report of genomic findings
selected using approved curated resources for:

- genes associated with AML or MDS;
- known hotspot variants; and
- known recurrent translocations.

These resources will inform prioritization for report inclusion. Their exact
contents, evidence requirements, representation, and inclusion logic remain
open.

## Reporting boundary

The final report is intended for clinicians. It is not intended to be a
technical report for bioinformatics specialists.

The report will not provide:

- a diagnosis;
- a prognosis;
- a treatment recommendation; or
- patient-specific clinical interpretation.

The project does not define or validate downstream clinical review, sign-out,
or decision-making workflows.

## Open matters

This document does not yet decide:

- specimen and assay requirements;
- supported input types;
- supported variant classes or analytical methods;
- the contents, evidence hierarchy, provenance, release process, or retirement
  process for curated resources;
- transcript, annotation, coordinate, or reference requirements;
- reporting thresholds, prioritization rules, or the report schema;
- technical, audit, or downstream machine-readable outputs;
- runtime or execution architecture;
- engineering-test requirements;
- analytical and scientific validation requirements;
- regulatory and quality-management requirements; or
- release criteria.
