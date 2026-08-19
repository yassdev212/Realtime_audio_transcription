import os
import sys
import chromadb
from dotenv import load_dotenv
from groq import Groq
from database import chroma_collection

# load environment variables for optional RAG Q&A
load_dotenv()


def semantic_search(query, top_k=3):
    """Performs 100% local semantic vector search across all past transcripts."""
    if chroma_collection.count() == 0:
        print("\n[Search] Vector database is empty. Run main.py first to record transcripts!\n")
        return []

    print(f"\n Searching vector index for: '{query}'...")
    results = chroma_collection.query(
        query_texts=[query],
        n_results=min(top_k, chroma_collection.count())
    )
    return results


def ask_rag(query, top_k=3):
    """Full RAG: Semantic search + Groq LLM synthesis."""
    results = semantic_search(query, top_k)
    if not results or not results['documents'][0]:
        return

    # 1. Extract matching snippets
    snippets = results['documents'][0]
    metadatas = results['metadatas'][0]
    
    context_blocks = []
    for doc, meta in zip(snippets, metadatas):
        context_blocks.append(f"[{meta['session_id']}]: \"{doc}\"")
    
    context_text = "\n".join(context_blocks)

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("\n[RAG Error] GROQ_API_KEY not found in .env. Cannot generate AI answer.")
        return

    print("\n🧠 Generating AI answer based on retrieved context via Groq...")

    system_prompt = (
        "You are an assistant answering questions about past meeting transcripts. "
        "Answer the question concisely and accurately based ONLY on the provided context snippets. "
        "If the context doesn't contain the answer, say you don't know."
    )

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context Snippets:\n{context_text}\n\nQuestion: {query}"}
            ],
            temperature=0.2,
            max_tokens=512
        )
        print("\n==================================")
        print("            RAG ANSWER            ")
        print("==================================")
        print(response.choices[0].message.content)
        print("==================================\n")

    except Exception as e:
        print(f"[RAG Error] Failed to generate answer: {e}")


# --- CLI ENTRY POINT ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python search.py \"<search query>\"         (Pure local semantic search)")
        print("  python search.py --ask \"<question>\"       (Full RAG with AI answer)\n")
        sys.exit(0)

    if sys.argv[1] == "--ask" and len(sys.argv) > 2:
        query_text = " ".join(sys.argv[2:])
        ask_rag(query_text)
    else:
        query_text = " ".join(sys.argv[1:])
        results = semantic_search(query_text)
        
        if results and results['documents'][0]:
            print("\n==================================")
            print("     SEMANTIC SEARCH RESULTS      ")
            print("==================================")
            for doc, meta, distance in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
                similarity = 1.0 - (distance / 2.0)  # Approximate similarity %
                print(f"• [{meta['session_id']}] (Match: {similarity*100:.1f}%)")
                print(f"  \"{doc}\"\n")
            print("==================================\n")