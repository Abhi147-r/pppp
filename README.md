# Revenue Desktop Assistant — Web Version

This is a browser website with the backend and frontend together in one `main.py` file.

## Files

```text
main.py
requirements.txt
Procfile
.gitignore
.env
README.md
```

## Features

- Continuously listens through the browser microphone
- Automatically detects a speech pause and sends the segment
- Generates answers continuously without a Stop & Send button
- Mute stops listening; Unmute resumes listening
- Hindi/Hinglish speech input with English answers
- Newest answer is shown as the main answer and previous answers stay above

## Render settings

```text
Root Directory:  leave empty if these files are in the repository root
Build Command:   pip install -r requirements.txt
Start Command:   gunicorn main:app
```

Add this Render environment variable:

```text
GROQ_API_KEY=your_groq_api_key
```

## Local run

```bash
pip install -r requirements.txt
python main.py
```

Open `http://localhost:10000` and allow microphone permission. The `.env` file is only a template; replace its placeholder with your real Groq API key. Never commit a real API key.
