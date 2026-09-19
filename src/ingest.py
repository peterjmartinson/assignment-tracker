import os
import sys
from src.trello_utils import (
    load_config,
    save_homework,
    get_credentials,
    fetch_active_cards,
    create_trello_card,
    find_duplicate_card,
    WORKSPACE_FILE
)
from src.email_parser import parse_classroom_email, parse_eml_file
from src.gmail_client import GmailIMAPClient
from src.state_tracker import StateTracker

def ingest_from_eml_file(file_path, dry_run=False):
    """Ingest an assignment from a single .eml file."""
    config = load_config()
    api_key, api_token = get_credentials()
    tracker = StateTracker()

    print(f"Reading EML file: {file_path}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"EML file not found: {file_path}")

    parsed = parse_eml_file(file_path, config)

    if not parsed.get("is_actionable", True):
        print(f"\n[FILTER] Non-actionable notification type (Subject: '{parsed.get('subject')}'). Skipping card creation.")
        return {"status": "filtered", "reason": "non_actionable"}

    kid_target = parsed.get('kid') or 'Isaac'
    if parsed.get("is_discovery"):
        print(f"\n⚠️ [DISCOVERY ALERT] Unrecognized class detected: '{parsed.get('class_name') or 'Unknown'}'. Card will be created at TOP of {kid_target}'s list.")

    print(f"\nParsed Assignment:")
    print(f"  Kid:       {kid_target}")
    print(f"  Class:     {parsed.get('class') or parsed.get('class_name') or 'None'}")
    print(f"  Title:     {parsed.get('name') or parsed.get('formatted_title')}")
    print(f"  Due:       {parsed.get('due') or 'None'}")
    print(f"  Position:  {parsed.get('pos', 'bottom')}")
    print(f"  MsgId:     {parsed.get('message_id') or 'None'}")

    msg_id = parsed.get("message_id")
    if msg_id and tracker.is_processed(msg_id):
        print(f"\nNotice: Email with Message-ID {msg_id} was already processed previously.")

    print("\nFetching active Trello cards for duplicate check...")
    active_cards = fetch_active_cards(config, api_key, api_token)
    duplicate = find_duplicate_card(parsed, active_cards)

    if duplicate:
        print(f"\n[SKIP] Duplicate card found on Trello: '{duplicate['name']}' in {kid_target}'s list")
        return {"status": "skipped", "reason": "duplicate", "card": duplicate}

    if dry_run:
        print(f"\n[DRY RUN] Would create Trello card: '{parsed.get('name')}' in {kid_target}'s list (pos: {parsed.get('pos', 'bottom')})")
        return {"status": "dry-run", "card": parsed}

    created = create_trello_card(parsed, config, api_key, api_token, dry_run=False)
    print(f"\n[SUCCESS] Created Trello card: '{parsed.get('name')}' (ID: {created.get('id')})")

    if msg_id:
        tracker.mark_processed(msg_id, {
            "title": parsed.get("name") or parsed.get("formatted_title"),
            "kid": kid_target,
            "card_id": created.get("id")
        })

    # Update local workspace
    cards = fetch_active_cards(config, api_key, api_token)
    save_homework(cards)
    print(f"Updated {WORKSPACE_FILE} with latest board state.")

    return {"status": "created", "card": created}

def ingest_from_gmail(dry_run=False, label_filter=None):
    """Scan Gmail IMAP mailboxes for each boy's Classroom notifications and create Trello cards."""
    config = load_config()
    api_key, api_token = get_credentials()
    tracker = StateTracker()

    gmail_cfg = config.get("gmail", {})
    host = gmail_cfg.get("host", "imap.gmail.com")
    port = gmail_cfg.get("port", 993)
    processed_label = gmail_cfg.get("processed_label")
    mark_as_read = gmail_cfg.get("mark_as_read", True)

    profiles = config.get("profiles", {})

    mailboxes_to_scan = []
    if label_filter:
        mailboxes_to_scan.append({"folder": label_filter, "kid": None})
    else:
        for kid_name, profile in profiles.items():
            folder = profile.get("gmail_label")
            if folder:
                mailboxes_to_scan.append({"folder": folder, "kid": kid_name})

    if not mailboxes_to_scan:
        mailboxes_to_scan.append({"folder": "INBOX", "kid": None})

    print(f"Connecting to Gmail IMAP ({host}:{port})...")
    client = GmailIMAPClient(host=host, port=port)

    stats = {
        "scanned_folders": 0,
        "emails_found": 0,
        "created": 0,
        "discovery_alerts": 0,
        "skipped_filtered": 0,
        "skipped_duplicate": 0,
        "skipped_already_processed": 0,
        "failed": 0
    }

    with client:
        print("Connected and authenticated successfully.")
        print("Fetching active Trello cards for duplicate checking...")
        active_cards = fetch_active_cards(config, api_key, api_token)

        for item in mailboxes_to_scan:
            folder_name = item["folder"]
            mailbox_kid = item["kid"]
            print(f"\nChecking folder '{folder_name}' (Assigned Kid: {mailbox_kid or 'Auto-detect'})...")
            stats["scanned_folders"] += 1

            try:
                unseen = client.fetch_unseen_messages(folder_name)
            except Exception as e:
                print(f"  Error accessing folder '{folder_name}': {e}", file=sys.stderr)
                stats["failed"] += 1
                continue

            if not unseen:
                print("  No new unread messages.")
                continue

            print(f"  Found {len(unseen)} unread message(s).")
            stats["emails_found"] += len(unseen)

            for email_entry in unseen:
                uid = email_entry["uid"]
                msg = email_entry["msg"]
                parsed = parse_classroom_email(msg, config, mailbox_kid=mailbox_kid)

                msg_id = parsed.get("message_id")
                subject = parsed.get("subject") or ""
                kid_target = parsed.get("kid") or mailbox_kid or "Isaac"

                # 1. Check Action Filter (e.g. Announcements)
                if not parsed.get("is_actionable", True):
                    print(f"\n  [FILTER] Skipping non-actionable email: '{subject}'")
                    stats["skipped_filtered"] += 1
                    if msg_id and not dry_run:
                        tracker.mark_processed(msg_id, {"subject": subject, "status": "filtered_non_actionable"})
                    if not dry_run and mark_as_read:
                        client.mark_as_read(uid, folder_name)
                    continue

                # 2. Log Discovery Alert if applicable
                if parsed.get("is_discovery"):
                    print(f"\n  ⚠️ [DISCOVERY ALERT] Unrecognized class: '{parsed.get('class_name')}' for {kid_target}")
                    stats["discovery_alerts"] += 1

                title_to_create = parsed.get("name") or parsed.get("formatted_title")
                print(f"\n  Processing: '{subject}'")
                print(f"    Target:    {title_to_create} (Kid: {kid_target}, Class: {parsed.get('class') or 'None'})")
                print(f"    Due:       {parsed.get('due') or 'None'}")
                print(f"    Position:  {parsed.get('pos', 'bottom')}")

                # 3. Check State Tracker
                if msg_id and tracker.is_processed(msg_id):
                    print(f"    [SKIP] Message-ID already processed in state tracker.")
                    stats["skipped_already_processed"] += 1
                    if not dry_run and mark_as_read:
                        client.mark_as_read(uid, folder_name)
                    continue

                # 4. Check Trello Duplicates
                duplicate = find_duplicate_card(parsed, active_cards)
                if duplicate:
                    print(f"    [SKIP] Card already exists on Trello: '{duplicate['name']}'")
                    stats["skipped_duplicate"] += 1
                    if msg_id and not dry_run:
                        tracker.mark_processed(msg_id, {"title": title_to_create, "status": "duplicate_on_board"})
                    if not dry_run and mark_as_read:
                        client.mark_as_read(uid, folder_name)
                    continue

                # 5. Create Trello Card
                if dry_run:
                    print(f"    [DRY RUN] Would create card: '{title_to_create}' in {kid_target}'s list (pos: {parsed.get('pos', 'bottom')})")
                    stats["created"] += 1
                else:
                    try:
                        created = create_trello_card(parsed, config, api_key, api_token, dry_run=False)
                        print(f"    [SUCCESS] Created card '{title_to_create}' (ID: {created.get('id')})")
                        stats["created"] += 1

                        # Append to in-memory active_cards to prevent duplicate creation in same run
                        active_cards.setdefault(kid_target, []).append({
                            "id": created.get("id"),
                            "name": title_to_create,
                            "class": parsed.get("class"),
                            "due": parsed.get("due"),
                            "desc": parsed.get("desc", "")
                        })

                        if msg_id:
                            tracker.mark_processed(msg_id, {
                                "title": title_to_create,
                                "kid": kid_target,
                                "card_id": created.get("id"),
                                "is_discovery": parsed.get("is_discovery", False)
                            })

                        # Mark message processed on IMAP
                        client.move_or_label_processed(uid, folder_name, processed_folder=processed_label)

                    except Exception as e:
                        print(f"    [ERROR] Failed to create Trello card: {e}", file=sys.stderr)
                        stats["failed"] += 1

    print("\n================ Ingestion Summary ================")
    print(f"Folders Scanned:             {stats['scanned_folders']}")
    print(f"Emails Evaluated:            {stats['emails_found']}")
    if dry_run:
        print(f"Cards To Create (Dry Run):   {stats['created']}")
    else:
        print(f"Cards Created on Trello:     {stats['created']}")
    print(f"Discovery Alerts Triggered:  {stats['discovery_alerts']}")
    print(f"Filtered (Announcements):    {stats['skipped_filtered']}")
    print(f"Skipped (Board Duplicates):  {stats['skipped_duplicate']}")
    print(f"Skipped (Already Processed): {stats['skipped_already_processed']}")
    if stats["failed"] > 0:
        print(f"Errors / Failures:           {stats['failed']}")
    print("====================================================")

    if not dry_run and stats["created"] > 0:
        cards = fetch_active_cards(config, api_key, api_token)
        save_homework(cards)
        print(f"Updated {WORKSPACE_FILE} with latest cards.")
