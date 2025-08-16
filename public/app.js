/* global MediaRecorder */
const $ = (s) => document.querySelector(s);

let sessionId = "";
let recorder;
let chunks = [];
let recording = false;

const serverStatus = $("#server-status");
const sessionIdEl = $("#session-id");
const baseUrlInput = $("#base-url");
const nextQ = $("#next-q");
const formStateEl = $("#form-state");
const historyEl = $("#history");
const agentAudio = $("#agent-audio");
const lastTranscript = $("#last-transcript");
const agentReply = $("#agent-reply");
const recStatus = $("#rec-status");

function logHistory(role, text) {
  const div = document.createElement("div");
  div.className = "item";
  const who = role === "user" ? "u" : "a";
  div.innerHTML = `<span class="${who}">${role}:</span> <span class="mono">${escapeHtml(text)}</span>`;
  historyEl.prepend(div);
}
function escapeHtml(s) {
  return (s ?? "").replace(/[&<>"'`=\/]/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;","/":"&#x2F;","`":"&#x60;","=":"&#x3D;"
  }[c]));
}

async function ping() {
  try {
    const res = await fetch(`${baseUrlInput.value}/health`);
    const j = await res.json();
    serverStatus.textContent = `Backend: ${j.status} (${j.env})`;
  } catch {
    serverStatus.textContent = "Backend: unreachable";
  }
}
ping();

function newSession() {
  sessionId = `sess_${Math.random().toString(36).slice(2, 10)}`;
  sessionIdEl.textContent = sessionId;
  historyEl.innerHTML = "";
  formStateEl.textContent = "{}";
  nextQ.textContent = "";
  lastTranscript.textContent = "";
  agentReply.textContent = "";
  agentAudio.style.display = "none";
}
newSession();

$("#btn-new-session").addEventListener("click", newSession);

$("#btn-start").addEventListener("click", async () => {
  const schemaStr = $("#schema-json").value;
  let schema;
  try {
    schema = JSON.parse(schemaStr);
  } catch (e) {
    alert("Invalid JSON schema:\n" + e.message);
    return;
  }
  if (!schema.fields || !Array.isArray(schema.fields) || schema.fields.length === 0) {
    alert("schema.fields must be a non-empty array");
    return;
  }
  try {
    const res = await fetch(`${baseUrlInput.value}/v1/form/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, schema }),
    });
    if (!res.ok) throw new Error(await res.text());
    const j = await res.json();
    nextQ.textContent = j.next_question || "(no question yet)";
    await refreshState();
    logHistory("agent", j.next_question || "…");
    speakIfAudio(""); // clears previous
  } catch (e) {
    alert("Start form failed:\n" + e.message);
  }
});

$("#btn-reset").addEventListener("click", async () => {
  if (!sessionId) return;
  await fetch(`${baseUrlInput.value}/v1/agent/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  }).catch(() => {});
  newSession();
});

async function refreshState() {
  if (!sessionId) return;
  const res = await fetch(`${baseUrlInput.value}/v1/agent/state/${sessionId}`);
  if (res.ok) {
    const j = await res.json();
    formStateEl.textContent = JSON.stringify(j.form ?? j, null, 2);
  }
}

$("#btn-send").addEventListener("click", async () => {
  const text = $("#text-input").value.trim();
  if (!text) return;
  $("#text-input").value = "";
  logHistory("user", text);
  await sendTextTurn(text);
});

async function sendTextTurn(userText) {
  try {
    const res = await fetch(`${baseUrlInput.value}/v1/agent/turn`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, user_text: userText }),
    });
    if (!res.ok) throw new Error(await res.text());
    const j = await res.json();
    nextQ.textContent = j.is_complete ? "All fields captured. Submit?" : (j.agent_reply || "");
    agentReply.textContent = j.agent_reply || "";
    logHistory("agent", j.agent_reply || "");
    await refreshState();
    speakIfAudio(j.audio_url);
  } catch (e) {
    alert("Turn failed:\n" + e.message);
  }
}

function speakIfAudio(url) {
  if (!url) {
    agentAudio.style.display = "none";
    agentAudio.src = "";
    return;
  }
  // ensure absolute URL
  const absolute = url.startsWith("http") ? url : `${baseUrlInput.value}${url}`;
  agentAudio.src = absolute;
  agentAudio.style.display = "block";
  agentAudio.play().catch(() => {});
}

// -------- Recording (MediaRecorder) --------
const btnRec = $("#btn-record");
const btnStop = $("#btn-stop");

btnRec.addEventListener("click", async () => {
  if (recording) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    // pick a MIME type the browser supports
    let mime = "";
    const preferred = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/mp4",
      "audio/wav"
    ];
    for (const m of preferred) {
      if (MediaRecorder.isTypeSupported(m)) { mime = m; break; }
    }
    recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    chunks = [];
    recorder.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    recorder.onstop = async () => {
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      await sendAudio(blob);
    };
    recorder.start(100);
    recording = true;
    btnRec.disabled = true;
    btnStop.disabled = false;
    recStatus.textContent = `Mic: recording (${recorder.mimeType || "default"})…`;
  } catch (e) {
    alert("Microphone error:\n" + e.message);
  }
});

btnStop.addEventListener("click", () => {
  if (!recording || !recorder) return;
  recorder.stop();
  recorder.stream.getTracks().forEach(t => t.stop());
  recording = false;
  btnRec.disabled = false;
  btnStop.disabled = true;
  recStatus.textContent = "Mic: processing…";
});

async function sendAudio(blob) {
  try {
    const fd = new FormData();
    // Whisper endpoint expects `file` field name
    fd.append("file", blob, `audio.${blob.type.split("/")[1] || "webm"}`);
    const sttRes = await fetch(`${baseUrlInput.value}/v1/stt`, {
      method: "POST",
      body: fd
    });
    if (!sttRes.ok) throw new Error(await sttRes.text());
    const sttJson = await sttRes.json();
    const text = (sttJson.text || "").trim();
    lastTranscript.textContent = text || "(empty transcript)";
    recStatus.textContent = "Mic: idle";
    if (text) {
      logHistory("user", text);
      await sendTextTurn(text);
    }
  } catch (e) {
    recStatus.textContent = "Mic: error";
    alert("STT failed:\n" + e.message);
  }
}