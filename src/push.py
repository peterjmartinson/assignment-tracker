import os
import sys

# Ensure the root directory is in sys.path so we can import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import push_command

if __name__ == "__main__":
    print("Note: Running push via the new unified CLI. In the future, you can run:\n  python main.py push\n")
    push_command()

