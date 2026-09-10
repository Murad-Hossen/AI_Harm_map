# Neo4j storage

Neo4j provides an optional persistent graph-oriented representation of the
enriched event corpus. It is not the rendering backend of the Dynamic AI Harm
Map.

## Event-centered schema

```text
(:Event)-[:USES_AI_SYSTEM]->(:AISystem)
(:Event)-[:INVOLVES_ORGANIZATION]->(:Organization)
(:Event)-[:AFFECTS]->(:AffectedGroup)
(:Event)-[:HAS_ACTION]->(:Action)
(:Event)-[:HAS_CONSEQUENCE]->(:Consequence)
(:Event)-[:OCCURRED_IN]->(:Location)
(:Event)-[:HAS_HARM_CATEGORY]->(:HarmCategory)
(:Event)-[:REPORTED_BY]->(:Source)
(:Event)-[:SIMILAR_TO]->(:Event)
```

Named entities may be canonicalized during ingestion while the original
extracted values remain on Event nodes. The complete original event object is
also retained as `raw_json`.

Example browser query:

```cypher
MATCH (e:Event)
WITH e
LIMIT 20
OPTIONAL MATCH (e)-[r]->(n)
RETURN e, r, n
```
