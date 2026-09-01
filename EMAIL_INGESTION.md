# Google Classroom Email Ingestion Guide

This guide walks you through setting up automated ingestion of Google Classroom notification emails into your Trello board.

---

## 🏗️ How It Works

1. Your boys' school accounts forward Google Classroom notification emails to your personal Gmail.
2. Gmail filters automatically apply labels (`Classroom/Isaac` and `Classroom/Asher`).
3. The server runs `python main.py ingest-email` on a schedule (e.g. twice a day via cron).
4. The script connects securely to Gmail via IMAP:
   - Identifies which kid the assignment belongs to.
   - Extracts the class name, assignment title, due date, description, and Classroom link.
   - Formats the card title using configured class rules (e.g. `[Art History] Homework for May 27th, 2026`).
   - Checks Trello to prevent duplicate cards.
   - Creates the card in your **Backlog** list on Trello with the proper kid label ID, cover color, and due date.
   - Marks the email as read and records the `Message-ID` in a local state cache.

---

## 🛠️ Step-by-Step Setup Instructions

### 1. Generate a Gmail App Password
Because modern Google accounts require 2-Step Verification, you will need a 16-character App Password for IMAP:

1. Go to your [Google Account Security Settings](https://myaccount.google.com/security).
2. Under **"How you sign in to Google"**, click on **"2-Step Verification"**.
3. Scroll to the bottom and click on **"App passwords"**.
4. Enter an app name (e.g., `Assignment Tracker`) and click **Create**.
5. Copy the generated 16-character password (e.g., `abcd efgh ijkl mnop`).

---

### 2. Configure Your `.env` Secrets
Open or create the `.env` file in the root directory and add your credentials:

```env
# Trello Secrets
TRELLO_API_KEY="your_trello_api_key"
TRELLO_API_TOKEN="your_trello_api_token"

# Gmail IMAP Secrets
GMAIL_USER="your.personal.email@gmail.com"
GMAIL_APP_PASSWORD="abcd efgh ijkl mnop"
```

---

### 3. Set Up Gmail Labels and Filters
In your personal Gmail web interface:

1. **Create Labels:**
   - Create parent label: `Classroom`
   - Create nested labels: `Classroom/Isaac` and `Classroom/Asher`

2. **Create Filter for Isaac:**
   - In Gmail search bar, click the filter settings icon.
   - In the **To** field (or **Includes the words**): `isaac.martinson@mainlineclassical.org` (or whatever address the email was originally sent to).
   - Click **Create filter**.
   - Check **Apply the label:** choose `Classroom/Isaac`.
   - Optional: Check **Never send it to Spam**.

3. **Create Filter for Asher:**
   - In the **To** field: `asher.martinson@mainlineclassical.org`
   - Check **Apply the label:** choose `Classroom/Asher`.

*(Note: If you name your Gmail labels differently, you can customize them in `config.yaml` under `profiles.<Name>.gmail_label`)*.

---

### 4. Configuration Options (`config.yaml`)

You can customize the labels, target list, and class title formatting rules in `config.yaml`:

```yaml
board_id: "6a0dd7e64e205c4e01db1b21"
ingest_list: "Backlog"

gmail:
  host: "imap.gmail.com"
  port: 993
  mark_as_read: true

profiles:
  Isaac:
    label_id: "6a0dd7e769a7a10ca5f5ced0"
    cover_color: "blue"
    gmail_label: "Classroom/Isaac"
    email_patterns:
      - "isaac.martinson@mainlineclassical.org"
      - "isaac"
  Asher:
    label_id: "6a0dd7e67d3bffa03d62a17a"
    cover_color: "green"
    gmail_label: "Classroom/Asher"
    email_patterns:
      - "asher.martinson@mainlineclassical.org"
      - "asher"

class_rules:
  - match: "(?i)art\\s*history"
    prefix: "[Art History]"
  - match: "(?i)french"
    prefix: "[French]"
  - match: "(?i)beast\\s*academy|bao"
    prefix: "[BAO]"
  - match: "(?i)math|arithmetic"
    prefix: "[Math]"
  - match: "(?i)eng\\s*lit|english|literature"
    prefix: "[Eng Lit]"
  - match: "(?i)alcumus"
    prefix: "[Alcumus]"
```

---

## 🧪 Testing & Verification

### 1. Test Ingestion with a Sample `.eml` File
To test parsing without connecting to IMAP:
```bash
python main.py ingest-email --file "path/to/sample.eml" --dry-run
```

### 2. Test Gmail Polling with Dry Run
To test IMAP connection and view unread emails that would be processed without altering Trello or marking emails as read:
```bash
python main.py ingest-email --dry-run
```

### 3. Run Live Ingestion
To process unread Classroom emails and create cards on Trello:
```bash
python main.py ingest-email
```

---

---

## ⏰ Scheduling on Your Basement Server

### Method A: Using the Automated Runner Script (Recommended)

A helper script [`cron_ingest.sh`](cron_ingest.sh) is included that automatically resolves the virtual environment, executes the pipeline, and logs timestamps:

1. Make the script executable:
   ```bash
   chmod +x cron_ingest.sh
   ```
2. Open crontab:
   ```bash
   crontab -e
   ```
3. Add the scheduled entry (e.g. twice daily at 7:00 AM & 7:00 PM):
   ```cron
   0 7,19 * * * /home/user/assignment-tracker/cron_ingest.sh >> /var/log/assignment-tracker.log 2>&1
   ```

---

### Method B: Direct Crontab Entry

```cron
0 7,19 * * * cd /home/user/assignment-tracker && /home/user/assignment-tracker/.venv/bin/python main.py ingest-email >> /var/log/assignment-tracker.log 2>&1
```

---

### Method C: Windows Task Scheduler (If server runs Windows)
1. Open **Task Scheduler** $\to$ **Create Basic Task**.
2. Trigger: **Daily** (set to repeat every 12 hours).
3. Action: **Start a program**:
   - Program: `python.exe` (or `uv.exe` / path inside `.venv\Scripts\python.exe`)
   - Arguments: `main.py ingest-email`
   - Start in: `C:\path\to\assignment-tracker`

