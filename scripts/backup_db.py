"""Back up the Learnova SQLite database. Cron it: 0 3 * * * python scripts/backup_db.py"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from learnova.auth import phone  # noqa: E402

if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / ".data" / "backups")
    print(phone.backup(dest))
