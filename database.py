import sqlite3

DB_FILE = "transcripts.db"

def init_db():
    """Creates the transcripts table if it doesn't exist."""
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
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transcripts (session_id, text) VALUES (?, ?)", 
        (session_id, text)
    )
    conn.commit()
    conn.close()

def get_session_transcript(session_id):
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
    

