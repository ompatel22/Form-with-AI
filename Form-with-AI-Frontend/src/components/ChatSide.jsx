import  React,{ useEffect, useRef } from 'react';

export default function ChatSide({
  messages,
  inputText,
  setInputText,
  handleSend,
  handleMic,
  status,
  pendingAudio,
  handleAudioEnable,
  isPlaying,
  onSkipAudio,
}) {
  const chatRef = useRef(null);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && inputText.trim()) {
      handleSend();
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-gradient-to-b from-gray-800 to-gray-900 p-10 rounded-r-2xl">
      {/* CHAT CONTAINER WITH FIXED HEIGHT AND SCROLLING */}
      <div
        ref={chatRef}
        className="flex-1 overflow-y-auto space-y-4 pr-2 max-h-96 min-h-80 border border-gray-600 rounded-lg p-4 bg-gray-700/50"
        style={{ scrollBehavior: 'smooth' }}
      >
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="text-center">
              <div className="text-3xl mb-2">💬</div>
              <p>Start a conversation with the AI assistant...</p>
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <div
              key={index}
              className={`relative p-4 rounded-xl max-w-[80%] shadow-sm transition-all ${
                msg.who === 'user'
                  ? 'bg-blue-600 ml-auto text-white after:content-[""] after:absolute after:top-2 after:right-[-8px] after:border-8 after:border-transparent after:border-l-blue-600'
                  : msg.isError 
                    ? 'bg-red-600/20 border border-red-500/30 mr-auto text-red-200 after:content-[""] after:absolute after:top-2 after:left-[-8px] after:border-8 after:border-transparent after:border-r-red-600/20'
                    : msg.isSuccess
                      ? 'bg-green-600/20 border border-green-500/30 mr-auto text-green-200 after:content-[""] after:absolute after:top-2 after:left-[-8px] after:border-8 after:border-transparent after:border-r-green-600/20'
                      : 'bg-gray-600 mr-auto text-white after:content-[""] after:absolute after:top-2 after:left-[-8px] after:border-8 after:border-transparent after:border-r-gray-600'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">{msg.text}</div>
                {msg.isVoice && (
                  <span className="ml-2 text-xs opacity-75">🎤</span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
      
      {/* ENHANCED CONTROL BUTTONS */}
      <div className="mt-6">
        {/* Skip Audio Button - Show when AI is speaking */}
        {isPlaying && (
          <div className="mb-3">
            <button
              onClick={onSkipAudio}
              className="w-full bg-yellow-600 text-white p-2 rounded-lg hover:bg-yellow-500 transition-all duration-300 shadow-md hover:shadow-lg font-medium"
            >
              ⏭️ Skip AI Response & Start Listening
            </button>
          </div>
        )}
        
        {/* Input and Send Controls */}
        <div className="flex gap-3">
          <input
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message..."
            className="flex-1 p-3 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
          />
          <button
            onClick={handleSend}
            disabled={!inputText.trim() || status === 'waiting...'}
            className="bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-500 transition-all duration-300 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
          <button
            onClick={handleMic}
            disabled={status === 'listening' || status === 'waiting...'}
            className={`p-3 rounded-lg transition-all duration-300 shadow-md hover:shadow-lg ${
              status === 'listening' 
                ? 'bg-red-600 text-white animate-pulse' 
                : 'bg-gray-600 text-white hover:bg-gray-500'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {status === 'listening' ? '🔴' : '🎙️'}
          </button>
          {pendingAudio && (
            <button
              onClick={handleAudioEnable}
              className="bg-yellow-600 text-white p-3 rounded-lg hover:bg-yellow-500 transition-all duration-300 shadow-md hover:shadow-lg"
            >
              🔊
            </button>
          )}
        </div>
      </div>
      
      <div className="mt-3 text-sm text-gray-400">
        Status: <span className="font-medium text-gray-300">{status}</span>
        {isPlaying && (
          <span className="ml-2 text-yellow-400">• AI Speaking</span>
        )}
      </div>
    </div>
  );
}