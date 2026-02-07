import React, { useState } from 'react';
import './ChatInput.css';

/**
 * ChatInput Component
 * Provides a text input for sending chat messages via WebSocket
 */
const ChatInput = ({ onSendMessage, isConnected, chatFlushIndicatorRef }) => {
  const [message, setMessage] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();

    if (message.trim() && isConnected) {
      onSendMessage(message);
      setMessage('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="chat-input-panel">
      <form onSubmit={handleSubmit} className="chat-form">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isConnected ? "Ask about the board, generate images..." : "Waiting for connection..."}
          disabled={!isConnected}
          className="chat-textarea"
          rows={4}
        />
        <div className="chat-controls">
          <button
            type="submit"
            disabled={!isConnected}
            className="chat-send-btn"
          >
            Send
          </button>
          <div ref={chatFlushIndicatorRef} className="chat-flush-indicator"></div>
        </div>
      </form>
    </div>
  );
};

export default ChatInput;
