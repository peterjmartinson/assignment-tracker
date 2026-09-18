import argparse
import sys
import os
import requests
from src.trello_utils import (
    load_config,
    load_homework,
    save_homework,
    backup_workspace,
    get_credentials,
    fetch_active_cards,
    fetch_board_labels,
    validate_homework,
    normalize_date_for_trello,
    normalize_date_for_yaml,
    WORKSPACE_FILE
)
from src.ingest import ingest_from_gmail, ingest_from_eml_file

def pull_command():
    try:
        config = load_config()
        api_key, api_token = get_credentials()

        print("Backing up existing workspace...")
        backup_path = backup_workspace()
        if backup_path:
            print(f"Snapshot created at: {backup_path}")

        print("Fetching cards from Trello...")
        cards_by_kid = fetch_active_cards(config, api_key, api_token)
        save_homework(cards_by_kid)

        total_cards = sum(len(cards) for cards in cards_by_kid.values())
        print(f"\nSuccessfully pulled {total_cards} active card(s) across {len(cards_by_kid)} kid(s):")
        for kid, cards in cards_by_kid.items():
            print(f"  • {kid}: {len(cards)} card(s)")
        print(f"\nSaved clean homework file to: {WORKSPACE_FILE}")
    except Exception as e:
        print(f"Error during pull: {e}", file=sys.stderr)
        sys.exit(1)

def validate_command():
    try:
        config = load_config()
        if not os.path.exists(WORKSPACE_FILE):
            print(f"No workspace file found at {WORKSPACE_FILE}. Run 'python main.py pull' first.", file=sys.stderr)
            sys.exit(1)

        local_data = load_homework(WORKSPACE_FILE)
        is_valid, errors = validate_homework(local_data, config)

        if not is_valid:
            print("Validation Failed:", file=sys.stderr)
            for err in errors:
                print(f"  ❌ {err}", file=sys.stderr)
            sys.exit(1)

        total_cards = sum(len(cards) for cards in local_data.values())
        print(f"Validation Passed! {total_cards} card(s) validated across {list(local_data.keys())}.")
    except Exception as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)

def push_command(dry_run=False):
    try:
        config = load_config()
        api_key, api_token = get_credentials()
        board_id = config['board_id']

        if not os.path.exists(WORKSPACE_FILE):
            print(f"Workspace file not found at {WORKSPACE_FILE}. Run 'python main.py pull' first.", file=sys.stderr)
            sys.exit(1)

        local_data = load_homework(WORKSPACE_FILE)
        is_valid, errors = validate_homework(local_data, config)
        if not is_valid:
            print("Cannot push: Validation failed:", file=sys.stderr)
            for err in errors:
                print(f"  ❌ {err}", file=sys.stderr)
            sys.exit(1)

        print("Fetching current Trello state...")
        trello_state_by_kid = fetch_active_cards(config, api_key, api_token)
        name_to_label_id, id_to_label_name = fetch_board_labels(board_id, api_key, api_token)

        # Build index of active Trello cards by ID
        trello_cards_by_id = {}
        for kid, cards in trello_state_by_kid.items():
            for c in cards:
                trello_cards_by_id[c['id']] = {**c, 'kid': kid}

        local_card_ids = set()
        to_create = []
        to_update = []

        for kid, cards in local_data.items():
            list_id = config.get('lists', {}).get(kid)
            if not list_id:
                print(f"Warning: No list ID configured for kid '{kid}'. Skipping.", file=sys.stderr)
                continue

            for card in cards:
                card_id = card.get('id')
                if card_id:
                    local_card_ids.add(card_id)
                    if card_id in trello_cards_by_id:
                        trello_card = trello_cards_by_id[card_id]
                        # Check if card needs update
                        needs_update = False
                        if (card.get('name') or '') != (trello_card.get('name') or ''):
                            needs_update = True
                        if (card.get('class') or '') != (trello_card.get('class') or ''):
                            needs_update = True
                        if (card.get('desc') or '') != (trello_card.get('desc') or ''):
                            needs_update = True
                        if normalize_date_for_yaml(card.get('due')) != normalize_date_for_yaml(trello_card.get('due')):
                            needs_update = True
                        if trello_card.get('kid') != kid:
                            needs_update = True

                        if needs_update:
                            to_update.append({'card': card, 'kid': kid, 'list_id': list_id})
                    else:
                        # Card had an ID but was deleted/closed on Trello -> treat as new
                        to_create.append({'card': card, 'kid': kid, 'list_id': list_id})
                else:
                    # New card without ID
                    to_create.append({'card': card, 'kid': kid, 'list_id': list_id})

        # Cards on Trello that are NOT in local YAML -> to archive
        to_archive = []
        for card_id, trello_card in trello_cards_by_id.items():
            if card_id not in local_card_ids:
                to_archive.append(trello_card)

        # Print Sync Summary / Preview
        print("\n================== Sync Plan ==================")
        print(f"➕ To Create:  {len(to_create)} card(s)")
        for item in to_create:
            c = item['card']
            cls_str = f"[{c.get('class')}] " if c.get('class') else ""
            due_str = f" (Due: {c.get('due')})" if c.get('due') else ""
            print(f"   • [{item['kid']}] {cls_str}{c.get('name')}{due_str}")

        print(f"🔄 To Update:  {len(to_update)} card(s)")
        for item in to_update:
            c = item['card']
            cls_str = f"[{c.get('class')}] " if c.get('class') else ""
            due_str = f" (Due: {c.get('due')})" if c.get('due') else ""
            print(f"   • [{item['kid']}] {cls_str}{c.get('name')}{due_str}")

        print(f"🗑️  To Archive: {len(to_archive)} card(s) (removed from YAML)")
        for c in to_archive:
            cls_str = f"[{c.get('class')}] " if c.get('class') else ""
            print(f"   • [{c.get('kid')}] {cls_str}{c.get('name')}")
        print("===============================================")

        if dry_run:
            print("\n[DRY RUN] No changes were made to Trello.")
            return

        # Execute Archives
        archived_count = 0
        for c in to_archive:
            url = f"https://api.trello.com/1/cards/{c['id']}"
            res = requests.put(url, params={'key': api_key, 'token': api_token}, json={'closed': True}, timeout=10)
            if res.status_code == 200:
                archived_count += 1
            else:
                print(f"Failed to archive card '{c['name']}': {res.text}", file=sys.stderr)

        # Execute Updates
        updated_count = 0
        for item in to_update:
            c = item['card']
            kid = item['kid']
            list_id = item['list_id']

            label_ids = []
            cls_name = c.get('class')
            if cls_name and cls_name.lower() in name_to_label_id:
                label_ids.append(name_to_label_id[cls_name.lower()])

            payload = {
                'name': c.get('name'),
                'idList': list_id,
                'desc': c.get('desc', ''),
                'due': normalize_date_for_trello(c.get('due')) or '',
                'idLabels': label_ids
            }

            url = f"https://api.trello.com/1/cards/{c['id']}"
            res = requests.put(url, params={'key': api_key, 'token': api_token}, json=payload, timeout=10)
            if res.status_code == 200:
                updated_count += 1
            else:
                print(f"Failed to update card '{c.get('name')}': {res.text}", file=sys.stderr)

        # Execute Creates & Backfill IDs
        created_count = 0
        for item in to_create:
            c = item['card']
            kid = item['kid']
            list_id = item['list_id']

            label_ids = []
            cls_name = c.get('class')
            if cls_name and cls_name.lower() in name_to_label_id:
                label_ids.append(name_to_label_id[cls_name.lower()])

            payload = {
                'name': c.get('name'),
                'idList': list_id,
                'desc': c.get('desc', ''),
                'due': normalize_date_for_trello(c.get('due')) or '',
                'idLabels': label_ids
            }

            url = "https://api.trello.com/1/cards"
            res = requests.post(url, params={'key': api_key, 'token': api_token}, json=payload, timeout=10)
            if res.status_code == 200:
                created_card = res.json()
                c['id'] = created_card['id']
                created_count += 1
            else:
                print(f"Failed to create card '{c.get('name')}': {res.text}", file=sys.stderr)

        # Save backfilled IDs to workspace file
        save_homework(local_data)
        print(f"\n[SUCCESS] Push complete: {created_count} created, {updated_count} updated, {archived_count} archived.")
        print(f"Workspace file updated with new Trello IDs: {WORKSPACE_FILE}")

    except Exception as e:
        print(f"Error during push: {e}", file=sys.stderr)
        sys.exit(1)

def ingest_email_command(dry_run=False, file_path=None, label_filter=None):
    try:
        if file_path:
            ingest_from_eml_file(file_path, dry_run=dry_run)
        else:
            ingest_from_gmail(dry_run=dry_run, label_filter=label_filter)
    except Exception as e:
        print(f"Error during email ingestion: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Two-List Homework Tracker & Sync Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # pull
    subparsers.add_parser("pull", help="Pull latest active cards from Trello into workspace/homework.yaml")

    # validate
    subparsers.add_parser("validate", help="Validate workspace/homework.yaml syntax, dates, and schema")

    # push
    push_parser = subparsers.add_parser("push", help="Push local changes from workspace/homework.yaml to Trello")
    push_parser.add_argument("--dry-run", action="store_true", help="Preview creations, updates, and archives without modifying Trello")

    # ingest-email
    ingest_parser = subparsers.add_parser(
        "ingest-email",
        help="Poll Gmail IMAP or ingest a .eml file and create cards in the appropriate kid's list"
    )
    ingest_parser.add_argument("--dry-run", action="store_true", help="Preview without creating cards")
    ingest_parser.add_argument("--file", "-f", help="Path to .eml file")
    ingest_parser.add_argument("--label", "-l", help="Override Gmail folder/label to scan")

    args = parser.parse_args()

    if args.command == "pull":
        pull_command()
    elif args.command == "validate":
        validate_command()
    elif args.command == "push":
        push_command(dry_run=args.dry_run)
    elif args.command == "ingest-email":
        ingest_email_command(dry_run=args.dry_run, file_path=args.file, label_filter=args.label)

if __name__ == "__main__":
    main()
