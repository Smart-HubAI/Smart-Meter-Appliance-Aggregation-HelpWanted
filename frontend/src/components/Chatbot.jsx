import React, { useState, useEffect, useRef } from "react";
import ReactDOM from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import "./Chatbot.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5000/api";

const Chatbot = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const token = localStorage.getItem("smart_meter_token");
  const userObj = (() => {
    try { return JSON.parse(localStorage.getItem("smart_meter_user") || "null"); } catch { return null; }
  })();
  const consumerId = userObj?.consumer_id || "CON001";
  const userRole = userObj?.role || "consumer";

  const CONSUMER_SUGGESTIONS = [
    "Why is my bill high?",
    "Which appliance consumes the most energy?",
    "How can I reduce my electricity bill?",
    "Compare this month with last month.",
    "Explain my Energy Score.",
    "Why was I flagged?"
  ];

  const ADMIN_SUGGESTIONS = [
    "Which zone consumed the most electricity?",
    "Show critical consumers.",
    "Summarize today's grid.",
    "Show tampering statistics.",
    "Generate today's operational report."
  ];

  const DEVELOPER_SUGGESTIONS = [
    "Explain NILM workflow",
    "Explain appliance signatures",
    "Explain Random Forest",
    "Explain XGBoost",
    "Explain Isolation Forest",
    "Explain Ground Truth",
    "Explain feature engineering",
    "Explain evaluation metrics",
    "Explain Flask API",
    "Explain repository",
    "Explain database schema"
  ];

  let suggestions = CONSUMER_SUGGESTIONS;
  if (userRole === "admin") suggestions = ADMIN_SUGGESTIONS;
  if (userRole === "developer") suggestions = DEVELOPER_SUGGESTIONS;

  // Load history from session storage
  useEffect(() => {
    const saved = sessionStorage.getItem("chatHistory");
    if (saved) {
      setMessages(JSON.parse(saved));
    } else {
      setMessages([{
        role: "assistant",
        content: "Hello! I'm the **⚡ Tata Power AI Energy Assistant**. I can explain your electricity usage, appliances, bills, anomalies, and provide personalised energy-saving recommendations based on your smart meter data."
      }]);
    }
  }, []);

  // Save history on change
  useEffect(() => {
    if (messages.length > 1) { // Don't just save the greeting repeatedly
      sessionStorage.setItem("chatHistory", JSON.stringify(messages));
    }
  }, [messages]);

  // Auto-scroll
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading]);

  const handleSend = async (text) => {
    if (!text.trim()) return;

    const userMessage = { role: "user", content: text };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    try {
      const currentToken = localStorage.getItem("smart_meter_token");
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${currentToken}`
        },
        body: JSON.stringify({
          consumer_id: consumerId,
          role: userRole,
          message: text,
          history: messages.slice(-10) // Send last 10 messages
        })
      });

      const data = await response.json();
      if (data.success) {
        setMessages([...newMessages, { role: "assistant", content: data.answer }]);
      } else {
        setMessages([...newMessages, { role: "assistant", content: `Error: ${data.error || "Unable to process request."}` }]);
      }
    } catch (error) {
      setMessages([...newMessages, { role: "assistant", content: "AI Assistant is temporarily unavailable. Please try again later." }]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    sessionStorage.removeItem("chatHistory");
    setMessages([{
      role: "assistant",
      content: "Hello! I'm the **⚡ Tata Power AI Energy Assistant**. How can I help you today?"
    }]);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  const chatbotContent = (
    <>
      <div className="chatbot-floating-btn" onClick={() => setIsOpen(!isOpen)}>
        {isOpen ? <i className="bi bi-x-lg"></i> : <i className="bi bi-chat-dots-fill"></i>}
      </div>

      <AnimatePresence>
        {isOpen && (
          <motion.div 
            className="chatbot-window shadow-lg"
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
          >
            <div className="chatbot-header">
              <div className="d-flex align-items-center">
                <div className="chatbot-avatar bg-light text-primary rounded-circle p-2 me-2">
                  <i className="bi bi-lightning-charge-fill"></i>
                </div>
                <div>
                  <h6 className="mb-0 fw-bold">⚡ AI Energy Assistant</h6>
                  <small className="text-white-50">Tata Power Analytics</small>
                </div>
              </div>
              <div className="chatbot-header-actions">
                <button className="btn btn-sm btn-link text-white" onClick={clearChat} title="Clear Chat">
                  <i className="bi bi-trash3"></i>
                </button>
              </div>
            </div>

            <div className="chatbot-messages">
              {messages.map((msg, idx) => (
                <div key={idx} className={`chat-bubble-container ${msg.role}`}>
                  <div className={`chat-bubble ${msg.role}`}>
                    {msg.role === "assistant" ? (
                      <div className="markdown-content">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                        <button className="copy-btn" onClick={() => copyToClipboard(msg.content)} title="Copy">
                          <i className="bi bi-clipboard"></i>
                        </button>
                      </div>
                    ) : (
                      msg.content
                    )}
                  </div>
                </div>
              ))}
              
              {isLoading && (
                <div className="chat-bubble-container assistant">
                  <div className="chat-bubble assistant typing-indicator">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              )}
              
              {messages.length === 1 && (
                <div className="suggestions-container">
                  <p className="suggestions-title">Suggested questions:</p>
                  <div className="suggestions-list">
                    {suggestions.map((sug, i) => (
                      <button key={i} className="suggestion-btn" onClick={() => handleSend(sug)}>
                        {sug}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chatbot-input-area">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask me anything... (Shift+Enter for new line)"
                rows="1"
              />
              <button 
                className="send-btn" 
                onClick={() => handleSend(input)}
                disabled={isLoading || !input.trim()}
              >
                <i className="bi bi-send-fill"></i>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );

  return ReactDOM.createPortal(chatbotContent, document.body);
};

export default Chatbot;
