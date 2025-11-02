import React, { useState, useEffect, useRef } from "react";
import FormSide from "./components/FormSide.jsx";
import ChatSide from "./components/ChatSide.jsx";
import FormManager from "./components/FormManager.jsx";
import DynamicFormRenderer from "./components/DynamicFormRenderer.jsx";

const API = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

// Helper to bypass the ngrok browser warning page.
const fetchWithNgrokHeader = (url, options = {}) => {
  const headers = {
    ...options.headers,
    'ngrok-skip-browser-warning': 'true',
  };
  return fetch(url, { ...options, headers });
};

function App() {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [status, setStatus] = useState("idle");
  const [pendingAudio, setPendingAudio] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false); // Current conversation language
  const [language, setLanguage] = useState("en");
  
  // Dynamic form state only (no legacy)
  const [currentForm, setCurrentForm] = useState(null);
  const [formData, setFormData] = useState({});
  const [showFormManager, setShowFormManager] = useState(true); // Start with form manager
  
  // Enhanced phone call experience state
  const [isPhoneCallMode, setIsPhoneCallMode] = useState(false); // Simplified phone mode
  
  // Session Management - Generate unique session IDs for each form
  const [sessionId, setSessionId] = useState(() => 
    `form_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  );
  
  const initialized = useRef(false);
  const currentAudio = useRef(null);
  const activeRecognition = useRef(null);
  const microphoneState = useRef("idle"); // Track microphone state
  const languageRef = useRef("en"); // Ref to always get current language synchronously

  const b64ToBlob = (b64, mime) => {
    const bytes = atob(b64);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    return new Blob([arr], { type: mime });
  };

  const speakText = (text) => {
    if (!text || !("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(text);
    
    // Set language based on conversation language - use ref for current value
    utterance.lang = languageRef.current === "gu" ? "gu-IN" : "en-US";
    utterance.rate = 0.9;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
  };

  // Enhanced phone call experience with better audio handling
  const playBase64WavOrFallback = async (b64, text) => {
    if (!b64 && text) {
      setIsPhoneCallMode(true);
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
      setIsPhoneCallMode(true);

      await audio.play();
      setPendingAudio(null);

      // Enhanced auto-listening with phone call experience
      audio.addEventListener('ended', () => {
        setIsPlaying(false);
        currentAudio.current = null;
        setTimeout(() => {
          console.log("🎙️ Phone call mode: Auto-starting microphone after TTS");
          handleMic(true); // Pass true to indicate auto-start
        }, 300);
      });

      setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (err) {
      console.warn("Audio playback failed, using speech synthesis:", err);
      setPendingAudio({ b64, text });
      
      if (text) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = languageRef.current === "gu" ? "gu-IN" : "en-US";
        utterance.rate = 0.9;
        utterance.pitch = 1.0;
        
        setIsPhoneCallMode(true);
        
        // Phone call mode for speech synthesis
        utterance.onend = () => {
          setIsPlaying(false);
          setTimeout(() => {
            console.log("🎙️ Phone call mode: Auto-starting microphone after speech synthesis");
            handleMic(true);
          }, 300);
        };
        
        setIsPlaying(true);
        window.speechSynthesis.speak(utterance);
      }
    }
  };

  // Stop phone call mode with cleanup
  const stopPhoneCallMode = () => {
    setIsPhoneCallMode(false);
    
    if (activeRecognition.current) {
      activeRecognition.current.stop();
      activeRecognition.current = null;
    }
    
    microphoneState.current = "idle";
    console.log("📞 Phone call mode deactivated");
  };

  // Enhanced skip audio function
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
    stopPhoneCallMode();
    
    // Immediately start listening after skip
    setTimeout(() => {
      console.log("🎙️ Starting microphone after skip");
      handleMic(true);
    }, 200);
  };

  // Enhanced dynamic form data update
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

  // Enhanced language detection and switching
  const detectLanguageSwitch = (text) => {
    if (!text) return null;
    
    const textLower = text.toLowerCase().trim();
    
    // Enhanced language switching patterns
    const switchToGujarati = [
      "gujarati", "ગુજરાતી", "gujarati ma bolo", "gujarati mein bolo",
      "change to gujarati", "switch to gujarati", "gujarati please",
      "gujarati ma", "ગુજરાતીમાં બોલો", "ગુજરાતી ભાષા"
    ];
    
    const switchToEnglish = [
      "english", "અંગ્રેજી", "english bolo", "english ma bolo",
      "change to english", "switch to english", "english please",
      "અંગ્રેજીમાં બોલો", "અંગ્રેજી ભાષા"
    ];
    
    if (languageRef.current === "en") {
      for (const pattern of switchToGujarati) {
        if (textLower.includes(pattern)) {
          return "gu";
        }
      }
    } else if (languageRef.current === "gu") {
      for (const pattern of switchToEnglish) {
        if (textLower.includes(pattern)) {
          return "en";
        }
      }
    }
    
    return null;
  };

  // Enhanced Dynamic backend chat with better language and interruption support
  const dynamicBackendChat = async (msg, includeFormData = true) => {
    if (!currentForm) return;

    // Detect language switch
    const newLanguage = detectLanguageSwitch(msg);
    if (newLanguage && newLanguage !== languageRef.current) {
      languageRef.current = newLanguage;
      setLanguage(newLanguage);
      console.log("Language switched to:", newLanguage);
    }

    setStatus("waiting...");
    try {
      const requestBody = { 
        session_id: sessionId, 
        form_id: currentForm.id,
        message: msg,
        language: newLanguage || languageRef.current, // Use detected language or current
        user_language_preference: languageRef.current // Send current UI language
      };

      if (includeFormData && Object.keys(formData).length > 0) {
        requestBody.manual_form_data = formData;
      }

      const res = await fetchWithNgrokHeader(`${API}/dynamic-chat`, {
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

      // Update language if switched by backend
      if (data.language && data.language !== languageRef.current) {
        languageRef.current = data.language;
        setLanguage(data.language);
        console.log("Backend switched language to:", data.language);
      }

      if (data.reply) {
        setMessages((prev) => [
          ...prev,
          {
            text: data.reply,
            who: "agent",
            timestamp: new Date().toISOString(),
            action: data.action,
            tone: data.tone,
            language: data.language || language,
            originalText: data.original_text // Store original if translated
          },
        ]);
      }

      // Update form data based on form_summary and updates
      setFormData(prev => {
        const newFormData = { ...prev };

        // Update from form_summary.fields (comprehensive field state)
        if (data.form_summary && data.form_summary.fields) {
          Object.entries(data.form_summary.fields).forEach(([fieldName, fieldInfo]) => {
            if (fieldInfo.value && fieldInfo.status === 'collected') {
              newFormData[fieldName] = fieldInfo.value;
              console.log(`📝 Form field updated from summary: ${fieldName} = ${fieldInfo.value}`);
            }
          });
        }

        // Update from direct updates field (latest changes)
        if (data.updates) {
          Object.entries(data.updates).forEach(([fieldName, value]) => {
            if (value !== null && value !== undefined) {
              newFormData[fieldName] = value;
              console.log(`📝 Form field updated directly: ${fieldName} = ${value}`);
            }
          });
        }

        // Log conditional field triggers for debugging
        if (data.conditional_fields_triggered && data.conditional_fields_triggered.length > 0) {
          console.log(`🔄 Conditional fields triggered: ${data.conditional_fields_triggered.join(', ')}`);
        }

        console.log("📋 Complete form data state:", newFormData);
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
      stopPhoneCallMode();
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
        originalLanguage: language
      },
    ]);
    setInputText("");

    await dynamicBackendChat(message);
  };

  // Enhanced microphone handling with better state management
  const handleMic = (isAutoStart = false) => {
    const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Rec) {
      alert(
        "Speech recognition not supported in this browser. Please type your message or try Chrome/Edge."
      );
      return;
    }

    // Prevent multiple microphone instances
    if (microphoneState.current === "active" && !isAutoStart) {
      console.log("Microphone already active, ignoring request");
      return;
    }

    // Stop phone call mode when user manually starts microphone
    if (!isAutoStart) {
      stopPhoneCallMode();
    }

    // Stop any existing recognition
    if (activeRecognition.current) {
      activeRecognition.current.stop();
      activeRecognition.current = null;
    }

    const rec = new Rec();
    rec.lang = languageRef.current === "gu" ? "gu-IN" : "en-US";
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.continuous = true;
    
    activeRecognition.current = rec;
    microphoneState.current = "active";
    
    // Smart timeout and noise detection
    let silenceTimer = null;
    let noiseTimer = null;
    let finalTranscript = '';
    let interimTranscript = '';
    let speechDetected = false;
    let lastSpeechTime = Date.now();
    
    // Adjusted timeouts for different modes
    const SILENCE_TIMEOUT = isAutoStart ? 2000 : 3000;
    const MAX_LISTENING_TIME = isAutoStart ? 12000 : 25000;
    const NOISE_TIMEOUT = 3000;
    const MIN_SPEECH_LENGTH = 2;

    setStatus("🎙️ listening - speak now");

    // Auto-stop after max listening time
    const maxTimer = setTimeout(() => {
      console.log("Max listening time reached, stopping");
      rec.stop();
    }, MAX_LISTENING_TIME);

    // Stop if only noise detected for too long
    const startNoiseTimer = () => {
      if (noiseTimer) clearTimeout(noiseTimer);
      noiseTimer = setTimeout(() => {
        if (!speechDetected && !isAutoStart) {
          console.log("Only background noise detected, stopping");
          setStatus("🔇 background noise detected");
          rec.stop();
        }
      }, NOISE_TIMEOUT);
    };

    if (!isAutoStart) {
      startNoiseTimer();
    }

    rec.onresult = (e) => {
      let interim = '';
      let final = '';
      
      for (let i = 0; i < e.results.length; i++) {
        const transcript = e.results[i][0].transcript;
        const confidence = e.results[i][0].confidence;
        
        // More lenient confidence for Gujarati
        const confidenceThreshold = languageRef.current === "gu" ? 0.4 : 0.6;
        
        if (confidence > confidenceThreshold || e.results[i].isFinal) {
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
        
        if (noiseTimer) {
          clearTimeout(noiseTimer);
          noiseTimer = null;
        }
        
        if (silenceTimer) {
          clearTimeout(silenceTimer);
        }
        
        setStatus("🎤 got it - keep talking");
        console.log("Real speech detected:", currentText);
        
        silenceTimer = setTimeout(() => {
          console.log("Silence after real speech, processing");
          setStatus("processing speech");
          rec.stop();
        }, SILENCE_TIMEOUT);
      }
    };

    rec.onend = () => {
      // Clear all timers
      if (silenceTimer) clearTimeout(silenceTimer);
      if (noiseTimer) clearTimeout(noiseTimer);
      if (maxTimer) clearTimeout(maxTimer);
      
      microphoneState.current = "idle";
      activeRecognition.current = null;
      setStatus("idle");
      
      const finalText = finalTranscript.trim();
      
      // Process if we have meaningful speech
      if (finalText && finalText.length >= MIN_SPEECH_LENGTH && speechDetected) {
        console.log("Processing final speech:", finalText);
        
        setMessages((prev) => [
          ...prev,
          {
            text: finalText,
            who: "user",
            timestamp: new Date().toISOString(),
            isVoice: true,
            originalLanguage: language
          },
        ]);
        
        dynamicBackendChat(finalText);
      } else if (!speechDetected && !isAutoStart) {
        console.log("Only background noise, no action taken");
        const noiseMessage = languageRef.current === "en" 
          ? "Only background noise detected. Click the microphone when you're ready to speak."
          : "માત્ર પૃષ્ઠભૂમિનો અવાજ સાંભળ્યો. તમે બોલવા તૈયાર હો ત્યારે માઇક્રોફોન પર ક્લિક કરો.";
          
        setMessages((prev) => [
          ...prev,
          {
            text: noiseMessage,
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
      
      microphoneState.current = "idle";
      activeRecognition.current = null;
      setStatus("error");
      
      // Better error handling
      let errorMessage = "Speech recognition error";
      if (e.error === 'no-speech') {
        errorMessage = languageRef.current === "en" 
          ? "No speech detected. Try speaking louder or closer to the microphone."
          : "કોઈ વાણી મળી નથી. જોરથી બોલવાનો અથવા માઇક્રોફોનની નજીક બોલવાનો પ્રયાસ કરો.";
      } else if (e.error === 'audio-capture') {
        errorMessage = languageRef.current === "en"
          ? "Microphone access error. Please check your microphone permissions."
          : "માઇક્રોફોન એક્સેસ એરર. કૃપા કરીને તમારી માઇક્રોફોન પરવાનગીઓ તપાસો.";
      } else if (e.error === 'not-allowed') {
        errorMessage = languageRef.current === "en"
          ? "Microphone access denied. Please allow microphone access and try again."
          : "માઇક્રોફોનની પરવાનગી નકારવામાં આવી. કૃપા કરીને માઇક્રોફોનની પરવાનગી આપો અને ફરીથી પ્રયાસ કરો.";
      }
      
      if (!isAutoStart) {
        setMessages((prev) => [
          ...prev,
          {
            text: errorMessage,
            who: "agent",
            timestamp: new Date().toISOString(),
            isError: true,
          },
        ]);
      }
      
      setTimeout(() => setStatus("idle"), 2000);
    };

    rec.onspeechstart = () => {
      console.log("Speech pattern detected");
      speechDetected = true;
      setStatus("🎤 listening - I hear you");
      
      if (noiseTimer) {
        clearTimeout(noiseTimer);
        noiseTimer = null;
      }
    };

    rec.onspeechend = () => {
      console.log("Speech pattern ended");
      setStatus("⏳ processing...");
    };

    try {
      rec.start();
    } catch (err) {
      console.error("Failed to start speech recognition:", err);
      microphoneState.current = "idle";
      setStatus("error");
      if (!isAutoStart) {
        alert("Could not start voice recognition. Please check microphone permissions.");
      }
    }
  };

  const handleAudioEnable = async () => {
    if (pendingAudio) {
      await playBase64WavOrFallback(pendingAudio.b64, pendingAudio.text);
      setPendingAudio(null);
    }
  };

  // Enhanced language change handler with better reliability
  const handleLanguageChange = async (newLanguage) => {
    console.log("🌐 Language change initiated:", languageRef.current, "→", newLanguage);
    
    // Prevent unnecessary changes
    if (languageRef.current === newLanguage) {
      console.log("Language already set to", newLanguage);
      return;
    }
    
    try {
      // Stop any active audio/speech immediately
      if (currentAudio.current) {
        currentAudio.current.pause();
        currentAudio.current = null;
        console.log("🔇 Stopped current audio");
      }
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
        console.log("🔇 Cancelled speech synthesis");
      }
      
      setIsPlaying(false);
      stopPhoneCallMode();
      
      // Update language ref IMMEDIATELY for synchronous access
      languageRef.current = newLanguage;
      console.log("✅ Language ref updated to:", languageRef.current);
      
      // Update language state for UI components
      setLanguage(newLanguage);
      console.log("✅ Language state updated to:", newLanguage);
      
      // Send explicit language change command to backend
      const langCommands = {
        "gu": "switch to gujarati language please",
        "en": "switch to english language please"
      };
      
      const langCommand = langCommands[newLanguage];
      console.log("🌐 Sending language change command:", langCommand);
      
      // Send language change request without form data
      await dynamicBackendChat(langCommand, false);
      
      // Update UI message
      const switchMessage = newLanguage === "gu" 
        ? "🌐 ભાષા બદલીને ગુજરાતીમાં સેટ કરી દીધી!" 
        : "🌐 Language switched to English!";
        
      setMessages(prev => [
        ...prev,
        {
          text: switchMessage,
          who: "agent",
          timestamp: new Date().toISOString(),
          isInfo: true,
          tone: "friendly"
        }
      ]);
      
      console.log("✅ Language change completed successfully");
      
    } catch (error) {
      console.error("❌ Language change failed:", error);
      
      // Revert language on error - need to get the old value
      const oldLanguage = newLanguage === "gu" ? "en" : "gu";
      languageRef.current = oldLanguage;
      setLanguage(oldLanguage);
      
      const errorMessage = oldLanguage === "en" 
        ? "Failed to change language. Please try again."
        : "ભાષા બદલવામાં નિષ્ફળતા. કૃપા કરીને ફરીથી પ્રયાસ કરો.";
        
      setMessages(prev => [
        ...prev,
        {
          text: errorMessage,
          who: "agent",
          timestamp: new Date().toISOString(),
          isError: true
        }
      ]);
    }
  };

  // Rest of the component remains the same...
  const handleDynamicSubmit = async (e) => {
    e.preventDefault();

    try {
      setStatus("submitting");

      const submissionData = {
        session_id: sessionId,
        responses: formData
      };

      const res = await fetchWithNgrokHeader(`${API}/forms/${currentForm.id}/submit`, {
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

      stopPhoneCallMode();

    } catch (err) {
      console.error("Submission error:", err);
      alert(`Error submitting form: ${err.message}`);
    } finally {
      setStatus("idle");
    }
  };

  const handleFormSelected = (form) => {
    console.log("Form selected:", form);
    
    const newSessionId = `form_${form.id}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newSessionId);
    
    setCurrentForm(form);
    setFormData({});
    setMessages([]);
    setShowFormManager(false);
    setLanguage("en");
    
    stopPhoneCallMode();
    
    window.history.pushState({}, '', `/forms/${form.id}/fill`);
    setTimeout(() => dynamicBackendChat("", false), 200);
  };

  const handleReset = async () => {
    if (!confirm("Are you sure you want to reset the conversation and form?")) {
      return;
    }

    try {
      stopPhoneCallMode();
      
      await fetchWithNgrokHeader(`${API}/reset?session_id=${sessionId}`, {
        method: "POST",
      });

      setMessages([]);
      setStatus("idle");
      setPendingAudio(null);
      setLanguage("en");
      
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
    stopPhoneCallMode();
    
    setShowFormManager(true);
    setCurrentForm(null);
    setFormData({});
    setMessages([]);
    setStatus("idle");
    setLanguage("en");
    
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
          await fetchWithNgrokHeader(`${API}/reset?session_id=${sessionId}`, {
            method: "POST",
          });
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

  // Handle loading form directly from URL
  useEffect(() => {
    const path = window.location.pathname;
    const match = path.match(/^\/forms\/(.+)\/fill$/);

    if (match && match[1]) {
      const formId = match[1];
      const loadFormFromUrl = async (id) => {
        try {
          const response = await fetchWithNgrokHeader(`${API}/forms/${id}`);
          if (response.ok) {
            const data = await response.json();
            handleFormSelected(data.form);
          } else {
            alert('The requested form could not be found. Returning to the form manager.');
            window.history.replaceState({}, document.title, "/");
          }
        } catch (error) {
          console.error('Error loading form from URL:', error);
          alert('There was an error loading the form.');
          window.history.replaceState({}, document.title, "/");
        }
      };
      loadFormFromUrl(formId);
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPhoneCallMode();
    };
  }, []);

  // Sync languageRef with language state
  useEffect(() => {
    languageRef.current = language;
    console.log("🔄 Language ref synced to:", language);
  }, [language]);

  if (showFormManager) {
    return (
      <FormManager
        onFormSelected={handleFormSelected}
        onClose={() => setShowFormManager(false)}
      />
    );
  }

  return (
    <div className="h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-4 md:p-8 font-inter antialiased flex flex-col">
      <div className="max-w-7xl mx-auto w-full flex flex-col flex-1 min-h-0">
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
            
            {/* {currentForm && (
              <button
                onClick={handleReset}
                className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-500 transition-colors shadow-md"
              >
                Reset Chat
              </button>
            )} */}
          </div>
          
          <div className="flex items-center justify-center gap-4 text-sm text-gray-300">
            <span
              className={`px-3 py-1 rounded-full ${
                status === "idle"
                  ? "bg-green-500/20 text-green-300 border border-green-500/30"
                  : status === "waiting..."
                  ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                  : status.includes("listening")
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

            <span className="px-3 py-1 bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-full">
              Lang: {language === "en" ? "English" : "ગુજરાતી"}
            </span>
          </div>
        </div>

        {/* Main Content with Dark Theme */}
        <div className="flex flex-col lg:flex-row gap-6 shadow-2xl rounded-2xl overflow-hidden bg-gray-800 border border-gray-700 flex-1 min-h-0">
          {currentForm ? (
            <div className="flex-1 overflow-y-auto">
              <DynamicFormRenderer
                formSchema={currentForm}
                formData={formData}
                onChange={updateDynamicFormData}
                onSubmit={handleDynamicSubmit}
              />
            </div>
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
            language={language}
            onLanguageChange={handleLanguageChange}
          />
        </div>
      </div>
    </div>
  );
}

export default App;