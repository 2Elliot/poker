# Poker Tournament Web Interface Setup Guide

This guide will help you connect your JavaScript frontend with the Python backend.

## Project Structure

```
poker-tournament/
├── index.html           # Frontend HTML
├── styles.css          # Frontend CSS
├── scripts.js          # Frontend JavaScript (updated)
├── api_server.py       # NEW: Flask API server
├── requirements.txt    # NEW: Python dependencies
└── backend/
    ├── tournament_runner.py
    ├── tournament.py
    ├── bot_manager.py
    ├── bot_api.py
    ├── run_tournament.py
    ├── run_tournaments.py
    ├── engine/
    │   ├── __init__.py
    │   ├── cards.py
    │   └── poker_game.py
    └── players/
        ├── aggressive_bot.py
        ├── conservative_bot.py
        └── random_bot.py
```

## Installation Steps

### 1. Install Python Dependencies

Create a `requirements.txt` file with:

```txt
Flask==3.0.0
Flask-CORS==4.0.0
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 2. File Placement

1. Save `api_server.py` in your project root directory (same level as index.html)
2. Replace your existing `scripts.js` with the updated version
3. Keep your existing `index.html` and `styles.css` as-is

### 3. Backend Structure

Make sure your backend folder structure matches:
- All engine files go in `backend/engine/`
- All bot files go in `backend/players/`
- Tournament files go directly in `backend/`

## Running the Application

### Step 1: Start the API Server

Open a terminal and run:

```bash
python api_server.py
```

You should see:
```
Starting Poker Tournament API Server...
API will be available at http://localhost:5000
```

Leave this terminal running.

### Step 2: Open the Web Interface

Open `index.html` in your browser. You can either:
- Double-click the file
- Use a local web server (recommended): `python -m http.server 8000`
- Use Live Server in VS Code

## How It Works

### Backend API (api_server.py)

The Flask server provides these endpoints:

- `GET /api/bots` - Lists all available bots from `backend/players/`
- `POST /api/tournament/init` - Initializes a tournament with selected bots
- `POST /api/tournament/step` - Executes one hand of poker
- `GET /api/tournament/state` - Gets current tournament state
- `GET /api/logs/stream` - Server-sent events for real-time logs
- `POST /api/tournament/reset` - Resets the tournament

### Frontend (scripts.js)

The updated JavaScript:

1. **Loads bots** from the backend instead of hardcoded list
2. **Initializes tournament** by sending selected bots to backend
3. **Steps through hands** by calling the backend API
4. **Streams logs** from Python logging to the console
5. **Updates display** based on backend tournament state

### Communication Flow

```
Frontend (Browser)
    ↓ HTTP Request
Flask API Server (Python)
    ↓ Function Call
Tournament Runner (Python)
    ↓ Uses
Bot Manager + Poker Engine
    ↓ Returns State
Flask API Server
    ↓ JSON Response
Frontend (Updates UI)
```

## Usage

1. **Start API server** (see Step 1 above)
2. **Open web interface** in browser
3. **Click bots** from left sidebar to add them to the table
4. **Click "Play"** to start the tournament
5. **Watch** as hands play out automatically
6. **View statistics** in the Statistics tab

## Controls

- **Play/Pause**: Start or pause the tournament
- **Step**: Execute one hand at a time (manual mode)
- **Reset**: Reset all chip counts to starting values
- **Clear Table**: Remove all bots from the table
- **Speed**: Adjust tournament speed (0.25x to 4x)

## Troubleshooting

### "Failed to connect to backend"

- Make sure `api_server.py` is running
- Check that it's running on port 5000
- Verify no firewall is blocking localhost:5000

### "Error loading bots"

- Check that bot files exist in `backend/players/`
- Verify bot files inherit from `PokerBotAPI`
- Check Python console for error messages

### Bots not loading

- Make sure all bot files have the `.py` extension
- Verify they're in the correct directory: `backend/players/`
- Check that each bot class inherits from `PokerBotAPI`

### Tournament not advancing

- Check the Python console (where api_server.py is running) for errors
- Verify at least 2 bots are at the table
- Try clicking "Step" to advance one hand manually

## Adding New Bots

1. Create a new `.py` file in `backend/players/`
2. Implement a class that inherits from `PokerBotAPI`
3. Implement required methods: `get_action()` and `hand_complete()`
4. Restart the API server
5. Refresh the browser - new bot should appear in the list

## Advanced Configuration

Edit the `initializeTournament()` function in `scripts.js` to change:
- `starting_chips`: Starting chip count (default: 1000)
- `small_blind`: Small blind amount (default: 10)
- `big_blind`: Big blind amount (default: 20)
- `blind_increase_interval`: Hands between blind increases (default: 10)

## Notes

- The frontend controls the tournament pace (play/pause/step)
- The backend handles all poker logic and bot execution
- Logs are streamed in real-time from Python to the browser console
- Tournament state is maintained on the backend
- Statistics are calculated on the frontend based on chip changes

## Need Help?

Check the browser console (F12) and Python console for error messages.