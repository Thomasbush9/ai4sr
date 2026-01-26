from db.connection import init_db
from config import DB_PATH

if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at {DB_PATH}")
