import os
import sys
from dotenv import load_dotenv
from groq import Groq
from database import get_session_transcript, get_latest_session_id, get_all_sessions

# Load the secret API key from .env
load_dotenv()

def generate_summary(session_id=None):
    """
    Summarizes a meeting session using Groq API and writes a Markdown report.
    If session_id is None, it defaults to the latest session in SQLite.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[Summarizer Warning] GROQ_API_KEY not found in .env. Skipping AI summary.")
        return None

    # Default to latest session if none provided
    if not session_id:
        session_id = get_latest_session_id()
        if not session_id:
            print("[Summarizer] No sessions found in database.")
            return None

    # 1. Fetch raw transcript from SQLite
    raw_transcript = get_session_transcript(session_id)
    if not raw_transcript.strip():
        print(f"[Summarizer] Session '{session_id}' has no transcript text.")
        return None

    print(f"\n[Summarizer] Generating AI summary for {session_id} ")

    # 2. Structured Executive System Prompt
    system_prompt = (
        "You are an executive meeting assistant. Analyze the provided meeting transcript "
        "and generate a concise, structured summary in Markdown format with the following sections:\n"
        "1. 📌 Executive Summary (2-3 sentences overview)\n"
        "2. 🎯 Key Discussion Points (bulleted list)\n"
        "3. ✅ Action Items & Decisions (bulleted list of tasks/outcomes)\n"
        "Be direct, factual, and concise. Do not invent information not in the transcript."
    )

    try:
       
        client = Groq(api_key=api_key)   
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",  
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Meeting Transcript:\n{raw_transcript}"}
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        

        ai_summary = response.choices[0].message.content

        # 4. Build single-artifact Markdown file with full transcript appendix
        markdown_content = (
            f"# 📋 Meeting Report: {session_id}\n\n"
            f"{ai_summary}\n\n"
            f"---\n\n"
            f"## 📝 Full Raw Transcript\n\n"
            f"> {raw_transcript}\n"
        )

        
        # 5. Save to summaries/ folder
        output_dir = "summaries"
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"summary_{session_id}.md")
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        print(f"[Summarizer] Report saved to: {filename}")
        
    except Exception as e:
        print(f"[Summarizer Error] Failed to generate summary: {e}")
        return None


# --- STANDALONE CLI TEST RUNNER ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--list":
            sessions = get_all_sessions()
            print("\nAvailable Meeting Sessions in Database:")
            for s in sessions:
                print(f"  • {s}")
            print()
        else:
            summary = generate_summary(arg)
            if summary:
                print("\n" + summary + "\n")
    else:
        summary = generate_summary()
        if summary:
            print("\n" + summary + "\n")