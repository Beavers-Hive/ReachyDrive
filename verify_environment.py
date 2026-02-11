import sys
import shutil
import requests
import os

def check_command(cmd):
    path = shutil.which(cmd)
    if path:
        print(f"[OK] Found command: {cmd} at {path}")
        return True
    else:
        print(f"[FAIL] Command not found: {cmd}")
        return False

def check_voicevox():
    try:
        response = requests.get("http://localhost:50021/version")
        if response.status_code == 200:
            print(f"[OK] Voicevox is running (Version: {response.json()})")
            return True
        else:
            print(f"[FAIL] Voicevox returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("[FAIL] Voicevox is NOT running on localhost:50021")
        return False

def check_imports():
    try:
        import google.genai
        import googlemaps
        import reachy_mini
        import mcp
        print("[OK] All python dependencies importable.")
        return True
    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        return False

if __name__ == "__main__":
    print("Verifying Environment...")
    check_imports()
    check_command("reachy-mini-daemon") # Check if installed by pip
    check_voicevox()
    
    # Check if .env loaded
    from dotenv import load_dotenv
    load_dotenv()
    if os.getenv("GEMINI_API_KEY"):
         print("[OK] GEMINI_API_KEY found.")
    else:
         print("[FAIL] GEMINI_API_KEY NOT found.")
    
    if os.getenv("GOOGLEMAP_API_KEY"):
         print("[OK] GOOGLEMAP_API_KEY found.")
    else:
         print("[FAIL] GOOGLEMAP_API_KEY NOT found.")
