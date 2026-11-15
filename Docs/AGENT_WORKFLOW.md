# TerraPulse Agent Workflow

The existing LangGraph StateGraph remains the orchestration boundary for both
legacy SatQuery analyses and NISAR analyses:

`input -> validation -> classification -> specialist -> evidence fusion -> report`

NISAR routes are:

- `nisar_change`: temporal HH/HV backscatter comparison.
- `nisar_flood`: candidate surface-water and inundated-vegetation analysis.

The generalized NISAR job validates products and AOI data first, then passes
the validated processing result into the typed graph. The graph records the
source as `validated_processing_result`, preserves the thread ID, and emits
the same evidence and report shape used by other specialists.

Failures are surfaced as failed job status or an explicit graph error. A
failed specialist is never represented as a successful result.
