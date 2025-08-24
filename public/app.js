const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const recordBtn = document.getElementById("recordBtn");

let recognition;
if ("webkitSpeechRecognition" in window) {
  recognition = new webkitSpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = "en-US";

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    userInput.value = transcript;
    sendMessage(); // auto-send after speech input
  };

  recognition.onerror = (event) => {
    console.error("Speech recognition error:", event.error);
  };
}

// ✅ Append message to chat
function appendMessage(sender, text) {
  const msg = document.createElement("div");
  msg.classList.add("message", sender);
  msg.textContent = text;
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// ✅ Send user message to backend
async function sendMessage() {
  const text = userInput.value.trim();
  if (!text) return;

  appendMessage("user", text);
  userInput.value = "";

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user: text })
    });

    const data = await res.json();
    console.log("Agent response:", data);

    if (data.ask) {
      appendMessage("agent", data.ask);
    } else if (data.action === "done") {
      appendMessage("agent", "✅ All fields completed. Thank you!");
    }
  } catch (err) {
    console.error("Fetch error:", err);
    appendMessage("agent", "⚠️ Something went wrong.");
  }
}

// ✅ Event listeners
sendBtn.addEventListener("click", sendMessage);

recordBtn.addEventListener("click", () => {
  if (recognition) {
    recognition.start();
    console.log("🎤 Listening...");
  } else {
    alert("Speech recognition not supported in this browser.");
  }
});

// ✅ On load, greet user
window.onload = () => {
  appendMessage("agent", "Hello! Let's get started. Could you provide your first detail?");
};
