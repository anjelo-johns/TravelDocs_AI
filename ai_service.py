import os, re, json, time
from datetime import date
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

def get_azure_client_and_deployment():
    # Reload .env dynamically so user edits take effect immediately
    load_dotenv(override=True)
    provider = os.getenv("MODEL_PROVIDER", "azure_ai_foundry").lower().strip()
    endpoint = os.getenv("MODEL_ENDPOINT", "").strip()
    deployment = os.getenv("MODEL_DEPLOYMENT", "").strip()
    api_key = os.getenv("MODEL_API_KEY", "").strip()
    api_version = os.getenv("MODEL_API_VERSION", "2024-10-21").strip()

    is_placeholder = any(
        x in endpoint.lower() or x in api_key.lower() or x in deployment.lower()
        for x in ["your-resource", "your-model", "your-api-key", "your-azure", "your-foundry", "replace-with"]
    )

    if not endpoint or not deployment or not api_key or is_placeholder:
        return None, deployment, "Microsoft Azure AI Foundry / Azure OpenAI credentials not configured or still using placeholders in .env"

    try:
        from openai import AzureOpenAI, OpenAI

        # Strip query parameters (e.g. ?api-version=...)
        if "?" in endpoint:
            endpoint = endpoint.split("?")[0]

        # Strip trailing completion or deployment paths if user pasted full inference URL
        if "/openai/deployments" in endpoint:
            endpoint = endpoint.split("/openai/deployments")[0]
        if endpoint.endswith("/chat/completions"):
            endpoint = endpoint[:-len("/chat/completions")]
        endpoint = endpoint.rstrip("/")

        if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
            endpoint = f"https://{endpoint}"

        # Detect whether this is classic Azure OpenAI endpoint or Azure AI Foundry Model Inference/Serverless
        is_classic_azure = ("openai.azure.com" in endpoint or "cognitiveservices.azure.com" in endpoint) and not ("services.ai.azure.com/models" in endpoint)

        if is_classic_azure:
            client = AzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=endpoint,
                timeout=30.0
            )
        else:
            # Azure AI Foundry Model Inference / Serverless API endpoint
            # If endpoint is models.ai.azure.com without /v1, append /v1 for OpenAI client compliance
            base_url = endpoint
            if "models.ai.azure.com" in base_url and not base_url.endswith("/v1"):
                base_url = f"{base_url}/v1"

            client = OpenAI(
                base_url=base_url,
                api_key=api_key,
                default_headers={"api-key": api_key},
                timeout=30.0
            )

        return client, deployment, None
    except Exception as e:
        return None, deployment, f"Client initialization error: {str(e)}"

def get_model_status():
    load_dotenv(override=True)
    provider_raw = os.getenv("MODEL_PROVIDER", "azure_ai_foundry").strip()
    endpoint = os.getenv("MODEL_ENDPOINT", "").strip()
    deployment = os.getenv("MODEL_DEPLOYMENT", "").strip()
    api_key = os.getenv("MODEL_API_KEY", "").strip()
    api_version = os.getenv("MODEL_API_VERSION", "2024-10-21").strip()

    is_placeholder = any(
        x in endpoint.lower() or x in api_key.lower() or x in deployment.lower()
        for x in ["your-resource", "your-model", "your-api-key", "your-azure", "your-foundry", "replace-with"]
    )

    configured = bool(endpoint and deployment and api_key and not is_placeholder)

    is_foundry = any(k in endpoint.lower() or k in provider_raw.lower() for k in ["foundry", "services.ai.azure.com", "models.ai.azure.com"])
    display_provider = "Microsoft Azure AI Foundry" if is_foundry or "foundry" in provider_raw.lower() else "Azure OpenAI"

    return {
        "provider": display_provider,
        "endpoint": endpoint[:35] + "..." if len(endpoint) > 35 else endpoint,
        "deployment": deployment,
        "api_version": api_version,
        "configured": configured,
        "is_placeholder": is_placeholder,
        "status_text": f"Active ({display_provider})" if configured else ("Needs Setup" if not endpoint else "Placeholder Config")
    }

def test_azure_connection():
    client, deployment, error = get_azure_client_and_deployment()
    if error:
        return {"success": False, "error": error}
    try:
        start = time.time()
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "You are a test ping responder. Reply with only 'pong'."},
                {"role": "user", "content": "ping"}
            ],
            max_tokens=10
        )
        latency = int((time.time() - start) * 1000)
        reply = response.choices[0].message.content.strip()
        status = get_model_status()
        return {
            "success": True,
            "message": f"Successfully connected to {status['provider']} deployment '{deployment}'!",
            "latency_ms": latency,
            "reply": reply,
            "provider": status["provider"]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def extract_text_from_file(file_path):
    """Extract text from uploaded documents (PDF, TXT, JSON, MD, CSV, etc.)"""
    if not os.path.exists(file_path):
        return ""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            pages_text = []
            for i, page in enumerate(reader.pages[:10]):  # First 10 pages
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            return "\n".join(pages_text)
        except Exception as e:
            return f"[PDF text extraction failed: {str(e)}]"
            
    # Plain text formats
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(15000)
    except Exception as e:
        return f"[File read error: {str(e)}]"

def parse_fallback_heuristics(text, filename=""):
    """
    Intelligent heuristic fallback when Azure OpenAI API credentials are not yet configured.
    Ensures the application works seamlessly for demo/development while reminding the user.
    """
    clean_text = text.lower()
    doc_type = "Other"
    if any(k in clean_text for k in ["flight", "airline", "boarding pass", "pnr", "departure"]):
        doc_type = "Flight Ticket"
    elif any(k in clean_text for k in ["hotel", "reservation", "check-in", "check-out", "room", "booking.com", "airbnb"]):
        doc_type = "Hotel Booking"
    elif any(k in clean_text for k in ["train", "railway", "irctc", "coach", "berth"]):
        doc_type = "Train Ticket"
    elif any(k in clean_text for k in ["insurance", "policy", "premium", "coverage", "medical emergency"]):
        doc_type = "Travel Insurance"
    elif "visa" in clean_text or "entry permit" in clean_text or "consulate" in clean_text:
        doc_type = "Visa"
    elif "passport" in clean_text or "nationality" in clean_text:
        doc_type = "Passport"

    # Extract dates YYYY-MM-DD or DD/MM/YYYY or DD-MM-YYYY
    date_matches = re.findall(r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})\b", text)
    issue_date = ""
    expiry_date = ""
    if date_matches:
        import datetime
        parsed_dates = []
        for d in date_matches:
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
                try:
                    dt = datetime.datetime.strptime(d, fmt).date()
                    parsed_dates.append(dt)
                    break
                except ValueError:
                    pass
        parsed_dates = sorted(list(set(parsed_dates)))
        today = date.today()
        # Dates in past or today could be issue date
        past_dates = [d for d in parsed_dates if d <= today]
        future_dates = [d for d in parsed_dates if d > today]
        if past_dates:
            issue_date = past_dates[-1].isoformat()
        if future_dates:
            expiry_date = future_dates[0].isoformat()

    # Document number heuristic
    doc_num_match = re.search(r"(?:PNR|Booking Reference|Booking Ref|Confirmation|Passport No|Policy No|Ticket No|Visa No)[\s\(PNR\)]*[:\s#]+([A-Z0-9]{5,15})\b", text, re.IGNORECASE)
    document_number = doc_num_match.group(1) if doc_num_match else ""

    first_line = [l.strip() for l in text.splitlines() if l.strip()][:1]
    title = first_line[0][:60] if first_line else (filename or f"{doc_type} Document")

    return {
        "title": title,
        "doc_type": doc_type,
        "document_number": document_number,
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "summary": "• Extracted via local fallback pattern matching.\n• To enable deep cognitive extraction with Microsoft Azure AI Foundry, enter your deployment details in .env.",
        "warnings": ["Microsoft Azure AI Foundry credentials not yet provided in .env. Showing local heuristic extraction."],
        "suggested_destination": "",
        "mode": "heuristic_fallback"
    }

def analyze_travel_document(text, filename=""):
    """
    Calls Azure OpenAI to extract structured travel document information.
    Falls back gracefully if credentials are not yet set.
    """
    client, deployment, error = get_azure_client_and_deployment()

    if error or not client:
        result = parse_fallback_heuristics(text, filename)
        result["azure_error"] = error
        return result

    system_prompt = """You are an advanced AI Travel Document Parser.
Analyze the provided document text and return ONLY a valid JSON object matching this schema:
{
  "title": "Clear concise descriptive title, e.g. 'United Airlines UA821 London to NYC' or 'Schengen Visa - France'",
  "doc_type": "One of: Passport, Visa, Flight Ticket, Train Ticket, Bus Ticket, Hotel Booking, Travel Insurance, ID Proof, Permit, Other",
  "document_number": "PNR, Booking Reference, Passport number, Policy number, or Ticket number (empty string if not found)",
  "issue_date": "YYYY-MM-DD format (empty string if not found)",
  "expiry_date": "YYYY-MM-DD format - expiry date, departure date, or valid until date (empty string if not found)",
  "summary": "Concise 2-4 bullet point summary of critical details (Flight times, terminal, baggage, check-in rules, hotel address, emergency contact, conditions)",
  "warnings": ["List of critical alerts or notices, e.g. 'Passport expires within 6 months', 'Terminal check-in closes 60m prior', 'Non-refundable booking'"],
  "suggested_destination": "City or country detected from the document (or empty string)"
}
Return pure JSON with no markdown wrapping or backticks."""

    user_prompt = f"Filename: {filename}\nDocument Content:\n{text[:8000]}"

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=800
        )
        raw_content = response.choices[0].message.content.strip()
        # Clean markdown code blocks if present
        if raw_content.startswith("```"):
            raw_content = re.sub(r"^```(?:json)?\n?", "", raw_content)
            raw_content = re.sub(r"\n?```$", "", raw_content)
        
        parsed = json.loads(raw_content)
        parsed["mode"] = "azure_openai"
        parsed["deployment"] = deployment
        return parsed
    except Exception as e:
        # If API failed, return heuristic fallback with error notes
        fallback = parse_fallback_heuristics(text, filename)
        fallback["mode"] = "azure_error_fallback"
        fallback["azure_error"] = str(e)
        fallback["warnings"].append(f"Azure OpenAI API call failed: {str(e)}")
        return fallback

def chat_travel_copilot(user_message, conversation_history, app_context):
    """
    Conversational AI travel assistant powered by Microsoft Azure AI Foundry / Azure OpenAI
    with full context of trips, documents, and profile.
    """
    client, deployment, error = get_azure_client_and_deployment()

    system_instruction = f"""You are 'TravelDocs AI Copilot', an intelligent, highly knowledgeable travel assistant and itinerary guardian.
You help travelers organize their documents, verify expiry dates, ensure visa compliance, suggest packing & documentation checklists, and summarize trips.

Traveler Profile & Travel Vault Context:
{json.dumps(app_context, indent=2, default=str)}

Rules:
1. Be helpful, clear, and proactive.
2. Check expiry dates against trip dates when answering: if a passport or visa expires within 6 months of a trip, warn the traveler!
3. Format output cleanly using bullet points, emojis, and clear headings.
4. Provide concise, actionable advice tailored to the traveler's stored documents and trips."""

    if error or not client:
        # Fallback offline assistant response
        return {
            "reply": f"🤖 **TravelDocs AI Assistant (Demo Mode)**\n\nI received your query: *\"{user_message}\"*\n\nTo enable full interactive conversation via Microsoft Azure AI Foundry:\n1. Update your credentials in `.env` (`MODEL_ENDPOINT`, `MODEL_DEPLOYMENT`, `MODEL_API_KEY`).\n2. Run connection test in the dashboard.\n\n*Quick Status based on your vault:*\n• You have **{len(app_context.get('trips', []))} trips** planned.\n• You have **{len(app_context.get('documents', []))} documents** stored.",
            "mode": "demo"
        }

    messages = [{"role": "system", "content": system_instruction}]
    for msg in conversation_history[-6:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    try:
        resp = client.chat.completions.create(
            model=deployment,
            messages=messages,
            temperature=0.5,
            max_tokens=700
        )
        return {
            "reply": resp.choices[0].message.content.strip(),
            "mode": "azure_ai_foundry"
        }
    except Exception as e:
        return {
            "reply": f"⚠️ Microsoft Azure AI Foundry encountered an error: {str(e)}.\nPlease check your deployment name and API key in `.env`.",
            "mode": "error"
        }
