# robot/audio.py
import subprocess
import os
import tempfile
import requests
from config import WINDOWS_SERVER_BASE

def play_audio_message(text):
    """
    Convert text to speech and play it using espeak with ALSA output.
    This plays on the robot's speaker using ALSA configuration.
    """
    try:
        # Using espeak with ALSA output device (matching picture taken sound)
        espeak_cmd = f'espeak "{text}" --stdout | aplay -D plughw:1,0 2>/dev/null'
        subprocess.run(espeak_cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error playing audio: {e}")
        return False
    except FileNotFoundError as e:
        print(f"Audio tool not found: {e}. Install with: sudo apt-get install espeak alsa-utils")
        return False

def send_text_to_server(text, reset_history=False):
    """
    Send text message to Windows server for AI processing.
    Returns the AI response.
    """
    try:
        url = f"{WINDOWS_SERVER_BASE}/chat/text"
        payload = {
            "message": text,
            "reset_history": reset_history
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        return {
            "success": True,
            "user_message": data.get("user_message"),
            "ai_response": data.get("ai_response"),
            "conversation_length": data.get("conversation_length")
        }
    except requests.exceptions.RequestException as e:
        print(f"Error sending text to server: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def send_audio_to_server(audio_file_path):
    """
    Send audio file to Windows server for transcription and AI processing.
    Returns the transcribed text and AI response.
    """
    try:
        url = f"{WINDOWS_SERVER_BASE}/chat/audio"
        
        with open(audio_file_path, 'rb') as audio_file:
            files = {'audio': ('recording.wav', audio_file, 'audio/wav')}
            response = requests.post(url, files=files, timeout=30)
            response.raise_for_status()
        
        data = response.json()
        return {
            "success": True,
            "transcribed_text": data.get("transcribed_text"),
            "ai_response": data.get("ai_response"),
            "conversation_length": data.get("conversation_length")
        }
    except requests.exceptions.RequestException as e:
        print(f"Error sending audio to server: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def reset_conversation():
    """Reset the conversation history on the server."""
    try:
        url = f"{WINDOWS_SERVER_BASE}/chat/reset"
        response = requests.post(url, timeout=5)
        response.raise_for_status()
        return {"success": True, "message": "Conversation reset"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}
