import whisper


def load_model(model_name: str = "base"):
    return whisper.load_model(model_name)


def process_voice_note(audio_path: str, model) -> str | None:
    try:
        result = model.transcribe(audio_path, fp16=False)
        return result["text"].strip()
    except Exception as e:
        print(f"Whisper transcription failed: {e}")
        return None
