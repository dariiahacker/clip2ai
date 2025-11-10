#!/bin/bash
set -euo pipefail

# macOS PATH (Automator/Hammerspoon)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

BASE_URL="http://127.0.0.1:5000"

# Flipped by toggle_endpoint (generate-code <-> test)
ENDPOINT="test"  # DO NOT DELETE - used by toggle command
endpoint="${1:-$ENDPOINT}"

have() { command -v "$1" >/dev/null 2>&1; }

# ---- 1) Попытаться отправить ТЕКСТ из буфера ----
clip_text="$(pbpaste || true)"
text_bytes="$(printf "%s" "$clip_text" | LC_ALL=C wc -c | tr -d ' ')"

send_text_test() {
  local txt="$1"
  local payload
  payload=$(printf "%s" "$txt" | jq -Rs '{text: .}')
  curl -sS -m 30 -o /tmp/clip2ai_body -w "%{http_code}" \
    -X POST "$BASE_URL/api/test" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d "$payload"
}

send_text_generate_code() {
  local txt="$1"
  local payload
  payload=$(printf "%s" "$txt" | jq -Rs '{prompt: .}')
  curl -sS -m 30 -o /tmp/clip2ai_body -w "%{http_code}" \
    -X POST "$BASE_URL/api/generate-code" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d "$payload"
}

send_image_test() {
  local file="$1"
  curl -sS -m 60 -o /tmp/clip2ai_body -w "%{http_code}" \
    -X POST "$BASE_URL/api/test" \
    -F "images=@${file}"
}

# ---- роутинг по endpoint ----
case "$endpoint" in
  test)
    if [[ "$text_bytes" -gt 0 ]]; then
      code="$(send_text_test "$clip_text" || true)"
    else
      # текста нет → пробуем изображение из буфера
      tmp_png="$(mktemp -t clip2ai_img).png"
      used_image=""
      if have pngpaste && pngpaste - >"$tmp_png" 2>/dev/null && [[ -s "$tmp_png" ]]; then
        used_image="$tmp_png"
      fi
      if [[ -n "$used_image" ]]; then
        code="$(send_image_test "$used_image" || true)"
        rm -f "$tmp_png" 2>/dev/null || true
      else
        echo "ERROR: No text or image in clipboard to send." >&2
        have osascript && echo "clipboard info: $(osascript -e 'clipboard info' 2>/dev/null || true)" >&2
        exit 1
      fi
    fi
    ;;

  generate-code)
    # тут только текст; если его нет — честно падаем
    if [[ "$text_bytes" -gt 0 ]]; then
      code="$(send_text_generate_code "$clip_text" || true)"
    else
      echo "ERROR: No text in clipboard for /api/generate-code." >&2
      have osascript && echo "clipboard info: $(osascript -e 'clipboard info' 2>/dev/null || true)" >&2
      exit 1
    fi
    ;;

  *)
    echo "ERROR: Unknown endpoint '$endpoint'. Use 'test' or 'generate-code'." >&2
    exit 1
    ;;
esac

# ---- общая обработка ответа ----
body="$(cat /tmp/clip2ai_body 2>/dev/null || true)"
if [[ "${code:-}" != "200" ]]; then
  echo "ERROR (${code:-no-code}): ${body:-<empty>}" >&2
  exit 1
fi

# /api/test возвращает text/plain; /api/generate-code — JSON
if [[ "$endpoint" == "generate-code" ]]; then
  # попытаемся вытащить поле response; если не JSON — просто выведем body
  generated=$(printf "%s" "$body" | /usr/bin/python3 - <<'PY'
import sys, json
s=sys.stdin.read()
try:
    d=json.loads(s)
    print(d.get("response") or s)
except Exception:
    print(s)
PY
)
  printf "%s" "$generated" | pbcopy
  printf "%s\n" "$generated"
else
  printf "%s" "$body" | pbcopy
  printf "%s\n" "$body"
fi
