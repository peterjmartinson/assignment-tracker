# Trello Homework Tracker

A lightweight, "infrastructure-as-text" pipeline for managing Trello cards in bulk. This tool allows you to pull a Trello board down to a clean YAML file, make bulk edits (or create new cards) using your text editor, and push the state back to Trello.

Built to quickly ingest and organize weekly homework assignments without having to click through the Trello UI.

## Prerequisites

- Python 3.x
- A Trello account and [Developer API Keys](https://trello.com/app-key)

## Installation & Setup

1. **Clone and install dependencies:**
   ```bash
   pip install requests pyyaml python-dotenv
   ```

2. **Configure Secrets:**
   Create a `.env` file in the root directory (this file is git-ignored) and add your Trello credentials:
   ```env
   TRELLO_API_KEY="your_api_key_here"
   TRELLO_API_TOKEN="your_api_token_here"
   ```

3. **Configure Board Architecture:**
   Update `config.yaml` with your specific Trello IDs. 
   *(Tip: You can find your Board and List IDs by adding `.json` to the end of your Trello board URL and searching the raw output.)*
   ```yaml
   board_id: "YOUR_BOARD_ID"

   lists:
     "To Do": "64abcdef1234567890abcdef"
     "In Progress": "64bbcdef1234567890abcdef"
     "Done": "64cbcdef1234567890abcdef"
   ```

## The Workflow

The pipeline operates in a simple Pull -> Edit -> Push loop.

### 1. Pull Current State
Run the pull command to grab all active cards from the board and write them to `homework.yaml`.
```bash
python main.py pull
```

### 2. Edit the YAML
Open `homework.yaml` in your editor of choice. 

* **To update an existing card:** Modify properties like `list`, `due`, or `cover` (e.g., `blue` or `green`). Leave the `id` field intact so the script knows which card to update.
* **To create a new card:** Copy an existing YAML block, **delete the `id` field**, and fill in the new assignment details. 

```yaml
# Example of an existing card (will trigger a PUT request)
- id: 65d1234567890abcdef12345
  name: Math Worksheet Page 42
  kid: Isaac
  list: To Do
  due: '2026-07-15T12:00:00.000Z'
  cover: blue
  desc: Fractions review

# Example of a new card (will trigger a POST request)
- name: Read Chapter 4
  kid: Asher
  list: To Do
  due: null
  cover: green
  desc: ''
```

### 3. Push Changes
Preview your changes first using `--dry-run`:
```bash
python main.py push --dry-run
```

Sync your local YAML state back to Trello:
```bash
python main.py push
```
