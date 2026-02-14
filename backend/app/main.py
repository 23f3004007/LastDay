from fastapi import FastAPI, Header, HTTPException, Body, BackgroundTasks
from pydantic import BaseModel
import os
import requests
import base64
from bs4 import BeautifulSoup
from fastapi.middleware.cors import CORSMiddleware
from .gservices import fetch_recent_emails
from .scheduler import schedule_deadline_reminder
from .schemas import SyncResponse, Deadline, FeedbackRequest
from typing import List, Optional
import dateparser
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
import joblib
from .model_manager import get_user_model, update_user_model
from dateparser.search import search_dates 
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
load_dotenv()

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_user_email_from_token(token: str):
    try:
        creds = Credentials(token=token)
        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()
        return profile['emailAddress']
    except Exception as e:
        print(f"Failed to fetch user profile: {e}")
        return None

def get_clean_body(msg_data):
    try:
        payload = msg_data.get('payload', {})
        parts = payload.get('parts', [])
        data = None

        if 'body' in payload and 'data' in payload['body']:
            data = payload['body']['data']
        
        elif parts:
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    data = part['body'].get('data')
                    break
            if not data:
                for part in parts:
                    if part.get('mimeType') == 'text/html':
                        data = part['body'].get('data')
                        break
        
        if not data:
            return ""

        file_data = base64.urlsafe_b64decode(data + '===').decode('utf-8')
        soup = BeautifulSoup(file_data, "html.parser") 
        clean_text = soup.get_text(separator=' ', strip=True)
        return clean_text

    except Exception as e:
        print(f"Error parsing body: {e}")
        return ""


def extract_deadline_from_body(text: str, email_date: datetime) -> datetime:
    clean_text = " ".join(text.split())
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

    try:
        all_dates_found = search_dates(clean_text[:10000], settings={
            'RELATIVE_BASE': email_date,
            'PREFER_DATES_FROM': 'future',
            'DATE_ORDER': 'DMY',
            'STRICT_PARSING': False
        })
    except Exception as e:
        print(f"   ⚠️ Parser crashed: {e}")
        return email_date

    if not all_dates_found:
        return email_date

    valid_future_dates = []
    
    for match_str, date_obj in all_dates_found:
        diff_minutes = (date_obj - email_date).total_seconds() / 60
        if diff_minutes > 30 and diff_minutes < 525600: 
            valid_future_dates.append(date_obj)
            print(f"   Candidate: {date_obj} (from '{match_str}')")

    if valid_future_dates:
        valid_future_dates.sort()
        best_date = valid_future_dates[-1]
        print(f"✅ Selected Best Deadline: {best_date}")
        return best_date

    return email_date


@app.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest, authorization: str = Header(None)):
    if not authorization or "Bearer " not in authorization:
        raise HTTPException(status_code=401, detail="Missing Token")
    
    token = authorization.split(" ")[1]
    user_email = get_user_email_from_token(token)
    
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid Token or Failed to Fetch Profile")

    training_text = f"{feedback.subject} {feedback.snippet}"
    is_important = not feedback.is_spam
    
    update_user_model(user_email, training_text, is_important)
    
    return {"status": "learned", "user": user_email}

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
    messages, service = fetch_recent_emails(token)
    profile = service.users().getProfile(userId='me').execute()
    user_email = profile['emailAddress']
    user_model = get_user_model(user_email)

    found_deadlines = []
    print(f"\n--- SYNCING FOR {user_email} ---")

    for m in messages:
        try:
            prediction = 1 
            msg_data = service.users().messages().get(userId='me', id=m['id']).execute()
            internal_date_ms = int(msg_data.get('internalDate', datetime.now().timestamp() * 1000))
            email_date = datetime.fromtimestamp(internal_date_ms / 1000.0)

            payload = msg_data.get('payload', {})
            headers = payload.get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown Sender")
            full_body = msg_data.get('snippet', "") 
            if user_model:
                clean_input = f"{subject} {sender} {full_body}"
                clean_input = clean_input.lower()
                clean_input = re.sub(r'\d+', '', clean_input) 
                prediction = user_model.predict([clean_input])[0]
            important_keywords = [
                "deadline", "due date", "submit", "submission", 
                "internship", "offer", "schedule", "meeting", 
                "urgent", "important", "exam", "quiz", "test", 
                "interview", "shortlist", "application"
            ]
            
            is_explicitly_important = any(word in subject.lower() for word in important_keywords)
            
            if prediction == 0 and not is_explicitly_important:
                print(f"🗑️ Skipped (AI): {subject[:30]}...")
                continue
            elif is_explicitly_important and prediction == 0:
                print(f"🛡️ SAFEGUARD: AI blocked '{subject[:15]}...' but keyword found. Keeping.")
            else:
                print(f"✅ Relevant (AI): {subject[:30]}...")

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
                sender="AppScript Ingest",
                deadline_time=deadline,
                snippet=m.snippet,
            )
            schedule_deadline_reminder(dl)
            processed.append({"email_id": m.email_id, "deadline": deadline.isoformat()})
        except Exception as e:
            continue

    return {"status": "ok", "processed": len(processed), "items": processed}