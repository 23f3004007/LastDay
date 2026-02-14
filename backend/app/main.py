from fastapi import FastAPI, Header, HTTPException, Body, BackgroundTasks
from pydantic import BaseModel
import os
import requests
import base64
from bs4 import BeautifulSoup
from fastapi.middleware.cors import CORSMiddleware
# Ensure these files exist in the same directory (gservices.py, scheduler.py, schemas.py)
from .gservices import fetch_recent_emails
from .scheduler import schedule_deadline_reminder
from .schemas import SyncResponse, Deadline
from typing import List, Optional
import dateparser
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
import joblib
from .model_manager import get_user_model, update_user_model
from .gservices import fetch_recent_emails
from .scheduler import schedule_deadline_reminder
from .schemas import SyncResponse, Deadline
from dateparser.search import search_dates  # <--- NEW IMPORT
load_dotenv()

app = FastAPI()

class FeedbackRequest(BaseModel):
    email_id: str
    snippet: str
    subject: str = "" # Added subject for better training context
    is_important: bool

# --- FIX: Absolute Path for Model Loading ---
# This ensures it finds the file regardless of where you run the command from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'spam_classifier.pkl')

try:
    spam_model = joblib.load(MODEL_PATH)
    print(f"✅ ML Filter Loaded from: {MODEL_PATH}")
except Exception as e:
    spam_model = None
    print(f"⚠️ WARNING: Could not load spam_classifier.pkl. Running without filter.\nError: {e}")

# --- Data Models ---
class FeedbackRequest(BaseModel):
    email_id: str
    snippet: str
    is_important: bool

class ExchangeRequest(BaseModel):
    code: str

class MessageIn(BaseModel):
    email_id: str
    subject: Optional[str] = None
    snippet: str
    thread_id: Optional[str] = None

class BatchIn(BaseModel):
    messages: List[MessageIn]


# --- HELPER: Extract Full Text from Gmail Payload ---
# --- HELPER: Extract Full Text from Gmail Payload ---
def get_clean_body(msg_data):
    try:
        payload = msg_data.get('payload', {})
        parts = payload.get('parts', [])
        data = None

        # 1. Try to find the text part directly
        if 'body' in payload and 'data' in payload['body']:
            data = payload['body']['data']
        
        # 2. If nested (multipart), search for 'text/plain' or 'text/html'
        elif parts:
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    data = part['body'].get('data')
                    break
            # Fallback to HTML if no plain text
            if not data:
                for part in parts:
                    if part.get('mimeType') == 'text/html':
                        data = part['body'].get('data')
                        break
        
        if not data:
            return ""

        # 3. Decode Base64URL
        file_data = base64.urlsafe_b64decode(data + '===').decode('utf-8')

        # 4. Strip HTML using 'html.parser' (Built-in, no crash)
        # CHANGED FROM "lxml" TO "html.parser"
        soup = BeautifulSoup(file_data, "html.parser") 
        clean_text = soup.get_text(separator=' ', strip=True)
        return clean_text

    except Exception as e:
        print(f"Error parsing body: {e}")
        return ""

# --- ML / Logic Functions ---
def extract_deadline_from_body(text: str, email_date: datetime) -> datetime:
    """
    Scans the ENTIRE text for dates. 
    Heuristic: The Deadline is usually the date mentioned that is furthest in the future.
    """
    print(f"🔍 Scanning text length: {len(text)} chars")

    # 1. Clean the text to help the parser
    # Remove excessive whitespace/newlines to make patterns clearer
    clean_text = " ".join(text.split())

    # 2. explicit "On or Before" check (Your specific case)
    # matches "on or before 16th Feb 2026"
    on_or_before_match = re.search(r"on or before\s+(.{5,30})", clean_text, re.IGNORECASE)
    if on_or_before_match:
        snippet = on_or_before_match.group(1)
        print(f"   🎯 Found 'on or before': {snippet}")
        try:
            dates = search_dates(snippet, settings={'RELATIVE_BASE': email_date, 'PREFER_DATES_FROM': 'future'})
            if dates:
                return dates[0][1]
        except:
            pass

    # 3. General Scan: Find ALL dates in the email
    try:
        # We scan the first 4000 characters (covers 99% of emails)
        all_dates_found = search_dates(clean_text[:4000], settings={
            'RELATIVE_BASE': email_date,
            'PREFER_DATES_FROM': 'future',
            'DATE_ORDER': 'DMY', # Prefer Day-Month-Year
            'STRICT_PARSING': False
        })
    except Exception as e:
        print(f"   ⚠️ Parser crashed: {e}")
        return email_date

    if not all_dates_found:
        return email_date

    # 4. Filter for Valid Future Deadlines
    valid_future_dates = []
    
    for match_str, date_obj in all_dates_found:
        # Calculate difference in minutes
        diff_minutes = (date_obj - email_date).total_seconds() / 60
        
        # Filter 1: Must be > 30 mins in the future (Avoids "Sent: 10:00am")
        # Filter 2: Must be < 365 days (Avoids "Copyright 2025" or weird parsing errors)
        if diff_minutes > 30 and diff_minutes < 525600: 
            valid_future_dates.append(date_obj)
            print(f"   Candidate: {date_obj} (from '{match_str}')")

    if valid_future_dates:
        # 5. Pick the BEST date
        # If we found explicit future dates, the deadline is usually the LAST one.
        # (e.g. "Project starts Feb 12... Submission Feb 16")
        valid_future_dates.sort()
        best_date = valid_future_dates[-1] # Take the furthest date
        print(f"✅ Selected Best Deadline: {best_date}")
        return best_date

    return email_date
# --- Endpoints ---

@app.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest, authorization: str = Header(None)):
    if not authorization or "Bearer " not in authorization:
        raise HTTPException(status_code=401, detail="Missing Token")
    
    token = authorization.split(" ")[1]

    user_email = "current_user_placeholder" 
    training_text = f"{feedback.subject} {feedback.snippet}"
    update_user_model(user_email, training_text, feedback.is_important)
    
    return {"status": "learned"}

# Allow CORS for Emulator (10.0.2.2) and others
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/sync", response_model=SyncResponse)
async def sync_emails(authorization: str = Header(None)):
    if not authorization or "Bearer " not in authorization:
        raise HTTPException(status_code=401, detail="Missing Token")

    token = authorization.split(" ")[1]
    
    # 1. Fetch Emails
    messages, service = fetch_recent_emails(token)
    
    # 2. Get User's Email
    profile = service.users().getProfile(userId='me').execute()
    user_email = profile['emailAddress']
    
    # 3. Load THEIR personal model
    user_model = get_user_model(user_email)

    found_deadlines = []
    print(f"\n--- SYNCING FOR {user_email} ---")

    for m in messages:
        try:
            # --- Initialize SAFE DEFAULTS ---
            # Default to "1" (Relevant) so if AI fails, we don't delete important stuff.
            prediction = 1 
            
            msg_data = service.users().messages().get(userId='me', id=m['id']).execute()
            internal_date_ms = int(msg_data.get('internalDate', datetime.now().timestamp() * 1000))
            email_date = datetime.fromtimestamp(internal_date_ms / 1000.0)

            payload = msg_data.get('payload', {})
            headers = payload.get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown Sender")
            full_body = msg_data.get('snippet', "") 

            # --- PERSONALIZED AI CHECK ---
            if user_model:
                clean_input = f"{subject} {sender} {full_body}"
                clean_input = clean_input.lower()
                clean_input = re.sub(r'\d+', '', clean_input) 
                
                # Update prediction using the model
                prediction = user_model.predict([clean_input])[0]
            
            # --- SAFETY OVERRIDE (Keywords) ---
            important_keywords = [
                "deadline", "due date", "submit", "submission", 
                "internship", "offer", "schedule", "meeting", 
                "urgent", "important", "exam", "quiz", "test", 
                "interview", "shortlist", "application", "hackathon"
            ]
            
            is_explicitly_important = any(word in subject.lower() for word in important_keywords)
            
            # --- FINAL DECISION LOGIC ---
            # If AI says Spam (0) AND it's NOT explicitly important -> Skip it
            if prediction == 0 and not is_explicitly_important:
                print(f"🗑️ Skipped (AI): {subject[:30]}...")
                continue
            elif is_explicitly_important and prediction == 0:
                print(f"🛡️ SAFEGUARD: AI blocked '{subject[:15]}...' but keyword found. Keeping.")
            else:
                print(f"✅ Relevant (AI): {subject[:30]}...")

            # --- DEADLINE EXTRACTION ---
            analysis_text = f"{subject} . {full_body}"
            deadline_time = extract_deadline_from_body(analysis_text, email_date)
            
            new_deadline = Deadline(
                email_id=m['id'],
                subject=subject,
                sender=sender,
                deadline_time=deadline_time,
                snippet=full_body
            )
            found_deadlines.append(new_deadline)
            schedule_deadline_reminder(new_deadline)

        except Exception as e:
            # Now this will print the actual error without crashing the loop
            print(f"Error processing email {m.get('id')}: {e}")
            continue

    return {
        "status": "success",
        "new_deadlines_found": len(found_deadlines),
        "deadlines": found_deadlines
    }

@app.post("/auth/exchange")
async def exchange_code(req: ExchangeRequest = Body(...)):
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="OAuth credentials not configured")

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": req.code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": "", 
        "grant_type": "authorization_code",
    }
    
    r = requests.post(token_url, data=data)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {r.text}")

    return r.json()

@app.post("/apps/ingest")
async def apps_ingest(batch: BatchIn = Body(...), x_apps_script_secret: Optional[str] = Header(None)):
    secret = os.environ.get("APPS_SCRIPT_SECRET")
    if not secret or x_apps_script_secret != secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    processed = []
    current_time = datetime.now() 

    for m in batch.messages:
        full_text = f"{m.subject or ''} {m.snippet}"
        deadline = extract_deadline_from_body(full_text, current_time)
        
        try:
            dl = Deadline(
                email_id=m.email_id,
                subject=m.subject or "No Subject",
                sender="AppScript Ingest", # Added default sender to match schema
                deadline_time=deadline,
                snippet=m.snippet,
            )
            schedule_deadline_reminder(dl)
            processed.append({"email_id": m.email_id, "deadline": deadline.isoformat()})
        except Exception as e:
            continue

    return {"status": "ok", "processed": len(processed), "items": processed}