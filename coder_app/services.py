import base64
import io
import json
import re

import requests
from django.conf import settings
from PIL import Image


# ─── Image Preprocessing ────────────────────────────────────────────────────

def preprocess_image(image_path: str) -> tuple[bytes, str]:
    """
    Resize image to max 2MP and compress to JPEG at 85% quality.
    Returns (bytes, mime_type).
    Keeps payload small while preserving enough detail for the VLM.
    """
    MAX_PIXELS = 2_000_000  # 2 megapixels

    with Image.open(image_path) as img:
        img = img.convert("RGB")  # strip alpha, ensure JPEG-compatible

        w, h = img.size
        if w * h > MAX_PIXELS:
            scale = (MAX_PIXELS / (w * h)) ** 0.5
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue(), "image/jpeg"


# ─── VLM Call ────────────────────────────────────────────────────────────────

def call_vlm(image_path: str) -> list[dict]:
    """
    Send a medical document image to Qwen 2.5 VL via OpenRouter.
    Returns a list of ICD-10 code dicts:
        [{"code": "J18.9", "description": "Pneumonia, unspecified organism"}, ...]
    Raises RuntimeError on failure.
    """
    # 1. Preprocess: resize to 2MP max, compress to JPEG
    image_bytes, mime = preprocess_image(image_path)
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # 2. Build prompt
    prompt = (
        "You are a certified medical coder. Analyse this medical document image "
        "and return ONLY a JSON array of ICD-10 diagnosis codes that apply. "
        "Each element must have exactly two keys: \"code\" and \"description\". "
        "Do not include any explanation, markdown, or extra text — just the raw JSON array. "
        "Example: [{\"code\": \"J18.9\", \"description\": \"Pneumonia, unspecified organism\"}]"
    )

    # 3. Call OpenRouter
    response = requests.post(
        settings.OPENROUTER_API_URL,
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        },
        timeout=60,
    )

    if not response.ok:
        raise RuntimeError(
            f"OpenRouter error {response.status_code}: {response.text[:300]}"
        )

    # 4. Extract and parse JSON from model output
    content = response.json()["choices"][0]["message"]["content"]

    # Strip any accidental markdown fences the model might add
    content = re.sub(r"```(?:json)?", "", content).strip().rstrip("`").strip()

    try:
        results = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"VLM returned non-JSON content: {content[:200]}") from exc

    if not isinstance(results, list):
        raise RuntimeError(f"Expected a JSON array, got: {type(results)}")

    return results
