import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
import dateutil.parser
import requests
import yaml

WORKSPACE_DIR = "workspace"
SNAPSHOT_FILE = os.path.join(WORKSPACE_DIR, "homework_snapshot.json")
LEGACY_WORKSPACE_FILE = os.path.join(WORKSPACE_DIR, "homework.yaml")

STARTER_WEEKLY_ITEMS = [
    {"id": "hw-seed-isaac-1", "kid": "Isaac", "class": "Art History", "type": "weekly", "title": "Google Classroom", "due": "Monday", "notes": "", "active": True},
    {"id": "hw-seed-isaac-2", "kid": "Isaac", "class": "English Language", "type": "weekly", "title": "Spelling Test", "due": "Wednesday", "notes": "", "active": True},
    {"id": "hw-seed-isaac-3", "kid": "Isaac", "class": "English Language", "type": "weekly", "title": "Trad Spelling", "due": "Wednesday", "notes": "", "active": True},
    {"id": "hw-seed-isaac-4", "kid": "Isaac", "class": "Math Competition", "type": "weekly", "title": "Work Packet 1 Hour!", "due": "Thursday", "notes": "", "active": True},
    {"id": "hw-seed-asher-1", "kid": "Asher", "class": "Piano", "type": "weekly", "title": "Hand in Piano log", "due": "Monday", "notes": "", "active": True},
    {"id": "hw-seed-asher-2", "kid": "Asher", "class": "Math", "type": "weekly", "title": "Beast Academy Book", "due": "Tuesday", "notes": "", "active": True},
    {"id": "hw-seed-asher-3", "kid": "Asher", "class": "French", "type": "weekly", "title": "Watch moi, c'est twice", "due": "Tuesday", "notes": "", "active": True},
    {"id": "hw-seed-asher-4", "kid": "Asher", "class": "French", "type": "weekly", "title": "Homework Packet", "due": "Tuesday", "notes": "", "active": True},
    {"id": "hw-seed-asher-5", "kid": "Asher", "class": "English Language", "type": "weekly", "title": "Spelling Test", "due": "Friday", "notes": "", "active": True},
    {"id": "hw-seed-asher-6", "kid": "Asher", "class": "English Language", "type": "weekly", "title": "Workbook Pages", "due": "Friday", "notes": "", "active": True},
]


def load_tracker_config(config_path: str = "config.yaml") -> dict:
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def fetch_items_from_sheets(config: dict) -> list[dict]:
    """Fetch raw homework items from the Google Apps Script Web App URL."""
    sheets_cfg = config.get("google_sheets", {}) or {}
    script_url = (
        os.environ.get("GOOGLE_SCRIPT_URL")
        or sheets_cfg.get("script_url")
        or ""
    ).strip()
    sheet_name = (sheets_cfg.get("sheet_name") or "Homework").strip()

    if not script_url:
        raise ValueError("Google Apps Script URL is not configured in config.yaml or GOOGLE_SCRIPT_URL.")

    sep = "&" if "?" in script_url else "?"
    target_url = f"{script_url}{sep}sheet={sheet_name}"
    response = requests.get(target_url, timeout=15)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(data.get("message") or "Google Apps Script returned an error")

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data.get("data"), list):
            return data["data"]
    return []


def save_snapshot(items: list[dict], path: str = SNAPSHOT_FILE) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


def load_snapshot(path: str = SNAPSHOT_FILE) -> list[dict]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    return list(STARTER_WEEKLY_ITEMS)


def format_date_range(start_date: date, end_date: date) -> str:
    """Format date range with fully spelled-out month names."""
    if start_date.month == end_date.month and start_date.year == end_date.year:
        return f"{start_date.strftime('%B')} {start_date.day} - {end_date.strftime('%B')} {end_date.day}, {end_date.year}"
    elif start_date.year == end_date.year:
        return f"{start_date.strftime('%B')} {start_date.day} - {end_date.strftime('%B')} {end_date.day}, {end_date.year}"
    else:
        return f"{start_date.strftime('%B')} {start_date.day}, {start_date.year} - {end_date.strftime('%B')} {end_date.day}, {end_date.year}"


def get_week_boundaries(target: str = "next", ref_date: date | None = None) -> tuple[date, date]:
    """
    Calculate the Monday-to-Friday school week boundaries (dumping Saturday and Sunday).

    Monday is weekday 0, Friday is weekday 4.
    - target="this": Monday-to-Friday of the current week.
    - target="next": The upcoming Monday-to-Friday school week.
    """
    if ref_date is None:
        ref_date = date.today()

    if target == "this":
        monday = ref_date - timedelta(days=ref_date.weekday())
        friday = monday + timedelta(days=4)
        return monday, friday
    elif target == "next":
        if ref_date.weekday() == 5:
            monday = ref_date + timedelta(days=2)
        elif ref_date.weekday() == 6:
            monday = ref_date + timedelta(days=1)
        else:
            monday = (ref_date - timedelta(days=ref_date.weekday())) + timedelta(days=7)
        friday = monday + timedelta(days=4)
        return monday, friday
    else:
        raise ValueError(f"Unknown target week '{target}'. Expected 'this' or 'next'.")


def parse_card_due_date(due_raw) -> date | None:
    """Parse due date field from card into a date object."""
    if not due_raw:
        return None
    if isinstance(due_raw, datetime):
        return due_raw.date()
    if isinstance(due_raw, date):
        return due_raw
    try:
        dt = dateutil.parser.parse(str(due_raw))
        return dt.date()
    except Exception:
        return None


def normalize_sheet_items_to_cards_by_kid(
    raw_source: list[dict] | dict,
    start_date: date,
    end_date: date,
    kids_order: list[str] | None = None
) -> dict[str, list[dict]]:
    """
    Convert either:
      - a list of Google Sheet rows ({kid, class, type, title, due, notes, active}), OR
      - a legacy dict of {kid: [{name, class, due, desc}]}
    into a unified {kid: [{name, class, due, desc, type}]} dictionary mapped to the target week.
    """
    if isinstance(raw_source, dict):
        return raw_source

    if not kids_order:
        kids_order = ["Isaac", "Asher"]

    # Map weekday name -> date in the target Monday..Friday week
    weekday_to_date = {}
    curr = start_date
    while curr <= end_date:
        weekday_to_date[curr.strftime("%A").lower()] = curr
        curr += timedelta(days=1)

    cards_by_kid: dict[str, list[dict]] = {k: [] for k in kids_order}

    for item in raw_source:
        active_val = item.get("active", item.get("Active", True))
        if isinstance(active_val, str) and active_val.strip().lower() in ("false", "0", "no"):
            continue
        if active_val is False:
            continue

        kid = str(item.get("kid") or item.get("Kid") or "").strip()
        if not kid:
            continue
        if kid not in cards_by_kid:
            cards_by_kid[kid] = []

        subj = str(item.get("class") or item.get("Class") or "General").strip()
        item_type = str(item.get("type") or item.get("Type") or "upcoming").strip().lower()
        title = str(item.get("title") or item.get("Title") or item.get("name") or "").strip()
        notes = str(item.get("notes") or item.get("Notes") or item.get("desc") or "").strip()
        due_raw = str(item.get("due") or item.get("Due") or "").strip()

        if not title or not due_raw:
            continue

        if item_type == "weekly":
            matched_date = weekday_to_date.get(due_raw.lower())
            if matched_date:
                cards_by_kid[kid].append({
                    "id": item.get("id") or item.get("ID") or "",
                    "name": title,
                    "class": subj,
                    "due": matched_date.isoformat(),
                    "desc": notes,
                    "type": "weekly",
                })
        else:
            cards_by_kid[kid].append({
                "id": item.get("id") or item.get("ID") or "",
                "name": title,
                "class": subj,
                "due": due_raw,
                "desc": notes,
                "type": "upcoming",
            })

    return cards_by_kid


def filter_and_group_cards(
    cards_source: dict | list[dict],
    start_date: date,
    end_date: date,
    kids_order: list[str] | None = None
) -> list[dict]:
    """
    Groups assignments by:
      Day (Monday through Friday) -> Boy -> Subject -> Assignments
    Supports both Weekly recurring rows and Upcoming dated rows.
    Any weekend Upcoming assignments gracefully attach to adjacent school days:
      - Sunday assignments roll to Monday
      - Saturday assignments roll to Friday
    """
    cards_by_kid = normalize_sheet_items_to_cards_by_kid(
        cards_source, start_date, end_date, kids_order=kids_order
    )

    days = []
    curr = start_date
    while curr <= end_date:
        days.append(curr)
        curr += timedelta(days=1)

    grouped_days = []

    for d in days:
        day_info = {
            "date": d,
            "day_name": d.strftime("%A"),
            "date_str": f"{d.strftime('%b')} {d.day}",
            "full_date_str": f"{d.strftime('%B')} {d.day}",
            "boys": {},
        }

        for kid_name, cards in cards_by_kid.items():
            kid_cards = []
            for c in cards:
                card_due = parse_card_due_date(c.get("due"))
                if card_due == d:
                    kid_cards.append(c)
                elif d == start_date and card_due == start_date - timedelta(days=1):
                    kid_cards.append(c)
                elif d == end_date and card_due == end_date + timedelta(days=1):
                    kid_cards.append(c)

            if kid_cards:
                subjects = {}
                for c in kid_cards:
                    subj = (c.get("class") or "General").strip()
                    subjects.setdefault(subj, []).append(c)

                sorted_subjects = dict(sorted(subjects.items()))
                day_info["boys"][kid_name] = sorted_subjects

        grouped_days.append(day_info)

    return grouped_days


def generate_markdown(grouped_days: list[dict], start_date: date, end_date: date, output_path: str) -> str:
    """
    Stage 1: Generate clean, spartan Markdown hierarchy:
    Day of week -> Boy -> Subject -> Description/Title
    """
    range_str = format_date_range(start_date, end_date)
    lines = []
    lines.append(f"# Weekly Homework: {range_str}")
    lines.append("")

    for day_info in grouped_days:
        date_label = day_info.get("full_date_str") or day_info["date_str"]
        lines.append(f"## {day_info['day_name']}, {date_label}")
        lines.append("")

        if not day_info["boys"]:
            lines.append("*No homework*")
            lines.append("")
            continue

        for boy_name, subjects in day_info["boys"].items():
            lines.append(f"### {boy_name}")
            lines.append("")

            for subj_name, cards in subjects.items():
                lines.append(f"#### {subj_name}")
                for c in cards:
                    title = c.get("name", "").strip()
                    desc = (c.get("desc") or "").strip()
                    lines.append(f"- [ ] **{title}**")
                    if desc:
                        lines.append(f"  {desc}")
                lines.append("")

    content = "\n".join(lines).strip() + "\n"
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return content


def _render_kid_cell_html(subjects: dict | None) -> str:
    if not subjects:
        return '<div class="empty-cell">—</div>'

    subj_blocks = []
    for subj_name, cards in subjects.items():
        item_rows = []
        for c in cards:
            name = c.get("name", "").strip()
            desc = (c.get("desc") or "").strip()
            desc_html = f'<span class="item-desc"> — {desc}</span>' if desc else ""
            item_rows.append(
                f'''
                <div class="assignment-item">
                    <div class="checkbox"></div>
                    <div class="assignment-text">
                        <span class="item-title">{name}</span>{desc_html}
                    </div>
                </div>
                '''
            )

        subj_blocks.append(
            f'''
            <div class="subject-block">
                <div class="subject-title">{subj_name}</div>
                <div class="subject-items">
                    {"".join(item_rows)}
                </div>
            </div>
            '''
        )

    return f'<div class="kid-cell-content">{"".join(subj_blocks)}</div>'


def generate_html_printout(
    grouped_days: list[dict],
    start_date: date,
    end_date: date,
    output_path: str,
    kids_order: list[str] | None = None
) -> str:
    """
    Stage 2: Generate spartan, right-angled, black-and-white HTML with a
    rotated 5-Row (Mon-Fri) x 2-Column (Isaac | Asher) matrix layout.
    """
    if not kids_order:
        kids_order = ["Isaac", "Asher"]

    range_str = format_date_range(start_date, end_date)

    kid_headers_html = "".join(
        f'<th class="col-kid">{kid.upper()}</th>' for kid in kids_order
    )

    rows_html = []
    for day_info in grouped_days:
        day_name = day_info["day_name"].upper()
        date_str = day_info["date_str"]
        boys_map = day_info.get("boys", {})

        kid_cells = []
        for kid in kids_order:
            cell_inner = _render_kid_cell_html(boys_map.get(kid))
            kid_cells.append(f'<td class="kid-td">{cell_inner}</td>')

        rows_html.append(
            f'''
            <tr class="day-row">
                <td class="day-td">
                    <div class="day-name">{day_name}</div>
                    <div class="day-date">{date_str}</div>
                </td>
                {"".join(kid_cells)}
            </tr>
            '''
        )

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Weekly Homework Printout</title>
<style>
  @page {{
    size: letter portrait;
    margin: 0.35in 0.4in;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    border-radius: 0 !important;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #000000;
    background: #ffffff;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  .page-container {{
    width: 100%;
    display: flex;
    flex-direction: column;
  }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    border-bottom: 3px solid #000000;
    padding-bottom: 6px;
    margin-bottom: 10px;
  }}
  .title-group {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    width: 100%;
  }}
  h1 {{
    font-size: 22px;
    font-weight: 900;
    letter-spacing: -0.3px;
    color: #000000;
    text-transform: uppercase;
  }}
  .date-range {{
    font-size: 15px;
    font-weight: 800;
    color: #000000;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  table.matrix-table {{
    width: 100%;
    border-collapse: collapse;
    border: 2px solid #000000;
    table-layout: fixed;
  }}
  table.matrix-table th,
  table.matrix-table td {{
    border: 2px solid #000000;
    vertical-align: top;
  }}
  table.matrix-table thead th {{
    background: #000000;
    color: #ffffff;
    font-size: 15px;
    font-weight: 900;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 8px 10px;
    text-align: left;
  }}
  table.matrix-table thead th.col-day {{
    width: 115px;
    text-align: center;
  }}
  .day-row {{
    min-height: 150px;
  }}
  .day-td {{
    background: #f5f5f5;
    padding: 10px 8px;
    text-align: center;
    width: 115px;
  }}
  .day-name {{
    font-size: 14px;
    font-weight: 900;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: #000000;
  }}
  .day-date {{
    font-size: 12px;
    font-weight: 700;
    color: #222222;
    margin-top: 3px;
  }}
  .kid-td {{
    padding: 8px 10px;
    background: #ffffff;
  }}
  .kid-cell-content {{
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}
  .subject-block {{
    margin-bottom: 2px;
  }}
  .subject-title {{
    font-size: 11px;
    font-weight: 900;
    text-transform: uppercase;
    color: #000000;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #000000;
    padding-bottom: 1px;
    margin-bottom: 4px;
  }}
  .subject-items {{
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}
  .assignment-item {{
    display: flex;
    align-items: flex-start;
    gap: 7px;
  }}
  .checkbox {{
    width: 13px;
    height: 13px;
    border: 2px solid #000000;
    flex-shrink: 0;
    margin-top: 2px;
    background: #ffffff;
  }}
  .assignment-text {{
    font-size: 13px;
    line-height: 1.3;
    word-break: break-word;
  }}
  .item-title {{
    font-weight: 700;
    color: #000000;
  }}
  .item-desc {{
    font-size: 11.5px;
    color: #222222;
    font-style: italic;
  }}
  .empty-cell {{
    color: #999999;
    font-size: 13px;
    padding: 4px 0;
  }}
</style>
</head>
<body>
<div class="page-container">
  <div class="header">
    <div class="title-group">
      <h1>Weekly Homework</h1>
      <span class="date-range">{range_str}</span>
    </div>
  </div>

  <table class="matrix-table">
    <thead>
      <tr>
        <th class="col-day">DAY</th>
        {kid_headers_html}
      </tr>
    </thead>
    <tbody>
      {"".join(rows_html)}
    </tbody>
  </table>
</div>
</body>
</html>
'''
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html


def find_browser_executable() -> str:
    """Find Google Chrome or Microsoft Edge executable on the system."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    for name in ["chrome", "msedge", "google-chrome"]:
        path = shutil.which(name)
        if path:
            return path

    raise FileNotFoundError("Could not find Google Chrome or Microsoft Edge to render PDF.")


def render_pdf_from_html(html_path: str, pdf_path: str) -> str:
    """Render HTML to PDF using Chrome or Edge headless mode."""
    browser_exe = find_browser_executable()
    abs_html = os.path.abspath(html_path)
    abs_pdf = os.path.abspath(pdf_path)

    if os.path.exists(abs_pdf):
        try:
            os.remove(abs_pdf)
        except Exception:
            pass

    cmd = [
        browser_exe,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={abs_pdf}",
        abs_html,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if not os.path.exists(abs_pdf) or os.path.getsize(abs_pdf) == 0:
        err = result.stderr or result.stdout
        raise RuntimeError(f"Failed to generate PDF with {os.path.basename(browser_exe)}: {err}")

    return abs_pdf


def generate_weekly_printout(
    target: str = "next",
    ref_date_str: str | None = None,
    no_pull: bool = False,
    open_pdf: bool = False,
    output_dir: str = WORKSPACE_DIR,
) -> dict:
    """
    Main orchestration routine:
    1. Determine school week boundaries (Monday to Friday).
    2. Pull from Google Sheets (unless no_pull is True) & cache workspace/homework_snapshot.json.
    3. Map Weekly + Upcoming items for Monday through Friday.
    4. Stage 1: Generate workspace/homework_week.md.
    5. Stage 2: Generate rotated Mon-Fri x Isaac|Asher HTML & PDF.
    """
    if ref_date_str:
        try:
            ref_date = dateutil.parser.parse(ref_date_str).date()
            start_date, end_date = get_week_boundaries(target="this", ref_date=ref_date)
        except Exception as e:
            raise ValueError(f"Invalid date format '{ref_date_str}': {e}")
    else:
        start_date, end_date = get_week_boundaries(target=target)

    config = load_tracker_config()
    kids_cfg = config.get("kids", {})
    kids_order = list(kids_cfg.keys()) if isinstance(kids_cfg, dict) and kids_cfg else ["Isaac", "Asher"]

    if not no_pull:
        print("[1/4] Fetching homework rows from Google Sheets...")
        try:
            items = fetch_items_from_sheets(config)
            if not items:
                print("      Sheet is currently empty; using starter weekly schedule.")
                items = list(STARTER_WEEKLY_ITEMS)
            save_snapshot(items)
            print(f"      Cached {len(items)} row(s) to {SNAPSHOT_FILE}")
        except Exception as e:
            print(f"      Warning: Could not reach Google Sheets ({e}). Falling back to local snapshot.")
            items = load_snapshot()
    else:
        print(f"[1/4] Loading cached homework rows from {SNAPSHOT_FILE} (offline mode)...")
        items = load_snapshot()

    grouped_days = filter_and_group_cards(items, start_date, end_date, kids_order=kids_order)

    total_assignments = 0
    for d in grouped_days:
        for subj_dict in d["boys"].values():
            for cards in subj_dict.values():
                total_assignments += len(cards)

    range_str = format_date_range(start_date, end_date)
    md_path = os.path.join(output_dir, "homework_week.md")
    html_path = os.path.join(output_dir, "homework_week.html")
    pdf_path = os.path.join(output_dir, "homework_week.pdf")

    print(f"[2/4] Generating Markdown ({md_path})...")
    generate_markdown(grouped_days, start_date, end_date, md_path)

    print(f"[3/4] Generating Rotated Mon-Fri x Kid Matrix HTML ({html_path})...")
    generate_html_printout(grouped_days, start_date, end_date, html_path, kids_order=kids_order)

    print(f"[4/4] Rendering One-Page Fridge PDF ({pdf_path})...")
    render_pdf_from_html(html_path, pdf_path)

    print("\n" + "=" * 60)
    print(f"[SUCCESS] Printout ready for the fridge! ({range_str})")
    print(f"   * Total Assignments: {total_assignments}")
    print(f"   * Markdown: {md_path}")
    print(f"   * PDF:      {pdf_path}")
    print("=" * 60 + "\n")

    if open_pdf:
        try:
            os.startfile(pdf_path)
            print("Opened PDF in default viewer.")
        except Exception as e:
            print(f"Note: Could not automatically open PDF: {e}")

    return {
        "start_date": start_date,
        "end_date": end_date,
        "range_str": range_str,
        "total_assignments": total_assignments,
        "markdown_path": md_path,
        "html_path": html_path,
        "pdf_path": pdf_path,
    }
