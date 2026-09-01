# System Architecture & Design Specification

This document details the architectural design, daily workflows, and technical components of the **Assignment Tracker** ecosystem.

---

## 1. High-Level System Architecture

The Assignment Tracker bridges automated digital intake with a high-visibility physical morning routine:

```
 ┌────────────────────────────────────────────────────────┐
 │           1. Ingestion Layer (Basement Server)         │
 │  - Gmail IMAP Polling (Twice daily via Cron)           │
 │  - Action Allowlist Filter (Drops Announcements)       │
 │  - Class Keyword Sentinel Matching                     │
 │  - Discovery Alert System (New Classes to Top of Board)│
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │              2. State Hub (Trello Board)               │
 │  - Lists: Backlog (Radar Inbox) | To Do (Focus) | Done │
 │  - Kid Labels & Visual Cover Colors (Isaac/Asher)      │
 │  - Automated ISO-8601 Due Dates                        │
 └─────────────┬────────────────────────────┬─────────────┘
               │                            │
  (Read via REST API)                 (Mobile Swipe: 1s)
               ▼                            ▼
 ┌───────────────────────────┐   ┌────────────────────────┐
 │ 3. Random Task API (Vercel│   │ 5. Physical Wall Board │
 │  - Gathers Calendar Tasks │   │  - Tactile Post-its:   │
 │  - Evaluates Due Radar    │   │    Blue (Isaac)        │
 │  - Generates Daily Agenda │   │    Green (Asher)       │
 └─────────────┬─────────────┘   └──────────▲─────────────┘
               │                            │
               ▼                            │ (Transcribe)
 ┌───────────────────────────┐              │
 │ 4. Screamsheet Printout   │──────────────┘
 │  - Morning Printed Paper  │
 │  - Daily Priority Section │
 │  - "Due Soon" Alert Radar │
 └───────────────────────────┘
```

---

## 2. The "Focus + Safety Net Radar" Trello Model

Instead of a complex 4-column digital Kanban that duplicates physical Post-it tracking, the board uses a lean **3-list structure**:

### Board Lists:
1. **`Backlog` (The Automated Radar Inbox):**
   * Every incoming school assignment from Gmail is automatically created here with its due date, kid label, and cover color.
   * Unmatched classes land here at the **top** of the list with a `[DISCOVERY ALERT]` tag.
2. **`To Do` (Curated Focus):**
   * You manually move 3–5 top-priority assignments here for the week/day.
   * This list directly mirrors the physical Post-it notes on the wall.
3. **`Done` (Completed):**
   * When an assignment is finished, swipe the card here (1 second on mobile).
   * Once in `Done`, it is permanently filtered out from morning Screamsheet printouts.

---

## 3. Screamsheet Morning Radar Integration

The downstream **Random Task API** (running on Vercel) aggregates tasks for the morning **Screamsheet** printout using two complementary rules:

1. **Curated Focus Tasks:**
   * Prints all cards currently residing in the **`To Do`** list (matching your physical wall).
2. **Automated "Due Soon" Safety Net:**
   * Scans cards in **`Backlog`** with upcoming due dates ($\le 3$ days) or past-due dates.
   * Promotes them to an **"⚠️ Due Soon / Alert"** section on the morning paper.
   * **Result:** You never miss a surprise Friday assignment from a teacher even if you didn't manually triage `Backlog`.

---

## 4. Inclusion-First (Allowlist) Filtering & Discovery Mode

To protect the board from chatter, newsletters, and grading notices, the ingestion pipeline enforces a 3-stage inclusion filter:

```
 Incoming Forwarded Email
           │
           ▼
 ┌────────────────────────────────────────┐
 │  Stage 1: Action Type Allowlist        │  Only allow: "New assignment", "Due tomorrow",
 │  (Drops announcements & chatter)       │  "Due soon", "New question"
 └───────────────────┬────────────────────┘
                     │  Pass
                     ▼
 ┌────────────────────────────────────────┐
 │  Stage 2: Class Keyword Sentinels      │  Per kid in config.yaml:
 │  (Matches enrolled subject keywords)   │  Isaac: [Math, French, Art History, Eng Lit]
 └───────────────────┬────────────────────┘  Asher: [Math, Art History, Reading]
                     │
         ┌───────────┴───────────┐
         │ Match?                │
    YES  ▼                  NO   ▼
 ┌──────────────────────┐  ┌───────────────────────────────────┐
 │ Format Clean Title:  │  │ Discovery Alert Card:             │
 │ e.g. [Art History]   │  │ '[DISCOVERY ALERT] Class - Title' │
 │ Placed in Backlog    │  │ Created at TOP of Backlog         │
 └──────────────────────┘  └───────────────────────────────────┘
```

### Discovery Mode Details:
* When a teacher introduces a brand new subject (e.g. *Latin* or *Science Lab*) that is not yet configured with keyword sentinels in `config.yaml`:
  * The system **still creates the card** so it is never lost.
  * It tags the card with **`[DISCOVERY ALERT]`** and sets `pos="top"` to pin it to the top of the Trello Backlog.
  * You see the alert on Trello, add the sentinel keyword to `config.yaml`, and future assignments format cleanly.

---

## 5. Summary of Daily Roles

* **Basement Server:** Automatically ingests emails, filters noise, checks duplicates, and keeps Trello Backlog populated.
* **Vercel (`random-task`):** Pulls from Trello (`To Do` + `Backlog` Due Soon radar) and delivers your morning agenda to Screamsheet.
* **Parent:** 
  * Morning: Compare Screamsheet with physical wall Post-it notes.
  * Evening: Swipe completed cards to `Done` on Trello mobile app (1 swipe).
