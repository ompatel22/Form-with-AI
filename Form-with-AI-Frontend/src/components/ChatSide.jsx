import React, { useEffect, useRef, useState } from "react";

const ChatSide = ({
  messages = [],
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
  language = "gu",
  onLanguageChange
}) => {
  const messagesEndRef = useRef(null);
  const [isAutoListening, setIsAutoListening] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  };

  useEffect(scrollToBottom, [messages]);

  // Enhanced status display with phone call experience indicators
  const getStatusDisplay = () => {
    const statusMap = {
      "idle": { text: "Ready", color: "text-green-300", bg: "bg-green-500/20", border: "border-green-500/30" },
      "🎙️ listening - speak now": { text: "🎙️ Listening", color: "text-blue-300", bg: "bg-blue-500/20", border: "border-blue-500/30" },
      "🎤 got it - keep talking": { text: "🎤 Recording", color: "text-purple-300", bg: "bg-purple-500/20", border: "border-purple-500/30" },
      "⏳ processing in 1.2s...": { text: "⏳ Processing", color: "text-yellow-300", bg: "bg-yellow-500/20", border: "border-yellow-500/30" },
      "processing speech": { text: "🔄 Processing", color: "text-blue-300", bg: "bg-blue-500/20", border: "border-blue-500/30" },
      "waiting...": { text: "⏳ Thinking", color: "text-yellow-300", bg: "bg-yellow-500/20", border: "border-yellow-500/30" },
      "error": { text: "❌ Error", color: "text-red-300", bg: "bg-red-500/20", border: "border-red-500/30" },
      "🔇 background noise detected": { text: "🔇 Noise", color: "text-orange-300", bg: "bg-orange-500/20", border: "border-orange-500/30" }
    };
    
    return statusMap[status] || { text: status, color: "text-gray-300", bg: "bg-gray-500/20", border: "border-gray-500/30" };
  };

  const statusInfo = getStatusDisplay();

  // Language switch handler
  const handleLanguageSwitch = () => {
    const newLanguage = language === "en" ? "gu" : "en";
    onLanguageChange && onLanguageChange(newLanguage);
  };

  // Enhanced message rendering with language support
  const renderMessage = (msg, index) => {
    const isUser = msg.who === "user";
    const isError = msg.isError;
    const isInfo = msg.isInfo;
    const isSuccess = msg.isSuccess;

    let bgClass = isUser ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-100";
    let alignClass = isUser ? "ml-auto" : "mr-auto";

    if (isError) {
      bgClass = "bg-red-600/80 text-white border border-red-500/50";
    } else if (isInfo) {
      bgClass = "bg-blue-600/80 text-white border border-blue-500/50";
    } else if (isSuccess) {
      bgClass = "bg-green-600/80 text-white border border-green-500/50";
    }

    return (
      <div key={index} className={`mb-4 flex ${isUser ? "justify-end" : "justify-start"}`}>
        <div className={`max-w-xs lg:max-w-md px-4 py-3 rounded-2xl shadow-lg ${bgClass} ${alignClass}`}>
          <div className="flex items-start gap-2">
            {!isUser && (
              <div className="flex-shrink-0 w-6 h-6 bg-gradient-to-br from-blue-400 to-purple-500 rounded-full flex items-center justify-center text-xs font-bold text-white mt-0.5">
                AI
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm leading-relaxed break-words">{msg.text}</p>
              <div className="flex items-center gap-2 mt-2 text-xs opacity-75">
                <span>{new Date(msg.timestamp).toLocaleTimeString()}</span>
                {msg.isVoice && <span className="text-blue-300">🎙️</span>}
                {msg.tone && <span className="capitalize">({msg.tone})</span>}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex-1 bg-gradient-to-b from-gray-800 to-gray-900 flex flex-col min-h-0">
      {/* Enhanced Header with Phone Call Controls */}
      <div className="bg-gray-700 px-6 py-4 border-b border-gray-600">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold text-white">AI Assistant</h2>
            {isPlaying && (
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
                <span className="text-sm text-green-300">Speaking...</span>
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {/* Language Switch Button */}
            {/* <button
              onClick={handleLanguageSwitch}
              className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-500 transition-colors"
              title={language === "en" ? "Switch to Gujarati" : "Switch to English"}
            >
              {language === "en" ? "ગુ" : "EN"}
            </button> */}
            
            {/* Phone Call Status */}
            <div className={`px-3 py-1.5 rounded-lg text-sm border ${statusInfo.bg} ${statusInfo.color} ${statusInfo.border}`}>
              {statusInfo.text}
            </div>
          </div>
        </div>

        {/* Phone Call Experience Indicator */}
        {(isPlaying || status.includes("listening")) && (
          <div className="mt-3 p-3 bg-gray-600/50 rounded-lg border border-gray-500/50">
            <div className="flex items-center gap-2 text-sm text-gray-300">
              <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></div>
              <span>Phone call mode active - speak anytime to interrupt</span>
            </div>
          </div>
        )}
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-gray-400 mt-12">
            <div className="text-6xl mb-4">💬</div>
            <p className="text-lg mb-2">Ready to chat!</p>
            <p className="text-sm">
              {language === "en" 
                ? "Click the microphone to start a voice conversation or type your message."
                : "વાતચીત શરૂ કરવા માઈક્રોફોન પર ક્લિક કરો અથવા તમારો સંદેશ ટાઈપ કરો."
              }
            </p>
          </div>
        ) : (
          messages.map((msg, index) => renderMessage(msg, index))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Enhanced Input Area with Phone Call Controls */}
      <div className="bg-gray-700 border-t border-gray-600 p-6">
        {/* Skip Audio Button (when AI is speaking) */}
        {isPlaying && (
          <div className="mb-4 flex justify-center">
            <button
              onClick={onSkipAudio}
              className="px-6 py-2 bg-orange-600 hover:bg-orange-500 text-white rounded-lg transition-colors shadow-lg flex items-center gap-2"
            >
              ⏭️ Skip & Speak
            </button>
          </div>
        )}

        {/* Audio Enable Button */}
        {pendingAudio && (
          <div className="mb-4 flex justify-center">
            <button
              onClick={handleAudioEnable}
              className="bg-green-600 hover:bg-green-500 text-white px-6 py-2 rounded-lg transition-colors shadow-lg flex items-center gap-2"
            >
              🔊 Enable Audio
            </button>
          </div>
        )}

        {/* Input Controls */}
        <div className="flex items-center gap-3">
          {/* Microphone Button - Enhanced for Phone Call Experience */}
          <button
            onClick={handleMic}
            disabled={status === "waiting..."}
            className={`flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center text-white font-bold shadow-lg ${
              status.includes("listening") || status.includes("processing")
                ? "bg-red-500 hover:bg-red-400 mic-recording"
                : status === "waiting..."
                ? "bg-gray-500 cursor-not-allowed opacity-50"
                : "bg-blue-600 hover:bg-blue-500 mic-idle"
            }`}
            title={
              status.includes("listening") 
                ? "Recording - Click to stop" 
                : "Click to start voice input"
            }
          >
            <div className={`transition-all duration-200 ${
              status.includes("listening") || status.includes("processing") 
                ? "animate-bounce text-lg" 
                : "text-base"
            }`}>
              {status.includes("listening") || status.includes("processing") ? "🔴" : "🎙️"}
            </div>
          </button>

          {/* Text Input */}
          <div className="flex-1 flex gap-2">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSend()}
              disabled={status === "waiting..."}
              placeholder={
                language === "en" 
                  ? "Type your message..." 
                  : "તમારો સંદેશ લખો..."
              }
              className="flex-1 px-4 py-3 bg-gray-600 text-white rounded-xl border border-gray-500 focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20 outline-none transition-all placeholder-gray-400"
            />
            
            {/* Send Button */}
            <button
              onClick={handleSend}
              disabled={!inputText.trim() || status === "waiting..."}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-500 disabled:cursor-not-allowed text-white rounded-xl transition-colors shadow-lg font-medium"
            >
              {language === "en" ? "Send" : "મોકલો"}
            </button>
          </div>
        </div>

        {/* Phone Call Instructions */}
        <div className="mt-4 text-center">
          <p className="text-xs text-gray-400">
            {language === "en" 
              ? "💡 Phone call mode: You can interrupt AI anytime by speaking"
              : "💡 ફોન કૉલ મોડ: તમે કોઈપણ સમયે બોલીને AI ને અટકાવી શકો છો"
            }
          </p>
        </div>

        {/* Reset Button
        <div className="mt-4 flex justify-center">
          <button
            onClick={onReset}
            className="px-4 py-2 bg-red-600/80 hover:bg-red-600 text-white text-sm rounded-lg transition-colors border border-red-500/50"
          >
            {language === "en" ? "🔄 Reset Chat" : "🔄 ચેટ રીસેટ કરો"}
          </button>
        </div> */}
      </div>
    </div>
  );
};

export default ChatSide;