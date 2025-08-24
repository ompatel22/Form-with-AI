import React, { useState, useEffect, useRef } from 'react';
import FormSide from './components/FormSide.jsx';
import ChatSide from './components/ChatSide.jsx';

const API = 'http://127.0.0.1:8000';
const sessionId = 'session1';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [status, setStatus] = useState('idle');
  const [pendingAudio, setPendingAudio] = useState(null);
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    phone: '',
    dob: '',
  });
  const initialized = useRef(false);

  const b64ToBlob = (b64, mime) => {
    const bytes = atob(b64);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    return new Blob([arr], { type: mime });
  };

  const speakText = (text) => {
    if (!text || !('speechSynthesis' in window)) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    window.speechSynthesis.speak(utterance);
  };

  const playBase64WavOrFallback = async (b64, text) => {
    if (!b64 && text) {
      speakText(text);
      return;
    }
    if (!b64) return;
    const blob = b64ToBlob(b64, 'audio/wav');
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    try {
      await audio.play();
      setPendingAudio(null);
    } catch (err) {
      setPendingAudio({ b64, text });
      if (text) speakText(text);
    }
  };

  const backendChat = async (msg) => {
    setStatus('waiting...');
    try {
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: msg }),
      });
      const data = await res.json();
      setStatus('idle');
      if (data.reply) {
        setMessages((prev) => [...prev, { text: data.reply, who: 'agent' }]);
      }
      if (data.updates) {
        setFormData((prev) => ({
          ...prev,
          fullName: data.updates.full_name || prev.fullName,
          email: data.updates.email || prev.email,
          phone: data.updates.phone || prev.phone,
          dob: data.updates.dob || prev.dob,
        }));
      }
      await playBase64WavOrFallback(data.audio_b64, data.reply);
    } catch (err) {
      console.error('Chat error:', err);
      setStatus('error');
      setMessages((prev) => [...prev, { text: `Error: ${err}`, who: 'agent' }]);
    }
  };

  const handleSend = async () => {
    if (!inputText.trim()) return;
    setMessages((prev) => [...prev, { text: inputText, who: 'user' }]);
    setInputText('');
    await backendChat(inputText);
  };

  const handleMic = () => {
    const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Rec) {
      alert('Speech recognition not supported');
      return;
    }
    const rec = new Rec();
    rec.lang = 'en-US';
    rec.interimResults = false;
    setStatus('listening');
    rec.onresult = (e) => {
      const text = e.results[0][0].transcript;
      setMessages((prev) => [...prev, { text, who: 'user' }]);
      backendChat(text);
    };
    rec.onend = () => setStatus('idle');
    rec.start();
  };

  const handleAudioEnable = async () => {
    if (pendingAudio) {
      await playBase64WavOrFallback(pendingAudio.b64, pendingAudio.text);
      setPendingAudio(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: formData.fullName,
          email: formData.email,
          phone: formData.phone,
          dob: formData.dob,
        }),
      });
      const out = await res.json();
      alert('Form submitted! Check backend logs.');
      console.log('Submitted:', out);
    } catch (err) {
      console.error('Submission error:', err);
      alert('Error submitting form.');
    }
  };

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const start = async () => {
      await fetch(`${API}/reset?session_id=${sessionId}`, { method: 'POST' });
      await backendChat('');
    };
    start();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-8 font-inter antialiased">
      <h1 className="text-4xl font-bold text-center text-gray-800 mb-10 tracking-tight">
        Student Registration — Conversational Agent
      </h1>
      <div className="flex gap-8 max-w-7xl mx-auto shadow-2xl rounded-2xl overflow-hidden bg-white">
        <FormSide formData={formData} setFormData={setFormData} handleSubmit={handleSubmit} />
        <ChatSide
          messages={messages}
          inputText={inputText}
          setInputText={setInputText}
          handleSend={handleSend}
          handleMic={handleMic}
          status={status}
          pendingAudio={pendingAudio}
          handleAudioEnable={handleAudioEnable}
        />
      </div>
    </div>
  );
}

export default App;