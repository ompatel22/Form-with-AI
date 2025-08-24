import React, { useState, useEffect, useRef } from "react";
import FormSide from "./components/FormSide.jsx";
import ChatSide from "./components/ChatSide.jsx";

const API = "http://127.0.0.1:8000";
const sessionId = "session1";

function App() {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [status, setStatus] = useState("idle");
  const [pendingAudio, setPendingAudio] = useState(null);
  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
    phone: "",
    dob: "",
  });
  const [sessionStatus, setSessionStatus] = useState({
    completed: false,
    current_field: null,
    frustration_level: 0,
  });
  const initialized = useRef(false);

  const b64ToBlob = (b64, mime) => {
    const bytes = atob(b64);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    return new Blob([arr], { type: mime });
  };

  const speakText = (text) => {
    if (!text || !("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 0.9;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
  };

  const playBase64WavOrFallback = async (b64, text) => {
    if (!b64 && text) {
      speakText(text);
      return;
    }
    if (!b64) return;

    try {
      const blob = b64ToBlob(b64, "audio/wav");
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);

      await audio.play();
      setPendingAudio(null);

      // Clean up the URL to prevent memory leaks
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      console.warn("Audio playback failed, using speech synthesis:", err);
      setPendingAudio({ b64, text });
      if (text) speakText(text);
    }
  };

  // Enhanced form data update function with better field extraction
  const updateFormData = (updates) => {
    console.log("Raw updates from backend:", updates);

    if (!updates || typeof updates !== "object") {
      console.warn("Invalid updates object:", updates);
      return;
    }

    setFormData((prev) => {
      const newFormData = { ...prev };

      // Handle different field name formats from backend
      const fieldMappings = {
        full_name: "fullName",
        fullName: "fullName",
        email: "email",
        phone: "phone",
        dob: "dob",
      };

      // Process each field in updates
      Object.entries(updates).forEach(([key, fieldData]) => {
        console.log(`Processing field: ${key}`, fieldData);

        const frontendFieldName = fieldMappings[key];

        if (frontendFieldName) {
          let value = "";

          // Handle different data structures from backend
          if (typeof fieldData === "string") {
            value = fieldData;
          } else if (fieldData && typeof fieldData === "object") {
            // Try multiple possible value locations
            value =
              fieldData.value ||
              fieldData.collected ||
              fieldData.data ||
              (fieldData.status === "collected" ? fieldData.value : "") ||
              "";

            console.log(`Extracted value for ${key}:`, value);
          }

          // Validate and update field
          if (
            value &&
            typeof value === "string" &&
            value.trim() &&
            value !== "[object Object]"
          ) {
            const cleanValue = value.trim();
            console.log(`✅ Updating ${frontendFieldName}: "${cleanValue}"`);
            newFormData[frontendFieldName] = cleanValue;
          } else {
            console.log(`⚠️ Skipping invalid value for ${key}:`, value);
          }
        } else {
          console.log(`⚠️ Unknown field mapping for: ${key}`);
        }
      });

      // SPECIAL DOB HANDLING - Check for date patterns in recent messages
      if (!newFormData.dob || newFormData.dob.trim() === "") {
        // Look for DOB patterns in the updates or recent conversation
        const possibleDob = updates.dob || updates.date_of_birth || "";
        if (possibleDob && possibleDob.includes("/")) {
          console.log(`✅ Setting DOB: ${possibleDob}`);
          newFormData.dob = possibleDob;
        }
      }

      // FORMAT PHONE NUMBER
      if (newFormData.phone && !newFormData.phone.includes("(")) {
        const digits = newFormData.phone.replace(/\D/g, "");
        if (digits.length === 10) {
          newFormData.phone = `(${digits.slice(0, 3)}) ${digits.slice(
            3,
            6
          )}-${digits.slice(6)}`;
        }
      }

      console.log("Final updated form data:", newFormData);
      return newFormData;
    });
  };

  const backendChat = async (msg) => {
    setStatus("waiting...");
    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: msg }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();
      console.log("Backend response:", data);

      setStatus("idle");

      // Add agent message
      if (data.reply) {
        setMessages((prev) => [
          ...prev,
          {
            text: data.reply,
            who: "agent",
            timestamp: new Date().toISOString(),
            action: data.action,
            tone: data.tone,
          },
        ]);
      }

      // Update session status
      if (data.session_status) {
        setSessionStatus(data.session_status);
      }

      // Update form data with enhanced handling
      if (data.updates) {
        updateFormData(data.updates);
      }

      // Play audio response
      if (data.audio_b64 || data.reply) {
        await playBase64WavOrFallback(data.audio_b64, data.reply);
      }
    } catch (err) {
      console.error("Chat error:", err);
      setStatus("error");
      setMessages((prev) => [
        ...prev,
        {
          text: `Connection error: ${err.message}. Please check if the backend is running.`,
          who: "agent",
          timestamp: new Date().toISOString(),
          isError: true,
        },
      ]);
    }
  };

  const handleSend = async () => {
    const message = inputText.trim();
    if (!message) return;

    // Add user message immediately
    setMessages((prev) => [
      ...prev,
      {
        text: message,
        who: "user",
        timestamp: new Date().toISOString(),
      },
    ]);
    setInputText("");

    // Send to backend
    await backendChat(message);
  };

  const handleMic = () => {
    const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Rec) {
      alert(
        "Speech recognition not supported in this browser. Please type your message or try Chrome/Edge."
      );
      return;
    }

    const rec = new Rec();
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.maxAlternatives = 1;

    setStatus("listening");

    rec.onresult = (e) => {
      const text = e.results[0][0].transcript;
      console.log("Speech recognized:", text);

      setMessages((prev) => [
        ...prev,
        {
          text: text,
          who: "user",
          timestamp: new Date().toISOString(),
          isVoice: true,
        },
      ]);
      backendChat(text);
    };

    rec.onerror = (e) => {
      console.error("Speech recognition error:", e.error);
      setStatus("error");
      setMessages((prev) => [
        ...prev,
        {
          text: `Speech recognition error: ${e.error}. Please try typing instead.`,
          who: "agent",
          timestamp: new Date().toISOString(),
          isError: true,
        },
      ]);
      setTimeout(() => setStatus("idle"), 2000);
    };

    rec.onend = () => {
      setStatus("idle");
    };

    try {
      rec.start();
    } catch (err) {
      console.error("Failed to start speech recognition:", err);
      setStatus("error");
      alert(
        "Could not start voice recognition. Please check microphone permissions."
      );
    }
  };

  const handleAudioEnable = async () => {
    if (pendingAudio) {
      await playBase64WavOrFallback(pendingAudio.b64, pendingAudio.text);
      setPendingAudio(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Validate required fields
    const requiredFields = ["fullName", "email", "phone", "dob"];
    const emptyFields = requiredFields.filter(
      (field) => !formData[field] || !formData[field].trim()
    );

    if (emptyFields.length > 0) {
      const fieldLabels = {
        fullName: "Full Name",
        email: "Email",
        phone: "Phone",
        dob: "Date of Birth",
      };

      const missingLabels = emptyFields
        .map((field) => fieldLabels[field])
        .join(", ");
      alert(`Please fill in the following fields: ${missingLabels}`);
      return;
    }

    try {
      setStatus("submitting");

      const submissionData = {
        session_id: sessionId,
        full_name: formData.fullName,
        email: formData.email,
        phone: formData.phone,
        dob: formData.dob,
      };

      console.log("Submitting form data:", submissionData);

      const res = await fetch(`${API}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(submissionData),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const result = await res.json();
      console.log("Submission result:", result);

      // Success feedback
      alert("Form submitted successfully! ✅");
      setMessages((prev) => [
        ...prev,
        {
          text: "Form has been successfully submitted! Thank you for your information.",
          who: "agent",
          timestamp: new Date().toISOString(),
          isSuccess: true,
        },
      ]);

      setSessionStatus((prev) => ({ ...prev, completed: true }));
    } catch (err) {
      console.error("Submission error:", err);
      alert(`Error submitting form: ${err.message}`);
      setMessages((prev) => [
        ...prev,
        {
          text: `Submission failed: ${err.message}`,
          who: "agent",
          timestamp: new Date().toISOString(),
          isError: true,
        },
      ]);
    } finally {
      setStatus("idle");
    }
  };

  // Enhanced form field update handler
  const handleFormFieldChange = (fieldName, value) => {
    setFormData((prev) => ({
      ...prev,
      [fieldName]: value,
    }));
  };

  // Reset conversation
  const handleReset = async () => {
    if (!confirm("Are you sure you want to reset the conversation and form?")) {
      return;
    }

    try {
      await fetch(`${API}/reset?session_id=${sessionId}`, { method: "POST" });

      // Reset all state
      setMessages([]);
      setFormData({
        fullName: "",
        email: "",
        phone: "",
        dob: "",
      });
      setSessionStatus({
        completed: false,
        current_field: null,
        frustration_level: 0,
      });
      setStatus("idle");
      setPendingAudio(null);

      // Start new conversation
      await backendChat("");
    } catch (err) {
      console.error("Reset error:", err);
      alert("Failed to reset conversation");
    }
  };

  // Initialize conversation
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    const startConversation = async () => {
      try {
        setStatus("initializing");
        await fetch(`${API}/reset?session_id=${sessionId}`, { method: "POST" });
        await backendChat(""); // Start conversation
      } catch (err) {
        console.error("Initialization error:", err);
        setStatus("error");
        setMessages([
          {
            text: "Failed to connect to the server. Please check if the backend is running on http://127.0.0.1:8000",
            who: "agent",
            timestamp: new Date().toISOString(),
            isError: true,
          },
        ]);
      }
    };

    startConversation();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-8 font-inter antialiased">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-gray-800 mb-4 tracking-tight">
            Student Registration — Conversational Agent
          </h1>
          <div className="flex items-center justify-center gap-4 text-sm text-gray-600">
            <span
              className={`px-3 py-1 rounded-full ${
                status === "idle"
                  ? "bg-green-100 text-green-700"
                  : status === "waiting..."
                  ? "bg-blue-100 text-blue-700"
                  : status === "listening"
                  ? "bg-purple-100 text-purple-700"
                  : status === "error"
                  ? "bg-red-100 text-red-700"
                  : "bg-gray-100 text-gray-700"
              }`}
            >
              Status: {status}
            </span>
            {sessionStatus.current_field && (
              <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full">
                Focus: {sessionStatus.current_field.replace("_", " ")}
              </span>
            )}
            {sessionStatus.completed && (
              <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full">
                ✓ Complete
              </span>
            )}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex flex-col lg:flex-row gap-6 shadow-2xl rounded-2xl overflow-hidden bg-white">
          <FormSide
            formData={formData}
            setFormData={handleFormFieldChange}
            handleSubmit={handleSubmit}
            sessionStatus={sessionStatus}
            status={status}
          />
          <ChatSide
            messages={messages}
            inputText={inputText}
            setInputText={setInputText}
            handleSend={handleSend}
            handleMic={handleMic}
            status={status}
            pendingAudio={pendingAudio}
            handleAudioEnable={handleAudioEnable}
            onReset={handleReset}
            sessionStatus={sessionStatus}
          />
        </div>
      </div>
    </div>
  );
}

export default App;
