"""Gmail drafts for the Windows build — drafts only, never sends.

One-time setup (on your PC):
  1. pip install google-api-python-client google-auth-oauthlib
  2. console.cloud.google.com -> new project -> enable the Gmail API
  3. OAuth consent screen -> External -> add yourself as a test user
  4. Credentials -> Create Credentials -> OAuth client ID -> Desktop app
  5. Download the JSON, save it as %USERPROFILE%\\.friday\\gmail_credentials.json
  6. Ask FRIDAY to draft a mail — a browser window opens once for consent,
     then the token is cached (gmail_token.json) and never asked again.

Scope is gmail.compose: create drafts only. FRIDAY cannot read your inbox
or send mail.
"""
import base64
import os

from common import data_dir

CRED_FILE = os.path.join(data_dir(), "gmail_credentials.json")
TOKEN_FILE = os.path.join(data_dir(), "gmail_token.json")
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


def _service():
    """Returns (service, error). Google libs are imported lazily so the
    module loads (and the command lists) even before pip install."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        return None, ("Gmail libraries aren't installed — run:\n"
                      "pip install google-api-python-client google-auth-oauthlib")
    if not os.path.isfile(CRED_FILE):
        return None, ("Gmail isn't set up yet. Download your OAuth client JSON "
                      f"from Google Cloud Console and save it as:\n{CRED_FILE}\n"
                      "(Full steps: README > Gmail setup.)")
    creds = None
    if os.path.isfile(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CRED_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds), ""


def _draft(params):
    svc, err = _service()
    if err:
        return err
    to = (params.get("to") or "").strip()
    if not to or "@" not in to:
        return "Who should the draft go to? Give me an email address."
    from email.mime.text import MIMEText
    msg = MIMEText(params.get("body") or "")
    msg["to"] = to
    msg["subject"] = params.get("subject") or ""
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        svc.users().drafts().create(
            userId="me", body={"message": {"raw": raw}}).execute()
    except Exception as e:
        return f"Gmail API error: {e}"
    subj = f" — {msg['subject']!r}" if msg["subject"] else ""
    return f"Draft saved in Gmail (to {to}{subj}). It is NOT sent."


TOOLS = [
    {"name": "gmail_draft",
     "description": "Create a Gmail draft (never sends). "
                    "Usage: draft an email to boss@work.com subject Standup body ...",
     "triggers": ["draft email", "draft mail", "gmail draft", "compose email",
                  "write email", "draft a mail"],
     "parameters": {"type": "OBJECT", "properties": {
         "to": {"type": "STRING", "description": "recipient email address"},
         "subject": {"type": "STRING", "description": "email subject"},
         "body": {"type": "STRING", "description": "email body text"}}},
     "arg_patterns": {"to": r"to\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
                      "subject": r"subject\s+(.+?)(?:\s+body\s+|$)",
                      "body": r"body\s+(.+)$"},
     "handler": _draft},
]
