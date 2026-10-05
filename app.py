from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from datetime import date
from dotenv import load_dotenv
import os, sqlite3, json

# Load environment configuration (.env)
load_dotenv()

from ai_service import (
    get_model_status,
    test_azure_connection,
    analyze_travel_document,
    extract_text_from_file,
    chat_travel_copilot
)

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD = os.path.join(BASE, "uploads")
DB = os.path.join(BASE, "travel.db")
os.makedirs(UPLOAD, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "traveldocs-secret-key-change-me")
app.config["UPLOAD_FOLDER"] = UPLOAD

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS trips(
      id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,destination TEXT NOT NULL,
      start_date TEXT,end_date TEXT,purpose TEXT,notes TEXT);
    CREATE TABLE IF NOT EXISTS documents(
      id INTEGER PRIMARY KEY AUTOINCREMENT,trip_id INTEGER,title TEXT NOT NULL,
      doc_type TEXT NOT NULL,document_number TEXT,issue_date TEXT,expiry_date TEXT,
      filename TEXT,ai_summary TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(trip_id) REFERENCES trips(id));
    CREATE TABLE IF NOT EXISTS profile(
      id INTEGER PRIMARY KEY CHECK(id=1),name TEXT,email TEXT,phone TEXT,
      passport_number TEXT,emergency_contact TEXT);
    INSERT OR IGNORE INTO profile(id,name) VALUES(1,'Traveler');
    """)
    c.commit()
    c.close()

@app.context_processor
def inject_globals():
    return {"model": get_model_status()}

def get_vault_context():
    """Compiles profile, trips, and document records for AI context."""
    c = conn()
    profile = dict(c.execute("SELECT * FROM profile WHERE id=1").fetchone() or {})
    trips = [dict(r) for r in c.execute("SELECT * FROM trips ORDER BY start_date").fetchall()]
    docs = [dict(r) for r in c.execute("SELECT id, trip_id, title, doc_type, document_number, issue_date, expiry_date, ai_summary FROM documents").fetchall()]
    c.close()
    return {
        "profile": profile,
        "trips": trips,
        "documents": docs,
        "today": date.today().isoformat()
    }

@app.route("/")
def dashboard():
    c = conn()
    trips = c.execute("SELECT * FROM trips ORDER BY start_date").fetchall()
    docs = c.execute("""SELECT d.*, t.name trip_name FROM documents d
                        LEFT JOIN trips t ON d.trip_id=t.id ORDER BY d.created_at DESC""").fetchall()
    exp = c.execute("""SELECT d.*, t.name trip_name FROM documents d LEFT JOIN trips t ON d.trip_id=t.id
                     WHERE d.expiry_date IS NOT NULL AND d.expiry_date!=''
                     AND d.expiry_date<=date(?, '+90 day') ORDER BY d.expiry_date""",
                  (date.today().isoformat(),)).fetchall()
    c.close()
    return render_template("dashboard.html", trips=trips, documents=docs, expiring=exp)

@app.route("/trips", methods=["GET", "POST"])
def trips():
    c = conn()
    if request.method == "POST":
        c.execute("""INSERT INTO trips(name,destination,start_date,end_date,purpose,notes)
                     VALUES(?,?,?,?,?,?)""", tuple(request.form.get(k, "") for k in
                     ["name", "destination", "start_date", "end_date", "purpose", "notes"]))
        c.commit()
        c.close()
        flash("Trip created successfully.", "success")
        return redirect(url_for("trips"))
    rows = c.execute("SELECT * FROM trips ORDER BY start_date DESC").fetchall()
    c.close()
    return render_template("trips.html", trips=rows)

@app.post("/trips/delete/<int:id>")
def delete_trip(id):
    c = conn()
    c.execute("DELETE FROM trips WHERE id=?", (id,))
    c.commit()
    c.close()
    flash("Trip deleted.", "success")
    return redirect(url_for("trips"))

@app.route("/documents", methods=["GET", "POST"])
def documents():
    c = conn()
    if request.method == "POST":
        f = request.files.get("file")
        filename = ""
        saved_path = ""
        extracted_text = ""
        
        if f and f.filename:
            filename = secure_filename(f.filename)
            saved_path = os.path.join(UPLOAD, filename)
            f.save(saved_path)
            extracted_text = extract_text_from_file(saved_path)

        title = request.form.get("title", "").strip()
        doc_type = request.form.get("doc_type", "Other").strip()
        doc_num = request.form.get("document_number", "").strip()
        issue_date = request.form.get("issue_date", "").strip()
        expiry_date = request.form.get("expiry_date", "").strip()
        ai_summary = request.form.get("ai_summary", "").strip()
        auto_ai = request.form.get("auto_ai") == "1"

        # If user enabled auto-AI or left title/summary blank and uploaded a document
        if (auto_ai or not ai_summary) and (extracted_text or title):
            text_to_analyze = extracted_text if extracted_text else title
            ai_res = analyze_travel_document(text_to_analyze, filename=filename)
            if not title and ai_res.get("title"):
                title = ai_res.get("title")
            if (not doc_type or doc_type == "Other") and ai_res.get("doc_type"):
                doc_type = ai_res.get("doc_type")
            if not doc_num and ai_res.get("document_number"):
                doc_num = ai_res.get("document_number")
            if not issue_date and ai_res.get("issue_date"):
                issue_date = ai_res.get("issue_date")
            if not expiry_date and ai_res.get("expiry_date"):
                expiry_date = ai_res.get("expiry_date")
            if not ai_summary and ai_res.get("summary"):
                ai_summary = ai_res.get("summary")

        if not title:
            title = filename or f"{doc_type} Document"

        c.execute("""INSERT INTO documents(trip_id,title,doc_type,document_number,issue_date,
                     expiry_date,filename,ai_summary) VALUES(?,?,?,?,?,?,?,?)""",
                  (request.form.get("trip_id") or None, title, doc_type,
                   doc_num, issue_date, expiry_date, filename, ai_summary))
        c.commit()
        c.close()
        flash("Document saved successfully with Azure AI parsing.", "success")
        return redirect(url_for("documents"))

    docs = c.execute("""SELECT d.*, t.name trip_name FROM documents d
                      LEFT JOIN trips t ON d.trip_id=t.id ORDER BY d.created_at DESC""").fetchall()
    trips = c.execute("SELECT * FROM trips ORDER BY start_date").fetchall()
    c.close()
    return render_template("documents.html", documents=docs, trips=trips)

@app.post("/documents/delete/<int:id>")
def delete_doc(id):
    c = conn()
    r = c.execute("SELECT filename FROM documents WHERE id=?", (id,)).fetchone()
    if r and r["filename"]:
        p = os.path.join(UPLOAD, r["filename"])
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    c.execute("DELETE FROM documents WHERE id=?", (id,))
    c.commit()
    c.close()
    flash("Document deleted.", "success")
    return redirect(url_for("documents"))

# ==================== AZURE OPENAI REST APIS ====================

@app.get("/api/health")
def health():
    return jsonify(
        status="ok",
        service="Travel Documentation API",
        model=get_model_status()
    )

@app.get("/api/model/status")
def model_api():
    return jsonify(get_model_status())

@app.post("/api/model/test-connection")
def model_test():
    """Tests live connection to Azure OpenAI deployment."""
    result = test_azure_connection()
    return jsonify(result)

@app.post("/api/model/analyze")
def analyze():
    """
    Main Azure OpenAI Document Analysis Endpoint.
    Accepts JSON: {"text": "...", "filename": "..."}
    or multipart form data with a file.
    """
    text = ""
    filename = ""
    
    # Check if a file was submitted
    if "file" in request.files:
        f = request.files["file"]
        if f and f.filename:
            filename = secure_filename(f.filename)
            temp_path = os.path.join(UPLOAD, f"temp_{filename}")
            f.save(temp_path)
            try:
                text = extract_text_from_file(temp_path)
            finally:
                if os.path.exists(temp_path):
                    try: os.remove(temp_path)
                    except Exception: pass

    # If JSON was submitted
    if not text:
        data = request.get_json(silent=True) or {}
        text = data.get("text", "").strip()
        filename = data.get("filename", filename).strip()

    # If form data text was submitted
    if not text:
        text = request.form.get("text", "").strip()

    if not text:
        return jsonify(error="Document text or valid file is required for analysis"), 400

    analysis = analyze_travel_document(text, filename=filename)
    return jsonify(analysis)

@app.post("/api/ai/chat")
def ai_chat():
    """
    Azure OpenAI Travel Copilot conversational endpoint.
    Accepts: {"message": "...", "history": [...]}
    """
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    history = data.get("history", [])

    if not message:
        return jsonify(error="Message cannot be empty"), 400

    context = get_vault_context()
    reply_obj = chat_travel_copilot(message, history, context)
    return jsonify(reply_obj)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    c = conn()
    if request.method == "POST":
        c.execute("""UPDATE profile SET name=?,email=?,phone=?,passport_number=?,emergency_contact=? WHERE id=1""",
                  tuple(request.form.get(k, "") for k in ["name", "email", "phone", "passport_number", "emergency_contact"]))
        c.commit()
        flash("Profile updated.", "success")
    p = c.execute("SELECT * FROM profile WHERE id=1").fetchone()
    c.close()
    return render_template("profile.html", profile=p)

init_db()

if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1"
    )
