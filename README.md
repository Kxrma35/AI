# JOESTAR

**Voice-Enabled Personal AI Assistant**

A full-stack AI assistant with a cyberpunk HUD interface, real-time voice I/O, agentic tool calling, and semantic memory. JOESTAR listens, thinks, and talks back — powered by Groq's LLaMA model with edge TTS voice synthesis, deployed and accessible from any device.

---

## Demo

> Live cyberpunk HUD showing the 3D orb visualizer, system log, active tools, and real-time response display.

![JOESTAR Dashboard](https://raw.githubusercontent.com/Kxrma35/AI/main/joestar/assets/dashboard.png)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│                                                                 │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │              Browser (joestar.onrender.com)              │  │
│   │  Three.js Orb · HUD Panels · Voice Input · Text Input   │  │
│   └────────────────────────┬─────────────────────────────────┘  │
└────────────────────────────│────────────────────────────────────┘
                             │ WebSocket (wss://)
┌────────────────────────────▼────────────────────────────────────┐
│                        BRAIN LAYER                              │
│                    FastAPI (Render.com)                         │
│                                                                 │
│  main.py ──► brain.py (Groq LLaMA) ──┬──► get_weather()        │
│  (WebSocket        (agentic loop,     │    (OpenWeather API)    │
│   server)           tool calling)     │                         │
│                                       ├──► search_web()         │
│                                       │    (Serper API)         │
│                                       │                         │
│                                       ├──► get_schedule()       │
│                                       │    (iCal parser)        │
│                                       │                         │
│                                       ├──► read_file()          │
│                                       │    write_file()         │
│                                       │    (local filesystem)   │
│                                       │                         │
│  voice.py ◄───────────────────────────┘                         │
│  (Edge TTS synthesis)                                           │
│                                                                 │
│  memory.py                                                      │
│  (SQLite short-term + ChromaDB vector long-term)                │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Browser** captures voice via Web Speech API or text input and sends it over a WebSocket
2. **main.py** receives the message and passes it to `brain.py`
3. **brain.py** runs an agentic loop — calls Groq's LLaMA model, executes tool calls (weather, search, calendar, files), and loops until a final response is produced
4. **memory.py** retrieves semantically relevant past context from ChromaDB before each call, and saves the exchange after
5. **voice.py** synthesizes the text response to MP3 audio using Microsoft Edge TTS
6. **main.py** sends both the text and audio back to the browser over the WebSocket
7. **Browser** renders the typewriter text response, plays the audio, and animates the 3D orb

---

## Software Stack

| Layer | Language | Key Libraries |
|---|---|---|
| Frontend | JavaScript | Three.js, Web Speech API, WebSocket API |
| Backend | Python 3.11 | FastAPI, uvicorn, Groq SDK, edge-tts |
| AI / LLM | Python | groq (LLaMA 3.3 70B), tool calling |
| Memory | Python | chromadb, sqlite3 |
| Voice | Python | edge-tts (Microsoft Neural TTS) |
| Search | Python | httpx → Serper API |
| Weather | Python | httpx → OpenWeather API |
| Calendar | Python | icalendar, pytz |

### Python Dependencies

```
fastapi
uvicorn
groq
chromadb
httpx
python-dotenv
icalendar
pytz
edge-tts
```

---

## Project Structure

```
joestar/
├── main.py               # FastAPI app — WebSocket server, TTS dispatch
├── brain.py              # Agentic LLM loop with Groq tool calling
├── memory.py             # Short-term SQLite + long-term ChromaDB memory
├── voice.py              # Edge TTS speech synthesis
├── index.html            # Cyberpunk HUD frontend
├── script.js             # Three.js orb, WebSocket client, UI logic
├── style.css             # HUD styling — scanlines, panels, animations
├── tools/
│   ├── weather.py        # OpenWeather API integration
│   ├── web_search.py     # Serper API web search
│   ├── calendar.py       # iCal schedule reader
│   └── files.py          # Local file read/write
├── requirements.txt
└── Procfile              # Render.com deployment config
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- A [Groq API key](https://console.groq.com) (free tier available)
- A [Serper API key](https://serper.dev) for web search (optional)
- An [OpenWeather API key](https://openweathermap.org/api) for weather (optional)

### 1. Clone and set up the environment

```bash
git clone https://github.com/Kxrma35/AI.git
cd AI/joestar
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file inside the `joestar/` folder:

```env
GROQ_API_KEY=your_groq_key_here
SERPER_API_KEY=your_serper_key_here
OPENWEATHER_API_KEY=your_openweather_key_here
```

### 3. Start the server

```bash
cd joestar
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. Open the interface

```
http://localhost:8000
```

Type a command or click the microphone to speak. JOESTAR will respond in text and voice.

---

## Active Tools

| Tool | File | Description |
|---|---|---|
| Web Search | `tools/web_search.py` | Searches the web via Serper API for current information |
| Weather | `tools/weather.py` | Fetches live weather and forecast from OpenWeather |
| Calendar | `tools/calendar.py` | Reads today's events from a local `.ics` calendar file |
| File Read | `tools/files.py` | Reads the contents of any local file |
| File Write | `tools/files.py` | Writes or appends content to a local file |

---

## Memory System

JOESTAR maintains two layers of memory across conversations:

| Layer | Technology | Purpose |
|---|---|---|
| Short-term | SQLite (`joestar.db`) | Logs every exchange with timestamp |
| Long-term | ChromaDB (vector store) | Semantic search over past conversations for relevant context injection |

Before each LLM call, the top 3 semantically similar past exchanges are retrieved and injected as context. After each response, the new exchange is saved to both stores.

---

## Voice System

JOESTAR uses **Microsoft Edge TTS** (`en-GB-RyanNeural`) for voice output — a free, high-quality British neural voice with no API key required. The voice is streamed as MP3 audio and played directly in the browser.

Voice output is skipped automatically for:
- Responses over 600 characters
- Responses containing code blocks (` ``` `)

---

## Deployment

JOESTAR is deployed on [Render.com](https://render.com) (free tier).

**Live URL:** [https://joestar.onrender.com](https://joestar.onrender.com)

> Note: The free tier spins down after 15 minutes of inactivity. The first request after inactivity may take 30–50 seconds to wake the server.

To deploy your own instance:

1. Push the repo to GitHub
2. Create a new **Web Service** on Render
3. Set **Root Directory** to `joestar`
4. Set **Build Command** to `pip install -r requirements.txt`
5. Set **Start Command** to `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add your environment variables under **Environment**

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/ws` | WebSocket | Main AI conversation channel |
| `/search` | POST | Direct web search endpoint |
| `/health` | GET | Server health check |
| `/test-voice` | GET | Test TTS synthesis |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot connect to backend` | Ensure uvicorn is running and you're on `http://localhost:8000` not `0.0.0.0` |
| Voice not playing | Click anywhere on the page first — browsers require a user gesture before audio playback |
| Mic not working | Use Chrome or Edge — Firefox does not support the Web Speech API |
| `groq` import error | Activate your virtual environment and run `pip install groq` |
| Cold start on Render | Wait 30–50 seconds on first load — the free tier server is waking up |
| ChromaDB crash on startup | Ensure the `data/` directory is writable; it is created automatically on first run |

---

## Licence

MIT License — free to use, modify, and distribute with attribution.

---

## Contact

**Developer:** Kxrma35
**Email:** karmanjeruh5@gmail.com
**Phone:** +254 793 960 550
**GitHub:** [github.com/Kxrma35](https://github.com/Kxrma35)
