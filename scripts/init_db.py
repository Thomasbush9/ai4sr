from ai4sr.db.connection import init_db
from ai4sr.config import DB_PATH

if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at {DB_PATH}")
