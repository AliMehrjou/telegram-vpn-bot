این هم کل متن فایل `README.md` به صورت یک‌پارچه و آماده. این بار برای بخش‌های کد به جای استفاده از بک‌تیک از ساختار کدهای HTML (`<pre><code>`) استفاده کردم که **تحت هیچ شرایطی** موقع کپی کردن به هم نریزد و در گیت‌هاب هم با بالاترین کیفیت و استاندارد نمایش داده شود.

کل کادر زیر را کپی کنید و داخل فایل `README.md` خود قرار دهید:

```markdown
# 🤖 Telegram VPN Bot (Without need API panel)

A production-ready, fully asynchronous Telegram bot for distributing, selling, and managing VPN configurations. Built with **Python**, **aiogram 3**, and **MySQL**, it supports free config distribution, manual payment verification, a referral/reward system, an automatic stock pipeline, and a comprehensive admin panel — all within Telegram.

---

## ✨ Features

### 👤 User Features
* **Free VPN Config** — Users can claim a free VPN config at a configurable time interval (default: once per day).
* **Purchase Plans** — Browse available subscription plans and initiate a purchase directly in Telegram.
* **Payment by Receipt** — Manual card-to-card payment: user sends a screenshot of the payment receipt; admin approves or rejects it.
* **My Services** — View all active, pending, or expired VPN configs with full details (traffic, expiry, config link).
* **Referral System** — Share a unique invite link and earn rewards:
  * Every **5 referrals** who join → 1-day unlimited config.
  * Every **10 purchases** by referrals → 1-month unlimited single-user config (you can change this plan).
* **Support Contact** — Instantly contact the admin from within the bot.

### 🛡️ Admin Features
| Command | Description |
|---|---|
| `/add_config [config_text]` | Add one or more free VPN configs (multiline supported) |
| `/add_plan Name:...\|Price:...\|Days:...\|GB:...` | Create a new subscription plan |
| `/edit_plan [plan_id] Field:Value` | **Modify an existing plan's fields (e.g., `Price:60000` or `Name:New\|GB:80`)** 🆕 |
| `/add_vip [plan_id] [config_text]` | Stock the inventory for a specific plan (multiline) |
| `/add_reward [invite/purchase] [config_text]` | Add configs to the referral reward inventory |
| `/set_free_limit [days]` | Configure the free config cooldown (e.g., `0.5` = 12 hours) |
| `/plans_list` | View all plans and their IDs |
| `/sub_info [id or name]` | Look up a specific config (owner, expiry, traffic, status) |
| `/user_subs [telegram_id]` | View all services belonging to a user |
| `/sendall` | Broadcast a message to all registered users |
| `/send_message [user_id] [text]` | Send a private message to a specific user |
| `/users_count` | Display the total number of registered users |
| `/help_admin` | Show the full admin help guide |

### ⚙️ System Features
* **Race Condition Prevention** — Per-user asyncio locks prevent duplicate free config claims.
* **Force Channel Join Middleware** — Users must join a sponsor channel before using the bot.
* **Expiry Reminders** — A scheduled daily task (APScheduler) automatically notifies users 3 days before their subscription expires.
* **Low Stock Alerts** — Admins receive instant alerts when a plan's config inventory runs out.
* **Receipt-to-Config Pipeline** — On approval, a config is automatically pulled from the plan's inventory, assigned, and delivered to the buyer.
* **Proxy Support** — Optional HTTP proxy for running in restricted network environments.
* **Docker Ready** — Full Docker + Docker Compose setup with a managed MySQL instance.

---

## 🗂️ Project Structure

<pre><code>telegram-vpn-bot/
├── main.py                        # Entry point: bot init, scheduler, polling
├── config.py                      # Loads all settings from .env
├── tasks.py                       # Scheduled task: expiry reminder notifications
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Docker image definition
├── docker-compose.yml             # Orchestrates bot + MySQL services
├── bot/
│   ├── handlers/
│   │   ├── admin_handlers.py      # All admin commands and receipt approval flows
│   │   └── user_handlers.py       # User flows: start, free config, purchase, referral
│   ├── keyboards/
│   │   ├── inline.py              # Inline keyboard builders
│   │   └── reply.py               # Reply keyboard (main menu)
│   └── middlewares/
│       └── force_join.py          # Blocks users who haven't joined the sponsor channel
├── database/
│   ├── connection.py              # Async SQLAlchemy engine & session factory
│   └── models.py                  # ORM models: User, Config, Plan
└── utils/
    └── broadcaster.py             # Rate-limit-aware broadcast utility</code></pre>

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11 |
| Telegram Framework | [aiogram 3](https://docs.aiogram.dev/en/latest/) |
| Database | MySQL 8 via [SQLAlchemy 2 (async)](https://docs.sqlalchemy.org/en/20/) + aiomysql |
| Task Scheduling | [APScheduler](https://apscheduler.readthedocs.io/en/stable/) |
| Containerization | Docker + Docker Compose |
| Config Management | `python-dotenv` |

---

## 🚀 Getting Started

### Prerequisites
* Python 3.11+ (or Docker)
* A MySQL 8 instance (or use the provided Docker Compose)
* A Telegram Bot Token from [@BotFather](https://t.me/BotFather)
* Your Telegram User ID (to set as admin)

---

### Option A: Run with Docker (Recommended)

**1. Clone the repository**
<pre><code>git clone https://github.com/AliMehrjou/telegram-vpn-bot.git
cd telegram-vpn-bot</code></pre>

**2. Create your `.env` file**
<pre><code>cp .env.example .env
# Then edit .env with your values</code></pre>

**3. Start the services**
<pre><code>docker-compose up -d --build</code></pre>

The bot and database will start automatically. The bot waits 10 seconds for MySQL to initialize before connecting.

---

### Option B: Run Locally (without Docker)

**1. Clone and install dependencies**
<pre><code>git clone https://github.com/AliMehrjou/telegram-vpn-bot.git
cd telegram-vpn-bot
pip install -r requirements.txt</code></pre>

**2. Set up your `.env` file** (see Configuration section below)

**3. Create the database**
<pre><code>CREATE DATABASE vpn_bot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;</code></pre>

**4. Run the bot**
<pre><code>python main.py</code></pre>

Tables are created automatically on startup.

---

## ⚙️ Configuration

Create a `.env` file in the project root with the following variables:

<pre><code># ─── Telegram ───────────────────────────────────────────
BOT_TOKEN=your_bot_token_here

# Comma-separated Telegram user IDs of administrators
ADMIN_IDS=123456789,987654321

# Telegram username shown to users for support (with @)
SUPPORT_ADMIN_USERNAME=@your_admin_username

# Optional: Display name for card payment instructions
ADMIN_NAME=John Doe

# ─── Sponsor Channel ────────────────────────────────────
# Numeric channel ID (e.g., -1001234567890) or @username
SPONSOR_CHANNEL_ID=-1001234567890
SPONSOR_CHANNEL_LINK=https://t.me/your_channel

# ─── Payment ────────────────────────────────────────────
# Bank card number shown to users during purchase
CARD_NUMBER=6037-XXXX-XXXX-XXXX

# URL of a tutorial on how to connect using the VPN config
SUB_LINK_TUTORIAL_URL=https://your-tutorial-link.com

# ─── Database ───────────────────────────────────────────
# Use "localhost" if running locally without Docker
DB_HOST=db
DB_PORT=3306
DB_NAME=vpn_bot
DB_USER=vpn_user
DB_PASSWORD=your_db_password

# ─── Optional ───────────────────────────────────────────
# HTTP proxy for running in restricted environments
PROXY_URL=http://user:pass@host:port</code></pre>

---

## 📖 Usage Guide

### For Admins

**1. Stock free configs**
<pre><code>/add_config vless://...</code></pre>
To add multiple at once, send each config on a new line after the command.

**2. Create a subscription plan**
<pre><code>/add_plan Name:30-Day VIP|Price:150000|Days:30|GB:100</code></pre>

**3. Edit an existing subscription plan** 🆕
Get the target plan's ID via `/plans_list`, then update any specific field without changing the rest (you can provide one or multiple fields separated by `|`):
* *Update price only:* `/edit_plan 1 Price:180000`
* *Update multiple fields:* `/edit_plan 2 Name:Premium V2|GB:120`
* *Update duration days:* `/edit_plan 1 Days:45`

**4. Stock the plan's inventory**
First, get the plan ID:
<pre><code>/plans_list</code></pre>
Then add configs for that plan:
<pre><code>/add_vip 1 vless://your-config-here</code></pre>

**5. Add reward configs for the referral system**
<pre><code>/add_reward invite vless://...    # 1-day reward for every 5 referrals
/add_reward purchase vless://...  # 1-month reward for every 10 purchases</code></pre>

**6. Approve or reject a purchase**
When a user submits a payment receipt, the bot forwards it to all admins with **Approve** and **Reject** buttons. On approval, a config is automatically assigned and sent to the user.

---

### For Users

1. Start the bot with `/start`.
2. Join the sponsor channel when prompted.
3. Use the main menu to:
   * **🎁 Get Free Config** — Claim a free config (subject to the admin-set cooldown).
   - **💰 Buy Config** — Select a plan, pay by card transfer, and submit a screenshot.
   - **My Services** — View your active subscriptions and config links.
   - **🤝 Referral Program** — Get your unique invite link and track your rewards.
   - **📞 Contact Admin** — Reach support directly.

---

## 🗄️ Database Models

**User**
* `telegram_id`, `username`, `balance`
* `last_free_config_date` — tracks the free config cooldown
* `invited_by`, `invite_count`, `purchase_invite_count` — powers the referral system

**Config**
* `config_string` — the raw VPN config text
* `type` — `free`, `paid`, `pool_{plan_id}`, `reward_invite`, `reward_purchase`
* `status` — `active`, `pending`, `disabled`
* `expire_date`, `total_traffic_gb`, `used_traffic_gb`
* `is_notified` — prevents duplicate expiry reminders

**Plan**
* `name`, `price`, `duration_days`, `volume_gb`

---

## 🔒 Security Notes

* Admin-only commands are protected at the router level using `ADMIN_IDS` — non-admins cannot trigger any admin handler.
* The `.env` file and `bot_settings.json` are excluded from version control via `.gitignore`.
* Per-user asyncio locks prevent race conditions on the free config endpoint.
* Database row-level locking (`with_for_update()`) prevents duplicate config assignment during concurrent purchases.

---

## 🤝 Contributing

Contributions are welcome! Please open an issue to discuss your idea before submitting a pull request. Make sure any new code follows the existing async patterns and includes appropriate error handling.

---

## 📄 License

This project is open source. See the repository for details.

```
