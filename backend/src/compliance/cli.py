"""Command-line maintenance helpers for the compliance backend."""

import argparse
import getpass
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.orm import Session

from compliance._helpers import ROOT_DIR
from compliance.db.db_access import get_engine
from compliance.llm.rag.extract_clauses import import_rag_clauses
from compliance.llm.rag.parse_boe import fetch_boe_regulation, parse_boe_regulation
from compliance.services.rag import upsert_rag_document_from_parsed_json
from compliance.services.users import bootstrap_first_admin

RAG_STORAGE_DIR = ROOT_DIR / "backend" / "storage" / "rag"
PARSED_BOES_DIR = RAG_STORAGE_DIR / "parsed_boes"
CLAUSES_DIR = RAG_STORAGE_DIR / "clauses"


def parsed_boe_path(boe_id: str) -> Path:
    """Return the default parsed BOE JSON path for a BOE identifier."""
    return PARSED_BOES_DIR / f"{boe_id}.json"


def clauses_path(parsed_boe_file: Path, output_dir: Path = CLAUSES_DIR) -> Path:
    """Return the default clauses JSON path for a parsed BOE JSON file."""
    return output_dir / parsed_boe_file.name


def write_json(path: Path, data: object, *, overwrite: bool) -> None:
    """Write JSON to disk, optionally refusing to replace an existing file."""
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists. Pass --overwrite to replace it.")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def parse_boe(args: argparse.Namespace) -> int:
    """Fetch and serialize a BOE regulation for RAG ingestion."""
    output_path = args.output_path or parsed_boe_path(args.boe_id)

    try:
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(
                f"{output_path} already exists. Pass --overwrite to replace it."
            )

        raw_data = fetch_boe_regulation(args.boe_id)
        regulation = parse_boe_regulation(raw_data)
        write_json(output_path, regulation, overwrite=args.overwrite)
    except Exception as exc:
        print(f"BOE parsing failed: {exc}", file=sys.stderr)
        return 1

    print(f"Saved parsed BOE to: {output_path.resolve()}")
    return 0


def extract_clauses(args: argparse.Namespace) -> int:
    """Extract RAG clauses from every parsed BOE JSON file."""
    input_dir = args.input_dir
    output_dir = args.output_dir
    parsed_boe_files = sorted(input_dir.glob("*.json"))

    if not parsed_boe_files:
        print(f"No parsed BOE JSON files found in: {input_dir.resolve()}")
        return 0

    total_clauses = 0

    for parsed_boe_file in parsed_boe_files:
        output_path = clauses_path(parsed_boe_file, output_dir)

        try:
            with parsed_boe_file.open("r", encoding="utf-8") as file:
                document = json.load(file)

            clauses = import_rag_clauses(document)
            write_json(output_path, clauses, overwrite=True)
        except Exception as exc:
            print(
                f"Clause extraction failed for {parsed_boe_file}: {exc}",
                file=sys.stderr,
            )
            return 1

        total_clauses += len(clauses)
        print(f"Created {len(clauses)} clauses: {output_path.resolve()}")

    print(f"Created {total_clauses} clauses from {len(parsed_boe_files)} files.")
    return 0


def import_rag_documents(args: argparse.Namespace) -> int:
    """Import RAG document metadata from parsed BOE JSON files."""
    parsed_boe_files = sorted(args.input_dir.glob("*.json"))

    if not parsed_boe_files:
        print(f"No parsed BOE JSON files found in: {args.input_dir.resolve()}")
        return 0

    action_counts = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
    }

    with Session(get_engine()) as session:
        for parsed_boe_file in parsed_boe_files:
            try:
                with parsed_boe_file.open("r", encoding="utf-8") as file:
                    document = json.load(file)

                result = upsert_rag_document_from_parsed_json(session, document)
            except Exception as exc:
                print(
                    f"RAG document import failed for {parsed_boe_file}: {exc}",
                    file=sys.stderr,
                )
                return 1

            action_counts[result.action] += 1

    print(
        f"Imported {len(parsed_boe_files)} RAG documents: "
        f"{action_counts['created']} created, "
        f"{action_counts['updated']} updated, "
        f"{action_counts['skipped']} skipped."
    )
    return 0


def bootstrap_admin(args: argparse.Namespace) -> int:
    """Create the first admin user from command-line arguments."""
    password = getpass.getpass("Admin password: ")
    password_confirmation = getpass.getpass("Confirm admin password: ")

    if not password:
        print("Admin password cannot be empty.", file=sys.stderr)
        return 1

    if password != password_confirmation:
        print("Admin passwords do not match.", file=sys.stderr)
        return 1

    try:
        with Session(get_engine()) as session:
            result = bootstrap_first_admin(
                session,
                full_name=args.full_name,
                email=args.email,
                password=password,
            )

    except Exception as exc:
        print(f"First admin bootstrap failed: {exc}", file=sys.stderr)
        return 1

    if result.created and result.user is not None:
        print(f"Created first admin user: {result.user.email}")
    else:
        print("Active admin user already exists; no user created.")

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the backend maintenance command parser."""
    parser = argparse.ArgumentParser(prog="python -m compliance.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    rag_parser = subparsers.add_parser(
        "rag",
        help="Run RAG ingestion maintenance commands.",
    )
    rag_subparsers = rag_parser.add_subparsers(dest="rag_command", required=True)

    parse_boe_parser = rag_subparsers.add_parser(
        "parse-boe",
        help="Fetch and serialize a BOE regulation.",
    )
    parse_boe_parser.add_argument("--boe-id", required=True)
    parse_boe_parser.add_argument(
        "--output-path",
        type=Path,
        help="Destination for the parsed BOE JSON.",
    )
    parse_boe_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing parsed BOE JSON file.",
    )
    parse_boe_parser.set_defaults(func=parse_boe)

    extract_clauses_parser = rag_subparsers.add_parser(
        "extract-clauses",
        help="Extract RAG clauses from all parsed BOE JSON files.",
    )
    extract_clauses_parser.add_argument(
        "--input-dir",
        type=Path,
        default=PARSED_BOES_DIR,
        help="Directory containing parsed BOE JSON files.",
    )
    extract_clauses_parser.add_argument(
        "--output-dir",
        type=Path,
        default=CLAUSES_DIR,
        help="Directory where clause JSON files should be written.",
    )
    extract_clauses_parser.set_defaults(func=extract_clauses)

    import_documents_parser = rag_subparsers.add_parser(
        "import-documents",
        help="Import RAG document metadata from parsed BOE JSON files.",
    )
    import_documents_parser.add_argument(
        "--input-dir",
        type=Path,
        default=PARSED_BOES_DIR,
        help="Directory containing parsed BOE JSON files.",
    )
    import_documents_parser.set_defaults(func=import_rag_documents)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap-admin",
        help="Create the first active admin user if one does not already exist.",
    )
    bootstrap_parser.add_argument("--full-name", required=True)
    bootstrap_parser.add_argument("--email", required=True)
    bootstrap_parser.set_defaults(func=bootstrap_admin)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the compliance maintenance CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
