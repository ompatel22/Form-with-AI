import React, { useState, useEffect, useRef } from "react";
import LanguageSwitcher from "./LanguageSwitcher";

const EnhancedChatSide = ({
  messages,
  inputText,
  setInputText,
  handleSend,
  handleMic,
  status,
  pendingAudio,
  handleAudioEnable,
  onReset,
  isPlaying,
  onSkipAudio,
  currentLanguage,
  onLanguageChange,
  translations
}) => {
  const chatEndRef = useRef(null);
  const [isListening, setIsListening] = useState(false);

  // Scroll to bottom when messages change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleEnhancedSend = async () => {
    await handleSend();
  };

  const handleEnhancedMic = () => {
    setIsListening(true);
    
    // Enhanced microphone handling with interruption detection
    const enhancedMicHandler = () => {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        alert(
          currentLanguage === 'gu' 
            ? "આ બ્રાઉઝરમાં વાણી ઓળખ સપોર્ટેડ નથી. કૃપા કરીને Chrome/Edge વાપરો."
            : "Speech recognition not supported in this browser. Please use Chrome/Edge."
        );
        setIsListening(false);
        return;
      }

      const recognition = new SpeechRecognition();
      recognition.lang = currentLanguage === 'gu' ? 'gu-IN' : 'en-US';
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      recognition.continuous = true;

      let finalTranscript = '';
      let silenceTimer = null;
      const SILENCE_TIMEOUT = 2000; // 2 seconds

      recognition.onresult = (event) => {
        let interimTranscript = '';
        let final = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          
          if (event.results[i].isFinal) {
            final += transcript;
          } else {
            interimTranscript += transcript;
          }
        }

        finalTranscript = final;

        // Reset silence timer
        if (silenceTimer) clearTimeout(silenceTimer);
        if (currentText.length > 0) {
          silenceTimer = setTimeout(() => {
            recognition.stop();
          }, SILENCE_TIMEOUT);
        }
      };

      recognition.onend = () => {
        setIsListening(false);
        if (silenceTimer) clearTimeout(silenceTimer);
        
        if (finalTranscript.trim()) {
          setInputText(finalTranscript.trim());
          // Auto-send after voice input
          setTimeout(() => {
            handleEnhancedSend();
          }, 100);
        }
      };

      recognition.onerror = (event) => {
        setIsListening(false);
        const errorMessage = currentLanguage === 'gu'
          ? "વાણી ઓળખમાં ભૂલ. કૃપા કરીને ફરીથી પ્રયાસ કરો."
          : `Speech recognition error: ${event.error}`;
        console.error(errorMessage);
      };

      recognition.start();
    };

    enhancedMicHandler();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleEnhancedSend();
    }
    // ESC key for interruption
    else if (e.key === "Escape" && isPlaying) {
      onSkipAudio();
    }
  };

  const getStatusText = () => {
    if (isListening) return translations?.status_listening || "listening";
    return translations?.[`status_${status}`] || status;
  };

  return (
    <div className="flex-1 bg-gradient-to-b from-gray-800 to-gray-900 flex flex-col rounded-r-2xl border-l border-gray-700">
      {/* Header */}
      <div className="p-6 border-b border-gray-700 bg-gray-800/50 rounded-tr-2xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-white">
            {translations?.chat_title || "AI Assistant"}
          </h2>
          <LanguageSwitcher 
            currentLanguage={currentLanguage}
            onLanguageChange={onLanguageChange}
            translations={translations}
          />
        </div>
        
        <div className="flex items-center gap-4 text-sm">
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${
              getStatusText() === "idle"
                ? "bg-green-500/20 text-green-300 border border-green-500/30"
                : getStatusText().includes("listening")
                ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                : getStatusText().includes("waiting")
                ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                : "bg-gray-500/20 text-gray-300 border border-gray-500/30"
            }`}
          >
            {getStatusText()}
          </span>
          
          {isPlaying && (
            <div className="flex items-center gap-2">
              <span className="px-2 py-1 bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 rounded-full text-xs">
                🔊 {translations?.ai_speaking || "AI Speaking..."}
              </span>
              <button
                onClick={onSkipAudio}
                className="px-2 py-1 bg-red-500/20 text-red-300 border border-red-500/30 rounded text-xs hover:bg-red-500/30 transition-colors"
                title={translations?.skip_audio || "Skip"}
              >
                {translations?.skip_audio || "Skip"}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-6 space-y-4">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.who === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] p-4 rounded-2xl ${
                msg.who === "user"
                  ? "bg-blue-600 text-white ml-auto"
                  : msg.isError
                  ? "bg-red-500/20 text-red-300 border border-red-500/30"
                  : msg.isSuccess
                  ? "bg-green-500/20 text-green-300 border border-green-500/30"
                  : msg.isInfo
                  ? "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30"
                  : "bg-gray-700 text-white"
              }`}
              style={{
                direction: currentLanguage === 'gu' ? 'ltr' : 'ltr', // Both languages LTR for now
                fontFamily: currentLanguage === 'gu' ? 'Noto Sans Gujarati, sans-serif' : 'inherit'
              }}
            >
              <div className="text-sm leading-relaxed whitespace-pre-wrap">
                {msg.text}
              </div>
              
              {msg.isVoice && (
                <div className="text-xs opacity-70 mt-2 flex items-center gap-1">
                  🎙️ {currentLanguage === 'gu' ? 'અવાજ' : 'Voice'}
                </div>
              )}
              
              <div className="text-xs opacity-50 mt-2">
                {new Date(msg.timestamp).toLocaleTimeString(
                  currentLanguage === 'gu' ? 'gu-IN' : 'en-US'
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Input Controls */}
      <div className="p-6 border-t border-gray-700 bg-gray-800/50 rounded-br-2xl">
        <div className="flex gap-3">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={translations?.type_message || "Type your answer..."}
            className="flex-1 p-3 bg-gray-700 text-white border border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400"
            disabled={isPlaying}
            style={{
              fontFamily: currentLanguage === 'gu' ? 'Noto Sans Gujarati, sans-serif' : 'inherit'
            }}
          />
          
          <button
            onClick={handleEnhancedSend}
            disabled={!inputText.trim() || isPlaying}
            className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 font-medium shadow-md hover:shadow-lg"
          >
            {translations?.send || "Send"}
          </button>
          
          <button
            onClick={handleEnhancedMic}
            disabled={isPlaying}
            className={`px-6 py-3 rounded-xl font-medium shadow-md hover:shadow-lg transition-all duration-200 ${
              isListening
                ? "bg-red-600 text-white animate-pulse"
                : "bg-purple-600 text-white hover:bg-purple-500"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {isListening ? "🛑" : "🎙️"} {translations?.microphone || "Mic"}
          </button>
        </div>

        {pendingAudio && (
          <div className="mt-3 flex items-center justify-between bg-yellow-500/20 border border-yellow-500/30 rounded-lg p-3">
            <span className="text-yellow-300 text-sm">
              {currentLanguage === 'gu' 
                ? "ઓડિયો ચલાવવા માટે ક્લિક કરો" 
                : "Click to enable audio playback"}
            </span>
            <button
              onClick={handleAudioEnable}
              className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-500 transition-colors text-sm"
            >
              🔊 {currentLanguage === 'gu' ? 'સક્ષમ કરો' : 'Enable'}
            </button>
          </div>
        )}

        {/* Voice commands help */}
        <div className="mt-3 text-xs text-gray-400">
          Press the <kbd className="px-2 py-1.5 text-xs font-semibold text-gray-800 bg-gray-100 border border-gray-200 rounded-lg">ESC</kbd> key to skip audio.
        </div>
      </div>
    </div>
  );
};

export default EnhancedChatSide;