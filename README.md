Judo — Local assistant prototype

Overview
- Judo is a lightweight, local Python prototype agent for Windows that can:
  - create and open files
  - launch apps and open websites
  - attempt to close processes by name
  - send HTTP commands to devices (basic IoT hook)
  - optional voice input/output (requires additional dependencies)

Files
- judo.py: Main prototype script and interactive shell
- requirements.txt: Python dependencies

Quickstart (Windows)
1. Install Python 3.8+.
2. Create a virtual environment and activate it.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Create `judo_config.json` from `judo_config.example.json` and set your API or Home Assistant values if you want secure device integration.

4. Run the assistant interactively:

```powershell
python judo.py
```

Voice Mode
- Start voice-first mode:

```powershell
python judo.py voice
```

- Judo will listen for natural language commands and execute them:
  - "open youtube" → opens YouTube
  - "open xbox" → launches Xbox
  - "create file named test" → creates a file called test
  - "shut down the pc" → shuts down (with 10-second delay)
  - "open file C:\\path\\to\\file.txt" → opens the file
  - "tell me hello" → Judo speaks "hello"
  - "close notepad" → terminates the Notepad process

Commands
- `create <path>` — create a new file
- `openfile <path>` — open a file with the default application
- `openapp <command>` — launch an app or command
- `website <url>` — open URL in browser
- `close <process_name>` — terminate matching processes (requires psutil)
- `shutdown` — shutdown the PC (asks for confirmation)
- `speak <text>` — TTS output (requires pyttsx3)
- `listen` — listen once from microphone (requires SpeechRecognition + PyAudio)
- `device <url> [method] [json]` — send a secure HTTP request to a trusted device
- `ha_service <domain> <service> [json]` — call a Home Assistant service
- `ha_state <entity_id>` — fetch a Home Assistant entity state

Configuration
- Copy `judo_config.example.json` to `judo_config.json` and fill in values:
  - `device_api_key`: bearer token for device requests
  - `trusted_devices`: list of allowed device base URLs
  - `home_assistant_url`: Home Assistant base URL
  - `home_assistant_token`: long-lived access token for Home Assistant

Security
- Device control is protected by trusted device URLs and bearer token auth.
- Do not commit `judo_config.json` to source control if it contains secrets.

Notes & next steps
- This is a prototype. For a full "Jarvis"-style assistant you'll likely want:
  - secure authentication for device control
  - integrations with smart home APIs (e.g., Home Assistant, Philips Hue)
  - better process management for opening/closing files

Security & next steps
- Add authentication for device endpoints before enabling networked control.
- Integrate with Home Assistant or Philips Hue via their APIs for safer device management.
- Be careful with commands like `shutdown` and arbitrary device requests. Only run trusted commands and configure device endpoints you control.
