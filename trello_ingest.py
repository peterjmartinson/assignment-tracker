import json
import os
import requests
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("TRELLO_API_KEY")
TOKEN = os.getenv("TRELLO_API_TOKEN")
LIST_ID = os.getenv("TRELLO_LIST_ID", "")

filename = "asher_homework.json"

# 1. Fetch board labels to get the exact ID for the 'blue' label
if not API_KEY or not TOKEN or not LIST_ID:
    print("Please ensure TRELLO_API_KEY, TRELLO_API_TOKEN, and TRELLO_LIST_ID are set in .env")
    exit(1)

list_url = f"https://api.trello.com/1/lists/{LIST_ID}"
board_id = requests.get(list_url, params={"key": API_KEY, "token": TOKEN}).json()["idBoard"]

labels_url = f"https://api.trello.com/1/boards/{board_id}/labels"
labels_data = requests.get(labels_url, params={"key": API_KEY, "token": TOKEN}).json()

# Map color strings to their Trello IDs
label_map = {label["color"]: label["id"] for label in labels_data if label["color"]}

# 2. Load and POST the cards
with open(filename, "r") as f:
    cards = json.load(f)

for card in cards:
    payload = {
        "key": API_KEY,
        "token": TOKEN,
        "idList": LIST_ID,
        "name": card["name"],
        "desc": card["desc"],
        "idLabels": [label_map.get(card["color"])] if label_map.get(card["color"]) else []
    }
    
    response = requests.post("https://api.trello.com/1/cards", json=payload)
    if response.status_code == 200:
        print(f"Created: {card['name']}")
    else:
        print(f"Failed to create: {card['name']} - {response.text}")
