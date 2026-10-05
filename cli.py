import os, sys, json
from dotenv import load_dotenv

# Ensure safe console output for Windows PowerShell / CMD
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

from ai_service import (
    get_model_status,
    test_azure_connection,
    analyze_travel_document,
    extract_text_from_file,
    chat_travel_copilot
)
from app import get_vault_context, conn

def print_banner():
    status = get_model_status()
    print("=" * 65)
    print("✈️   TravelDocs AI — Terminal Command Center")
    print(f"    AI Provider:          {status['provider']}")
    print(f"    Model Deployment:     {status['deployment'] or 'Not set'}")
    print(f"    Endpoint:             {status['endpoint'] or 'Not set'}")
    print(f"    Status:               {status['status_text']}")
    print("=" * 65)

def run_test_connection():
    print("\nConnecting to Microsoft Azure AI Foundry deployment...")
    res = test_azure_connection()
    if res.get("success"):
        print(f"✅ SUCCESS: {res.get('message')}")
        print(f"   Latency: {res.get('latency_ms')} ms")
        print(f"   Ping Reply: {res.get('reply')}\n")
    else:
        print(f"⚠️  FAILED: {res.get('error')}\n")

def run_document_analysis():
    print("\n--- Analyze Travel Document ---")
    print("Enter 1 to paste document/ticket text")
    print("Enter 2 to specify path to a file (PDF, TXT, etc.)")
    choice = input("Choice (1/2): ").strip()
    
    text = ""
    filename = ""
    if choice == "2":
        path = input("Enter full path to file: ").strip().strip('"').strip("'")
        if not os.path.exists(path):
            print(f"❌ File not found: {path}\n")
            return
        filename = os.path.basename(path)
        text = extract_text_from_file(path)
        print(f"Extracted {len(text)} characters from {filename}.")
    else:
        print("Paste or type your document text below (end input with an empty line or press Ctrl+Z / Enter):")
        lines = []
        while True:
            try:
                line = input()
                if not line and lines:
                    break
                lines.append(line)
            except EOFError:
                break
        text = "\n".join(lines).strip()

    if not text:
        print("No text provided.\n")
        return

    print("\nAnalyzing with Azure AI...")
    analysis = analyze_travel_document(text, filename=filename)
    print("\n" + "=" * 50)
    print("📋 EXTRACTED DOCUMENT DETAILS:")
    print(f"• Title:             {analysis.get('title')}")
    print(f"• Document Type:     {analysis.get('doc_type')}")
    print(f"• Document Number:   {analysis.get('document_number') or 'N/A'}")
    print(f"• Issue Date:        {analysis.get('issue_date') or 'N/A'}")
    print(f"• Expiry/Travel Date: {analysis.get('expiry_date') or 'N/A'}")
    print(f"• Destination:       {analysis.get('suggested_destination') or 'N/A'}")
    print(f"• Mode:              {analysis.get('mode')}")
    print("\n📝 SUMMARY:")
    print(analysis.get("summary", "None"))
    if analysis.get("warnings"):
        print("\n⚠️ WARNINGS & ALERTS:")
        for w in analysis["warnings"]:
            print(f"  - {w}")
    print("=" * 50 + "\n")

    save = input("Save this document to your travel vault? (y/n): ").strip().lower()
    if save == "y":
        c = conn()
        c.execute("""INSERT INTO documents(title, doc_type, document_number, issue_date, expiry_date, filename, ai_summary)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (analysis.get("title"), analysis.get("doc_type"), analysis.get("document_number"),
                   analysis.get("issue_date"), analysis.get("expiry_date"), filename, analysis.get("summary")))
        c.commit()
        c.close()
        print("✅ Saved to database!\n")

def run_chat_copilot():
    print("\n--- TravelDocs AI Copilot (Terminal Chat) ---")
    print("Type your questions (e.g., 'What are my upcoming trips?', 'Check my passport validity'). Type 'exit' to return to menu.\n")
    history = []
    context = get_vault_context()

    while True:
        try:
            msg = input("You > ").strip()
            if not msg:
                continue
            if msg.lower() in ["exit", "quit", "q"]:
                break
            
            resp = chat_travel_copilot(msg, history, context)
            reply = resp.get("reply", "No response")
            print(f"\nAI Copilot ({resp.get('mode')}) >\n{reply}\n")
            history.append({"role": "user", "content": msg})
            history.append({"role": "assistant", "content": reply})
        except (KeyboardInterrupt, EOFError):
            break

def list_vault():
    c = conn()
    trips = c.execute("SELECT * FROM trips ORDER BY start_date").fetchall()
    docs = c.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    c.close()

    print("\n--- SAVED TRIPS ---")
    for t in trips:
        print(f"• [{t['id']}] {t['name']} &rarr; {t['destination']} ({t['start_date']} to {t['end_date']})")
    if not trips:
        print("No trips saved.")

    print("\n--- STORED DOCUMENTS ---")
    for d in docs:
        exp = f"(Expires: {d['expiry_date']})" if d['expiry_date'] else ""
        num = f"#{d['document_number']}" if d['document_number'] else ""
        print(f"• [{d['id']}] {d['title']} [{d['doc_type']}] {num} {exp}")
    if not docs:
        print("No documents saved.")
    print("")

def main():
    while True:
        print_banner()
        print("1. Test Azure OpenAI Connection")
        print("2. Analyze Travel Document (Text / PDF)")
        print("3. Chat with Azure Travel Copilot")
        print("4. View Stored Trips & Documents")
        print("5. Exit")
        choice = input("\nEnter choice (1-5): ").strip()

        if choice == "1":
            run_test_connection()
        elif choice == "2":
            run_document_analysis()
        elif choice == "3":
            run_chat_copilot()
        elif choice == "4":
            list_vault()
        elif choice == "5":
            print("Goodbye! ✈️")
            break
        else:
            print("Invalid choice, please select 1-5.\n")

if __name__ == "__main__":
    main()
