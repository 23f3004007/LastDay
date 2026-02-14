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