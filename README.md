# Student Ops + Market Intelligence Discord Notifier

A GitHub Actions-powered notification system that posts academic deadlines and market intelligence to Discord via webhooks.

## Features

- 📚 **Academic Tracking**: Canvas LMS integration for assignments, exams, and announcements
- 🚨 **Smart Alerts**: Only notifies when something matters (due <24h, deadline moved, exam <72h)
- 📰 **Market Intelligence**: AI/tech shifts, earnings watch, macro signals via RSS
- 📊 **Analyst Prompts**: Template-based "If I were an analyst" prompts after high-impact events
- 🔁 **Deduplication**: Never repeats the same alert unless something changed
- ⏰ **Scheduled**: Runs automatically via GitHub Actions

## Quick Start

### 1. Fork/Clone this Repository

```bash
git clone https://github.com/YOUR_USERNAME/student-ops-discord.git
cd student-ops-discord
```

### 2. Create Discord Webhooks

Create a webhook for each channel in your Discord server:
- Settings → Integrations → Webhooks → New Webhook

### 3. Configure GitHub Secrets

Go to your repo → Settings → Secrets and variables → Actions → New repository secret

**Required Secrets:**

| Secret | Description |
|--------|-------------|
| `CANVAS_BASE_URL` | Your Canvas instance URL (e.g., `https://school.instructure.com`) |
| `CANVAS_TOKEN` | Canvas API access token ([How to get one](https://community.canvaslms.com/t5/Student-Guide/How-do-I-manage-API-access-tokens-as-a-student/ta-p/273)) |
| `DISCORD_WEBHOOK_DAILY` | Webhook URL for #daily-brief |
| `DISCORD_WEBHOOK_ALERTS` | Webhook URL for #alerts |
| `DISCORD_WEBHOOK_STUDYPLAN` | Webhook URL for #study-plan |
| `DISCORD_WEBHOOK_AI` | Webhook URL for #ai-and-tech-shifts |
| `DISCORD_WEBHOOK_EARNINGS` | Webhook URL for #earnings-watch |
| `DISCORD_WEBHOOK_MACRO` | Webhook URL for #macro-signals |
| `DISCORD_WEBHOOK_MARKET_ALERTS` | Webhook URL for #market-alerts |
| `DISCORD_WEBHOOK_ANALYST` | Webhook URL for #if-i-were-an-analyst |
| `DISCORD_WEBHOOK_VALUATION` | Webhook URL for #valuation-context |

**Optional Secrets:**

| Secret | Description |
|--------|-------------|
| `DISCORD_WEBHOOK_BRIDGE` | Webhook URL for #classroom-bridge |
| `NEWSAPI_KEY` | NewsAPI key (optional, uses RSS by default) |

### 4. Enable GitHub Actions

Actions should be enabled by default. The workflows will run on schedule:
- **Canvas Sync**: Every hour
- **Daily Brief**: Daily at 8:00 AM (America/Kentucky/Louisville)
- **News Poll**: Every hour

You can also trigger workflows manually from the Actions tab.

## Local Development

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (create .env file or export)
export CANVAS_BASE_URL="https://your-school.instructure.com"
export CANVAS_TOKEN="your-canvas-token"
export DISCORD_WEBHOOK_ALERTS="https://discord.com/api/webhooks/..."
# ... other webhooks
```

### Dry-Run Mode

Test without posting to Discord:

```bash
# Test Canvas sync
python -m src.jobs.run_canvas --dry-run

# Test daily brief
python -m src.jobs.run_daily_brief --dry-run

# Test news polling
python -m src.jobs.run_news --dry-run
```

## Architecture

```
src/
├── common/          # Shared utilities
│   ├── http.py      # HTTP client with retries
│   ├── time.py      # Timezone-safe date handling
│   ├── storage.py   # State persistence
│   ├── dedupe.py    # Event deduplication
│   ├── scoring.py   # Priority scoring
│   └── discord.py   # Webhook posting
├── canvas/          # Canvas LMS integration
│   ├── client.py    # API client
│   ├── sync.py      # Data fetching
│   └── normalize.py # Data normalization
├── news/            # Market intelligence
│   ├── sources.py   # RSS adapters
│   ├── filters.py   # Keyword/entity filtering
│   ├── earnings.py  # Earnings calendar
│   ├── macro.py     # Fed/CPI/macro news
│   └── analyst_prompts.py  # Template prompts
└── jobs/            # Scheduled job runners
    ├── run_canvas.py
    ├── run_daily_brief.py
    ├── run_news.py
    └── run_weekly_report.py
```

## Alert Rules

### Academic Alerts (#alerts)
- Assignment due in **<24 hours**
- Deadline **moved earlier** (detected vs previous state)
- Exam/quiz due in **<72 hours**
- Announcement contains: "required", "mandatory", "exam", "deadline", "changed"

### Daily Brief (#daily-brief)
- Posted once daily at 8:00 AM
- Sections: Today / Tomorrow / This Week
- Sorted by priority score

### Market Alerts
- **#ai-and-tech-shifts**: AI model releases, GPU news, major tech announcements
- **#earnings-watch**: Earnings for watchlist tickers
- **#macro-signals**: CPI, FOMC, Fed announcements, Treasury yields

## Customization

### Watchlists

Edit `config/watchlists.json`:

```json
{
  "tickers": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"],
  "ai_keywords": ["LLM", "GPT", "inference", "training", "GPU", "NVIDIA"],
  "macro_keywords": ["CPI", "FOMC", "Fed", "PCE", "Treasury", "unemployment"]
}
```

### RSS Sources

Edit `src/news/sources.py` to add/remove RSS feeds.

## License

MIT
