"""
Import enriched AI-harm events into Neo4j.

Schema:
    (:Event)-[:USES_AI_SYSTEM]->(:AISystem)
    (:Event)-[:INVOLVES_ORGANIZATION]->(:Organization)
    (:Event)-[:AFFECTS]->(:AffectedGroup)
    (:Event)-[:HAS_ACTION]->(:Action)
    (:Event)-[:HAS_CONSEQUENCE]->(:Consequence)
    (:Event)-[:OCCURRED_IN]->(:Location)
    (:Event)-[:HAS_HARM_CATEGORY]->(:HarmCategory)
    (:Event)-[:REPORTED_BY]->(:Source)
    (:Event)-[:SIMILAR_TO]->(:Event)

The original extracted values are retained on Event nodes. Named entities are
canonicalized only for graph identity, and the complete source record is also
stored in raw_json.
"""

import json
import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("ai_harm_neo4j")


@dataclass(frozen=True)
class Config:
    json_path: Path
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str = "neo4j"
    batch_size: int = 100


MISSING_VALUES = {
    "",
    "none",
    "null",
    "unknown",
    "n/a",
    "na",
    "not applicable",
    "not specified",
    "not specified in report",
}


def clean_text(value):
    if value is None:
        return ""

    text = unicodedata.normalize("NFKC", str(value))
    text = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )
    return re.sub(r"\s+", " ", text).strip()


def is_meaningful(value):
    text = clean_text(value)
    return bool(text and text.casefold() not in MISSING_VALUES)


def identity_key(value):
    text = clean_text(value).casefold().replace("&", " and ")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


ORGANIZATION_ALIASES_RAW = {
    "OpenAI": "OpenAI",
    "Open AI": "OpenAI",
    "OpenAI Inc": "OpenAI",
    "OpenAI Inc.": "OpenAI",
    "OpenAI (Microsoft-backed)": "OpenAI",
    "OpenAI (Microsoft-backed company)": "OpenAI",
    "OpenAI (ChatGPT provider)": "OpenAI",
    "OpenAI (developer of Sora 2)": "OpenAI",
    "Meta": "Meta",
    "Meta Platforms": "Meta",
    "Meta Platforms Inc": "Meta",
    "Meta Platforms Inc.": "Meta",
    "Meta (Facebook)": "Meta",
    "Meta (formerly Facebook)": "Meta",
    "xAI": "xAI",
    "X AI": "xAI",
    "x.ai": "xAI",
    "xAI (Elon Musk's company)": "xAI",
    "xAI (parent company of Grok)": "xAI",
    "DHS": "U.S. Department of Homeland Security",
    "Department of Homeland Security": "U.S. Department of Homeland Security",
    "U.S. Department of Homeland Security": "U.S. Department of Homeland Security",
    "CBP": "U.S. Customs and Border Protection",
    "Customs and Border Protection": "U.S. Customs and Border Protection",
    "U.S. Customs and Border Protection": "U.S. Customs and Border Protection",
    "U.S. Customs and Border Protection (CBP)": "U.S. Customs and Border Protection",
    "NOPD": "New Orleans Police Department",
    "New Orleans Police Department": "New Orleans Police Department",
}

AI_SYSTEM_ALIASES_RAW = {
    "ChatGPT": "ChatGPT",
    "Chat GPT": "ChatGPT",
    "OpenAI ChatGPT": "ChatGPT",
    "ChatGPT AI chatbot": "ChatGPT",
    "ChatGPT (AI chatbot)": "ChatGPT",
    "ChatGPT (AI language model)": "ChatGPT",
    "GPT4": "GPT-4",
    "GPT 4": "GPT-4",
    "GPT-4": "GPT-4",
    "GPT4o": "GPT-4o",
    "GPT 4o": "GPT-4o",
    "GPT-4o": "GPT-4o",
    "Google Gemini": "Gemini",
    "Gemini": "Gemini",
    "xAI Grok": "Grok",
    "Grok": "Grok",
    "Anthropic Claude": "Claude",
    "Claude": "Claude",
    "Microsoft Bing Image Creator": "Bing Image Creator",
    "Bing Image Creator": "Bing Image Creator",
    "VioGen": "VioGén",
    "Vio Gén": "VioGén",
    "VioGén": "VioGén",
    "LAION 5B": "LAION-5B",
    "LAION-5B": "LAION-5B",
}

COUNTRY_ALIASES = {
    "United States of America": "United States",
    "U.S.A.": "United States",
    "U.S.": "United States",
    "USA": "United States",
    "US": "United States",
    "Great Britain": "United Kingdom",
    "Britain": "United Kingdom",
    "U.K.": "United Kingdom",
    "UK": "United Kingdom",
    "U.A.E.": "United Arab Emirates",
    "UAE": "United Arab Emirates",
}


def compile_aliases(aliases):
    return {identity_key(alias): canonical for alias, canonical in aliases.items()}


ORGANIZATION_ALIASES = compile_aliases(ORGANIZATION_ALIASES_RAW)
AI_SYSTEM_ALIASES = compile_aliases(AI_SYSTEM_ALIASES_RAW)


def canonicalize(value, aliases):
    raw = clean_text(value)
    if not is_meaningful(raw):
        return ""
    return aliases.get(identity_key(raw), raw)


def normalize_location(value):
    text = clean_text(value)
    if not is_meaningful(text):
        return ""

    for alias, canonical in sorted(
        COUNTRY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True
    ):
        text = re.sub(
            rf"(?<!\w){re.escape(alias)}(?!\w)",
            canonical,
            text,
            flags=re.IGNORECASE,
        )

    text = re.sub(r"\s*,\s*", ", ", text)
    return re.sub(r"\s+", " ", text).strip()


def entity(raw_value, *, canonical_value=None):
    raw = clean_text(raw_value)
    if not is_meaningful(raw):
        return None

    canonical = clean_text(canonical_value if canonical_value is not None else raw)
    if not canonical:
        return None

    return {"key": identity_key(canonical), "name": canonical, "raw": raw}


def organization_entity(value):
    return entity(value, canonical_value=canonicalize(value, ORGANIZATION_ALIASES))


def ai_system_entity(value):
    return entity(value, canonical_value=canonicalize(value, AI_SYSTEM_ALIASES))


def location_entity(value):
    return entity(value, canonical_value=normalize_location(value))


def safe_float(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def numeric_vector(value):
    if not isinstance(value, list):
        return None

    values = []
    for item in value:
        number = safe_float(item)
        if number is None:
            return None
        values.append(number)

    return values


def load_events(path):
    if not path.exists():
        raise FileNotFoundError(path)

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Empty input file: {path}")

    if raw.startswith("["):
        events = json.loads(raw)
        if not isinstance(events, list):
            raise ValueError("Top-level JSON must be an array.")
    else:
        events = []
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_number}: {exc}") from exc

    if not all(isinstance(event, dict) for event in events):
        raise ValueError("Every event must be a JSON object.")

    logger.info("Loaded %d events", len(events))
    return events


def neo4j_safe_value(value):
    if value is None:
        return None

    if isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, list):
        if not value:
            return []

        vector = numeric_vector(value)
        if vector is not None:
            return vector

        if all(isinstance(item, str) for item in value):
            return value

        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    return str(value)


def event_properties(event):
    props = {key: neo4j_safe_value(value) for key, value in event.items()}
    props["raw_json"] = json.dumps(event, ensure_ascii=False)

    props["organization_raw"] = clean_text(event.get("organization"))
    props["organization_normalized"] = canonicalize(
        event.get("organization"), ORGANIZATION_ALIASES
    )
    props["ai_system_raw"] = clean_text(event.get("ai_system"))
    props["ai_system_normalized"] = canonicalize(
        event.get("ai_system"), AI_SYSTEM_ALIASES
    )
    props["location_raw"] = clean_text(event.get("location"))
    props["location_normalized"] = normalize_location(event.get("location"))

    learned = event.get("learned_representation")
    if isinstance(learned, dict):
        embedding = numeric_vector(learned.get("event_embedding"))
        temporal = numeric_vector(learned.get("temporal_representation"))

        if embedding is not None:
            props["event_embedding"] = embedding
        if temporal is not None:
            props["temporal_representation"] = temporal

        for field in (
            "ai_system_recurrence_probability",
            "harm_category_recurrence_probability",
            "phtkg_event_score",
            "pattern_probability",
        ):
            value = safe_float(learned.get(field))
            if value is not None:
                props[field] = value

    return {key: value for key, value in props.items() if value is not None}


def harm_categories(event):
    categories = event.get("harm_category")

    if isinstance(categories, dict):
        categories = [categories]
    if not isinstance(categories, list):
        return []

    result = []
    for category in categories:
        if not isinstance(category, dict):
            continue

        branch = clean_text(category.get("branch"))
        subcategory_id = clean_text(category.get("subcategory_id"))
        subcategory = clean_text(category.get("subcategory"))
        event_type = clean_text(category.get("event_type"))

        key = subcategory_id or identity_key(f"{branch}|{subcategory}")
        if not key:
            continue

        result.append(
            {
                "key": key,
                "branch": branch,
                "subcategory_id": subcategory_id,
                "subcategory": subcategory,
                "event_type": event_type,
            }
        )

    return result


def prepare_event(event):
    report_id = clean_text(event.get("report_id"))
    if not report_id:
        raise ValueError("Encountered event without report_id.")

    return {
        "report_id": report_id,
        "properties": event_properties(event),
        "organization": organization_entity(event.get("organization")),
        "ai_system": ai_system_entity(event.get("ai_system")),
        "affected_group": entity(event.get("affected_group")),
        "action": entity(event.get("action")),
        "consequence": entity(event.get("consequence")),
        "location": location_entity(event.get("location")),
        "source": clean_text(event.get("source")) or None,
        "harm_categories": harm_categories(event),
    }


CONSTRAINTS = (
    """
    CREATE CONSTRAINT event_report_id IF NOT EXISTS
    FOR (n:Event) REQUIRE n.report_id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT organization_key IF NOT EXISTS
    FOR (n:Organization) REQUIRE n.key IS UNIQUE
    """,
    """
    CREATE CONSTRAINT ai_system_key IF NOT EXISTS
    FOR (n:AISystem) REQUIRE n.key IS UNIQUE
    """,
    """
    CREATE CONSTRAINT affected_group_key IF NOT EXISTS
    FOR (n:AffectedGroup) REQUIRE n.key IS UNIQUE
    """,
    """
    CREATE CONSTRAINT action_key IF NOT EXISTS
    FOR (n:Action) REQUIRE n.key IS UNIQUE
    """,
    """
    CREATE CONSTRAINT consequence_key IF NOT EXISTS
    FOR (n:Consequence) REQUIRE n.key IS UNIQUE
    """,
    """
    CREATE CONSTRAINT location_key IF NOT EXISTS
    FOR (n:Location) REQUIRE n.key IS UNIQUE
    """,
    """
    CREATE CONSTRAINT harm_category_key IF NOT EXISTS
    FOR (n:HarmCategory) REQUIRE n.key IS UNIQUE
    """,
    """
    CREATE CONSTRAINT source_url IF NOT EXISTS
    FOR (n:Source) REQUIRE n.url IS UNIQUE
    """,
)


IMPORT_EVENTS_QUERY = """
UNWIND $rows AS row

MERGE (e:Event {report_id: row.report_id})
SET e = row.properties

FOREACH (_ IN CASE WHEN row.organization IS NULL THEN [] ELSE [1] END |
    MERGE (org:Organization {key: row.organization.key})
    ON CREATE SET org.name = row.organization.name, org.aliases = [row.organization.raw]
    SET org.aliases =
        CASE
            WHEN row.organization.raw IN coalesce(org.aliases, [])
            THEN org.aliases
            ELSE coalesce(org.aliases, []) + row.organization.raw
        END
    MERGE (e)-[:INVOLVES_ORGANIZATION]->(org)
)

FOREACH (_ IN CASE WHEN row.ai_system IS NULL THEN [] ELSE [1] END |
    MERGE (ai:AISystem {key: row.ai_system.key})
    ON CREATE SET ai.name = row.ai_system.name, ai.aliases = [row.ai_system.raw]
    SET ai.aliases =
        CASE
            WHEN row.ai_system.raw IN coalesce(ai.aliases, [])
            THEN ai.aliases
            ELSE coalesce(ai.aliases, []) + row.ai_system.raw
        END
    MERGE (e)-[:USES_AI_SYSTEM]->(ai)
)

FOREACH (_ IN CASE WHEN row.affected_group IS NULL THEN [] ELSE [1] END |
    MERGE (g:AffectedGroup {key: row.affected_group.key})
    ON CREATE SET g.name = row.affected_group.name, g.aliases = [row.affected_group.raw]
    SET g.aliases =
        CASE
            WHEN row.affected_group.raw IN coalesce(g.aliases, [])
            THEN g.aliases
            ELSE coalesce(g.aliases, []) + row.affected_group.raw
        END
    MERGE (e)-[:AFFECTS]->(g)
)

FOREACH (_ IN CASE WHEN row.action IS NULL THEN [] ELSE [1] END |
    MERGE (a:Action {key: row.action.key})
    ON CREATE SET a.name = row.action.name
    MERGE (e)-[:HAS_ACTION]->(a)
)

FOREACH (_ IN CASE WHEN row.consequence IS NULL THEN [] ELSE [1] END |
    MERGE (c:Consequence {key: row.consequence.key})
    ON CREATE SET c.name = row.consequence.name
    MERGE (e)-[:HAS_CONSEQUENCE]->(c)
)

FOREACH (_ IN CASE WHEN row.location IS NULL THEN [] ELSE [1] END |
    MERGE (l:Location {key: row.location.key})
    ON CREATE SET l.name = row.location.name, l.aliases = [row.location.raw]
    SET l.aliases =
        CASE
            WHEN row.location.raw IN coalesce(l.aliases, [])
            THEN l.aliases
            ELSE coalesce(l.aliases, []) + row.location.raw
        END
    MERGE (e)-[:OCCURRED_IN]->(l)
)

FOREACH (_ IN CASE WHEN row.source IS NULL THEN [] ELSE [1] END |
    MERGE (s:Source {url: row.source})
    MERGE (e)-[:REPORTED_BY]->(s)
)

FOREACH (category IN row.harm_categories |
    MERGE (h:HarmCategory {key: category.key})
    SET h.branch = category.branch,
        h.subcategory_id = category.subcategory_id,
        h.subcategory = category.subcategory
    MERGE (e)-[r:HAS_HARM_CATEGORY]->(h)
    SET r.event_type = category.event_type
)
"""


IMPORT_SIMILARITY_QUERY = """
UNWIND $rows AS row
MATCH (source:Event {report_id: row.source})
MATCH (target:Event {report_id: row.target})
MERGE (source)-[r:SIMILAR_TO]->(target)
SET r.similarity = row.similarity,
    r.rank = row.rank
"""


class Neo4jImporter:
    def __init__(self, config):
        self.config = config
        self.driver = GraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password),
        )

    def close(self):
        self.driver.close()

    def verify_connection(self):
        self.driver.verify_connectivity()
        logger.info("Connected to Neo4j.")

    def create_schema(self):
        for query in CONSTRAINTS:
            self.driver.execute_query(query, database_=self.config.neo4j_database)
        logger.info("Schema constraints ready.")

    def import_events(self, events):
        rows = [prepare_event(event) for event in events]
        total = len(rows)

        for start in range(0, total, self.config.batch_size):
            batch = rows[start : start + self.config.batch_size]
            self.driver.execute_query(
                IMPORT_EVENTS_QUERY,
                rows=batch,
                database_=self.config.neo4j_database,
            )
            logger.info("Events imported: %d/%d", min(start + len(batch), total), total)

    def import_similarities(self, events):
        valid_ids = {clean_text(event.get("report_id")) for event in events}
        rows = []

        for event in events:
            source_id = clean_text(event.get("report_id"))
            learned = event.get("learned_representation")

            if not isinstance(learned, dict):
                continue

            for rank, item in enumerate(learned.get("similar_events", []), start=1):
                if not isinstance(item, dict):
                    continue

                target_id = clean_text(item.get("report_id"))
                similarity = safe_float(item.get("similarity"))

                if target_id in valid_ids and similarity is not None:
                    rows.append(
                        {
                            "source": source_id,
                            "target": target_id,
                            "similarity": similarity,
                            "rank": rank,
                        }
                    )

        for start in range(0, len(rows), 500):
            self.driver.execute_query(
                IMPORT_SIMILARITY_QUERY,
                rows=rows[start : start + 500],
                database_=self.config.neo4j_database,
            )

        logger.info("Similarity edges imported: %d", len(rows))

    def verify_import(self, expected_events):
        records, _, _ = self.driver.execute_query(
            "MATCH (e:Event) RETURN count(e) AS count",
            database_=self.config.neo4j_database,
        )
        actual_events = records[0]["count"]

        if actual_events != expected_events:
            logger.warning(
                "Event count mismatch: expected %d, found %d",
                expected_events,
                actual_events,
            )
        else:
            logger.info("Event count verified: %d", actual_events)

        records, _, _ = self.driver.execute_query(
            """
            MATCH (n)
            UNWIND labels(n) AS label
            RETURN label, count(*) AS count
            ORDER BY count DESC
            """,
            database_=self.config.neo4j_database,
        )

        logger.info("Node counts:")
        for record in records:
            logger.info("  %-20s %d", record["label"], record["count"])

        records, _, _ = self.driver.execute_query(
            """
            MATCH ()-[r]->()
            RETURN type(r) AS type, count(*) AS count
            ORDER BY count DESC
            """,
            database_=self.config.neo4j_database,
        )

        logger.info("Relationship counts:")
        for record in records:
            logger.info("  %-30s %d", record["type"], record["count"])


def validate_report_ids(events):
    report_ids = [clean_text(event.get("report_id")) for event in events]

    missing = [index for index, report_id in enumerate(report_ids) if not report_id]
    if missing:
        raise ValueError(f"{len(missing)} events have no report_id.")

    seen = set()
    duplicates = set()
    for report_id in report_ids:
        if report_id in seen:
            duplicates.add(report_id)
        seen.add(report_id)

    if duplicates:
        raise ValueError(
            "Duplicate report_id values: " + ", ".join(sorted(duplicates))
        )


def main():
    json_path = Path("/content/predicted_events_FULL_EVIDENCE_PRETTY.json")

    config = Config(
        json_path=json_path,
        neo4j_uri=input("Neo4j URI: ").strip(),
        neo4j_user=input("Neo4j username [neo4j]: ").strip() or "neo4j",
        neo4j_password=getpass("Neo4j password: "),
        neo4j_database=input("Neo4j database [neo4j]: ").strip() or "neo4j",
        batch_size=100,
    )

    events = load_events(config.json_path)
    validate_report_ids(events)

    importer = Neo4jImporter(config)

    try:
        importer.verify_connection()
        importer.create_schema()
        importer.import_events(events)
        importer.import_similarities(events)
        importer.verify_import(expected_events=len(events))
        logger.info("Neo4j import completed successfully.")
    finally:
        importer.close()


if __name__ == "__main__":
    main()