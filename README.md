# 📚 Homework Tracker: Weekly Sunday Routine

A simple text-first system for managing your boys' weekly homework on Trello without touching the Trello UI.

---

## ⚡ The Quick Sunday Routine (TL;DR)

1. **Pull the latest cards from Trello down to your machine:**
   ```bash
   uv run pull
   ```
2. **Open `workspace/homework.yaml` in your editor and edit it:**
   * **Finished an assignment?** Just highlight the lines and **delete** them.
   * **Adding a new assignment?** Type a new block **without** an `id:` line.
   * **Adjusting a date or note?** Edit `due:` or `desc:`.
3. **Validate & Preview your changes (optional but recommended):**
   ```bash
   uv run push --dry-run
   ```
4. **Push your changes back up to Trello:**
   ```bash
   uv run push
   ```
   *(This creates new cards on Trello, updates modified ones, and **automatically archives** anything you deleted from the YAML).*

---

## 📝 How to Edit `workspace/homework.yaml`

The file is grouped into two simple sections: **`Isaac`** and **`Asher`**.

```yaml
Isaac:
  # ── 1. PERSISTENT / EXISTING CARDS (Have an 'id:') ────────────────────────
  # Leave the 'id:' alone. You can change the date, description, or title.
  - id: "6a962de81b0e70e0bfa214af"
    class: French
    name: "Test - Histoire d'une Revanche"
    due: 2026-09-22
    desc: "Review vocabulary chapters 1-3"

  # ── 2. NEW ASSIGNMENTS (No 'id:' line) ───────────────────────────────────
  # Just type class, name, and due date. The push command will create the card
  # on Trello and auto-fill the 'id:' line for you.
  - class: Math
    name: "Alcumus: Linear Equations"
    due: 2026-09-24

  - class: Science
    name: "Pendulum Lab Writeup"
    due: 2026-09-25
    desc: "Include graph of period vs length"

Asher:
  - id: "6a962dead3e82215b54adb2a"
    class: Art History
    name: "Ancient Egypt Project"
    due: 2026-09-23

  - class: Reading
    name: "Read Chapter 4 out loud"
    due: 2026-09-21
```

---

## 🏷️ Available Class Labels
When adding `class: <Name>`, use any of the standard names below (case-insensitive, script matches them automatically):

* `Art`
* `Art History`
* `Debate`
* `English Language`
* `English Literature`
* `French`
* `Geography`
* `Good Life`
* `Hands On Skills`
* `Hebrew`
* `History`
* `Latin`
* `Math`
* `Math Competition`
* `Music Theory`
* `Robotics`
* `Science`

---

## 📅 Due Date Formats
* **Specific date:** `2026-09-23` (defaults to end-of-day on Trello)
* **Date with time:** `2026-09-23 17:00`
* **No specific date:** `due: null` or just omit the line

---

## 🗑️ How Deleting / Wiping Works
* When you delete an assignment from `workspace/homework.yaml` and run `python main.py push`, the script notices it's gone and **archives the card on Trello**.
* You don't have to manually swipe or clean up Trello during the week.

---

## 🛡️ "Oops, I Broke Something" (Safety & Backups)
* **Pre-push preview:** Run `python main.py push --dry-run` to see a clean summary of what will be created, updated, and archived before touching Trello.
* **Automatic Backups:** Every time you run `python main.py pull`, a timestamped snapshot of your previous `homework.yaml` is automatically saved in `workspace/backups/`. If you ever accidentally delete something, check that folder.

---

## ⚙️ One-Time Setup (`config.yaml`)
Make sure your two list IDs are defined in `config.yaml`:
```yaml
board_id: "6a0dd7e64e205c4e01db1b21"

lists:
  Isaac: "YOUR_ISAAC_LIST_ID"
  Asher: "YOUR_ASHER_LIST_ID"
```

---

## 🖨️ Weekly Fridge Printout

Generate a clear, large-print, single-page landscape PDF for the fridge with a single command. It follows a two-stage process: pulling cards from Trello, saving a clean hierarchy to Markdown, and rendering a spartan, black-and-white, right-angled PDF.

```bash
# Default: pulls fresh cards from Trello and generates upcoming Monday-to-Friday week
uv run printout

# Did one of the boys eat the copy on the fridge? Re-print the current week:
uv run printout --this-week

# Generate and immediately pop open the PDF in your default viewer:
uv run printout --open

# Generate from your local workspace/homework.yaml without pulling from Trello:
uv run printout --no-pull
```

### Hierarchy & Design Details:
1. **Hierarchy:** `Day of Week (Mon-Fri)` ➔ `Boy` ➔ `Subject (Trello label)` ➔ `[ ] Title` (indented description below).
2. **Design:** Spartan, completely black-and-white, sharp right-angled corners, spelled-out month names (`September 28 – October 2, 2026`), and square checkboxes.
3. **Markdown Stage:** [`workspace/homework_week.md`](workspace/homework_week.md)
4. **Print-Ready PDF:** [`workspace/homework_week.pdf`](workspace/homework_week.pdf) (fits 1 landscape page, large bold fonts, checkboxes ready for pen/pencil checkoffs).
