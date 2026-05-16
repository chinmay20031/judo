import os
import sys
import time
import json
from pathlib import Path
from subprocess import Popen

try:
    from vosk import Model, KaldiRecognizer
    import sounddevice as sd
except Exception as e:
    print("Missing dependency for wake-word service:", e)
    print("Install 'vosk' and 'sounddevice' and download a Vosk model.")
    sys.exit(1)

MODEL_PATH = os.environ.get("VOSK_MODEL_PATH", str(Path(__file__).parent / "model"))

if not os.path.exists(MODEL_PATH):
    print(f"Vosk model not found at {MODEL_PATH}. Download a model from https://alphacephei.com/vosk/models and set VOSK_MODEL_PATH environment variable.")
    sys.exit(1)

model = Model(MODEL_PATH)
samplerate = 16000
rec = KaldiRecognizer(model, samplerate)

def callback(indata, frames, time_info, status):
    if status:
        pass
    if rec.AcceptWaveform(indata.tobytes()):
        res = rec.Result()
        try:
            j = json.loads(res)
            text = j.get("text", "")
            if "judo" in text.lower():
                print("[service_judo] Wake word detected:", text)
                # Trigger judo to listen for follow-up command
                Popen([sys.executable, str(Path(__file__).parent / "judo.py"), "listen"])
                time.sleep(1)
        except Exception:
            pass

def run():
    with sd.RawInputStream(samplerate=samplerate, blocksize=8000, dtype='int16', channels=1, callback=callback):
        print("service_judo: Listening for wake word 'judo'... (Ctrl+C to stop)")
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("service_judo: stopped by user")

if __name__ == "__main__":
    run()
