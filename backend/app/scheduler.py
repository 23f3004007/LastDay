import requests
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

scheduler = BackgroundScheduler()
scheduler.start()

def send_ntfy_notification(email_id, subject, deadline_time):
    # Your unique ntfy topic (change this!)
    topic = "glassify"
    
    # Deep link to open the specific email in the Gmail app
    gmail_deep_link = f"googlegmail:///v1/account/me/thread/{email_id}"
    
    message = f"Reminder: '{subject}' is due at {deadline_time.strftime('%I:%M %p')}"
    
    requests.post(f"https://ntfy.sh/{topic}",
        data=message.encode('utf-8'),
        headers={
            "Title": "Upcoming Deadline!",
            "Priority": "high",
            "Click": gmail_deep_link
        })

def schedule_deadline_reminder(deadline_obj):
    # Schedule for 2 hours before
    run_time = deadline_obj.deadline_time - timedelta(hours=2)
    
    # If the deadline is already less than 2 hours away, notify immediately
    if run_time < datetime.now():
        run_time = datetime.now() + timedelta(seconds=5)

    scheduler.add_job(
        send_ntfy_notification, 
        'date', 
        run_date=run_time, 
        args=[deadline_obj.email_id, deadline_obj.subject, deadline_obj.deadline_time]
    )