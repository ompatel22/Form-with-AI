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
    <div className="flex-1 flex flex-col bg-gradient-to-b from-white to-gray-50 p-10 rounded-r-2xl">
      {/* CHAT CONTAINER WITH FIXED HEIGHT AND SCROLLING */}
      <div
        ref={chatRef}
        className="flex-1 overflow-y-auto space-y-4 pr-2 max-h-96 min-h-80 border border-gray-200 rounded-lg p-4 bg-white/50"
        style={{ scrollBehavior: 'smooth' }}
      >
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`relative p-4 rounded-xl max-w-[80%] shadow-sm transition-all ${
              msg.who === 'user'
                ? 'bg-blue-100 ml-auto text-gray-800 after:content-[""] after:absolute after:top-2 after:right-[-8px] after:border-8 after:border-transparent after:border-l-blue-100'
                : 'bg-gray-100 mr-auto text-gray-800 after:content-[""] after:absolute after:top-2 after:left-[-8px] after:border-8 after:border-transparent after:border-r-gray-100'
            }`}
          >
            {msg.text}
          </div>
        ))}
      </div>
      <div className="mt-6 flex gap-3">
        <input
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your message..."
          className="flex-1 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
        />
        <button
          onClick={handleSend}
          className="bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 transition-all duration-300 shadow-md hover:shadow-lg"
        >
          Send
        </button>
        <button
          onClick={handleMic}
          className="bg-gray-600 text-white p-3 rounded-lg hover:bg-gray-700 transition-all duration-300 shadow-md hover:shadow-lg"
        >
          🎙️
        </button>
        {pendingAudio && (
          <button
            onClick={handleAudioEnable}
            className="bg-yellow-500 text-gray-800 p-3 rounded-lg hover:bg-yellow-600 transition-all duration-300 shadow-md hover:shadow-lg"
          >
            🔊
          </button>
        )}
      </div>
      <div className="mt-3 text-sm text-gray-500">Status: <span className="font-medium">{status}</span></div>
    </div>
  );
}