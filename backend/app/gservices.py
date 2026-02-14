from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError, DefaultCredentialsError
from googleapiclient.errors import HttpError
from fastapi import HTTPException

def fetch_recent_emails(token: str):
    try:
        # Create credentials object with just the access token
        creds = Credentials(token=token)
        service = build('gmail', 'v1', credentials=creds)
        
        # Get last 50 messages
        results = service.users().messages().list(userId='me', maxResults=50).execute()
        return results.get('messages', []), service

    except RefreshError:
        # This catches the specific crash you are seeing.
        # It means the token is expired and the backend cannot refresh it.
        print("⚠️ Token expired. Frontend needs to re-login.")
        raise HTTPException(status_code=401, detail="Token expired or invalid")
        
    except HttpError as e:
        # Catches other Google API errors (like 403 Forbidden)
        print(f"⚠️ Google API Error: {e}")
        raise HTTPException(status_code=401, detail="Google API Error")
        
    except Exception as e:
        # Catches anything else
        print(f"⚠️ Unexpected Error in fetch_recent_emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))