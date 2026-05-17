import os
import sys
import subprocess
import webbrowser
import threading
import time
import json
from pathlib import Path

# Set default Vosk model path - prioritize local model over environment variable
local_model = Path(__file__).parent / "model" / "vosk-model-small-en-us-0.15"
if local_model.exists():
    os.environ["VOSK_MODEL_PATH"] = str(local_model)
elif not os.environ.get("VOSK_MODEL_PATH") or not Path(os.environ.get("VOSK_MODEL_PATH", "")).exists():
    # If env var is set but invalid, clear it
    if "VOSK_MODEL_PATH" in os.environ:
        del os.environ["VOSK_MODEL_PATH"]

try:
    import psutil
except Exception:
    psutil = None

try:
    import requests
except Exception:
    requests = None
try:
    import graphify_integration as gfy
except Exception:
    gfy = None

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

SOUNDDEVICE_AVAILABLE = False
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except Exception:
    sd = None
    SOUNDDEVICE_AVAILABLE = False

# Vosk fallback (uses sounddevice) to avoid PyAudio build issues on Windows
VOSK_AVAILABLE = False
try:
    from vosk import Model, KaldiRecognizer
    import numpy as np
    if SOUNDDEVICE_AVAILABLE:
        VOSK_AVAILABLE = True
    else:
        VOSK_AVAILABLE = False
except Exception:
    VOSK_AVAILABLE = False

VOICE_AVAILABLE = sr is not None and SOUNDDEVICE_AVAILABLE or VOSK_AVAILABLE

# Common app name aliases -> command to run on Windows
APP_ALIASES = {
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "explorer": "explorer",
    "edge": "msedge",
    "chrome": "chrome",
    "firefox": "firefox",
    "vscode": "code",
    "code": "code",
    "spotify": "spotify",
    "slack": "slack",
    "steam": "steam",
}

# Default allowed apps (can be extended via judo_config.json `allowed_apps` comma-separated)
ALLOWED_APPS = set(APP_ALIASES.values())


def is_app_allowed(name):
    """Return True if the app/command is permitted to be launched via voice."""
    if not name:
        return False
    n = name.strip().lower()
    # allow obvious executables or paths
    if (n.startswith("http") or "." in n or n.endswith(".exe")
            or n.startswith("\\") or "/" in n or "\\\\" in n):
        return True
    # check aliases and config
    allowed = set(ALLOWED_APPS)
    cfg = get_config("allowed_apps")
    if cfg:
        if isinstance(cfg, str):
            for item in cfg.split(","):
                allowed.add(item.strip().lower())
        elif isinstance(cfg, list):
            for item in cfg:
                allowed.add(str(item).strip().lower())
    # match by first token
    first = n.split()[0]
    return first in allowed


def save_config(cfg):
    """Persist configuration to `judo_config.json`. Merges with existing file."""
    try:
        path = Path(__file__).parent / "judo_config.json"
        existing = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = {}
        merged = {**existing, **cfg}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
        return True
    except Exception as e:
        print("Failed to save config:", e)
        return False


def speak(text):
    if pyttsx3 is None:
        print("SPEAK:", text)
        return
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()


def listen_once(timeout=5, verbose=True):
    # Preferred: SpeechRecognition + sounddevice (Google) when PyAudio is unavailable
    if sr is not None and SOUNDDEVICE_AVAILABLE:
        if verbose:
            print("[VOICE] Trying SpeechRecognition with sounddevice...")
        try:
            r = sr.Recognizer()
            duration = max(1, int(timeout))
            if verbose:
                print("[VOICE] Recording audio for {} seconds...".format(duration))
            recording = sd.rec(int(duration * 16000), samplerate=16000, channels=1, dtype='int16')
            sd.wait()
            audio_data = sr.AudioData(recording.tobytes(), 16000, 2)
            if verbose:
                print("[VOICE] Processing audio with Google...")
            return r.recognize_google(audio_data)
        except Exception as e:
            if verbose:
                print("[VOICE] SpeechRecognition via sounddevice failed: {}: {}".format(type(e).__name__, e))

    # Fallback: SpeechRecognition with microphone if available
    if sr is not None:
        if verbose:
            print("[VOICE] Trying SpeechRecognition with microphone...")
        try:
            r = sr.Recognizer()
            with sr.Microphone() as source:
                if verbose:
                    print("[VOICE] Adjusting for ambient noise...")
                r.adjust_for_ambient_noise(source, duration=0.5)
                if verbose:
                    print("[VOICE] Listening (timeout={}s)...".format(timeout))
                audio = r.listen(source, timeout=timeout)
                if verbose:
                    print("[VOICE] Processing audio with Google...")
                return r.recognize_google(audio)
        except Exception as e:
            if verbose:
                print("[VOICE] SpeechRecognition failed: {}: {}".format(type(e).__name__, e))

    # Fallback: Vosk + sounddevice (requires a Vosk model)
    if VOSK_AVAILABLE:
        if verbose:
            print("[VOICE] Trying Vosk + sounddevice...")
        # Try VOSK_MODEL_PATH env var, then common locations
        model_path = os.environ.get("VOSK_MODEL_PATH")
        if not model_path:
            candidates = [
                str(Path(__file__).parent / "model" / "vosk-model-small-en-us-0.15"),
                str(Path(__file__).parent / "model"),
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    model_path = cand
                    break
        if verbose:
            print("[VOICE] Model path: {}".format(model_path))
        if not model_path or not os.path.exists(model_path):
            if verbose:
                print("[VOICE] Model path does not exist! Download from https://alphacephei.com/vosk/models/")
            return None
        try:
            if verbose:
                print("[VOICE] Loading Vosk model...")
            model = Model(model_path)
            rec = KaldiRecognizer(model, 16000)
            duration = max(1, int(timeout))
            if verbose:
                print("[VOICE] Recording audio for {} seconds...".format(duration))
            recording = sd.rec(int(duration * 16000), samplerate=16000, channels=1, dtype='int16')
            sd.wait()
            if verbose:
                print("[VOICE] Processing with Vosk...")
            data = recording.tobytes()
            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                return res.get("text")
            else:
                res = json.loads(rec.PartialResult())
                return res.get("partial")
        except Exception as e:
            if verbose:
                print("[VOICE] Vosk failed: {}: {}".format(type(e).__name__, e))
            return None

    if verbose:
        print("[VOICE] No voice method available!")
    return None


def load_config():
    config_path = Path(__file__).parent / "judo_config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            print("Failed to load judo_config.json:", exc)
    return {}


def get_config(key, default=None):
    env_key = f"JUDO_{key.upper()}"
    if env_key in os.environ:
        return os.environ[env_key]
    return load_config().get(key, default)


def get_auth_headers():
    headers = {}
    ha_token = get_config("home_assistant_token")
    api_key = get_config("device_api_key")
    if ha_token:
        headers["Authorization"] = f"Bearer {ha_token}"
    elif api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def is_trusted_device(url):
    trusted = get_config("trusted_devices") or []
    if isinstance(trusted, str):
        trusted = [trusted]
    return any(url.startswith(entry) for entry in trusted)


def strip_wake_word(text):
    """Remove the wake phrase from the incoming command text."""
    if not text:
        return text, False
    text = text.strip()
    lower = text.lower()
    wake_phrases = ["hey do then", "hey do", "hey then", "hey", "a"]
    for wake in wake_phrases:
        if lower == wake:
            return "", True
        if lower.startswith(wake + " "):
            return text[len(wake):].strip(), True
    return text, False


def parse_voice_command(text):
    """Parse natural language commands into executable actions."""
    if not text:
        return None, None
    text_lower = text.lower().strip()
    
    # File commands
    if "create file" in text_lower or "create a file" in text_lower or "new file" in text_lower:
        words = text.split()
        if "named" in words or "call" in words:
            idx = words.index("named") if "named" in words else words.index("call")
            filename = " ".join(words[idx+1:])
            return "create", filename
    if "open file" in text_lower or "open the file" in text_lower:
        words = text.split()
        path = " ".join(words[3:]) if len(words) > 3 else ""
        return "openfile", path
    
    # App commands
    if "open" in text_lower or "launch" in text_lower or "start" in text_lower:
        keywords = ["open", "launch", "start"]
        for kw in keywords:
            if kw in text_lower:
                idx = text_lower.index(kw)
                app = text[idx + len(kw):].strip()
                # remove common filler words
                for f in ("the", "a", "my", "please", "to", "that", "which"):
                    app = app.replace(f" {f} ", " ")
                app = app.strip()
                # direct website service shortcuts
                if "youtube" in app:
                    return "website", "https://www.youtube.com"
                if "google" in app and "search" not in app:
                    return "website", "https://www.google.com"
                if "facebook" in app:
                    return "website", "https://www.facebook.com"
                if "twitter" in app:
                    return "website", "https://www.twitter.com"
                # URL detection: contains a dot-like token or starts with http/www
                if app.startswith("http") or app.startswith("www") or "." in app:
                    if not app.startswith("http"):
                        app = "https://" + app
                    return "website", app
                # try mapping common app aliases, prefer the first word or two
                parts = app.split()
                candidate = " ".join(parts[:2]) if len(parts) > 1 else parts[0] if parts else ""
                cand_key = candidate.split()[0].lower() if candidate else ""
                if cand_key in APP_ALIASES:
                    return "openapp", APP_ALIASES[cand_key]
                return "openapp", candidate
    if "xbox" in text_lower:
        return "openapp", "xbox"
    if "youtube" in text_lower:
        return "website", "https://www.youtube.com"
    if "google" in text_lower and "search" not in text_lower:
        return "website", "https://www.google.com"
    if "facebook" in text_lower:
        return "website", "https://www.facebook.com"
    if "twitter" in text_lower:
        return "website", "https://www.twitter.com"
    
    # Close/shutdown commands
    if "close" in text_lower or "shut down" in text_lower or "shutdown" in text_lower or "turn off" in text_lower:
        if "process" in text_lower or "application" in text_lower or "app" in text_lower:
            words = text.split()
            app_name = " ".join(words[words.index("process" if "process" in words else ("application" if "application" in words else "app"))+1:])
            return "close", app_name
        if "pc" in text_lower or "computer" in text_lower or "system" in text_lower:
            return "shutdown", ""
    
    # Website commands
    if "go to" in text_lower or "visit" in text_lower or "website" in text_lower:
        for kw in ["go to", "visit", "website"]:
            if kw in text_lower:
                idx = text_lower.index(kw)
                url = text[idx + len(kw):].strip()
                if not url.startswith("http"):
                    url = "https://" + url
                return "website", url
    
    # Speech commands
    if "say" in text_lower or "speak" in text_lower or "tell" in text_lower:
        for kw in ["say", "speak", "tell"]:
            if kw in text_lower:
                idx = text_lower.index(kw)
                msg = text[idx + len(kw):].strip()
                return "speak", msg
    
    # Graphify commands
    if "graphify" in text_lower or "create graph" in text_lower or "create a graph" in text_lower or "make a graph" in text_lower:
        # try to extract a path
        words = text.split()
        # crude: last word as path
        path = words[-1]
        return "graphify", path
    
    return None, None


def execute_voice_command(command, arg):
    """Execute parsed voice command."""
    if command == "create":
        create_file(arg)
        speak(f"Created file {arg}")
    elif command == "openfile":
        open_file(arg)
        speak(f"Opened {arg}")
    elif command == "openapp":
        # enforce allowed apps for voice-triggered launches
        if not is_app_allowed(arg):
            speak(f"Refusing to open {arg}. Add it to allowed_apps in judo_config.json to enable this action.")
            return
        open_app(arg)
        speak(f"Opening {arg}")
    elif command == "website":
        open_website(arg)
        speak(f"Opening {arg}")
    elif command == "close":
        close_by_process_name(arg)
        speak(f"Closing {arg}")
    elif command == "shutdown":
        speak("Shutdown requested. Say 'confirm shutdown' to proceed, or say 'cancel'.")
        # listen for a short confirmation
        resp = listen_once(timeout=7)
        if resp and "confirm" in resp.lower():
            speak("Shutting down the PC in 10 seconds")
            time.sleep(10)
            shutdown(confirm=True)
        else:
            speak("Shutdown cancelled")
    elif command == "speak":
        speak(arg)
    elif command == "graphify":
        if gfy is None:
            speak("Graphify integration is not installed")
            return
        speak(f"Running graphify on {arg}")
        success, out = gfy.run_graphify(arg)
        if success:
            speak(f"Graph created at {out}")
        else:
            speak(f"Graphify failed: {out}")
    else:
        speak("Command not recognized")


def voice_loop():
    """Continuous voice command loop."""
    # Clean up stray temp files silently
    try:
        temp_file = Path(__file__).parent / "tempCodeRunnerFile.py"
        if temp_file.exists():
            temp_file.unlink()
    except Exception:
        pass
    
    if not VOICE_AVAILABLE:
        print("Voice not available. Install SpeechRecognition/pyttsx3 or install Vosk, sounddevice, and a Vosk model.")
        return
    
    if pyttsx3 is None:
        print("TTS not available, voice output will be printed instead.")
    
    speak("Judo voice mode active")
    while True:
        try:
            speak("Listening")
            text = listen_once(timeout=10)
            if not text:
                speak("Sorry, I did not hear that")
                continue
            
            print(f"You said: {text}")
            command, arg = parse_voice_command(text)
            if command:
                execute_voice_command(command, arg)
                continue
            else:
                speak("I did not understand that command")
                continue
        except KeyboardInterrupt:
            speak("Goodbye")
            break
        except Exception as e:
            print("Error:", e)
            speak("An error occurred")
            break


def create_file(path, content=""):
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created file: {path}")


def open_file(path):
    if not os.path.exists(path):
        print("File not found:", path)
        return
    if sys.platform.startswith("win"):
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path])
    print(f"Opened: {path}")


def open_app(command_or_path):
    try:
        if sys.platform.startswith("win"):
            # Try start for UWP/protocol handlers
            subprocess.Popen(["cmd", "/c", "start", "", command_or_path], shell=False)
        else:
            subprocess.Popen(command_or_path.split())
        print(f"Launched app/command: {command_or_path}")
    except Exception as e:
        print("Failed to launch:", e)


def open_website(url):
    webbrowser.open(url)
    print("Opened website:", url)


def shutdown(confirm=False):
    if not confirm:
        ans = input("Are you sure you want to shutdown the PC? (yes/no): ")
        if ans.strip().lower() != "yes":
            print("Shutdown cancelled")
            return
    if sys.platform.startswith("win"):
        subprocess.Popen(["shutdown", "/s", "/t", "0"], shell=False)
    else:
        subprocess.Popen(["shutdown", "-h", "now"]) 


def close_by_process_name(name):
    if psutil is None:
        print("psutil not installed; can't close processes reliably")
        return
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if name.lower() in (p.info.get("name") or "").lower() or any(name.lower() in (c or "").lower() for c in (p.info.get("cmdline") or [])):
                print("Terminating pid", p.info["pid"], p.info.get("name"))
                p.terminate()
        except Exception:
            pass


def send_device_command(url, method="POST", data=None, headers=None, require_trusted=True):
    if requests is None:
        print("requests not installed; cannot send device commands")
        return None
    if require_trusted and not is_trusted_device(url):
        print("Refusing to send command to untrusted device. Add the URL to trusted_devices in judo_config.json or JUDO_TRUSTED_DEVICES.")
        return None
    headers = headers or {}
    headers.update(get_auth_headers())
    try:
        if method.upper() == "POST":
            r = requests.post(url, json=data, headers=headers, timeout=10)
        else:
            r = requests.get(url, params=data, headers=headers, timeout=10)
        print("Device response:", r.status_code)
        return r
    except Exception as e:
        print("Device command failed:", e)
        return None


def home_assistant_service(domain, service, payload=None):
    base_url = get_config("home_assistant_url")
    if not base_url:
        print("Home Assistant URL not configured. Set home_assistant_url in judo_config.json or JUDO_HOME_ASSISTANT_URL.")
        return None
    headers = get_auth_headers()
    if "Authorization" not in headers:
        print("Home Assistant token not configured. Set home_assistant_token in judo_config.json or JUDO_HOME_ASSISTANT_TOKEN.")
        return None
    endpoint = f"{base_url.rstrip('/')}/api/services/{domain}/{service}"
    try:
        r = requests.post(endpoint, json=payload or {}, headers={**headers, "Content-Type": "application/json"}, timeout=10)
        print("Home Assistant response:", r.status_code, r.text)
        return r
    except Exception as e:
        print("Home Assistant service call failed:", e)
        return None


def home_assistant_state(entity_id):
    base_url = get_config("home_assistant_url")
    if not base_url:
        print("Home Assistant URL not configured. Set home_assistant_url in judo_config.json or JUDO_HOME_ASSISTANT_URL.")
        return None
    headers = get_auth_headers()
    if "Authorization" not in headers:
        print("Home Assistant token not configured. Set home_assistant_token in judo_config.json or JUDO_HOME_ASSISTANT_TOKEN.")
        return None
    endpoint = f"{base_url.rstrip('/')}/api/states/{entity_id}"
    try:
        r = requests.get(endpoint, headers=headers, timeout=10)
        print("Home Assistant state response:", r.status_code, r.text)
        return r
    except Exception as e:
        print("Home Assistant state request failed:", e)
        return None


def interactive_loop():
    print("Judo — simple prototype. Type 'help' for commands.")
    while True:
        try:
            cmd = input("Judo> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not cmd:
            continue
        if cmd in ("exit", "quit"):
            break
        if cmd == "help":
            print("Commands: create <path>, openfile <path>, openapp <cmd>, website <url>, close <process_name>, shutdown, speak <text>, listen, device <url> [method] [json], ha_service <domain> <service> [json], ha_state <entity_id>")
            continue
        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        if action == "create":
            if not arg:
                print("Usage: create <path>")
                continue
            create_file(arg)
        elif action == "openfile":
            open_file(arg)
        elif action == "openapp":
            open_app(arg)
        elif action == "website":
            open_website(arg)
        elif action == "close":
            close_by_process_name(arg)
        elif action == "shutdown":
            shutdown()
        elif action == "speak":
            speak(arg)
        elif action == "listen":
            print("Listening... (may require PyAudio and SpeechRecognition)")
            text = listen_once()
            print("Heard:", text)
        elif action == "allowapp":
            parts = arg.split(maxsplit=1)
            if not parts:
                print("Usage: allowapp add|remove|list <app>")
                continue
            sub = parts[0].lower()
            val = parts[1].strip() if len(parts) > 1 else ""
            cfg = load_config()
            allowed = cfg.get("allowed_apps") or []
            if isinstance(allowed, str):
                allowed = [x.strip() for x in allowed.split(",") if x.strip()]
            if sub == "list":
                print("Allowed apps:", ", ".join(allowed or list(ALLOWED_APPS)))
            elif sub == "add":
                if not val:
                    print("Usage: allowapp add <app>")
                    continue
                if val.lower() in [x.lower() for x in allowed]:
                    print(val, "already allowed")
                    continue
                allowed.append(val)
                if save_config({"allowed_apps": allowed}):
                    print("Added and saved allowed app:", val)
                else:
                    print("Failed to save allowed app")
            elif sub == "remove":
                if not val:
                    print("Usage: allowapp remove <app>")
                    continue
                allowed = [x for x in allowed if x.lower() != val.lower()]
                if save_config({"allowed_apps": allowed}):
                    print("Removed and saved:", val)
                else:
                    print("Failed to save allowed app")
            else:
                print("Unknown subcommand for allowapp. Use add|remove|list")
        elif action == "device":
            parts = arg.split(maxsplit=2)
            url = parts[0] if parts else ""
            method = parts[1] if len(parts) > 1 else "POST"
            payload = None
            if len(parts) == 3:
                try:
                    payload = json.loads(parts[2])
                except json.JSONDecodeError:
                    payload = parts[2]
            send_device_command(url, method=method, data=payload)
        elif action == "ha_service":
            parts = arg.split(maxsplit=2)
            if len(parts) < 2:
                print("Usage: ha_service <domain> <service> [json]")
                continue
            domain = parts[0]
            service = parts[1]
            payload = None
            if len(parts) == 3:
                try:
                    payload = json.loads(parts[2])
                except json.JSONDecodeError:
                    print("Invalid JSON payload for Home Assistant service call.")
                    continue
            home_assistant_service(domain, service, payload)
        elif action == "ha_state":
            if not arg:
                print("Usage: ha_state <entity_id>")
                continue
            home_assistant_state(arg)
        elif action == "graphify":
            if not arg:
                print("Usage: graphify <path>")
                continue
            if gfy is None:
                print("Graphify integration not installed. Add graphifyy to your environment.")
                continue
            print("Running graphify on", arg)
            ok, out = gfy.run_graphify(arg)
            if ok:
                print("Graph output:", out)
            else:
                print("Graphify failed:", out)
        else:
            print("Unknown command. Type 'help' for list.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # quick one-off commands: e.g., python judo.py openfile "C:\\file.txt"
        cmd = sys.argv[1].lower()
        arg = sys.argv[2] if len(sys.argv) > 2 else ""
        if cmd == "voice":
            voice_loop()
        elif cmd == "create":
            create_file(arg)
        elif cmd == "openfile":
            open_file(arg)
        elif cmd == "openapp":
            open_app(arg)
        elif cmd == "website":
            open_website(arg)
        elif cmd == "shutdown":
            shutdown(confirm=True)
        elif cmd == "listen":
            text = listen_once()
            print("Heard:", text)
            command, arg = parse_voice_command(text)
            if command:
                execute_voice_command(command, arg)
        else:
            print("Unknown quick command")
    else:
        interactive_loop()
