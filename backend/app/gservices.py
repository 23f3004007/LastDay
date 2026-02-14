from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError, DefaultCredentialsError
from googleapiclient.errors import HttpError
from fastapi import HTTPException

def fetch_recent_emails(token: str):
    try:
        creds = Credentials(token=token)
        service = build('gmail', 'v1', credentials=creds)
        results = service.users().messages().list(userId='me', maxResults=50).execute()
        return results.get('messages', []), service

    except RefreshError:
        print("⚠️ Token expired. Frontend needs to re-login.")
        raise HTTPException(status_code=401, detail="Token expired or invalid")
        
    except HttpError as e:
        print(f"⚠️ Google API Error: {e}")
        raise HTTPException(status_code=401, detail="Google API Error")
        
    except Exception as e:
        print(f"⚠️ Unexpected Error in fetch_recent_emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))