from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os, re, json, base64
from io import BytesIO
from typing import List
from PIL import Image
import pyperclip as pc
from openai import OpenAI
from dotenv import load_dotenv
import sys

# -------------------
# Config
# -------------------
load_dotenv()
app = Flask(__name__)
CORS(app)

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY not set")
client = OpenAI(api_key=API_KEY)

MODEL_MAIN = os.getenv("OPENAI_MODEL", "gpt-4o")
ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "bmp", "gif"}

# -------------------
# System prompts
# -------------------
CODE_STRICT_SYSTEM = """
You are a code generator. Follow these rules:
1. Return only raw code
2. Never add comments
3. Never include explanations
4. Never use markdown formatting
5. Maintain original code indentation
"""

TEST_STRICT_SYSTEM_PLAIN = """
You solve tests from text or screenshots.
Return ONLY the final answer(s). Do NOT ask questions. Do NOT add any other words, punctuation, or markdown.

Rules:
- Multiple choice: output ONLY the option identifier (e.g., A or 2). If multiple questions, output one answer per line.
- Short text: output ONLY the final word/number/phrase.
- Fill-in code: output ONLY the code (no backticks).
- If multiple questions, output one answer per line in order.
If information seems incomplete, give your best single answer; do NOT ask for more info.
"""

# -------------------
# Helpers
# -------------------
def _clean(s: str) -> str:
    if not s:
        return s
    s = s.strip()
    if s.startswith("```"): s = s.strip("` \n")
    if s.endswith("```"):   s = s.strip("` \n")
    if s.startswith("`") or s.endswith("`"):
        s = s.strip("` \n")
    return s.strip()

def _copy_and_echo(text: str) -> str:
    safe = _safe_text(text)
    try:
        pc.copy(safe)
    except Exception:
        pass
    try:
        # Write bytes to avoid stdout encoding issues
        sys.stdout.buffer.write((safe + "\n").encode("utf-8", "ignore"))
    except Exception:
        print(safe)
    return safe


def _allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTS

def _file_to_data_url(file_storage) -> str:
    file_storage.stream.seek(0)
    data = file_storage.read()
    if not data:
        raise ValueError("Empty upload")

    # Try Pillow re-encode to PNG
    try:
        from io import BytesIO
        img = Image.open(BytesIO(data))
        img.load()
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception:
        # Fallback: return original bytes as data URL with best-guess MIME
        import mimetypes
        mime = file_storage.mimetype or mimetypes.guess_type(file_storage.filename)[0] or "application/octet-stream"
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{b64}"

def _images_payload_from_request() -> List[str]:
    data_urls: List[str] = []
    if request.content_type and "multipart/form-data" in request.content_type:
        files = request.files.getlist("images")
        for f in files:
            if not f or not f.filename:
                continue
            if not _allowed_image(f.filename):
                # still accept; extension check can be too strict when users mislabel
                # raise ValueError(f"Unsupported file type: {f.filename}")
                pass
            data_urls.append(_file_to_data_url(f))
    elif request.is_json:
        body = request.get_json(silent=True) or {}
        urls = body.get("image_urls", [])
        if urls and isinstance(urls, list):
            data_urls.extend(urls)
    return data_urls

def _chat(messages: list, model: str = MODEL_MAIN) -> str:
    # sanitize ALL message strings before calling the API
    msg_sanitized = []
    for m in messages:
        c = m["content"]
        if isinstance(c, str):
            c = _safe_text(c)
        elif isinstance(c, list):
            new_parts = []
            for part in c:
                if part.get("type") == "text":
                    part = {"type": "text", "text": _safe_text(part.get("text", ""))}
                new_parts.append(part)
            c = new_parts
        msg_sanitized.append({"role": m["role"], "content": c})

    resp = client.chat.completions.create(
        model=model,
        messages=msg_sanitized,
        temperature=0,
        top_p=0,
        presence_penalty=0,
        frequency_penalty=0,
    )
    return _safe_text(resp.choices[0].message.content)

# Remove invalid surrogate code points from any string
def _strip_surrogates(s: str) -> str:
    if not isinstance(s, str):
        return ""
    # encode ignoring unencodable chars, then decode back
    return s.encode("utf-8", "ignore").decode("utf-8", "ignore")

def _safe_text(s: str) -> str:
    return _strip_surrogates(_clean(s or ""))

def _safe_lines(s: str) -> str:
    s = _safe_text(s)
    return "\n".join(line.strip() for line in s.splitlines() if line.strip())

# -------------------
# Endpoints
# -------------------
@app.route('/api/generate-code', methods=['POST'])
def generate_code():
    """
    Accepts JSON:
      { "prompt": "..."}  or  { "content": "..."}  or  { "text": "..." }
    Returns JSON:
      { "response": "<raw code>", "message": "Copied to clipboard" }
    """
    try:
        if not request.is_json:
            return jsonify({"error": "Use application/json"}), 415

        body = request.get_json(silent=True) or {}
        prompt = (body.get("prompt") or body.get("content") or body.get("text") or "")
        prompt = _safe_text(prompt)
        if not prompt:
            return jsonify({"error": "No prompt/content provided", "got_keys": list(body.keys())}), 400

        messages = [
            {"role": "system", "content": CODE_STRICT_SYSTEM},
            {"role": "user", "content": prompt}
        ]
        out = _chat(messages)
        _copy_and_echo(out)
        return jsonify({"response": out, "message": "Copied to clipboard"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/test', methods=['POST'])
def test_unified():
    """
    Accepts:
      - application/json:
          { "text": "...", "image_urls": ["https://..."], "answer_format": "letter|number|text|code" }
      - multipart/form-data:
          images: one or more files
          text: optional string
          answer_format: optional hint ("letter"|"number"|"text"|"code")

    Returns:
      text/plain — ONLY the answer(s). If multiple, one per line.
    """
    try:
        # gather text + images/urls
        user_text = ""
        answer_format = None

        if request.content_type and "multipart/form-data" in request.content_type:
            user_text = _safe_text(request.form.get("text") or "")
            answer_format = (request.form.get("answer_format") or "").strip().lower() or None
            data_urls = _images_payload_from_request()
        elif request.is_json:
            body = request.get_json(silent=True) or {}
            user_text = _safe_text(body.get("text") or "")   # ← sanitize here too
            answer_format = (body.get("answer_format") or "").strip().lower() or None
            data_urls = _images_payload_from_request()
        else:
            return Response("ERROR: Use application/json or multipart/form-data", status=415, mimetype="text/plain; charset=utf-8")

        if not user_text and not data_urls:
            return Response("ERROR: No text or images provided", status=400, mimetype="text/plain; charset=utf-8")

        # strict system message
        system_msg = TEST_STRICT_SYSTEM_PLAIN
        if answer_format in ("letter", "number", "text", "code"):
            system_msg += f"\nExpected answer format: {answer_format}."

        # build multi-modal content
        content_parts = [{"type": "text", "text": user_text if user_text else "Provide only the final answer(s)."}]
        for url in data_urls:
            content_parts.append({"type": "image_url", "image_url": {"url": url}})

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": content_parts}
        ]

        raw = _chat(messages)
        ans = _safe_lines(raw)  # ← single, sanitized result (no extra words, no broken Unicode)

        # copy to clipboard and return as text/plain
        _copy_and_echo(ans)
        return Response(ans, mimetype="text/plain; charset=utf-8")

    except Exception as e:
        return Response(f"ERROR: {str(e)}", status=500, mimetype="text/plain; charset=utf-8")

# -------------------
# Run
# -------------------
if __name__ == '__main__':
    app.run(debug=True, port=5000)
