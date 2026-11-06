# Discord Music Bot (Python)

A modern, high-performance Discord music bot built with **Python 3.10+**, **discord.py**, and **yt-dlp**.

## Features

- 🎧 **YouTube Streaming**: Stream any YouTube URL or search query using `yt-dlp` and `ffmpeg`.
- ⚡ **Non-Blocking Architecture**: Extracts audio in separate executor threads to prevent Discord heartbeat lag.
- 💬 **Hybrid Commands**: Every command works both as a modern Discord Slash Command (`/play`) and as a Prefix command (`!play`).
- 📜 **Queue & Repeat System**: Add multiple tracks, view upcoming songs, skip tracks, and repeat single songs or the whole queue.
- 🎚️ **Playback Controls**: Pause, resume, stop, skip, repeat modes, volume adjustment, and leave.
- 💬 **Dynamic Channel Routing**: Bot always replies and sends playback updates to the text channel where commands were invoked.
- 🔌 **Auto-Disconnect**: Leaves voice channels after 3 minutes of inactivity to save server bandwidth.
- 🔒 **Secure Secrets**: Managed through `.env` with strict type validation.

## Prerequisites

1. **Python 3.10+** (tested on Python 3.14)
2. **FFmpeg** installed and accessible in your system `PATH` (or configured via `FFMPEG_PATH` in `.env`).
   - Check with: `ffmpeg -version`
3. **Discord Bot Token**:
   - Go to [Discord Developer Portal](https://discord.com/developers/applications).
   - Create an Application -> Bot.
   - Under **Privileged Gateway Intents**, enable:
     - **Message Content Intent**
     - **Server Members Intent** (optional, recommended)
   - Under **OAuth2 -> URL Generator**, select scopes `bot` and `applications.commands`, with permissions:
     - Send Messages, Embed Links, Connect, Speak, Use Voice Activity.

## Quickstart

1. **Clone & Setup Environment:**
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Environment:**
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in your `DISCORD_TOKEN`:
   ```env
   DISCORD_TOKEN=your_token_here
   COMMAND_PREFIX=!
   FFMPEG_PATH=ffmpeg
   DEFAULT_VOLUME=0.5
   ```

3. **Run the Bot:**
   ```bash
   python main.py
   ```

4. **Run Automated Tests:**
   ```bash
   pytest
   ```

## Running with Docker

### Using Docker Compose (Recommended)

1. Make sure your `.env` file is configured with your `DISCORD_TOKEN`.
2. Start the container in detached mode:
   ```bash
   docker compose up -d --build
   ```
3. View container logs:
   ```bash
   docker compose logs -f
   ```
4. Stop the bot:
   ```bash
   docker compose down
   ```

### Using Plain Docker

1. Build the image:
   ```bash
   docker build -t discord-music-bot:latest .
   ```
2. Run the container:
   ```bash
   docker run -d --name discord-music-bot --restart unless-stopped --env-file .env discord-music-bot:latest
   ```

## CI/CD Workflow

The repository includes a GitHub Actions workflow in `.github/workflows/docker-build.yml` that:
- Runs `pytest` on Python 3.12 with all system dependencies (`ffmpeg`, `libopus0`).
- Automatically builds and pushes multi-platform Docker images to **GitHub Container Registry (`ghcr.io`)** on every push to `main`/`master` or new tag release (`v*.*.*`).
- Validates Docker image builds without pushing on Pull Requests.

## Available Commands

| Command | Slash Command | Description |
|---|---|---|
| `!play <url or search>` | `/play <query>` | Joins voice channel and plays audio or enqueues it |
| `!pause` | `/pause` | Pauses audio playback |
| `!resume` | `/resume` | Resumes paused audio |
| `!skip` | `/skip` | Skips current track |
| `!stop` | `/stop` | Stops playback and clears the queue |
| `!queue` | `/queue` | Shows currently playing and up to 10 queued songs |
| `!nowplaying` (`!np`) | `/nowplaying` | Displays rich embed of current playing song |
| `!repeat [off\|song\|queue]` (`!loop`) | `/repeat [mode]` | Toggles or sets repeat mode (`off`, `song`, or `queue`) |
| `!volume <1-150>` | `/volume <percent>` | Adjusts volume percentage |
| `!leave` (`!dc`) | `/leave` | Leaves the voice channel and resets state |
