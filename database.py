import sqlite3
import chromadb

DB_FILE = "transcripts.db"
CHROMA_PATH = "./chroma_db"

# 1. Initialize persistent local ChromaDB client & collection
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
chroma_collection = chroma_client.get_or_create_collection(name="meeting_transcripts")


def init_db():
    """Creates the SQLite transcripts table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            text TEXT
        )
    ''')
    conn.commit()
    conn.close()


def log_sentence(session_id, text):
    """Dual-writes the transcribed sentence to both SQLite and ChromaDB."""
    text = text.strip()
    if not text:
        return

    # --- WRITE 1: SQLite ---
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transcripts (session_id, text) VALUES (?, ?)", 
        (session_id, text)
    )
    row_id = cursor.lastrowid  # Grab the unique SQLite row ID
    conn.commit()
    conn.close()

    # --- WRITE 2: ChromaDB Vector Store ---
    try:
        chroma_collection.add(
            documents=[text],
            metadatas=[{"session_id": session_id}],
            ids=[f"row_{row_id}"]
        )
    except Exception as e:
        print(f"[Vector DB Error] Failed to index vector: {e}")


def get_session_transcript(session_id):
    """Fetches all sentences for a session, glues them together, and returns the paragraph."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT text FROM transcripts WHERE session_id = ? ORDER BY id ASC", 
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    sentences = [row[0] for row in rows]
    return " ".join(sentences)


def get_latest_session_id():
    """Returns the most recent session_id stored in the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT session_id FROM transcripts ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_all_sessions():
    """Returns a list of all unique session_ids in chronological order."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT session_id FROM transcripts ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]