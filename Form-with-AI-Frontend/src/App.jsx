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
  const [isPlaying, setIsPlaying] = useState(false);
  
  // Dynamic form state only (no legacy)
  const [currentForm, setCurrentForm] = useState(null);
  const [formData, setFormData] = useState({});
  const [showFormManager, setShowFormManager] = useState(true); // Start with form manager
  
  // Session Management - Generate unique session IDs for each form
  const [sessionId, setSessionId] = useState(() => 
    `form_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  );
  
  const initialized = useRef(false);
  const currentAudio = useRef(null);

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
      
      // Stop any currently playing audio
      if (currentAudio.current) {
        currentAudio.current.pause();
        currentAudio.current = null;
      }
      
      currentAudio.current = audio;
      setIsPlaying(true);

      await audio.play();
      setPendingAudio(null);

      // ENHANCED AUTO-LISTENING: Better timing and delay handling
      audio.addEventListener('ended', () => {
        setIsPlaying(false);
        currentAudio.current = null;
        
        // Add longer delay to allow for natural conversation flow
        setTimeout(() => {
          console.log("🎙️ Auto-starting microphone after TTS completion");
          handleMic();
        }, 500); // Increased delay to 800ms for better UX
      });

      setTimeout(() => URL.revokeObjectURL(url), 2000);
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
          setIsPlaying(false);
          setTimeout(() => {
            console.log("🎙️ Auto-starting microphone after speech synthesis");
            handleMic();
          }, 500);
        };
        
        setIsPlaying(true);
        window.speechSynthesis.speak(utterance);
      }
    }
  };

  // SKIP AUDIO FUNCTION - Allow users to skip AI response
  const skipAudio = () => {
    if (currentAudio.current) {
      currentAudio.current.pause();
      currentAudio.current = null;
    }
    
    // Stop speech synthesis if running
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
    }
    
    setIsPlaying(false);
    setPendingAudio(null);
    
    // Immediately start listening after skip
    setTimeout(() => {
      console.log("🎙️ Starting microphone after skip");
      handleMic();
    }, 200);
  };

  // Dynamic form data update function
  const updateDynamicFormData = (fieldName, value) => {
    setFormData(prev => {
      const updated = {
        ...prev,
        [fieldName]: value
      };
      console.log("Form data updated:", updated);
      return updated;
    });
  };

  // ENHANCED Dynamic backend chat with manual field detection
  const dynamicBackendChat = async (msg, includeFormData = true) => {
  if (!currentForm) return;

  setStatus("waiting...");
  try {
    const requestBody = { 
      session_id: sessionId, 
      form_id: currentForm.id,
      message: msg 
    };

    if (includeFormData && Object.keys(formData).length > 0) {
      requestBody.manual_form_data = formData;
    }

    const res = await fetch(`${API}/dynamic-chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
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

    // Update form data based on form_summary and updates
    setFormData(prev => {
      const newFormData = { ...prev };

      // Update from form_summary.fields
      if (data.form_summary && data.form_summary.fields) {
        Object.entries(data.form_summary.fields).forEach(([fieldName, fieldInfo]) => {
          if (fieldInfo.value && fieldInfo.status === 'collected') {
            newFormData[fieldName] = fieldInfo.value;
          }
        });
      }

      // Update from updates field
      if (data.updates) {
        Object.entries(data.updates).forEach(([fieldName, value]) => {
          if (value) {
            newFormData[fieldName] = value;
          }
        });
      }

      console.log("Updated form data:", newFormData);
      return newFormData;
    });

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

    await dynamicBackendChat(message);
  };

 // ENHANCED MICROPHONE HANDLING - Noise filtering and smart audio detection
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
  rec.interimResults = true;
  rec.maxAlternatives = 1;
  
  // ENHANCED CONFIGURATION with noise handling
  rec.continuous = true;
  rec.maxRecognitionTime = 15000; // Reduced to 15 seconds max to prevent long sessions
  
  // Smart timeout and noise detection
  let silenceTimer = null;
  let noiseTimer = null;
  let finalTranscript = '';
  let interimTranscript = '';
  let speechDetected = false;
  let lastSpeechTime = Date.now();
  
  const SILENCE_TIMEOUT = 3000; // 1.2 seconds after speech ends (faster response)
  const MAX_LISTENING_TIME = 30000; // 6 seconds total listening time (reduced)
  const NOISE_TIMEOUT = 3000; // 2 seconds of no meaningful speech = noise (faster detection)
  const MIN_SPEECH_LENGTH = 3; // Minimum characters to consider as real speech

  setStatus("🎙️ listening - speak now");

  // Auto-stop after max listening time to prevent infinite background noise
  const maxTimer = setTimeout(() => {
    console.log("Max listening time (6s) reached, stopping");
    rec.stop();
  }, MAX_LISTENING_TIME);

  // Stop if only noise detected for too long
  const startNoiseTimer = () => {
    if (noiseTimer) clearTimeout(noiseTimer);
    noiseTimer = setTimeout(() => {
      if (!speechDetected) {
        console.log("Only background noise detected, stopping");
        setStatus("🔇 background noise detected");
        rec.stop();
      }
    }, NOISE_TIMEOUT);
  };

  startNoiseTimer(); // Start noise detection immediately

  rec.onresult = (e) => {
    let interim = '';
    let final = '';
    
    for (let i = 0; i < e.results.length; i++) {
      const transcript = e.results[i][0].transcript;
      const confidence = e.results[i][0].confidence;
      
      // Filter out low-confidence results (likely noise)
      if (confidence > 0.7 || e.results[i].isFinal) {
        if (e.results[i].isFinal) {
          final += transcript;
        } else {
          interim += transcript;
        }
      }
    }
    
    finalTranscript = final;
    interimTranscript = interim;
    
    const currentText = (final + interim).trim();
    const hasRealSpeech = currentText.length >= MIN_SPEECH_LENGTH;
    
    // Clear timers if we detect real speech
    if (hasRealSpeech) {
      speechDetected = true;
      lastSpeechTime = Date.now();
      
      // Clear noise timer since we have real speech
      if (noiseTimer) {
        clearTimeout(noiseTimer);
        noiseTimer = null;
      }
      
      // Clear existing silence timer
      if (silenceTimer) {
        clearTimeout(silenceTimer);
      }
      
      setStatus("🎤 got it - keep talking");
      console.log("Real speech detected:", currentText);
      
      // Reset silence timer for real speech
      silenceTimer = setTimeout(() => {
        console.log("1.2s silence after real speech, processing");
        setStatus("processing speech");
        rec.stop();
      }, SILENCE_TIMEOUT);
    } else if (currentText.length > 0) {
      // Short or low-confidence speech - might be noise
      console.log("Possible noise or unclear speech:", currentText);
    }
  };

  rec.onend = () => {
    // Clear all timers
    if (silenceTimer) clearTimeout(silenceTimer);
    if (noiseTimer) clearTimeout(noiseTimer);
    if (maxTimer) clearTimeout(maxTimer);
    
    setStatus("idle");
    
    const finalText = finalTranscript.trim();
    
    // Only process if we have meaningful speech
    if (finalText && finalText.length >= MIN_SPEECH_LENGTH && speechDetected) {
      console.log("Processing final speech:", finalText);
      
      setMessages((prev) => [
        ...prev,
        {
          text: finalText,
          who: "user",
          timestamp: new Date().toISOString(),
          isVoice: true,
        },
      ]);
      
      dynamicBackendChat(finalText);
    } else if (!speechDetected) {
      // Only background noise detected
      console.log("Only background noise, no action taken");
      setMessages((prev) => [
        ...prev,
        {
          text: "Only background noise detected. Click the microphone when you're ready to speak.",
          who: "agent",
          timestamp: new Date().toISOString(),
          isInfo: true,
        },
      ]);
    } else {
      // Speech too short or unclear
      console.log("Speech too short or unclear");
      setMessages((prev) => [
        ...prev,
        {
          text: "I didn't catch that clearly. Please speak a bit longer and more clearly.",
          who: "agent",
          timestamp: new Date().toISOString(),
          isInfo: true,
        },
      ]);
    }
  };

  rec.onerror = (e) => {
    console.error("Speech recognition error:", e.error);
    
    // Clear all timers
    if (silenceTimer) clearTimeout(silenceTimer);
    if (noiseTimer) clearTimeout(noiseTimer);
    if (maxTimer) clearTimeout(maxTimer);
    
    setStatus("error");
    
    // More specific error messages
    let errorMessage = "Speech recognition error";
    if (e.error === 'no-speech') {
      errorMessage = "No speech detected. Try speaking louder or closer to the microphone.";
    } else if (e.error === 'audio-capture') {
      errorMessage = "Microphone access error. Please check your microphone permissions.";
    } else if (e.error === 'not-allowed') {
      errorMessage = "Microphone access denied. Please allow microphone access and try again.";
    } else {
      errorMessage = `Speech error: ${e.error}. Try using text input instead.`;
    }
    
    setMessages((prev) => [
      ...prev,
      {
        text: errorMessage,
        who: "agent",
        timestamp: new Date().toISOString(),
        isError: true,
      },
    ]);
    
    setTimeout(() => setStatus("idle"), 2000);
  };

  rec.onnomatch = () => {
    console.log("No speech pattern matched - likely noise");
    setStatus("idle");
  };

  rec.onspeechstart = () => {
    console.log("Speech pattern detected");
    speechDetected = true;
    setStatus("🎤 listening - I hear you");
    
    // Clear noise timer when real speech starts
    if (noiseTimer) {
      clearTimeout(noiseTimer);
      noiseTimer = null;
    }
  };

  rec.onspeechend = () => {
    console.log("Speech pattern ended");
    setStatus("⏳ processing in 1.2s...");
  };

  rec.onaudiostart = () => {
    console.log("Audio input started");
  };

  rec.onaudioend = () => {
    console.log("Audio input ended");
  };

  try {
    rec.start();
  } catch (err) {
    console.error("Failed to start speech recognition:", err);
    setStatus("error");
    alert("Could not start voice recognition. Please check microphone permissions.");
  }
};

  const handleAudioEnable = async () => {
    if (pendingAudio) {
      await playBase64WavOrFallback(pendingAudio.b64, pendingAudio.text);
      setPendingAudio(null);
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
    setShowFormManager(false);
    
    // Start conversation for the new form with new session
    setTimeout(() => dynamicBackendChat("", false), 200); // Don't include form data on initial load
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
      
      if (currentForm) {
        setFormData({});
        await dynamicBackendChat("", false);
      }
    } catch (err) {
      console.error("Reset error:", err);
      alert("Failed to reset conversation");
    }
  };

  const goBackToFormManager = () => {
    setShowFormManager(true);
    setCurrentForm(null);
    setFormData({});
    setMessages([]);
    setStatus("idle");
    
    // Stop any playing audio
    if (currentAudio.current) {
      currentAudio.current.pause();
      currentAudio.current = null;
    }
    setIsPlaying(false);
    setPendingAudio(null);
  };

  // Initialize conversation when form is selected
  useEffect(() => {
    if (currentForm && !initialized.current) {
      initialized.current = true;
      
      const startConversation = async () => {
        try {
          setStatus("initializing");
          await fetch(`${API}/reset?session_id=${sessionId}`, { method: "POST" });
          await dynamicBackendChat("", false);
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
    }
  }, [currentForm]);

  if (showFormManager) {
    return (
      <FormManager
        onFormSelected={handleFormSelected}
        onClose={() => setShowFormManager(false)}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-4 md:p-8 font-inter antialiased">
      <div className="max-w-7xl mx-auto">
        {/* Header with Dark Theme */}
        <div className="text-center mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-4 tracking-tight">
            {currentForm 
              ? `${currentForm.title} — AI Assistant`
              : "AI-Powered Form Builder"
            }
          </h1>
          
          {/* Navigation */}
          <div className="flex items-center justify-center gap-4 mb-4">
            <button
              onClick={goBackToFormManager}
              className="px-6 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors shadow-md"
            >
              ← Back to Forms
            </button>
            
            {currentForm && (
              <button
                onClick={handleReset}
                className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-500 transition-colors shadow-md"
              >
                Reset Chat
              </button>
            )}
          </div>
          
          <div className="flex items-center justify-center gap-4 text-sm text-gray-300">
            <span
              className={`px-3 py-1 rounded-full ${
                status === "idle"
                  ? "bg-green-500/20 text-green-300 border border-green-500/30"
                  : status === "waiting..."
                  ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                  : status === "listening"
                  ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                  : status === "error"
                  ? "bg-red-500/20 text-red-300 border border-red-500/30"
                  : "bg-gray-500/20 text-gray-300 border border-gray-500/30"
              }`}
            >
              Status: {status}
            </span>
            
            {isPlaying && (
              <span className="px-3 py-1 bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 rounded-full">
                🔊 AI Speaking...
              </span>
            )}
          </div>
        </div>

        {/* Main Content with Dark Theme */}
        <div className="flex flex-col lg:flex-row gap-6 shadow-2xl rounded-2xl overflow-hidden bg-gray-800 border border-gray-700">
          {currentForm ? (
            <DynamicFormRenderer
              formSchema={currentForm}
              formData={formData}
              onChange={updateDynamicFormData}
              onSubmit={handleDynamicSubmit}
            />
          ) : (
            <div className="flex-1 bg-gradient-to-b from-gray-700 to-gray-800 p-10 rounded-l-2xl flex items-center justify-center">
              <div className="text-center">
                <div className="text-6xl mb-4">🤖</div>
                <h3 className="text-xl font-semibold text-white mb-2">
                  AI Assistant Ready
                </h3>
                <p className="text-gray-300 mb-6">
                  Select a form to begin your conversational form filling experience with AI
                </p>
                <button
                  onClick={() => setShowFormManager(true)}
                  className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-500 transition-colors shadow-md"
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
            isPlaying={isPlaying}
            onSkipAudio={skipAudio}
          />
        </div>
      </div>
    </div>
  );
}

export default App;