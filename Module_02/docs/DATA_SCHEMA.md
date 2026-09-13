# Event data schema

| Field | Meaning |
|---|---|
| `report_id` | Stable source-report identifier |
| `event_type` | Extracted harm-event description |
| `ai_system` | AI system/model/tool when specified |
| `organization` | Relevant organization/actor |
| `affected_group` | Population or subject affected |
| `action` | Harm-relevant action |
| `consequence` | Documented consequence |
| `location` | Factual location text |
| `event_date` | Event date or documented fallback |
| `confidence` | Extraction/provenance confidence |
| `harm_category` | Supplied taxonomy classification |
| `original_evidence_span` | Full original source text |
| `translated_evidence_span` | Full supplied translation or English source |
| `taxonomy_audit` | Classification provenance |
| `inference_audit` | Extraction/inference metadata |

Enriched inference output may additionally include event embeddings, temporal
representations, similarity rankings, recurrence estimates, cluster/pattern
assignments, and verification audits.

`Not specified in report` is a missing-value marker and must not become a shared
Neo4j entity.
