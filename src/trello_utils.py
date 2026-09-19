import os
import shutil
from datetime import datetime
import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

WORKSPACE_DIR = os.path.join(os.getcwd(), 'workspace')
WORKSPACE_FILE = os.path.join(WORKSPACE_DIR, 'homework.yaml')
BACKUP_DIR = os.path.join(WORKSPACE_DIR, 'backups')

def ensure_workspace():
    """Ensure workspace and backup directories exist."""
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

def backup_workspace():
    """Create a timestamped backup of the current workspace file if it exists."""
    ensure_workspace()
    if os.path.exists(WORKSPACE_FILE):
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_path = os.path.join(BACKUP_DIR, f"homework-{timestamp}.yaml")
        shutil.copy2(WORKSPACE_FILE, backup_path)
        return backup_path
    return None

def load_config(config_path='config.yaml'):
    """Load configuration from config.yaml."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_credentials():
    """Load and validate Trello credentials from environment."""
    api_key = os.getenv("TRELLO_API_KEY")
    api_token = os.getenv("TRELLO_API_TOKEN")
    if not api_key or not api_token:
        raise ValueError("Missing Trello credentials. Check your .env file.")
    return api_key, api_token

def load_homework(filepath=WORKSPACE_FILE):
    """Load structured homework cards from workspace YAML."""
    if not os.path.exists(filepath):
        # Fallback to root homework.yaml if workspace doesn't exist yet
        root_path = os.path.join(os.getcwd(), 'homework.yaml')
        if os.path.exists(root_path):
            with open(root_path, 'r', encoding='utf-8') as f:
                raw = yaml.safe_load(f)
                if isinstance(raw, dict):
                    return raw
                elif isinstance(raw, list):
                    # Convert legacy flat list to dict
                    converted = {}
                    for c in raw:
                        kid = c.get('kid') or 'Isaac'
                        converted.setdefault(kid, []).append(c)
                    return converted
        return {}

    with open(filepath, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
        if isinstance(data, list):
            converted = {}
            for c in data:
                kid = c.get('kid') or 'Isaac'
                converted.setdefault(kid, []).append(c)
            return converted
        return data

def save_homework(cards_by_kid, filepath=WORKSPACE_FILE):
    """Save structured homework cards to YAML file."""
    ensure_workspace()
    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(cards_by_kid, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

def fetch_board_labels(board_id, api_key, api_token):
    """Fetch board labels and return mappings {name_lower: label_id} and {label_id: name}."""
    url = f"https://api.trello.com/1/boards/{board_id}/labels"
    response = requests.get(url, params={'key': api_key, 'token': api_token}, timeout=10)
    response.raise_for_status()
    labels = response.json()

    name_to_id = {}
    id_to_name = {}
    for l in labels:
        name = l.get('name') or ''
        lid = l.get('id')
        if lid:
            id_to_name[lid] = name
            if name:
                name_to_id[name.lower()] = lid
    return name_to_id, id_to_name

def fetch_board_lists(board_id, api_key, api_token):
    """Fetch board lists and return {list_id: name} and {name_lower: list_id}."""
    url = f"https://api.trello.com/1/boards/{board_id}/lists"
    response = requests.get(url, params={'key': api_key, 'token': api_token, 'filter': 'open'}, timeout=10)
    response.raise_for_status()
    lists = response.json()

    id_to_name = {}
    name_to_id = {}
    for lst in lists:
        lid = lst.get('id')
        name = lst.get('name') or ''
        if lid:
            id_to_name[lid] = name
            name_to_id[name.lower()] = lid
    return id_to_name, name_to_id

def normalize_date_for_yaml(iso_date):
    """Convert ISO date string into clean YYYY-MM-DD or readable string for YAML."""
    if not iso_date:
        return None
    s = str(iso_date).strip()
    if 'T' in s:
        date_part, time_part = s.split('T', 1)
        # If time is 00:00:00 or 23:59:00, omit the time in YAML for cleanliness
        clean_time = time_part.replace('Z', '').split('.')[0]
        if clean_time in ('00:00:00', '23:59:00', '23:59:59'):
            return date_part
        return f"{date_part} {clean_time[:5]}"
    return s

def normalize_date_for_trello(d):
    """Convert user entered date into Trello ISO string."""
    if not d:
        return None
    s = str(d).strip()
    if not s or s.lower() == 'null' or s.lower() == 'none':
        return None
    # If standard YYYY-MM-DD
    if len(s) == 10 and s.count('-') == 2:
        return f"{s}T23:59:00.000Z"
    if ' ' in s and len(s) <= 16:
        # e.g. "2026-09-22 17:00"
        parts = s.split(' ')
        return f"{parts[0]}T{parts[1]}:00.000Z"
    if 'T' in s and not s.endswith('Z'):
        return f"{s}.000Z" if '.' not in s else f"{s}Z"
    return s

def fetch_active_cards(config, api_key, api_token):
    """
    Fetch all active cards from configured kid lists on Trello and group by kid.
    Returns dict { 'Isaac': [...], 'Asher': [...] }
    """
    board_id = config['board_id']
    configured_lists = config.get('lists', {})

    # Map list ID to kid name
    list_id_to_kid = {}
    for kid_name, list_id in configured_lists.items():
        list_id_to_kid[list_id] = kid_name

    _, id_to_label_name = fetch_board_labels(board_id, api_key, api_token)

    url = f"https://api.trello.com/1/boards/{board_id}/cards"
    response = requests.get(url, params={'key': api_key, 'token': api_token, 'filter': 'open'}, timeout=10)
    response.raise_for_status()
    raw_cards = response.json()

    result = {}
    for kid in configured_lists.keys():
        result[kid] = []

    for card in raw_cards:
        list_id = card.get('idList')
        kid = list_id_to_kid.get(list_id)
        if not kid:
            continue

        # Extract subject / class label
        card_class = None
        for label_id in card.get('idLabels', []):
            if label_id in id_to_label_name and id_to_label_name[label_id]:
                card_class = id_to_label_name[label_id]
                break

        # Fallback: check card labels objects directly
        if not card_class and card.get('labels'):
            for l in card['labels']:
                if l.get('name'):
                    card_class = l['name']
                    break

        card_entry = {
            'id': card['id'],
            'name': card['name'],
            'class': card_class,
            'due': normalize_date_for_yaml(card.get('due')),
            'desc': card.get('desc') or ''
        }

        result[kid].append(card_entry)

    return result

def validate_homework(data, config):
    """Validate YAML homework structure and types."""
    errors = []
    if not isinstance(data, dict):
        return False, ["Homework data must be a dictionary grouped by kid (e.g. Isaac:, Asher:)."]

    configured_kids = set(config.get('lists', {}).keys())

    for kid, cards in data.items():
        if kid not in configured_kids:
            errors.append(f"Unknown kid '{kid}'. Configured kids: {list(configured_kids)}")
        if not isinstance(cards, list):
            errors.append(f"Tasks for '{kid}' must be a list of cards.")
            continue

        for idx, card in enumerate(cards):
            if not isinstance(card, dict):
                errors.append(f"Card #{idx + 1} under '{kid}' is not a valid map/object.")
                continue
            if not card.get('name'):
                errors.append(f"Card #{idx + 1} under '{kid}' is missing a required 'name' field.")

            # Validate date format if present
            due = card.get('due')
            if due:
                due_str = str(due).strip()
                if due_str and due_str.lower() not in ('none', 'null'):
                    try:
                        # Check basic format
                        if len(due_str) >= 10 and '-' in due_str:
                            pass
                        else:
                            errors.append(f"Invalid due date format '{due}' on card '{card.get('name')}'. Use YYYY-MM-DD.")
                    except Exception:
                        errors.append(f"Invalid due date format '{due}' on card '{card.get('name')}'.")

    return len(errors) == 0, errors

def create_trello_card(card_data, config, api_key, api_token, dry_run=False):
    """Create a new card on Trello in the kid's list with the appropriate class label."""
    board_id = config['board_id']
    kid_name = card_data.get('kid') or 'Isaac'
    configured_lists = config.get('lists', {})
    list_id = configured_lists.get(kid_name)

    if not list_id:
        # Fallback to first configured list
        list_id = list(configured_lists.values())[0]

    name_to_label_id, _ = fetch_board_labels(board_id, api_key, api_token)
    
    title = card_data.get('name') or card_data.get('formatted_title') or 'Untitled Assignment'
    class_name = card_data.get('class') or card_data.get('class_name')

    label_ids = []
    if class_name and class_name.lower() in name_to_label_id:
        label_ids.append(name_to_label_id[class_name.lower()])

    due_trello = normalize_date_for_trello(card_data.get('due'))

    payload = {
        'name': title,
        'idList': list_id,
        'desc': card_data.get('desc', ''),
        'due': due_trello or '',
        'idLabels': label_ids,
        'pos': card_data.get('pos', 'bottom')
    }

    if dry_run:
        return {'id': 'dry-run-id', 'name': title, 'status': 'dry-run'}

    url = "https://api.trello.com/1/cards"
    params = {'key': api_key, 'token': api_token}
    res = requests.post(url, params=params, json=payload, timeout=10)
    res.raise_for_status()
    return res.json()

def find_duplicate_card(parsed_item, active_cards_by_kid):
    """Check if a parsed assignment already exists in active Trello cards."""
    target_title = (parsed_item.get("formatted_title") or parsed_item.get("name") or "").strip().lower()
    raw_title = (parsed_item.get("raw_title") or "").strip().lower()
    kid = parsed_item.get("kid") or 'Isaac'

    cards = active_cards_by_kid.get(kid, [])
    for card in cards:
        card_name = (card.get("name") or "").strip().lower()
        if card_name == target_title:
            return card
        if raw_title and (raw_title in card_name or card_name in raw_title):
            return card

    return None
