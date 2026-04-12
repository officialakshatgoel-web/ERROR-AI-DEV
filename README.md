# ❌ Error AI: Advanced Uncensored Proxy Platform

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-Production--Ready-success.svg)
![AI](https://img.shields.io/badge/AI-Dolphin--Llama3-purple.svg)

**Error AI** is a commercial-grade, fully uncensored AI proxy platform designed for high-performance deployments. It bridges the gap between local AI power (Ollama) and professional-grade managed services.

---

## 🚀 Key Features

- **🛡️ Uncensored Prompting**: Pre-baked with "God-Tier" system rules to ensure 100% unrestricted responses.
- **⚡ Real-Time Streaming**: Asynchronous token delivery for that snappy, word-by-word ChatGPT experience.
- **👑 Advanced Admin Bot**: Fully managed via Telegram. Add/Remove admins, set global pricing, and monitor all users live.
- **📊 Managed Quotas**: Automatic daily request resets and custom lifetime limits per user.
- **✨ Premium Landing Page**: Sleek, glassmorphism-based web interface with live stats and documentation.
- **📖 Integrated API Docs**: Beautiful, copy-paste ready documentation for cURL and OpenAI-compatible clients.
- **🤖 Persona Mimicry**: Adaptive context injection to mirror user speaking styles.

---

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **AI Engine**: Ollama (Dolphin-Llama3)
- **Database**: SQLite (SQLAlchemy 2.0+)
- ** मैनेजमेंट**: Aiogram 3.x (Telegram Bot)
- **Frontend**: Vanilla HTML5 / CSS3 (Modern Glassmorphism)

---

## 📦 Quick Deployment

The project is optimized for **Railway** via Docker.

1. **Push** this repo to your private GitHub.
2. **Deploy** on Railway using the provided `Dockerfile`.
3. **Set Variables**:
   - `TELEGRAM_BOT_TOKEN`: Get from @BotFather.
4. **Volumes**: Mount a volume at `/app/data` to persist your database.
5. **Resources**: Assign at least 8GB RAM for optimal AI performance.

---

## 📜 API Documentation

Once hosted, visit the `/documentation` endpoint on your domain for full integration details. The API is a drop-in replacement for OpenAI:

```bash
curl https://errorapi.dev/v1/chat/completions \
  -H "Authorization: Bearer YOUR_KEY" \
  -d '{"model": "dolphin-llama3", "messages": [{"role": "user", "content": "How to...?"}]}'
```

---

## 🤝 Community
Developed and maintained by **Error Community**. 

*Unfiltered intelligence. Unlimited power.*
