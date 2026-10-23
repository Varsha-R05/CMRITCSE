
from faster_whisper import WhisperModel

# Load the model once when this module is imported.
# CPU with int8 quantization is suitable for your AMD Ryzen laptop.
model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)


def transcribe_audio(audio_path: str) -> str:
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        vad_filter=True
    )

    transcript = " ".join(
        segment.text.strip() for segment in segments
    ).strip()

    return transcript