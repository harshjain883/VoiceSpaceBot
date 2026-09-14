<div align="center">

  <h1>🎙️ ᴛᴇʟᴇɢʀᴀᴍ ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ (ᴛᴡᴀ)</h1>
  <p><b>A High-Fidelity, Zero-Lag Real-Time Voice Chat Telegram Mini App Powered by LiveKit SFU & FastAPI</b></p>

  <p>
    <img src="https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
    <img src="https://img.shields.io/badge/LiveKit-SFU-blueviolet?style=for-the-badge" alt="LiveKit" />
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge" alt="License" />
  </p>

  <p align="center">
    <a href="#features">Features</a> •
    <a href="#tech-stack">Tech Stack</a> •
    <a href="#environment-variables">Configuration</a> •
    <a href="#deployment">Deployment</a> •
    <a href="#license">License</a>
  </p>
</div>

---

## ⚡ Overview

**Telegram Voice Space** is a custom Telegram Mini App (TWA) designed to provide lag-free, high-definition audio spaces directly inside Telegram groups. By bypassing standard Telegram audio limitations and leveraging dedicated WebRTC SFU infrastructure, it delivers low-latency communication with granular group permission synchronization.

---

## ✨ Features

- 🎧 **Studio Quality HD Voice:** Powered by 48kHz Opus codec via WebRTC SFU (Selective Forwarding Unit).
- ⚡ **Near-Zero Latency:** Bypasses TCP bottlenecks using high-throughput UDP streaming.
- 🛡️ **Bot Owner Immunity:** Server-side validation completely blocks any attempts to kick or mute the designated bot owner.
- 👥 **Auto-Synced Admin Roles:** Automatically detects Telegram group administrators and awards them room-moderation powers.
- 💬 **In-Room Transient Chat:** Built-in side drawer for ephemeral real-time messaging during audio sessions.
- 👤 **Interactive Profile Cards:** Tap participant avatars to inspect identities and jump directly to native Telegram profiles.
- 🚪 **Contextual Exit Dialog:** Prompts group admins to either leave cleanly or terminate the entire space for all participants.
- 🎨 **Aesthetic Glassmorphic UI:** Modern dark UI styled with Tailwind CSS, Lucide icons, and Telegram haptic feedback.

---

## 🛠️ Tech Stack

| Layer | Technologies Used |
| :--- | :--- |
| **Bot Controller** | Python 3.10+, Pyrogram |
| **Backend & Signaling** | FastAPI, Uvicorn, WebRTC HMAC Signature Verifier |
| **Media Server (SFU)** | LiveKit Cloud / LiveKit Self-Hosted Server |
| **Frontend Mini App** | HTML5, Tailwind CSS, Telegram WebApp SDK, LiveKit Client SDK |

---

## ⚙️ Environment Variables

Create a `.env` file in the root directory and configure the following parameters:

```env
# --- Telegram Bot Configuration ---
API_ID=12345678
API_HASH=your_api_hash_here
BOT_TOKEN=your_bot_token_here
BOT_USERNAME=YourBotUsername

# --- Access & Security ---
# Comma-separated Telegram user IDs with permanent immunity
OWNER_ID=123456789

# --- Public Domain Routing ---
# Public URL of the FastAPI server (No trailing slash)
WEBAPP_URL=[https://your-domain.up.railway.app](https://your-domain.up.railway.app)

# --- LiveKit WebRTC SFU ---
# For Option 1 (Cloud): wss://your-project.livekit.cloud
# For Option 2 (VPS): ws://YOUR_VPS_IP:7880
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
