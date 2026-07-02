import base64
import email.utils
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session
from ..config.settings import settings
from ..models.raw_email import RawEmail
from ..models.gmail_sync_state import GmailSyncState
from ..repositories.raw_email import RawEmailRepository
from ..repositories.gmail_sync_state import GmailSyncStateRepository
from ..utils.logging import logger

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify"
]


class GmailService:
    """Service handling Google OAuth2 authentication and Gmail API integration."""

    def __init__(self) -> None:
        self.token_path = Path(settings.gmail.token_path)
        self.token_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_client_config(self) -> Dict[str, Any]:
        """Builds Google client config dynamically from settings."""
        if not settings.gmail.client_id or not settings.gmail.client_secret:
            raise ValueError(
                "Gmail Client ID and Secret must be configured in environment variables (.env)."
            )
        return {
            "web": {
                "client_id": settings.gmail.client_id,
                "client_secret": settings.gmail.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.gmail.redirect_uri],
            }
        }

    def get_auth_url(self) -> str:
        """Generates Google OAuth2 authorization URL."""
        logger.info("Generating Google OAuth authorization URL.", extra={"action": "AUTH_URL"})
        client_config = self._get_client_config()
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=settings.gmail.redirect_uri
        )
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        
        # Save code_verifier to local file to complete PKCE check in callback
        verifier_path = self.token_path.parent / "code_verifier.txt"
        with open(verifier_path, "w", encoding="utf-8") as f:
            f.write(flow.code_verifier)
            
        return auth_url

    def save_token(self, code: str) -> None:
        """Exchanges authorization code for credentials and saves them to token.json."""
        logger.info("Exchanging auth code for tokens...", extra={"action": "SAVE_TOKEN"})
        client_config = self._get_client_config()
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=settings.gmail.redirect_uri
        )
        
        # Load and set code_verifier for PKCE validation
        verifier_path = self.token_path.parent / "code_verifier.txt"
        code_verifier = None
        if verifier_path.exists():
            with open(verifier_path, "r", encoding="utf-8") as f:
                code_verifier = f.read().strip()
                
        flow.fetch_token(code=code, code_verifier=code_verifier)
        
        # Clean up code_verifier file
        if verifier_path.exists():
            try:
                verifier_path.unlink()
            except Exception:
                pass
        
        credentials = flow.credentials
        with open(self.token_path, "w", encoding="utf-8") as f:
            f.write(credentials.to_json())
        logger.info(
            f"Credentials successfully saved to {self.token_path}",
            extra={"action": "SAVE_TOKEN_SUCCESS"}
        )

    def get_credentials(self) -> Optional[Credentials]:
        """Loads credentials from token.json and refreshes them if expired."""
        if not self.token_path.exists():
            logger.warning(
                "token.json does not exist. OAuth authentication required.",
                extra={"action": "CREDENTIALS_MISSING"}
            )
            return None

        credentials = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        
        if credentials and credentials.expired and credentials.refresh_token:
            logger.info("OAuth credentials expired. Refreshing token...", extra={"action": "TOKEN_REFRESH"})
            try:
                credentials.refresh(Request())
                with open(self.token_path, "w", encoding="utf-8") as f:
                    f.write(credentials.to_json())
                logger.info("Token refreshed successfully.", extra={"action": "TOKEN_REFRESH_SUCCESS"})
            except Exception:
                logger.exception("Failed to refresh credentials token.", extra={"action": "TOKEN_REFRESH_FAILURE"})
                return None
                
        return credentials

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract plain text or HTML body from Gmail message payload."""
        if "parts" in payload:
            parts = payload["parts"]
            for part in parts:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/plain" and "data" in part.get("body", {}):
                    body_data = part["body"]["data"]
                    return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
            
            for part in parts:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/html" and "data" in part.get("body", {}):
                    body_data = part["body"]["data"]
                    return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
                
                if "parts" in part:
                    body = self._extract_body(part)
                    if body:
                        return body
        
        elif "body" in payload and "data" in payload["body"]:
            body_data = payload["body"]["data"]
            return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
            
        return ""

    def fetch_messages(
        self,
        query: Optional[str] = None,
        last_history_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Queries Gmail to list message summaries, supporting incremental fetching."""
        credentials = self.get_credentials()
        if not credentials:
            raise RuntimeError("Gmail authentication missing. Please login at /api/auth/login")

        try:
            service = build("gmail", "v1", credentials=credentials)
            messages_list = []
            
            if last_history_id:
                logger.info(
                    f"Attempting incremental sync using historyId: {last_history_id}",
                    extra={"action": "SYNC_HISTORY", "history_id": last_history_id}
                )
                try:
                    history_response = service.users().history().list(
                        userId="me",
                        startHistoryId=last_history_id,
                        historyTypes=["messageAdded"]
                    ).execute()
                    
                    histories = history_response.get("history", [])
                    for history in histories:
                        messages_added = history.get("messagesAdded", [])
                        for msg_added in messages_added:
                            msg = msg_added.get("message")
                            if msg:
                                messages_list.append(msg)
                                
                    logger.info(
                        f"History sync found {len(messages_list)} new messages.",
                        extra={"action": "SYNC_HISTORY_SUCCESS", "count": len(messages_list)}
                    )
                    if messages_list:
                        return [{"id": m["id"], "threadId": m["threadId"]} for m in messages_list]
                except HttpError as e:
                    logger.warning(
                        f"History ID expired or invalid. Falling back to query sync. Error: {e}",
                        extra={"action": "SYNC_HISTORY_EXPIRED"}
                    )
            
            if not query:
                date_after = (datetime.now() - timedelta(days=settings.gmail.history_days)).strftime("%Y/%m/%d")
                query = f"after:{date_after} (subject:job OR subject:application OR subject:interview OR subject:hiring OR subject:offer OR recruiting OR recruiter OR candidate)"

            logger.info(
                f"Querying Gmail inbox with query: '{query}'",
                extra={"action": "QUERY_MESSAGES", "query": query}
            )
            
            response = service.users().messages().list(userId="me", q=query).execute()
            messages = response.get("messages", [])
            
            next_page_token = response.get("nextPageToken")
            while next_page_token and len(messages) < 100:
                response = service.users().messages().list(
                    userId="me", q=query, pageToken=next_page_token
                ).execute()
                messages.extend(response.get("messages", []))
                next_page_token = response.get("nextPageToken")

            logger.info(
                f"Found {len(messages)} messages matching search query.",
                extra={"action": "QUERY_MESSAGES_SUCCESS", "count": len(messages)}
            )
            return messages
            
        except HttpError as error:
            logger.exception("Gmail API communication failed.", extra={"action": "FETCH_MESSAGES_FAILURE"})
            raise error

    def get_message_detail(self, message_id: str) -> Dict[str, Any]:
        """Fetches full content and metadata for a specific Gmail message."""
        credentials = self.get_credentials()
        if not credentials:
            raise RuntimeError("Gmail authentication missing.")

        try:
            service = build("gmail", "v1", credentials=credentials)
            msg_detail = service.users().messages().get(
                userId="me", id=message_id, format="full"
            ).execute()
            
            payload = msg_detail.get("payload", {})
            headers = payload.get("headers", [])
            
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "No Subject")
            sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "Unknown Sender")
            date_str = next((h["value"] for h in headers if h["name"].lower() == "date"), None)
            
            received_at = datetime.utcnow()
            if date_str:
                try:
                    received_at = email.utils.parsedate_to_datetime(date_str)
                    if received_at.tzinfo:
                        received_at = received_at.astimezone(timedelta(0)).replace(tzinfo=None)
                except Exception:
                    logger.exception(f"Failed to parse date header: {date_str}. Defaulting to UTC now.")
            
            snippet = msg_detail.get("snippet", "")
            body = self._extract_body(payload) or snippet
            gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{msg_detail.get('threadId')}"
            
            return {
                "message_id": message_id,
                "thread_id": msg_detail.get("threadId"),
                "subject": subject,
                "sender": sender,
                "received_at": received_at,
                "snippet": snippet,
                "body": body,
                "gmail_link": gmail_link,
                "history_id": msg_detail.get("historyId")
            }

        except HttpError as error:
            logger.exception(f"Failed to fetch message details for ID {message_id}.", extra={"action": "FETCH_DETAIL_FAILURE", "message_id": message_id})
            raise error

    def sync_emails(self, db: Session) -> int:
        """Executes the complete email synchronization loop, fetching unread or incremental

        messages from Gmail, resolving their body and metadata, and persisting them to SQLite.

        Returns:
            The number of newly ingested RawEmail records.
        """
        raw_repo = RawEmailRepository(db)
        sync_repo = GmailSyncStateRepository(db)
        
        # 1. Fetch latest sync state
        sync_state = sync_repo.get_latest_state()
        last_history_id = sync_state.last_history_id if sync_state else None
        
        # 2. Fetch messages from Gmail
        try:
            messages = self.fetch_messages(last_history_id=last_history_id)
        except Exception as e:
            logger.error(f"Gmail synchronization failed: {e}", extra={"action": "SYNC_EMAILS_ERROR"})
            return 0
            
        new_emails_count = 0
        latest_history_id = last_history_id
        latest_message_id = None
        
        # Process in reverse chronological order so the latest message ID and history ID can be checkpointed
        # (Messages from list() are usually newer-first, so reverse to process older first)
        for msg_summary in reversed(messages):
            message_id = msg_summary["id"]
            thread_id = msg_summary["threadId"]
            
            # Check if this email has already been stored
            existing = raw_repo.get_by_message_id(message_id)
            if existing:
                continue
                
            try:
                # Fetch full message details
                msg_detail = self.get_message_detail(message_id)
                
                # Write to raw_emails database table
                raw_email = RawEmail(
                    message_id=message_id,
                    thread_id=thread_id,
                    subject=msg_detail["subject"],
                    sender=msg_detail["sender"],
                    received_at=msg_detail["received_at"],
                    snippet=msg_detail["snippet"],
                    body=msg_detail["body"],
                    processing_state="NEW",
                    classification="unclassified"
                )
                raw_repo.create(raw_email)
                
                new_emails_count += 1
                latest_message_id = message_id
                if msg_detail.get("history_id"):
                    latest_history_id = msg_detail["history_id"]
                    
            except Exception:
                logger.exception(f"Skipping email message ID {message_id} due to ingestion error.")
                continue

        # 3. Update Sync state checkpoint
        if new_emails_count > 0 or latest_history_id != last_history_id:
            new_sync_state = GmailSyncState(
                last_history_id=latest_history_id,
                last_sync_time=datetime.utcnow(),
                last_processed_message_id=latest_message_id
            )
            sync_repo.create(new_sync_state)
            logger.info(
                f"Sync state checkpoint updated. historyId={latest_history_id}, new_emails={new_emails_count}",
                extra={
                    "action": "SYNC_STATE_UPDATED",
                    "history_id": latest_history_id,
                    "new_emails": new_emails_count
                }
            )
            
        return new_emails_count
