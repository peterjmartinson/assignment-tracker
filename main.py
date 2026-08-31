import argparse
import sys
import requests
from src.trello_utils import (
    load_config,
    load_homework,
    save_homework,
    get_credentials,
    fetch_active_cards,
    card_needs_update
)

def pull_command():
    try:
        config = load_config()
        api_key, api_token = get_credentials()
        
        print("Fetching cards from Trello...")
        cards = fetch_active_cards(config, api_key, api_token)
        save_homework(cards)
        print(f"Successfully pulled {len(cards)} cards and saved them to homework.yaml.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def push_command(dry_run=False):
    try:
        config = load_config()
        local_cards = load_homework()
        api_key, api_token = get_credentials()

        print("Fetching current state from Trello...")
        active_cards = fetch_active_cards(config, api_key, api_token)
        trello_state = {c['id']: c for c in active_cards}

        created = 0
        updated = 0
        skipped = 0
        failed = 0

        for card in local_cards:
            list_id = config['lists'].get(card['list'])
            if not list_id:
                print(f"Skipping '{card['name']}': Unknown list '{card['list']}'")
                skipped += 1
                continue

            # Build the payload
            payload = {
                'key': api_key,
                'token': api_token,
                'name': card['name'],
                'idList': list_id,
                'desc': card.get('desc', ''),
                'due': card.get('due', '') or ''
            }

            # Apply label and cover color based on the kid profile
            kid_name = card.get('kid')
            if kid_name and kid_name in config.get('profiles', {}):
                profile = config['profiles'][kid_name]
                payload['idLabels'] = profile['label_id']
                payload['cover'] = {'color': profile['cover_color'], 'size': 'normal'}
            else:
                if card.get('cover'):
                    payload['cover'] = {'color': card['cover'], 'size': 'normal'}
                else:
                    payload['cover'] = {'color': None, 'size': 'normal'}

            card_id = card.get('id')

            if card_id:
                # Update flow
                if card_id not in trello_state:
                    print(f"Warning: Card '{card['name']}' has ID {card_id} but doesn't exist on Trello. Skipping.")
                    failed += 1
                    continue

                trello_card = trello_state[card_id]
                if card_needs_update(card, trello_card, config):
                    if dry_run:
                        print(f"[DRY RUN] Would update: '{card['name']}'")
                        updated += 1
                    else:
                        url = f"https://api.trello.com/1/cards/{card_id}"
                        res = requests.put(url, json=payload)
                        if res.status_code == 200:
                            print(f"Updated: '{card['name']}'")
                            updated += 1
                        else:
                            print(f"Failed to update '{card['name']}': {res.text}")
                            failed += 1
                else:
                    skipped += 1
            else:
                # Create flow
                if dry_run:
                    print(f"[DRY RUN] Would create: '{card['name']}'")
                    created += 1
                else:
                    url = "https://api.trello.com/1/cards"
                    res = requests.post(url, json=payload)
                    if res.status_code == 200:
                        print(f"Created: '{card['name']}'")
                        created += 1
                    else:
                        print(f"Failed to create '{card['name']}': {res.text}")
                        failed += 1

        print("\n--- Push Summary ---")
        if dry_run:
            print(f"To Create: {created}")
            print(f"To Update: {updated}")
            print(f"To Skip:   {skipped}")
            if failed > 0:
                print(f"Issues:    {failed}")
        else:
            print(f"Created:   {created}")
            print(f"Updated:   {updated}")
            print(f"Skipped:   {skipped}")
            if failed > 0:
                print(f"Failed:    {failed}")
            
            if created > 0 or updated > 0:
                print("\nTip: Run 'python main.py pull' to refresh local IDs and cache.")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Trello Homework Tracker CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("pull", help="Pull latest cards from Trello board to homework.yaml")

    push_parser = subparsers.add_parser("push", help="Push local changes in homework.yaml to Trello board")
    push_parser.add_argument("--dry-run", action="store_true", help="Preview changes without executing them on Trello")

    args = parser.parse_args()

    if args.command == "pull":
        pull_command()
    elif args.command == "push":
        push_command(dry_run=args.dry_run)

if __name__ == "__main__":
    main()
