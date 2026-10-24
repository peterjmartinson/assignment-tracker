import argparse
import sys
import requests
from src.printout import (
    STARTER_WEEKLY_ITEMS,
    fetch_items_from_sheets,
    generate_weekly_printout,
    load_tracker_config,
    save_snapshot,
)


def seed_sheets_command(force: bool = False):
    """Seed the Google Sheet with starter weekly assignments if empty (or when --force is passed)."""
    try:
        config = load_tracker_config()
        sheets_cfg = config.get("google_sheets", {}) or {}
        script_url = (sheets_cfg.get("script_url") or "").strip()
        sheet_name = (sheets_cfg.get("sheet_name") or "Homework").strip()

        if not script_url:
            print("Error: google_sheets.script_url is not set in config.yaml", file=sys.stderr)
            sys.exit(1)

        existing = fetch_items_from_sheets(config)
        if existing and not force:
            print(f"Sheet already contains {len(existing)} item(s). Use --force to overwrite with starter weekly schedule.")
            return

        sep = "&" if "?" in script_url else "?"
        target_url = f"{script_url}{sep}sheet={sheet_name}"
        res = requests.post(
            target_url,
            data=requests.compat.json.dumps(STARTER_WEEKLY_ITEMS),
            headers={"Content-Type": "text/plain;charset=utf-8"},
            timeout=15,
        )
        res.raise_for_status()
        save_snapshot(STARTER_WEEKLY_ITEMS)
        print(f"[SUCCESS] Seeded Google Sheet '{sheet_name}' with {len(STARTER_WEEKLY_ITEMS)} weekly assignments!")
    except Exception as e:
        print(f"Error seeding Google Sheet: {e}", file=sys.stderr)
        sys.exit(1)


def printout_command(this_week=False, date_str=None, no_pull=False, open_pdf=False):
    try:
        target = "this" if this_week else "next"
        generate_weekly_printout(
            target=target,
            ref_date_str=date_str,
            no_pull=no_pull,
            open_pdf=open_pdf,
        )
    except Exception as e:
        print(f"Error during printout generation: {e}", file=sys.stderr)
        sys.exit(1)


def printout_cli():
    parser = argparse.ArgumentParser(description="Generate one-page fridge PDF printout of weekly homework")
    parser.add_argument("--this-week", action="store_true", help="Generate for current week instead of next week")
    parser.add_argument("--next-week", action="store_true", help="Generate for next week (default)")
    parser.add_argument("--date", "-d", help="Generate for the week containing this date (YYYY-MM-DD)")
    parser.add_argument("--no-pull", "--offline", action="store_true", help="Skip fetching from Google Sheets; use cached snapshot")
    parser.add_argument("--open", "-o", action="store_true", help="Open the generated PDF in default viewer")
    args, _ = parser.parse_known_args()
    printout_command(
        this_week=args.this_week,
        date_str=args.date,
        no_pull=args.no_pull,
        open_pdf=args.open,
    )


def seed_cli():
    parser = argparse.ArgumentParser(description="Seed Google Sheet with starter weekly homework")
    parser.add_argument("--force", action="store_true", help="Overwrite existing rows with starter weekly items")
    args, _ = parser.parse_known_args()
    seed_sheets_command(force=args.force)


def main():
    parser = argparse.ArgumentParser(description="Homework Tracker v2 CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    print_p = subparsers.add_parser("printout", help="Generate one-page weekly fridge printout")
    print_p.add_argument("--this-week", action="store_true", help="Generate for current week")
    print_p.add_argument("--next-week", action="store_true", help="Generate for next week (default)")
    print_p.add_argument("--date", "-d", help="Generate for week containing YYYY-MM-DD")
    print_p.add_argument("--no-pull", "--offline", action="store_true", help="Skip Google Sheets fetch")
    print_p.add_argument("--open", "-o", action="store_true", help="Open PDF in default viewer")

    seed_p = subparsers.add_parser("seed", help="Seed Google Sheet with starter weekly schedule")
    seed_p.add_argument("--force", action="store_true", help="Overwrite existing rows")

    args = parser.parse_args()

    if args.command == "printout":
        printout_command(
            this_week=args.this_week,
            date_str=args.date,
            no_pull=args.no_pull,
            open_pdf=args.open,
        )
    elif args.command == "seed":
        seed_sheets_command(force=args.force)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
