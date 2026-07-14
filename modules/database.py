import sqlite3
import os
import bcrypt

DB_PATH = os.path.join("data", "database.db")

def get_connection():
    """Return a connection to the SQLite database with row factory enabled."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Create all necessary tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            company_name TEXT
        );

        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bot_name TEXT NOT NULL,
            system_prompt TEXT,
            welcome_message TEXT,
            status TEXT DEFAULT 'inactive',
            vector_store_path TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            doc_name TEXT,
            content_preview TEXT,
            FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()

# ---------- User Operations ----------
def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_user(username: str, password: str, company: str = "") -> bool:
    """Create a new user. Returns True if successful, False if username exists."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, company_name) VALUES (?, ?, ?)",
            (username, hash_password(password), company)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user_by_username(username: str):
    """Retrieve a user row by username."""
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return user

# ---------- Bot Operations ----------
def create_bot(user_id: int, bot_name: str, system_prompt: str, welcome_msg: str) -> int:
    """Create a new bot and return its ID."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO bots (user_id, bot_name, system_prompt, welcome_message, status) VALUES (?, ?, ?, ?, 'inactive')",
        (user_id, bot_name, system_prompt, welcome_msg)
    )
    conn.commit()
    bot_id = cursor.lastrowid
    conn.close()
    return bot_id

def update_bot_vector_path(bot_id: int, path: str):
    """Update the vector store path for a bot."""
    conn = get_connection()
    conn.execute("UPDATE bots SET vector_store_path = ?, status = 'active' WHERE id = ?", (path, bot_id))
    conn.commit()
    conn.close()

def get_bot(bot_id: int):
    """Retrieve a bot by ID."""
    conn = get_connection()
    bot = conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)).fetchone()
    conn.close()
    return bot

def get_user_bots(user_id: int):
    """Return all bots belonging to a user."""
    conn = get_connection()
    bots = conn.execute("SELECT * FROM bots WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return bots

def add_knowledge_entry(bot_id: int, doc_name: str, preview: str):
    """Insert a knowledge base record."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO knowledge_base (bot_id, doc_name, content_preview) VALUES (?, ?, ?)",
        (bot_id, doc_name, preview)
    )
    conn.commit()
    conn.close()

def get_knowledge_entries(bot_id: int):
    """Retrieve all knowledge entries for a bot."""
    conn = get_connection()
    entries = conn.execute("SELECT * FROM knowledge_base WHERE bot_id = ?", (bot_id,)).fetchall()
    conn.close()
    return entries

def get_total_bots(user_id: int) -> int:
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM bots WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()
    return count
