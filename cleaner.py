#!/usr/bin/env python3
"""
gmail-cleaner: Unsubscribe from mailing lists and archive promotional emails.
"""

import argparse
import base64
import re
import urllib.request
import urllib.parse
from email.message import EmailMessage
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
]

TOKEN_FILE  = 'token.json'
CREDS_FILE  = 'credentials.json'

DEFAULT_QUERY = (
    'category:promotions OR category:updates OR label:spam'
)


# ── Auth ───────────────────────────────────────────────────────────────────────

def get_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


# ── Gmail helpers ──────────────────────────────────────────────────────────────

def search_messages(service, query, max_results):
    messages, page_token = [], None
    while len(messages) < max_results:
        kwargs = {
            'userId': 'me',
            'q': query,
            'maxResults': min(max_results - len(messages), 500),
        }
        if page_token:
            kwargs['pageToken'] = page_token
        result = service.users().messages().list(**kwargs).execute()
        messages.extend(result.get('messages', []))
        page_token = result.get('nextPageToken')
        if not page_token:
            break
    return messages[:max_results]


def get_headers(service, msg_id):
    msg = service.users().messages().get(
        userId='me', id=msg_id, format='metadata',
        metadataHeaders=['List-Unsubscribe', 'List-Unsubscribe-Post', 'From', 'Subject'],
    ).execute()
    return {h['name'].lower(): h['value'] for h in msg['payload'].get('headers', [])}


def archive_batch(service, msg_ids):
    for i in range(0, len(msg_ids), 1000):
        service.users().messages().batchModify(
            userId='me',
            body={'ids': msg_ids[i:i + 1000], 'removeLabelIds': ['INBOX']},
        ).execute()


# ── Unsubscribe logic ──────────────────────────────────────────────────────────

def parse_unsubscribe(header_value):
    """Return (mailto_uri, http_url) extracted from List-Unsubscribe header."""
    mailto = http_url = None
    for part in re.findall(r'<([^>]+)>', header_value):
        if part.startswith('mailto:') and not mailto:
            mailto = part
        elif part.startswith('http') and not http_url:
            http_url = part
    return mailto, http_url


def try_http_unsubscribe(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'gmail-cleaner/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status < 400
    except Exception as e:
        print(f"    HTTP error: {e}")
        return False


def try_mailto_unsubscribe(mailto_uri, service):
    try:
        parsed = urllib.parse.urlparse(mailto_uri)
        to_addr = parsed.path
        params  = urllib.parse.parse_qs(parsed.query)
        subject = params.get('subject', ['Unsubscribe'])[0]
        body    = params.get('body',    ['Please unsubscribe me from this list.'])[0]

        msg = EmailMessage()
        msg['To']      = to_addr
        msg['Subject'] = subject
        msg.set_content(body)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        return True
    except Exception as e:
        print(f"    mailto error: {e}")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Unsubscribe and archive Gmail promotions/spam.'
    )
    parser.add_argument(
        '--query', default=DEFAULT_QUERY,
        help='Gmail search query (default: category:promotions OR updates OR spam)',
    )
    parser.add_argument(
        '--max', type=int, default=200,
        help='Max emails to process (default: 200)',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Preview actions without making any changes',
    )
    parser.add_argument(
        '--no-unsubscribe', action='store_true',
        help='Skip unsubscribe attempts — archive only',
    )
    args = parser.parse_args()

    print('Authenticating with Gmail...')
    service = get_service()

    print(f'Searching: {args.query!r}  (max {args.max})')
    messages = search_messages(service, args.query, args.max)
    print(f'Found {len(messages)} message(s).\n')

    if not messages:
        print('Inbox is already clean.')
        return

    if args.dry_run:
        print('[DRY RUN] No changes will be made.\n')

    unsub_ok   = 0
    unsub_fail = 0
    no_header  = 0
    to_archive = []

    for i, m in enumerate(messages, 1):
        msg_id = m['id']
        try:
            headers = get_headers(service, msg_id)
        except Exception as e:
            print(f'[{i}/{len(messages)}] Error fetching headers: {e}')
            to_archive.append(msg_id)
            continue

        sender  = headers.get('from',    '?')[:50]
        subject = headers.get('subject', '(no subject)')[:60]
        unsub   = headers.get('list-unsubscribe', '')

        print(f'[{i}/{len(messages)}] {sender}')
        print(f'    {subject}')

        if unsub and not args.no_unsubscribe:
            mailto, http_url = parse_unsubscribe(unsub)
            unsubscribed = False

            if http_url:
                print(f'    → HTTP unsubscribe: {http_url[:70]}')
                unsubscribed = True if args.dry_run else try_http_unsubscribe(http_url)
            elif mailto:
                print(f'    → mailto unsubscribe: {mailto[:70]}')
                unsubscribed = True if args.dry_run else try_mailto_unsubscribe(mailto, service)

            if unsubscribed:
                print('    ✓ Unsubscribed')
                unsub_ok += 1
            else:
                print('    ✗ Failed')
                unsub_fail += 1
        else:
            no_header += 1

        to_archive.append(msg_id)

    if to_archive and not args.dry_run:
        print(f'\nArchiving {len(to_archive)} message(s)...')
        archive_batch(service, to_archive)

    print(f'\n{"─" * 44}')
    print(f'  Processed          {len(messages):>5}')
    print(f'  Unsubscribed ✓     {unsub_ok:>5}')
    print(f'  Unsubscribe ✗      {unsub_fail:>5}')
    print(f'  No unsub header    {no_header:>5}')
    print(f'  Archived           {len(to_archive) if not args.dry_run else 0:>5}')
    if args.dry_run:
        print('  (dry run — no changes made)')
    print(f'{"─" * 44}')


if __name__ == '__main__':
    main()
