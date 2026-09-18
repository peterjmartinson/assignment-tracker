# System Architecture & Design Specification

This document details the architectural design, Sunday batch workflows, and technical components of the **Assignment Tracker** ecosystem.

---

## 1. High-Level System Architecture

The Assignment Tracker bridges automated digital intake with a Sunday text-first editing loop and a morning physical printout:

```
 ┌────────────────────────────────────────────────────────┐
 │           1. Ingestion Layer (Basement Server)         │
 │  - Gmail IMAP Polling (Twice daily via Cron)           │
 │  - Action Allowlist Filter (Drops Announcements)       │
 │  - Class Keyword Sentinel Matching                     │
 │  - Direct Ingest into Kid Lists (Isaac / Asher)        │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │              2. State Hub (Trello Board)               │
 │  - Lists: Isaac | Asher                                │
 │  - Subject/Class Labels: Math, French, Physics, etc.   │
 │  - Automated ISO-8601 / Date-stamped Due Dates         │
 └─────────────┬────────────────────────────┬─────────────┘
               │                            │
  (Read via REST API)                 (CLI Pull / Push)
               ▼                            ▼
 ┌───────────────────────────┐   ┌────────────────────────┐
 │ 3. Random Task API        │   │ 5. Sunday Edit Loop    │
 │  - Fetches Kid Lists      │   │  - workspace/          │
 │  - Evaluates Due Horizon  │   │    homework.yaml       │
 │  - Partitions Agenda      │   │  - Wipe done / add new │
 └─────────────┬─────────────┘   └────────────────────────┘
               │
               ▼
 ┌───────────────────────────┐
 │ 4. Screamsheet Printout   │
 │  - Morning Printed Paper  │
 │  - Past Due & Today Focus │
 │  - Upcoming Due Radar     │
 └───────────────────────────┘
```

---

## 2. The Two-List Model & Class Labels

Instead of a multi-column digital Kanban that requires daily card-moving, the board uses a lean **two-list structure**:

### Board Structure:
1. **`Isaac` (List):** All active assignments for Isaac.
2. **`Asher` (List):** All active assignments for Asher.
3. **Class Labels:** Trello labels represent subjects/classes (`Math`, `French`, `Physics`, `Art History`, `Reading`, `Latin`).
4. **Due Dates:** The primary attribute used downstream to bucket items into Past Due, Today, and Upcoming.

---

## 3. Sunday Batch Loop (`workspace/homework.yaml`)

* **Pull (`python main.py pull`):** Downloads active cards from Trello, backs up the previous file to `workspace/backups/`, and generates clean, human-readable YAML.
* **Edit:** Batch-edit in your code editor. Delete finished items, add new items without an `id:`, and adjust due dates.
* **Validate (`python main.py validate`):** Validates YAML syntax, required fields, and date formats.
* **Push (`python main.py push`):** Syncs changes to Trello, creates new cards with labels, updates modified cards, and automatically archives cards removed from YAML.

---

## 4. Screamsheet Morning Radar Integration

The downstream **Random Task API** (running on Vercel) aggregates tasks for the morning **Screamsheet** printout:

1. **Past Due / Due Today:** Primary focus section on the morning paper.
2. **Due Soon Radar:** Scans tasks due within 3 days.
3. **Sections:** Partitioned by Kid (`Isaac` and `Asher`) or due horizon.
