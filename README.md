# clip2ai — Silent AI Clipboard Assistant

## Overview

**clip2ai** is a lightweight local bridge between your clipboard and OpenAI’s GPT models. It sends text or screenshots directly from your clipboard to GPT and places the answer instantly back — ready to paste anywhere.

It’s ideal for:

* Students solving tests or coding problems
* Developers generating or fixing code
* Anyone who wants instant AI answers without opening a browser

---

## Features

* **Instant response** — trigger via a hotkey or terminal.
* **Two modes:**

  * `/api/generate-code` — generates raw code only.
  * `/api/test` — solves textual or visual (image) tests.
* **Clipboard integration** — copies answers automatically.
* **Toggle system** — quickly switch between endpoints using a shell alias.
* **Supports screenshots** — works with `pngpaste` on macOS.

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/dariiahacker1/clip2ai.git
cd clip2ai
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install flask flask-cors openai pillow python-dotenv pyperclip
```

### 3. Set up environment variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4o
```

### 4. Run the local API server

```bash
python app.py
```

Server starts at `http://127.0.0.1:5000`.

---

## Endpoints

### `/api/generate-code`

**Description:** Generates only raw code — no explanations, no markdown.

**Accepts:**

```json
{ "prompt": "Write a Python function that returns True." }
```

**Returns:**

```json
{
  "response": "def check():\n    return True",
  "message": "Copied to clipboard"
}
```

**Usage example:**

```bash
curl -sS -X POST http://127.0.0.1:5000/api/generate-code \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"bash one-liner that prints ping"}'
```

---

### `/api/test`

**Description:** Automatically detects whether the input is a question, multiple-choice test, or code fill-in, and returns only the correct answer(s).

**Accepts:**

* Plain text (JSON):

  ```json
  { "text": "Cartoon Masha and... 1.loh 2.pidor 3.medved" }
  ```
* Images (multipart):

  ```bash
  curl -sS -X POST http://127.0.0.1:5000/api/test \
    -F "images=@screenshot.png"
  ```

**Returns:** plain text — only the answer(s):

```
3
```

**Behavior:**

* Works with both clipboard text and clipboard screenshots.
* If text is missing but an image exists, the image will be sent automatically.

---

## Shell Integration

The script `send_prompt.sh` reads your clipboard, detects whether you’re using text or an image, and sends it to the correct endpoint.

### Default paths

```
/usr/local/bin/send
/usr/local/bin/toggle_endpoint
```

### Example aliases (add to `~/.zshrc`)

```bash
alias send="/Users/macbook/send_prompt.sh"
alias toggle_endpoint="/Users/macbook/toggle_endpoint.sh"
```

After adding aliases:

```bash
source ~/.zshrc
```

### Toggle endpoint command

Use this to switch between code and test modes:

```bash
toggle_endpoint
```

* Prints: `Endpoint switched: generate-code → test`
* Next run of `send` will use `/api/test`

---

## macOS Clipboard Setup

### Required tools

```bash
brew install pngpaste jq
```

* `pngpaste`: lets the script grab screenshots directly from the clipboard.
* `jq`: formats JSON safely.

### Example workflow

1. Copy text or take a screenshot (`Cmd + Ctrl + Shift + 4`)
2. Press your custom shortcut bound to `send`
3. Wait ~2 seconds — result is automatically copied to clipboard
4. Paste the answer anywhere (`Cmd + V`)

---

## For Students

**clip2ai** is especially useful for academic or technical work:

* Answer tests quickly (supports both text and screenshots)
* Solve coding exercises instantly
* No need to switch tabs — everything happens locally and quietly

> Combine focus, speed, and privacy — the ultimate shortcut for study sessions.

---

## Example Automation (macOS Shortcut)

1. Open the **Shortcuts** app
2. Create a new shortcut: *Run Shell Script*
3. Point it to `/Users/macbook/send_prompt.sh`
4. Assign a keyboard shortcut (e.g., ⌘ + ⌥ + G)
5. Choose “Run silently”

Now, every time you press your shortcut, **clip2ai** will send whatever is in your clipboard (text or image) to GPT and copy the result automatically.

---

## Notes

* Supports GPT-4o and any multimodal model.
* If the clipboard is empty, it gracefully falls back to image mode.
* Fully local: only connects to your OpenAI API key.
