# Trello Homework Tracker

A lightweight, high-speed CLI sync engine for managing weekly homework on Trello via text. This tool pulls active Trello cards into a clean, human-editable YAML file (`workspace/homework.yaml`), lets you make bulk edits or add/delete cards using your code editor, validates the changes, and pushes state back to Trello with automatic deletion archiving.

---

## 🎯 Architecture: The Two-List Model

Rather than shuffling cards between Kanban columns (`To Do`, `Doing`, `Done`, `Backlog`), the board uses a streamlined **two-list structure**:

* **`Isaac` (List):** All active assignments for Isaac.
* **`Asher` (List):** All active assignments for Asher.
* **Labels = Classes/Subjects:** (`Math`, `French`, `Physics`, `Art History`, `Latin`, `Reading`).
* **Due Date:** Temporal anchor consumed downstream by the Screamsheet morning printout (`random-task`).

---

## 🚀 Weekly Workflow (Sunday Routine)

### 1. Pull Current State
Pulls active cards from Trello into `workspace/homework.yaml` (and creates an automated snapshot in `workspace/backups/`):
```bash
python main.py pull
```

### 2. Batch Edit in YAML
Open `workspace/homework.yaml` in your editor.

* **Wipe finished work:** Simply delete the YAML block for that card.
* **Update existing cards:** Modify properties like `due`, `desc`, or `name`. Keep the `id:` field intact.
* **Add new cards:** Add a new item without an `id:` field:

```yaml
Isaac:
  - id: "6a962de81b0e70e0bfa214af" # Existing card (persists across runs)
    class: French
    name: "Test - Histoire d'une Revanche"
    due: 2026-09-22
    desc: "Class: French Fifth Grade 5th"

  - class: Math                    # New card (no id needed!)
    name: "BAO Ch 5 Linear Equations"
    due: 2026-09-24

Asher:
  - id: "6a962dead3e82215b54adb2a"
    class: Art History
    name: "Homework for May 27th"
    due: 2026-05-27
```

### 3. Validate Local File
Verify YAML syntax, date formatting (`YYYY-MM-DD`), and structure:
```bash
python main.py validate
```

### 4. Push to Trello (with Auto-Archive)
Preview changes without modifying Trello:
```bash
python main.py push --dry-run
```

Apply changes:
```bash
python main.py push
```

* **Creates** new cards on Trello and attaches the appropriate class label.
* **Updates** modified cards.
* **Archives** cards on Trello that were removed from the local YAML.
* **Backfills** generated Trello IDs into `workspace/homework.yaml`.

---

## 📩 Automated Google Classroom Email Ingestion

The tracker polls Gmail IMAP (or ingests `.eml` files), parses Google Classroom notifications, and automatically creates Trello cards in the appropriate kid's list (`Isaac` or `Asher`) tagged with the subject label.

* **Preview Ingestion (Dry Run):**
  ```bash
  python main.py ingest-email --dry-run
  ```
* **Test Single EML File:**
  ```bash
  python main.py ingest-email --file "path/to/assignment.eml" --dry-run
  ```
* **Run Live Ingestion:**
  ```bash
  python main.py ingest-email
  ```
