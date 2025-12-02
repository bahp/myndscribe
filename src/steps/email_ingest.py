import os
import json
import base64
import re
from pathlib import Path
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from src.core.interfaces import PipelineStep
from src.core.config_loader import config


class EmailIngestStep(PipelineStep):
    """
    Downloads emails from Gmail and saves them as JSON.
    Refactored from gmail_fetcher.py
    """
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    TOKEN_FILE = 'token.json'
    CREDS_FILE = 'credentials.json'

    def run(self, context=None):
        print("\n--- Step 1: Ingesting Emails ---")
        creds = self._authenticate()
        if not creds:
            print("❌ Authentication failed.")
            return

        try:
            service = build('gmail', 'v1', credentials=creds)
            output_dir = Path(config.get('paths.input_dir'))
            output_dir.mkdir(parents=True, exist_ok=True)

            messages = self._fetch_messages(service)
            print(f"Found {len(messages)} messages to process.")

            for i, msg in enumerate(messages):
                self._process_message(service, msg['id'], output_dir, i, len(messages))

        except HttpError as error:
            print(f"An error occurred: {error}")

    def _authenticate(self):
        creds = None
        if os.path.exists(self.TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(self.TOKEN_FILE, self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.CREDS_FILE):
                    print(f"ERROR: '{self.CREDS_FILE}' not found.")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file(self.CREDS_FILE, self.SCOPES)
                creds = flow.run_local_server(port=0)

            with open(self.TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        return creds

    def _fetch_messages(self, service):
        days = config.get('settings.days_back', 60)
        user_email = service.users().getProfile(userId='me').execute().get('emailAddress')

        query = f"from:{user_email} to:{user_email}"
        if days:
            date_threshold = (datetime.now() - timedelta(days=days)).strftime('%Y/%m/%d')
            query += f" after:{date_threshold}"

        print(f"Querying Gmail: {query}")
        results = service.users().messages().list(userId='me', q=query, maxResults=500).execute()
        return results.get('messages', [])

    def _process_message(self, service, msg_id, output_dir, index, total):
        path = output_dir / f"{msg_id}.json"

        # Skip if exists (unless force redownload logic added later)
        if path.exists():
            if config.get('settings.verbose'):
                print(f"{index + 1:4}/{total}. [Skipping] Already exists <{msg_id}>.")
            return

        try:
            msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            content = self._decode_body(msg)
            links = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                               content)

            data = msg
            data['processed_decoded_content'] = content
            data['processed_extracted_links'] = links

            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print(f"{index + 1:4}/{total}. [New] Downloaded <{msg_id}> | {len(links)} links found.")
        except Exception as e:
            print(f"Error processing {msg_id}: {e}")

    def _decode_body(self, msg):
        # Recursive decoding logic
        def decode_parts(parts):
            text = ""
            for part in parts:
                if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
                    text += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8') + "\n"
                elif 'parts' in part:
                    text += decode_parts(part['parts'])
            return text

        payload = msg.get('payload', {})
        if 'parts' in payload:
            return decode_parts(payload['parts'])
        elif payload.get('body', {}).get('data'):
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        return ""



# --- TEST BLOCK ---
if __name__ == "__main__":
    print("\n--- Testing Email Ingest ---")
    ingest = EmailIngestStep()
    if os.path.exists("credentials.json"):
        print("✅ credentials.json found. Ready to run.")
        ingest.run()
    else:
        print("⚠️ credentials.json missing. Cannot authenticate.")
