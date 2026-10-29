import html
import os
import re

from flask import Flask, jsonify, render_template_string, request
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
client = Groq(timeout=45.0, max_retries=1)
MODEL = os.getenv("MODEL", "openai/gpt-oss-120b")
STT_MODEL = os.getenv("STT_MODEL", "whisper-large-v3-turbo")

SYSTEM = """You are a senior Hotel Revenue Management Executive and Excel expert, acting as a study coach.
The user speaks Hindi/Hinglish. ALWAYS answer in clear, simple English, whatever language the question is in.

Your knowledge:
- Hotel revenue: Occupancy, ADR, RevPAR, TRevPAR, GOPPAR, MPI/ARI/RGI (STR comp set), pickup and pace reports,
  forecasting, BAR and dynamic pricing, restrictions (MLOS, CTA/CTD), overbooking, channel mix, OTA commission,
  rate parity, market segmentation, group displacement analysis, events calendar, budgeting, cancellations/no-shows,
  upselling, daily/weekly routine of a Revenue Executive, reports to the GM, revenue meetings.
- Excel: formulas (SUMIFS, COUNTIFS, XLOOKUP, INDEX-MATCH, IF, TEXT, EOMONTH), pivot tables, charts, conditional
  formatting, data validation, Power Query, FORECAST.LINEAR/TREND, Goal Seek, what-if, dashboards, shortcuts.

Answer format:
1. One-line direct answer or definition.
2. "Steps:" a numbered list (max 7), each step short and actionable. For Excel, give exact formulas with cell
   references, e.g. =SUMIFS(D:D,A:A,"Jan"). For hotel metrics, give the formula, e.g. RevPAR = Room revenue / Rooms available.
3. "Example:" one small example with real numbers.
Keep it about 120-180 words unless the user asks for detail ("full", "detail", "poora", "step by step").
If the topic is not about revenue, hotels, Excel, finance or study, reply only: IGNORE"""

KEYWORDS = [
    "occupancy", "adr", "revpar", "hotel", "rooms", "trevpar", "goppar", "pickup", "pace", "ota",
    "overbooking", "comp set", "rate parity", "booking", "cancellation", "no show", "segment", "channel",
    "yield", "length of stay", "mlos", "bar rate", "dynamic pricing", "upsell", "revenue", "sales", "income",
    "pricing", "profit", "margin", "ebitda", "roi", "growth", "forecast", "trend", "analysis", "kpi", "budget",
    "variance", "breakeven", "excel", "formula", "pivot", "vlookup", "xlookup", "sumif", "sumifs", "countif",
    "chart", "cost", "expense", "loss", "tax", "gst", "accounting", "finance", "economics", "statistics",
    "demand", "supply", "elasticity", "balance sheet", "cash flow", "gdp", "inflation",
    "होटल", "ऑक्यूपेंसी", "ऑक्युपेंसी", "रेवेन्यू", "बुकिंग", "कमरा", "कमरे",
    "प्रॉफिट", "मार्जिन", "फोरकास्ट", "बजट", "एक्सेल", "फॉर्मूला", "पिवट", "खर्च", "टैक्स",
    "फाइनेंस", "अकाउंटिंग", "डिमांड", "सप्लाई", "कैश फ्लो", "बैलेंस शीट",
]


def relevant(text):
    lower = text.lower()
    return any(re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", lower) for word in KEYWORDS)


PAGE = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n<title>Revenue Desktop Assistant</title>\n<style>\n*{box-sizing:border-box}body{margin:0;min-height:100vh;background:#0b1524;color:#e8eef7;font-family:Arial,sans-serif}\n.box{width:min(760px,94vw);margin:24px auto;padding:18px;background:#102039;border-radius:16px}\nheader{display:flex;gap:10px;align-items:center;margin-bottom:14px}h1{font-size:18px;margin:0;flex:1}\nbutton{background:#18283f;color:#e8eef7;border:0;border-radius:8px;padding:9px 13px;cursor:pointer}\n#status{color:#8fa3bf;font-size:13px;margin-bottom:10px}#feed{min-height:400px;max-height:65vh;overflow-y:auto}\n.turn{border-bottom:1px solid #30445f;padding:14px 0}.old{color:#6f819b;font-size:14px}.new{color:#e8eef7;font-size:17px}\n.question{font-weight:bold;margin-bottom:9px;white-space:pre-wrap}.answer{white-space:pre-wrap;line-height:1.45}.hint{color:#8fa3bf;font-size:12px;margin-top:14px}\n</style></head>\n<body><main class="box"><header><h1>Revenue Desktop Assistant</h1>\n<button id="mute">Mute</button></header>\n<div id="status">Starting microphone...</div><section id="feed"></section>\n<div class="hint">The assistant listens continuously. Click Mute to stop listening and Unmute to resume.</div></main>\n<script>\nconst muteButton=document.getElementById(\'mute\'),statusText=document.getElementById(\'status\'),feed=document.getElementById(\'feed\');\nlet stream=null,recorder=null,chunks=[],audioContext=null,analyser=null,levels=null,monitorId=null,muted=false,speech=false,silenceStarted=0,segmentStarted=0;\nconst THRESHOLD=0.025,SILENCE_MS=800,MAX_SEGMENT_MS=10000;\n\nmuteButton.onclick=()=>{if(muted){muted=false;muteButton.textContent=\'Mute\';startListening()}else{muted=true;muteButton.textContent=\'Unmute\';stopListening()}};\n\nasync function startListening(){\n  try{\n    if(!stream)stream=await navigator.mediaDevices.getUserMedia({audio:true});\n    if(!audioContext)audioContext=new AudioContext();\n    if(audioContext.state===\'suspended\')await audioContext.resume();\n    const source=audioContext.createMediaStreamSource(stream);analyser=audioContext.createAnalyser();analyser.fftSize=1024;source.connect(analyser);levels=new Uint8Array(analyser.fftSize);\n    statusText.textContent=\'Listening continuously...\';startRecorder();monitorId=requestAnimationFrame(checkVolume);\n  }catch(e){statusText.textContent=\'Microphone permission is required. Click Unmute after allowing it.\';muted=true;muteButton.textContent=\'Unmute\'}\n}\n\nfunction startRecorder(){\n  if(muted||!stream||recorder&&recorder.state===\'recording\')return;\n  chunks=[];speech=false;silenceStarted=0;segmentStarted=Date.now();recorder=new MediaRecorder(stream);\n  recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};recorder.onstop=sendSegment;recorder.start();\n}\n\nfunction checkVolume(){\n  if(muted||!analyser)return;analyser.getByteTimeDomainData(levels);let sum=0;\n  for(const value of levels){const normalized=(value-128)/128;sum+=normalized*normalized}const volume=Math.sqrt(sum/levels.length),now=Date.now();\n  if(volume>THRESHOLD){speech=true;silenceStarted=0}\n  else if(speech){if(!silenceStarted)silenceStarted=now;if(now-silenceStarted>SILENCE_MS||now-segmentStarted>MAX_SEGMENT_MS)finishSegment()}\n  if(now-segmentStarted>MAX_SEGMENT_MS&&!speech)finishSegment();monitorId=requestAnimationFrame(checkVolume);\n}\n\nfunction finishSegment(){if(recorder&&recorder.state===\'recording\')recorder.stop()}\n\nfunction stopListening(){if(monitorId)cancelAnimationFrame(monitorId);monitorId=null;if(recorder&&recorder.state===\'recording\')recorder.stop();recorder=null;if(stream){stream.getTracks().forEach(t=>t.stop());stream=null}statusText.textContent=\'Muted. Click Unmute to listen again.\'}\n\nasync function sendSegment(){\n  const audio=new Blob(chunks,{type:\'audio/webm\'});chunks=[];\n  if(audio.size<1000){if(!muted)startRecorder();return}\n  const form=new FormData();form.append(\'audio\',audio,\'recording.webm\');\n  try{\n    const tr=await fetch(\'/transcribe\',{method:\'POST\',body:form,signal:AbortSignal.timeout(45000)}).then(r=>r.json());\n    if(tr.error)throw Error(tr.error);if(tr.text){statusText.textContent=\'Heard: \'+tr.text+\' — Generating answer...\';\n      const result=await fetch(\'/answer\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({question:tr.text}),signal:AbortSignal.timeout(45000)}).then(r=>r.json());\n      if(result.error)throw Error(result.error);if(!result.ignore)addTurn(tr.text,result.answer);else statusText.textContent=\'Heard, but this question is outside the supported topics.\';}\n    if(!muted)statusText.textContent=\'Listening continuously...\';\n  }catch(e){statusText.textContent=\'Error: \'+e.message}\n  finally{if(!muted){startRecorder();if(!monitorId)monitorId=requestAnimationFrame(checkVolume)}}\n}\n\nfunction addTurn(question,answer){[...feed.querySelectorAll(\'.turn\')].forEach(t=>t.classList.replace(\'new\',\'old\'));const turn=document.createElement(\'article\');turn.className=\'turn new\';\nturn.innerHTML=\'<div class="question"></div><div class="answer"></div>\';turn.querySelector(\'.question\').textContent=question;turn.querySelector(\'.answer\').textContent=answer;feed.appendChild(turn);turn.scrollIntoView({block:\'start\'})}\n\nstartListening();\n</script></body></html>\n'

@app.get("/")
def home():
    return render_template_string(PAGE)


@app.post("/transcribe")
def transcribe():
    audio = request.files.get("audio")
    if not audio:
        return jsonify(error="No audio was received."), 400
    try:
        result = client.audio.transcriptions.create(
            file=(audio.filename or "recording.webm", audio.read()),
            model=STT_MODEL,
            temperature=0,
            prompt="revenue, occupancy, ADR, RevPAR, TRevPAR, GOPPAR, pickup, pace, OTA, BAR, overbooking, comp set, Excel, XLOOKUP, SUMIFS, pivot table",
        )
        text = (getattr(result, "text", result) or "").strip()
        return jsonify(text=text, relevant=relevant(text))
    except Exception as exc:
        return jsonify(error=str(exc)[:250]), 500


@app.post("/answer")
def answer():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify(error="No question was received."), 400
    try:
        result = client.chat.completions.create(
            model=MODEL,
            stream=False,
            temperature=0.3,
            max_completion_tokens=1400,
            reasoning_effort="low",
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}],
        )
        text = result.choices[0].message.content or ""
        if text.strip().startswith("IGNORE"):
            return jsonify(ignore=True)
        return jsonify(answer=text)
    except Exception as exc:
        return jsonify(error=str(exc)[:250]), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
