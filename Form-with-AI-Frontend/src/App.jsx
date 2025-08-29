import React, { useState, useEffect, useRef } from "react";
import FormSide from "./components/FormSide.jsx";
import ChatSide from "./components/ChatSide.jsx";
import FormManager from "./components/FormManager.jsx";
import DynamicFormRenderer from "./components/DynamicFormRenderer.jsx";

const API = "http://127.0.0.1:8000";

function App() {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [status, setStatus] = useState("idle");
  const [pendingAudio, setPendingAudio] = useState(null);
  
  // Dynamic form state
  const [currentForm, setCurrentForm] = useState(null);
  const [formData, setFormData] = useState({});
  const [showFormManager, setShowFormManager] = useState(false);
  const [isLegacyMode, setIsLegacyMode] = useState(true); // Start with legacy form
  
  // Session Management - Generate unique session IDs for each form/mode
  const [sessionId, setSessionId] = useState(() => 
    `legacy_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  );
  
  // Legacy form data
  const [legacyFormData, setLegacyFormData] = useState({
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

      // AUTO-LISTENING: Automatically start listening after TTS completes
      audio.addEventListener('ended', () => {
        setTimeout(() => {
          // Auto-start microphone after a brief pause
          console.log("🎙️ Auto-starting microphone after TTS completion");
          handleMic();
        }, 500); // 500ms delay to feel natural
      });

      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      console.warn("Audio playback failed, using speech synthesis:", err);
      setPendingAudio({ b64, text });
      if (text) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "en-US";
        utterance.rate = 0.9;
        utterance.pitch = 1.0;
        
        // AUTO-LISTENING: Also handle for speech synthesis
        utterance.onend = () => {
          setTimeout(() => {
            console.log("🎙️ Auto-starting microphone after speech synthesis");
            handleMic();
          }, 500);
        };
        
        window.speechSynthesis.speak(utterance);
      }
    }
  };

  // Enhanced form data update function for legacy forms
  const updateLegacyFormData = (updates) => {
    console.log("Raw updates from backend:", updates);

    if (!updates || typeof updates !== "object") {
      console.warn("Invalid updates object:", updates);
      return;
    }

    setLegacyFormData((prev) => {
      const newFormData = { ...prev };

      const fieldMappings = {
        full_name: "fullName",
        fullName: "fullName",
        email: "email",
        phone: "phone",
        dob: "dob",
      };

      Object.entries(updates).forEach(([key, fieldData]) => {
        console.log(`Processing field: ${key}`, fieldData);

        const frontendFieldName = fieldMappings[key];

        if (frontendFieldName) {
          let value = "";

          if (typeof fieldData === "string") {
            value = fieldData;
          } else if (fieldData && typeof fieldData === "object") {
            value =
              fieldData.value ||
              fieldData.collected ||
              fieldData.data ||
              (fieldData.status === "collected" ? fieldData.value : "") ||
              "";
          }

          if (
            value &&
            typeof value === "string" &&
            value.trim() &&
            value !== "[object Object]"
          ) {
            const cleanValue = value.trim();
            console.log(`✅ Updating ${frontendFieldName}: "${cleanValue}"`);
            newFormData[frontendFieldName] = cleanValue;
          }
        }
      });

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

      console.log("Final updated legacy form data:", newFormData);
      return newFormData;
    });
  };

  // Dynamic form data update function
  const updateDynamicFormData = (fieldName, value) => {
    setFormData(prev => ({
      ...prev,
      [fieldName]: value
    }));
  };

  // Legacy backend chat
  const legacyBackendChat = async (msg) => {
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

      if (data.session_status) {
        setSessionStatus(data.session_status);
      }

      if (data.updates) {
        updateLegacyFormData(data.updates);
      }

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

  // Dynamic backend chat
  const dynamicBackendChat = async (msg) => {
    if (!currentForm) return;

    setStatus("waiting...");
    try {
      const res = await fetch(`${API}/dynamic-chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          session_id: sessionId, 
          form_id: currentForm.id,
          message: msg 
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();
      console.log("Dynamic backend response:", data);

      setStatus("idle");

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

      // Update form data based on form summary
      if (data.form_summary && data.form_summary.fields) {
        const newFormData = {};
        Object.entries(data.form_summary.fields).forEach(([fieldName, fieldInfo]) => {
          if (fieldInfo.value && fieldInfo.status === 'collected') {
            newFormData[fieldName] = fieldInfo.value;
          }
        });
        setFormData(prev => ({ ...prev, ...newFormData }));
      }

      if (data.audio_b64 || data.reply) {
        await playBase64WavOrFallback(data.audio_b64, data.reply);
      }
    } catch (err) {
      console.error("Dynamic chat error:", err);
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

    setMessages((prev) => [
      ...prev,
      {
        text: message,
        who: "user",
        timestamp: new Date().toISOString(),
      },
    ]);
    setInputText("");

    // Use appropriate chat function
    if (isLegacyMode) {
      await legacyBackendChat(message);
    } else {
      await dynamicBackendChat(message);
    }
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
      
      if (isLegacyMode) {
        legacyBackendChat(text);
      } else {
        dynamicBackendChat(text);
      }
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

  // Legacy form submission
  const handleLegacySubmit = async (e) => {
    e.preventDefault();

    const requiredFields = ["fullName", "email", "phone", "dob"];
    const emptyFields = requiredFields.filter(
      (field) => !legacyFormData[field] || !legacyFormData[field].trim()
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
        full_name: legacyFormData.fullName,
        email: legacyFormData.email,
        phone: legacyFormData.phone,
        dob: legacyFormData.dob,
      };

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
    } finally {
      setStatus("idle");
    }
  };

  // Dynamic form submission
  const handleDynamicSubmit = async (e) => {
    e.preventDefault();

    try {
      setStatus("submitting");

      const submissionData = {
        session_id: sessionId,
        responses: formData
      };

      const res = await fetch(`${API}/forms/${currentForm.id}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(submissionData),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const result = await res.json();
      console.log("Dynamic submission result:", result);

      alert("Form submitted successfully! ✅");
      setMessages((prev) => [
        ...prev,
        {
          text: result.message || "Form has been successfully submitted!",
          who: "agent",
          timestamp: new Date().toISOString(),
          isSuccess: true,
        },
      ]);

    } catch (err) {
      console.error("Submission error:", err);
      alert(`Error submitting form: ${err.message}`);
    } finally {
      setStatus("idle");
    }
  };

  const handleFormSelected = (form) => {
    console.log("Form selected:", form);
    
    // Create unique session ID for this specific form
    const newSessionId = `form_${form.id}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newSessionId);
    
    setCurrentForm(form);
    setFormData({});
    setMessages([]);
    setIsLegacyMode(false);
    setShowFormManager(false);
    
    // Start conversation for the new form with new session
    setTimeout(() => dynamicBackendChat(""), 100); // Small delay to ensure sessionId is updated
  };

  const switchToLegacyMode = () => {
    // Create unique session ID for legacy mode
    const newSessionId = `legacy_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newSessionId);
    
    setIsLegacyMode(true);
    setCurrentForm(null);
    setFormData({});
    setMessages([]);
    
    // Reset legacy form
    setLegacyFormData({
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

    // Start legacy conversation with new session
    setTimeout(() => legacyBackendChat(""), 100); // Small delay to ensure sessionId is updated
  };

  const handleReset = async () => {
    if (!confirm("Are you sure you want to reset the conversation and form?")) {
      return;
    }

    try {
      // Reset using current session ID
      await fetch(`${API}/reset?session_id=${sessionId}`, { method: "POST" });

      setMessages([]);
      setStatus("idle");
      setPendingAudio(null);

      if (isLegacyMode) {
        setLegacyFormData({
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
        await legacyBackendChat("");
      } else if (currentForm) {
        setFormData({});
        await dynamicBackendChat("");
      }
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
        
        if (isLegacyMode) {
          await legacyBackendChat("");
        }
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
  }, [isLegacyMode]);

  if (showFormManager) {
    return (
      <FormManager
        onFormSelected={handleFormSelected}
        onClose={() => setShowFormManager(false)}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-8 font-inter antialiased">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-gray-800 mb-4 tracking-tight">
            {isLegacyMode 
              ? "Student Registration — Conversational Agent" 
              : currentForm 
                ? `${currentForm.title} — Conversational Agent`
                : "Form Filling — Conversational Agent"
            }
          </h1>
          
          {/* Mode Switcher */}
          <div className="flex items-center justify-center gap-4 mb-4">
            <button
              onClick={switchToLegacyMode}
              className={`px-4 py-2 rounded-lg transition-colors ${
                isLegacyMode
                  ? "bg-blue-600 text-white"
                  : "bg-gray-200 text-gray-700 hover:bg-gray-300"
              }`}
            >
              Legacy Form
            </button>
            <button
              onClick={() => setShowFormManager(true)}
              className={`px-4 py-2 rounded-lg transition-colors ${
                !isLegacyMode
                  ? "bg-purple-600 text-white"
                  : "bg-gray-200 text-gray-700 hover:bg-gray-300"
              }`}
            >
              Dynamic Forms
            </button>
          </div>
          
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
            {sessionStatus.current_field && isLegacyMode && (
              <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full">
                Focus: {sessionStatus.current_field.replace("_", " ")}
              </span>
            )}
            {sessionStatus.completed && isLegacyMode && (
              <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full">
                ✓ Complete
              </span>
            )}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex flex-col lg:flex-row gap-6 shadow-2xl rounded-2xl overflow-hidden bg-white">
          {isLegacyMode ? (
            <FormSide
              formData={legacyFormData}
              setFormData={(field, value) => 
                setLegacyFormData(prev => ({ ...prev, [field]: value }))
              }
              handleSubmit={handleLegacySubmit}
              sessionStatus={sessionStatus}
              status={status}
            />
          ) : currentForm ? (
            <DynamicFormRenderer
              formSchema={currentForm}
              formData={formData}
              onChange={updateDynamicFormData}
              onSubmit={handleDynamicSubmit}
            />
          ) : (
            <div className="flex-1 bg-gradient-to-b from-blue-50 to-white p-10 rounded-l-2xl flex items-center justify-center">
              <div className="text-center">
                <div className="text-6xl mb-4">🚀</div>
                <h3 className="text-xl font-semibold text-gray-800 mb-2">
                  Ready to Get Started
                </h3>
                <p className="text-gray-600 mb-6">
                  Select a form to begin your conversational form filling experience
                </p>
                <button
                  onClick={() => setShowFormManager(true)}
                  className="bg-purple-600 text-white px-6 py-3 rounded-lg hover:bg-purple-700 transition-colors shadow-md"
                >
                  Choose Form
                </button>
              </div>
            </div>
          )}
          
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