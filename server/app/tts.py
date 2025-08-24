import pyttsx3
import base64
from io import BytesIO
import wave

class TextToSpeech:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 150)
        self.engine.setProperty("volume", 1.0)

    def synthesize(self, text: str) -> str:
        """Return audio as base64 WAV"""
        # Create in-memory WAV
        buffer = BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(22050)
            # Save speech to a temporary file
            temp_file = "temp_audio.wav"
            self.engine.save_to_file(text, temp_file)
            self.engine.runAndWait()
            # Read file and encode
            with open(temp_file, "rb") as f:
                audio_bytes = f.read()
        return base64.b64encode(audio_bytes).decode("utf-8")