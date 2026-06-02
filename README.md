# gmail-cleaner

CLI tool that connects to Gmail via API, **unsubscribes** from mailing lists and **archives** promotional/spam emails in bulk.

---

## What it does

1. Searches your inbox using a Gmail query (default: `category:promotions OR category:updates OR label:spam`)
2. For each email, reads the `List-Unsubscribe` header
3. Attempts to unsubscribe via HTTP request or by sending an unsubscribe email
4. Archives all matched emails (removes them from inbox, keeps them in All Mail)

---

## Setup

### 1. Enable Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable **Gmail API** → APIs & Services → Library → search "Gmail API"
4. Create credentials → **OAuth 2.0 Client ID** → Desktop app
5. Download the JSON file and save it as `credentials.json` in this folder

### 2. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run

```bash
# Preview without making changes
python cleaner.py --dry-run

# Process up to 200 emails (default)
python cleaner.py

# Process up to 500 emails
python cleaner.py --max 500

# Custom search query
python cleaner.py --query "from:noreply OR from:newsletter"

# Archive only, skip unsubscribe
python cleaner.py --no-unsubscribe
```

First run opens a browser window to authorize access. A `token.json` is saved so you only need to authorize once.

---

## Options

| Flag | Default | Description |
|---|---|---|
| `--query` | `category:promotions OR category:updates OR label:spam` | Gmail search query |
| `--max` | `200` | Max emails to process per run |
| `--dry-run` | off | Preview actions without making changes |
| `--no-unsubscribe` | off | Archive only, skip unsubscribe attempts |

---

## Security

- `credentials.json` and `token.json` are in `.gitignore` — never commit them
- The script only requests the `gmail.modify` scope (read + archive, cannot delete permanently)
