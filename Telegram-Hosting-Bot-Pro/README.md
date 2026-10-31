# Telegram Bot Hosting Manager

Arabic Telegram control panel for upload/review/start/stop. Requires a **dedicated Linux VPS with Docker**. It is not compatible with ordinary shared hosting (including 000webhost). User-submitted Python is arbitrary code: container limits reduce risk but do not make hostile code safe. Run on a disposable/dedicated VPS, keep Docker patched, and never expose the Docker socket to users.

## Quick setup (Ubuntu VPS)
1. Install Docker Engine and Python 3.11+.
2. `git clone YOUR_REPOSITORY && cd Telegram-Hosting-Bot-Pro`
3. `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
4. `cp .env.example .env`
5. Generate secrets:
   - Manager token: create a separate bot with @BotFather.
   - Admin ID: your numeric Telegram ID.
   - Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   Put these values into `.env`. Never commit `.env`.
6. Add the manager service account to the Docker group (Docker group is effectively root). Prefer a dedicated VPS with no sensitive workloads.
7. `python main.py`

## How it works
Upload a `.py` file or ZIP containing `main.py`, `bot.py`, or `app.py` at the project root. Admin reviews the request in the Telegram admin panel, then Start launches a separate Docker container with CPU/RAM/PID limits, no Linux capabilities, non-root UID, read-only project mount, no published ports and no-new-privileges. The bot requires outbound network access to Telegram. Uploaded requirements are intentionally not installed automatically; build a reviewed custom image if dependencies are needed.

## Security limitations
- This is not a guarantee of strong isolation. A Docker daemon socket is highly privileged, and kernel/container escapes are possible.
- Do not host unknown code on a server containing personal, business, or production data.
- The manager currently stores encrypted bot tokens in SQLite. Protect `.env`, backups, and database files.
- Telegram bot tokens are secrets. If one is exposed, revoke it with @BotFather.
- ZIP extraction rejects traversal and symlinks and limits entry count and expanded size.
- Configure host firewall, SSH keys, updates, backups, monitoring and disk quotas.
- Use a separate VPS per trust boundary for higher assurance.
