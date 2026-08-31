import json
import os
from datetime import datetime

class StateTracker:
    def __init__(self, filepath=".processed_emails.json"):
        self.filepath = filepath
        self._data = self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, sort_keys=True)

    def is_processed(self, message_id):
        if not message_id:
            return False
        return message_id.strip() in self._data

    def mark_processed(self, message_id, details=None):
        if not message_id:
            return
        entry = {
            "processed_at": datetime.now().isoformat()
        }
        if details:
            entry.update(details)
        self._data[message_id.strip()] = entry
        self._save()
