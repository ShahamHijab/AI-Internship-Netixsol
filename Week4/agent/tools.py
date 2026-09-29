import os, uuid, base64
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from .config import PROJECT_ROOT

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
]

calendar_service = None
gmail_service = None

def get_google_creds():
    creds = None
    token_path = PROJECT_ROOT / "token.json"
    credentials_path = PROJECT_ROOT / "credentials.json"
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds

def build_google_services():
    global calendar_service, gmail_service
    creds = get_google_creds()
    calendar_service = build("calendar", "v3", credentials=creds)
    gmail_service = build("gmail", "v1", credentials=creds)
    return calendar_service, gmail_service

def book_video_walkthrough(client_name: str, client_email: str, property_id: str,
                            start_iso: str, end_iso: str, timezone: str, notes: str = ""):
    if calendar_service is None:
        raise RuntimeError("Google Calendar service is not initialized.")
    event = {
        "summary": f"Video Walkthrough - {property_id} - {client_name}",
        "description": f"Overseas client walkthrough. Property: {property_id}. Notes: {notes}",
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end": {"dateTime": end_iso, "timeZone": timezone},
        "attendees": [{"email": client_email}],
        "conferenceData": {"createRequest": {"requestId": str(uuid.uuid4())}},
    }
    created = calendar_service.events().insert(
        calendarId="primary", body=event, conferenceDataVersion=1, sendUpdates="all"
    ).execute()
    return {"event_id": created["id"], "meet_link": created.get("hangoutLink"), "status": "booked"}

def reschedule_video_walkthrough(event_id: str, new_start_iso: str, new_end_iso: str, timezone: str):
    if calendar_service is None:
        raise RuntimeError("Google Calendar service is not initialized.")
    event = calendar_service.events().get(calendarId="primary", eventId=event_id).execute()
    event["start"] = {"dateTime": new_start_iso, "timeZone": timezone}
    event["end"] = {"dateTime": new_end_iso, "timeZone": timezone}
    updated = calendar_service.events().update(
        calendarId="primary", eventId=event_id, body=event, sendUpdates="all"
    ).execute()
    return {"event_id": updated["id"], "status": "rescheduled"}

def cancel_video_walkthrough(event_id: str):
    if calendar_service is None:
        raise RuntimeError("Google Calendar service is not initialized.")
    calendar_service.events().delete(calendarId="primary", eventId=event_id, sendUpdates="all").execute()
    return {"event_id": event_id, "status": "cancelled"}

def send_employee_notification(to_email: str, client_name: str, client_email: str, property_id: str,
                                meeting_time_readable: str, requirements: str, meet_link: str = ""):
    if gmail_service is None:
        raise RuntimeError("Gmail service is not initialized.")
    message = MIMEText(
        f"Client: {client_name} ({client_email})\n"
        f"Property: {property_id}\n"
        f"Meeting time: {meeting_time_readable}\n"
        f"Requirements/notes: {requirements}\n"
        f"Meet link: {meet_link}\n"
    )
    message["to"] = to_email
    message["subject"] = f"New NRP Video Walkthrough: {client_name} - {property_id}"
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"gmail_message_id": sent["id"], "status": "sent"}
