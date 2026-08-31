import os
import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

def load_config():
    """Load configuration from config.yaml."""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def load_homework(filepath='homework.yaml'):
    """Load homework cards from a YAML file."""
    with open(filepath, 'r') as f:
        return yaml.safe_load(f) or []

def save_homework(cards, filepath='homework.yaml'):
    """Save homework cards to a YAML file."""
    with open(filepath, 'w') as f:
        yaml.dump(cards, f, default_flow_style=False, sort_keys=False)

def get_credentials():
    """Load and validate Trello credentials from environment."""
    api_key = os.getenv("TRELLO_API_KEY")
    api_token = os.getenv("TRELLO_API_TOKEN")
    if not api_key or not api_token:
        raise ValueError("Missing Trello credentials. Check your .env file.")
    return api_key, api_token

def fetch_active_cards(config, api_key, api_token):
    """Fetch all active cards from the Trello board and parse them into standard format."""
    url = f"https://api.trello.com/1/boards/{config['board_id']}/cards"
    response = requests.get(url, params={'key': api_key, 'token': api_token})
    response.raise_for_status()
    raw_cards = response.json()

    list_id_to_name = {v: k for k, v in config['lists'].items()}
    
    label_id_to_kid = {}
    if 'profiles' in config:
        for kid, data in config['profiles'].items():
            label_id_to_kid[data['label_id']] = kid

    clean_cards = []
    for card in raw_cards:
        # Ignore cards from lists not configured in config.yaml (e.g., admin or ID lists)
        if card['idList'] not in list_id_to_name:
            continue

        # Determine kid profile assignment based on Trello label ID
        assigned_kid = None
        for label_id in card.get('idLabels', []):
            if label_id in label_id_to_kid:
                assigned_kid = label_id_to_kid[label_id]
                break

        clean_cards.append({
            'id': card['id'],
            'name': card['name'],
            'kid': assigned_kid,
            'list': list_id_to_name[card['idList']],
            'due': card.get('due'),
            'cover': card.get('cover', {}).get('color') if isinstance(card.get('cover'), dict) else None,
            'desc': card.get('desc') or ''
        })
    return clean_cards

def normalize_date(d):
    """Normalize Trello ISO-8601 dates and YAML dates/datetimes to a comparable string format."""
    if not d:
        return None
    # Strip milliseconds and Z/offsets for direct character comparison
    # e.g., "2026-07-15T12:00:00.000Z" -> "2026-07-15T12:00:00"
    s = str(d).strip()
    if '.' in s:
        s = s.split('.')[0]
    return s.replace('Z', '').replace('+00:00', '')

def card_needs_update(local_card, trello_card, config):
    """Compare a local card with its counterpart fetched from Trello to check for modifications."""
    if (local_card.get('name') or '') != (trello_card.get('name') or ''):
        return True
    
    if (local_card.get('list') or '') != (trello_card.get('list') or ''):
        return True
        
    if (local_card.get('desc') or '') != (trello_card.get('desc') or ''):
        return True
        
    # Check normalized due date
    local_due = normalize_date(local_card.get('due'))
    trello_due = normalize_date(trello_card.get('due'))
    if local_due != trello_due:
        return True

    # Check kid profile assignment
    local_kid = local_card.get('kid') or None
    trello_kid = trello_card.get('kid') or None
    if local_kid != trello_kid:
        return True
        
    # If no kid profile is assigned, check if the manual cover color is different
    if not local_kid:
        local_cover = local_card.get('cover') or None
        trello_cover = trello_card.get('cover') or None
        if local_cover != trello_cover:
            return True

    return False

def create_trello_card(card_data, config, api_key, api_token, dry_run=False):
    """Create a new card on Trello in the configured ingest list (default: Backlog)."""
    target_list_name = config.get("ingest_list", "Backlog")
    list_id = config.get("lists", {}).get(target_list_name)
    if not list_id:
        list_id = list(config.get("lists", {}).values())[0]

    title = card_data.get("formatted_title") or card_data.get("name")
    payload = {
        "key": api_key,
        "token": api_token,
        "name": title,
        "idList": list_id,
        "desc": card_data.get("desc", ""),
        "due": card_data.get("due") or ""
    }

    kid_name = card_data.get("kid")
    if kid_name and kid_name in config.get("profiles", {}):
        profile = config["profiles"][kid_name]
        payload["idLabels"] = [profile["label_id"]]
        payload["cover"] = {"color": profile["cover_color"], "size": "normal"}

    if dry_run:
        return {"id": "dry-run-preview-id", "name": title, "status": "dry-run"}

    url = "https://api.trello.com/1/cards"
    res = requests.post(url, json=payload)
    res.raise_for_status()
    return res.json()

def find_duplicate_card(parsed_item, active_cards):
    """Check if a parsed assignment already exists on Trello board."""
    target_title = (parsed_item.get("formatted_title") or "").strip().lower()
    raw_title = (parsed_item.get("raw_title") or "").strip().lower()
    target_kid = parsed_item.get("kid")

    for card in active_cards:
        card_name = (card.get("name") or "").strip().lower()
        card_kid = card.get("kid")

        # Match by kid (if known) and title
        if target_kid and card_kid and target_kid.lower() != card_kid.lower():
            continue

        if card_name == target_title:
            return card
        if raw_title and (raw_title in card_name or card_name in raw_title):
            return card

    return None
