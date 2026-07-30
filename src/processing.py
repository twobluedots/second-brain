import time
import whisper


def load_model(model_name: str = "base"):
    return whisper.load_model(model_name)


def process_voice_note(audio_path: str, model) -> tuple[str | None, int]:
    try:
        t0 = time.perf_counter()
        result = model.transcribe(audio_path, fp16=False)
        whisper_ms = int((time.perf_counter() - t0) * 1000)
        return result["text"].strip(), whisper_ms
    except Exception as e:
        print(f"Whisper transcription failed: {e}")
        return None, 0
