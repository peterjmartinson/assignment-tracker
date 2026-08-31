import email
import email.policy
import imaplib
import os
import ssl
from dotenv import load_dotenv

load_dotenv()

def get_gmail_credentials():
    """Load Gmail credentials from environment."""
    user = os.getenv("GMAIL_USER")
    password = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("GMAIL_PASSWORD") or os.getenv("GMAIL_PASS")
    if not user or not password:
        raise ValueError(
            "Missing Gmail credentials. Please set GMAIL_USER and GMAIL_APP_PASSWORD in your .env file."
        )
    return user, password

class GmailIMAPClient:
    def __init__(self, host="imap.gmail.com", port=993, user=None, password=None):
        self.host = host
        self.port = port
        if user and password:
            self.user = user
            self.password = password
        else:
            self.user, self.password = get_gmail_credentials()
        self.client = None

    def connect(self):
        """Establish SSL connection and log in to Gmail IMAP."""
        context = ssl.create_default_context()
        self.client = imaplib.IMAP4_SSL(self.host, self.port, ssl_context=context)
        self.client.login(self.user, self.password)
        return self

    def disconnect(self):
        """Safely close and log out of the IMAP connection."""
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            try:
                self.client.logout()
            except Exception:
                pass
            self.client = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def list_folders(self):
        """List all available IMAP folders / labels."""
        status, folder_list = self.client.list()
        if status != "OK":
            return []
        folders = []
        for f in folder_list:
            # e.g., b'(\\HasNoChildren) "/" "Classroom/Isaac"'
            decoded = f.decode("utf-8", errors="replace")
            folders.append(decoded)
        return folders

    def _quote_folder(self, folder_name):
        """Ensure folder name is safely quoted for IMAP commands."""
        clean = folder_name.strip('"')
        return f'"{clean}"'

    def fetch_unseen_messages(self, folder_name):
        """Fetch all unread messages from a specific folder/label."""
        quoted = self._quote_folder(folder_name)
        status, _ = self.client.select(quoted, readonly=False)
        if status != "OK":
            raise ValueError(f"Could not select IMAP folder: {folder_name}")

        status, response = self.client.uid("search", None, "UNSEEN")
        if status != "OK" or not response[0]:
            return []

        uids = response[0].split()
        messages = []

        for uid_bytes in uids:
            uid_str = uid_bytes.decode("utf-8")
            fetch_status, fetch_data = self.client.uid("fetch", uid_bytes, "(RFC822)")
            if fetch_status != "OK" or not fetch_data:
                continue

            raw_email = None
            for part in fetch_data:
                if isinstance(part, tuple):
                    raw_email = part[1]
                    break

            if raw_email:
                msg = email.message_from_bytes(raw_email, policy=email.policy.default)
                messages.append({
                    "uid": uid_str,
                    "folder": folder_name,
                    "msg": msg
                })

        return messages

    def mark_as_read(self, uid_str, folder_name):
        """Mark a message as read in the specified folder."""
        quoted = self._quote_folder(folder_name)
        self.client.select(quoted, readonly=False)
        self.client.uid("store", uid_str.encode("utf-8"), "+FLAGS", "(\\Seen)")

    def move_or_label_processed(self, uid_str, current_folder, processed_folder=None):
        """Mark message as read and optionally copy/move to a processed folder."""
        quoted = self._quote_folder(current_folder)
        self.client.select(quoted, readonly=False)

        # Mark as read
        self.client.uid("store", uid_str.encode("utf-8"), "+FLAGS", "(\\Seen)")

        if processed_folder:
            dest_quoted = self._quote_folder(processed_folder)
            try:
                # Copy to processed folder
                copy_status, _ = self.client.uid("copy", uid_str.encode("utf-8"), dest_quoted)
                if copy_status == "OK":
                    # Mark original as deleted
                    self.client.uid("store", uid_str.encode("utf-8"), "+FLAGS", "(\\Deleted)")
                    self.client.expunge()
            except Exception as e:
                # In Gmail IMAP, copying/moving between labels might fail if folder doesn't exist yet
                pass
