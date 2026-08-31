import email
import email.policy
import re
from datetime import datetime
from dateutil import parser as date_parser

def clean_text(s):
    if not s:
        return ""
    # Normalize unicode spaces and trailing/leading whitespace
    return re.sub(r'[\s\u200b\u202f\u00a0]+', ' ', s).strip()

def extract_body(msg):
    """Extract plain text and HTML bodies from email message."""
    plain_body = ""
    html_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition") or "")
            if "attachment" in content_disposition:
                continue

            try:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if content_type == "text/plain" and not plain_body:
                    plain_body = text
                elif content_type == "text/html" and not html_body:
                    html_body = text
            except Exception:
                continue
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    html_body = text
                else:
                    plain_body = text
        except Exception:
            pass

    return plain_body, html_body

def identify_kid(msg, config, mailbox_kid=None):
    """Determine which kid an email belongs to."""
    if mailbox_kid:
        return mailbox_kid

    profiles = config.get("profiles", {})
    from_hdr = (msg.get("From") or "").lower()
    to_hdr = (msg.get("To") or "").lower()
    x_forwarded = (msg.get("X-Forwarded-To") or "").lower()
    delivered_to = (msg.get("Delivered-To") or "").lower()

    all_hdrs = f"{from_hdr} {to_hdr} {x_forwarded} {delivered_to}"

    for kid_name, profile in profiles.items():
        patterns = profile.get("email_patterns", [])
        # Default pattern is kid's name in lower-case
        patterns = patterns + [kid_name.lower()]
        for pat in patterns:
            if pat.lower() in all_hdrs:
                return kid_name

    # Check forwarded text in body
    plain_body, _ = extract_body(msg)
    forwarded_to_match = re.search(r'To:\s*<?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+)>?', plain_body)
    if forwarded_to_match:
        fwd_email = forwarded_to_match.group(1).lower()
        for kid_name, profile in profiles.items():
            patterns = profile.get("email_patterns", []) + [kid_name.lower()]
            for pat in patterns:
                if pat.lower() in fwd_email:
                    return kid_name

    return None

def extract_due_date(text, reference_date=None):
    """Extract and normalize due dates from text (e.g. 'for May 27th, 2026', 'Due: May 27', 'Due tomorrow')."""
    if not text:
        return None

    # Match patterns like: "May 27th, 2026", "May 27 2026", "May 27, 2026", "05/27/2026"
    date_regexes = [
        r'(?:due\s+on|due\s+date:?|due:?|for)\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})',
        r'(?:due\s+on|due\s+date:?|due:?|for)\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?)',
        r'(?:due\s+on|due\s+date:?|due:?|for)\s+(\d{1,2}/\d{1,2}/\d{2,4})',
        r'([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})'
    ]

    for regex in date_regexes:
        m = re.search(regex, text, re.IGNORECASE)
        if m:
            date_str = m.group(1).strip()
            # Clean ordinal suffixes: 27th -> 27
            cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str, flags=re.IGNORECASE)
            try:
                dt = date_parser.parse(cleaned, default=reference_date or datetime.now())
                # Normalize time to 23:59:00 UTC (or standard end of day)
                return dt.strftime('%Y-%m-%dT23:59:00.000Z')
            except Exception:
                continue

    return None

def format_card_title(class_name, assignment_title, config):
    """Format the card title according to class rules in config.yaml."""
    if not assignment_title:
        assignment_title = "Untitled Assignment"

    clean_title = clean_text(assignment_title)
    # Strip any existing quotes
    clean_title = clean_title.strip('"\'')

    # If title already has bracketed prefix, check if it's already formatted
    if clean_title.startswith("[") and "]" in clean_title:
        return clean_title

    class_rules = config.get("class_rules", [])
    matched_prefix = None

    if class_name:
        for rule in class_rules:
            pattern = rule.get("match")
            if pattern and re.search(pattern, class_name):
                matched_prefix = rule.get("prefix")
                break

    if not matched_prefix:
        if class_name:
            # Clean class name (e.g. 'Art History - 1st grade' -> 'Art History')
            short_class = re.sub(r'\s*-\s*\d+(?:st|nd|rd|th)?\s*grade.*$', '', class_name, flags=re.IGNORECASE).strip()
            matched_prefix = f"[{short_class}]"
        else:
            matched_prefix = "[Assignment]"

    return f"{matched_prefix} {clean_title}"

def parse_classroom_email(msg, config, mailbox_kid=None):
    """Parse a Google Classroom email into structured assignment info."""
    subject = msg.get("Subject") or ""
    message_id = msg.get("Message-ID") or ""
    email_date = msg.get("Date")

    ref_date = datetime.now()
    if email_date:
        try:
            ref_date = date_parser.parse(email_date)
        except Exception:
            pass

    kid = identify_kid(msg, config, mailbox_kid=mailbox_kid)
    plain_body, html_body = extract_body(msg)

    # 1. Extract Assignment Title
    assignment_title = None
    # Check subject: New assignment: "Homework for May 27th, 2026"
    subj_match = re.search(r'(?:New assignment|Due tomorrow|Due soon|New question|New material):\s*[\"“]([^\r\n\"”]+)[\"”]', subject, re.IGNORECASE)
    if subj_match:
        assignment_title = clean_text(subj_match.group(1))
    else:
        # Check without quotes
        subj_match2 = re.search(r'(?:New assignment|Due tomorrow|Due soon):\s*(.+)$', subject, re.IGNORECASE)
        if subj_match2:
            assignment_title = clean_text(subj_match2.group(1))

    # 2. Extract Class Name
    class_name = None
    # In plain text Classroom emails:
    # Notification settings
    # <url>
    # Class Name - Grade
    # <url>
    # New assignment
    if plain_body:
        class_match = re.search(r'(?:Notification settings[\s\S]*?<\S+>[\r\n]+)([^\r\n<]+)[\r\n]+<\S+>[\r\n]+(?:New assignment|Due|New question|New material)', plain_body)
        if class_match:
            class_name = clean_text(class_match.group(1))

    if not class_name and html_body:
        # Try finding class name from HTML table/links
        html_class_match = re.search(r'<a[^>]+href=[\'"][^\'"]*notifications\.googleapis\.com[^\'"]*[\'"][^>]*>[\s\S]*?<td[^>]*>([^<]+)</td>', html_body)
        if html_class_match:
            class_name = clean_text(html_class_match.group(1))

    # 3. Extract Details Link
    details_link = None
    if plain_body:
        link_match = re.search(r'See details\s*[\r\n]+<(https://notifications\.googleapis\.com[^\r\n>]+|https://classroom\.google\.com[^\r\n>]+)>', plain_body)
        if link_match:
            details_link = link_match.group(1).strip()

    if not details_link and html_body:
        html_link_match = re.search(r'<a[^>]+href=[\'"](https://notifications\.googleapis\.com/email/redirect[^\'"]+|https://classroom\.google\.com[^\'"]+)[\'"][^>]*>\s*See details', html_body)
        if html_link_match:
            details_link = html_link_match.group(1).strip()

    # 4. Extract Description / Instructions
    instructions = ""
    if plain_body:
        desc_match = re.search(r'(?:New assignment|Due tomorrow|Due soon)[\r\n]+(?:[^\r\n]+)[\r\n]+([\s\S]*?)[\r\n]+See details', plain_body)
        if desc_match:
            instructions = clean_text(desc_match.group(1))

    # Build description field for Trello card
    desc_lines = []
    if instructions:
        desc_lines.append(instructions)
    if details_link:
        if desc_lines:
            desc_lines.append("")
        desc_lines.append(f"Classroom Link: {details_link}")
    if class_name:
        desc_lines.append(f"Class: {class_name}")

    full_desc = "\n".join(desc_lines)

    # 5. Extract Due Date
    # Try from assignment title first, then body instructions
    due_date = extract_due_date(assignment_title or "", reference_date=ref_date)
    if not due_date and instructions:
        due_date = extract_due_date(instructions, reference_date=ref_date)

    # 6. Format Final Card Title
    formatted_title = format_card_title(class_name, assignment_title or subject, config)

    return {
        "kid": kid,
        "class_name": class_name,
        "raw_title": assignment_title,
        "formatted_title": formatted_title,
        "due": due_date,
        "desc": full_desc,
        "details_link": details_link,
        "message_id": message_id,
        "subject": subject
    }

def parse_eml_file(file_path, config, mailbox_kid=None):
    """Load and parse a .eml file from disk."""
    with open(file_path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=email.policy.default)
    return parse_classroom_email(msg, config, mailbox_kid=mailbox_kid)
