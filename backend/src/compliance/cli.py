"""Command-line maintenance helpers for the compliance backend."""

import argparse
import getpass
import sys
from collections.abc import Sequence

from sqlalchemy.orm import Session

from compliance.db.db_access import get_engine
from compliance.services.users import bootstrap_first_admin


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
