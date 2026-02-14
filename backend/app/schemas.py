from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Deadline(BaseModel):
    email_id: str
    subject: Optional[str] = "No Subject"
    sender: Optional[str] = "Unknown Sender"
    deadline_time: datetime
    snippet: str

class SyncResponse(BaseModel):
    status: str
    new_deadlines_found: int
    deadlines: List[Deadline]

class FeedbackRequest(BaseModel):
    email_id: str
    subject: str  
    snippet: str
    is_spam: bool 

class ExchangeRequest(BaseModel):
    code: str

class MessageIn(BaseModel):
    email_id: str
    subject: Optional[str] = None
    snippet: str
    thread_id: Optional[str] = None

class BatchIn(BaseModel):
    messages: List[MessageIn]