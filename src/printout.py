import os
import sys
import subprocess
import shutil
from datetime import datetime, date, timedelta
import dateutil.parser
import yaml

from src.trello_utils import (
    load_config,
    load_homework,
    save_homework,
    backup_workspace,
    get_credentials,
    fetch_active_cards,
    WORKSPACE_DIR,
    WORKSPACE_FILE
)

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
        # Monday of current week
        monday = ref_date - timedelta(days=ref_date.weekday())
        friday = monday + timedelta(days=4)
        return monday, friday
    elif target == "next":
        # On Saturday (weekday 5), next school week starts Monday in 2 days.
        # On Sunday (weekday 6), next school week starts tomorrow (Monday in 1 day).
        # On Monday-Friday (weekday 0-4), next school week starts the following Monday.
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

def filter_and_group_cards(cards_by_kid: dict, start_date: date, end_date: date) -> list[dict]:
    """
    Groups cards by:
      Day (Monday through Friday) -> Boy -> Subject -> Cards
    Any weekend assignments gracefully attach to adjacent school days:
      - Sunday assignments roll to Monday
      - Saturday assignments roll to Friday
    """
    days = []
    curr = start_date
    while curr <= end_date:
        days.append(curr)
        curr += timedelta(days=1)

    grouped_days = []

    for d in days:
        day_info = {
            'date': d,
            'day_name': d.strftime('%A'),
            'date_str': f"{d.strftime('%B')} {d.day}",
            'boys': {}
        }

        for kid_name, cards in cards_by_kid.items():
            kid_cards = []
            for c in cards:
                card_due = parse_card_due_date(c.get('due'))
                # Direct match
                if card_due == d:
                    kid_cards.append(c)
                # Roll Sunday to Monday
                elif d == start_date and card_due == start_date - timedelta(days=1):
                    kid_cards.append(c)
                # Roll Saturday to Friday
                elif d == end_date and card_due == end_date + timedelta(days=1):
                    kid_cards.append(c)

            if kid_cards:
                # Group by subject (class)
                subjects = {}
                for c in kid_cards:
                    subj = (c.get('class') or 'General').strip()
                    subjects.setdefault(subj, []).append(c)

                # Sort subjects alphabetically
                sorted_subjects = dict(sorted(subjects.items()))
                day_info['boys'][kid_name] = sorted_subjects

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
        lines.append(f"## {day_info['day_name']}, {day_info['date_str']}")
        lines.append("")

        if not day_info['boys']:
            lines.append("*No homework*")
            lines.append("")
            continue

        for boy_name, subjects in day_info['boys'].items():
            lines.append(f"### {boy_name}")
            lines.append("")

            for subj_name, cards in subjects.items():
                lines.append(f"#### {subj_name}")
                for c in cards:
                    title = c.get('name', '').strip()
                    desc = (c.get('desc') or '').strip()
                    lines.append(f"- [ ] **{title}**")
                    if desc:
                        lines.append(f"  {desc}")
                lines.append("")

    content = "\n".join(lines).strip() + "\n"
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return content

def generate_html_printout(grouped_days: list[dict], start_date: date, end_date: date, output_path: str) -> str:
    """
    Stage 2: Generate spartan, right-angled, black-and-white HTML for 1-page landscape printing.
    """
    range_str = format_date_range(start_date, end_date)

    day_columns_html = []
    for day_info in grouped_days:
        day_name = day_info['day_name']
        date_str = day_info['date_str']

        if not day_info['boys']:
            body_html = '<div class="empty-day">No homework</div>'
        else:
            boy_blocks = []
            for boy_name, subjects in day_info['boys'].items():
                subj_blocks = []
                for subj_name, cards in subjects.items():
                    item_rows = []
                    for c in cards:
                        name = c.get('name', '').strip()
                        desc = (c.get('desc') or '').strip()
                        desc_html = f'<div class="item-desc">{desc}</div>' if desc else ''
                        item_rows.append(f'''
                        <div class="assignment-item">
                            <div class="checkbox"></div>
                            <div class="assignment-text">
                                <div class="item-title">{name}</div>
                                {desc_html}
                            </div>
                        </div>
                        ''')

                    subj_blocks.append(f'''
                    <div class="subject-block">
                        <div class="subject-title">{subj_name}</div>
                        {"".join(item_rows)}
                    </div>
                    ''')

                boy_blocks.append(f'''
                <div class="boy-section">
                    <div class="boy-header">{boy_name}</div>
                    {"".join(subj_blocks)}
                </div>
                ''')

            body_html = "".join(boy_blocks)

        day_columns_html.append(f'''
        <div class="day-col">
            <div class="day-header">
                <div class="day-name">{day_name}</div>
                <div class="day-date">{date_str}</div>
            </div>
            <div class="day-body">
                {body_html}
            </div>
        </div>
        ''')

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Weekly Homework Printout</title>
<style>
  @page {{
    size: letter landscape;
    margin: 0.3in 0.35in;
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
    border-bottom: 2px solid #000000;
    padding-bottom: 5px;
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
    font-size: 16px;
    font-weight: 700;
    color: #000000;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .grid-days {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 10px;
    align-items: stretch;
  }}
  .day-col {{
    border: 2px solid #000000;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    min-height: 640px;
  }}
  .day-header {{
    background: #000000;
    color: #ffffff;
    padding: 6px 4px;
    text-align: center;
    border-bottom: 2px solid #000000;
  }}
  .day-name {{
    font-size: 15px;
    font-weight: 900;
    letter-spacing: 0.8px;
    text-transform: uppercase;
  }}
  .day-date {{
    font-size: 12.5px;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: 0.3px;
  }}
  .day-body {{
    padding: 10px 8px;
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    gap: 12px;
    background: #ffffff;
  }}
  .boy-section {{
    background: #ffffff;
    padding: 0 2px;
  }}
  .boy-header {{
    font-size: 13.5px;
    font-weight: 900;
    text-transform: uppercase;
    color: #000000;
    border-bottom: 1.5px solid #000000;
    padding-bottom: 2px;
    margin-bottom: 8px;
    letter-spacing: 0.8px;
  }}
  .subject-block {{
    margin-bottom: 6px;
  }}
  .subject-block:last-child {{
    margin-bottom: 0;
  }}
  .subject-title {{
    font-size: 11.5px;
    font-weight: 800;
    text-transform: uppercase;
    color: #000000;
    letter-spacing: 0.4px;
    margin-bottom: 4px;
  }}
  .assignment-item {{
    display: flex;
    align-items: flex-start;
    gap: 7px;
    margin-bottom: 5px;
  }}
  .assignment-item:last-child {{
    margin-bottom: 0;
  }}
  .checkbox {{
    width: 14px;
    height: 14px;
    border: 2px solid #000000;
    flex-shrink: 0;
    margin-top: 1px;
    background: #ffffff;
  }}
  .assignment-text {{
    font-size: 13px;
    line-height: 1.25;
    word-break: break-word;
  }}
  .item-title {{
    font-weight: 700;
    color: #000000;
  }}
  .item-desc {{
    font-size: 11px;
    color: #333333;
    font-style: italic;
    margin-top: 2px;
  }}
  .empty-day {{
    color: #666666;
    font-size: 13px;
    font-style: italic;
    text-align: center;
    margin-top: 30px;
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

  <div class="grid-days">
    {"".join(day_columns_html)}
  </div>
</div>
</body>
</html>
'''
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
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

    for name in ['chrome', 'msedge', 'google-chrome']:
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
        abs_html
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
    output_dir: str = WORKSPACE_DIR
) -> dict:
    """
    Main orchestration routine:
    1. Determine school week boundaries (Monday to Friday).
    2. Pull from Trello (unless no_pull is True) & update workspace/homework.yaml.
    3. Filter cards for Monday through Friday.
    4. Stage 1: Generate workspace/homework_week.md.
    5. Stage 2: Generate workspace/homework_week.html & workspace/homework_week.pdf.
    """
    if ref_date_str:
        try:
            ref_date = dateutil.parser.parse(ref_date_str).date()
            start_date, end_date = get_week_boundaries(target="this", ref_date=ref_date)
        except Exception as e:
            raise ValueError(f"Invalid date format '{ref_date_str}': {e}")
    else:
        start_date, end_date = get_week_boundaries(target=target)

    if not no_pull:
        print("[1/4] Fetching latest cards from Trello...")
        config = load_config()
        api_key, api_token = get_credentials()
        backup_workspace()
        cards_by_kid = fetch_active_cards(config, api_key, api_token)
        save_homework(cards_by_kid)
        print(f"      Updated {WORKSPACE_FILE}")
    else:
        print(f"[1/4] Loading local cards from {WORKSPACE_FILE} (offline mode)...")
        cards_by_kid = load_homework(WORKSPACE_FILE)

    grouped_days = filter_and_group_cards(cards_by_kid, start_date, end_date)

    total_assignments = 0
    for d in grouped_days:
        for subj_dict in d['boys'].values():
            for cards in subj_dict.values():
                total_assignments += len(cards)

    range_str = format_date_range(start_date, end_date)
    md_path = os.path.join(output_dir, "homework_week.md")
    html_path = os.path.join(output_dir, "homework_week.html")
    pdf_path = os.path.join(output_dir, "homework_week.pdf")

    print(f"[2/4] Generating Markdown ({md_path})...")
    generate_markdown(grouped_days, start_date, end_date, md_path)

    print(f"[3/4] Generating Spartan B&W HTML Layout ({html_path})...")
    generate_html_printout(grouped_days, start_date, end_date, html_path)

    print(f"[4/4] Rendering One-Page Landscape PDF ({pdf_path})...")
    render_pdf_from_html(html_path, pdf_path)

    print("\n" + "="*60)
    print(f"[SUCCESS] Printout ready for the fridge! ({range_str})")
    print(f"   * Total Assignments: {total_assignments}")
    print(f"   * Markdown: {md_path}")
    print(f"   * PDF:      {pdf_path}")
    print("="*60 + "\n")

    if open_pdf:
        try:
            os.startfile(pdf_path)
            print("Opened PDF in default viewer.")
        except Exception as e:
            print(f"Note: Could not automatically open PDF: {e}")

    return {
        'start_date': start_date,
        'end_date': end_date,
        'range_str': range_str,
        'total_assignments': total_assignments,
        'markdown_path': md_path,
        'html_path': html_path,
        'pdf_path': pdf_path
    }
