import argparse
import os
from getpass import getpass
from pathlib import Path

from ai_harm_map.storage.neo4j_importer import (
    Config,
    Neo4jImporter,
    load_events,
    validate_report_ids,
)


def main():
    parser = argparse.ArgumentParser(description="Import enriched AI-harm events into Neo4j.")
    parser.add_argument("--input", required=True, type=Path, help="JSON or JSONL event file")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--database", default=os.getenv("NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    if not args.uri:
        raise SystemExit("Neo4j URI is required via --uri or NEO4J_URI.")

    password = os.getenv("NEO4J_PASSWORD") or getpass("Neo4j password: ")

    config = Config(
        json_path=args.input,
        neo4j_uri=args.uri,
        neo4j_user=args.user,
        neo4j_password=password,
        neo4j_database=args.database,
        batch_size=args.batch_size,
    )

    events = load_events(args.input)
    validate_report_ids(events)
    importer = Neo4jImporter(config)

    try:
        importer.verify_connection()
        importer.create_schema()
        importer.import_events(events)
        importer.import_similarities(events)
        importer.verify_import(expected_events=len(events))
    finally:
        importer.close()


if __name__ == "__main__":
    main()