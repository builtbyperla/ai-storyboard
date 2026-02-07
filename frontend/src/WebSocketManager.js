/**
 * WebSocket Manager - Singleton Pattern
 *
 * Manages multiple named WebSocket connections (chat, audio, bridge)
 * outside of React's lifecycle to avoid issues with React Strict Mode.
 */

class WebSocketManager {
  constructor() {
    if (WebSocketManager.instance) {
      return WebSocketManager.instance;
    }

    this.connections = {}; // Maps socket name -> WebSocket instance
    this.listeners = {}; // Maps socket name -> Set of listeners
    this.reconnectTimeouts = {}; // Maps socket name -> timeout
    this.reconnectDelay = 5000;
    this.isConnecting = {};

    WebSocketManager.instance = this;
  }

  /**
   * Connect to a named WebSocket endpoint
   * @param {string} name - Socket name (e.g., 'chat', 'audio', 'bridge')
   * @param {string} url - WebSocket URL
   * @param {function} onMessage - Message handler callback
   */
  connect(name, url, onMessage) {
    if (this.connections[name]?.readyState === WebSocket.OPEN || this.isConnecting[name]) {
      console.log(`[WS Manager ${name}] Already connected or connecting`);
      return;
    }

    this.isConnecting[name] = true;
    console.log(`[WS Manager ${name}] Connecting to:`, url);

    try {
      const ws = new WebSocket(url);
      this.connections[name] = ws;

      if (!this.listeners[name]) {
        this.listeners[name] = new Set();
      }

      ws.onopen = () => {
        console.log(`[WS Manager ${name}] Connected`);
        this.isConnecting[name] = false;
        this.clearReconnectTimeout(name);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Call provided message handler
          if (onMessage) {
            onMessage(data, ws);
          }

          // Notify subscribers
          this.notifyListeners(name, data);
        } catch (error) {
          console.error(`[WS Manager ${name}] Error parsing message:`, error);
        }
      };

      ws.onerror = (error) => {
        console.error(`[WS Manager ${name}] WebSocket error:`, error);
        this.isConnecting[name] = false;
      };

      ws.onclose = (event) => {
        console.log(`[WS Manager ${name}] Disconnected - Code:`, event.code, 'Reason:', event.reason);
        this.isConnecting[name] = false;
        this.scheduleReconnect(name, url, onMessage);
      };
    } catch (error) {
      console.error(`[WS Manager ${name}] Failed to connect:`, error);
      this.isConnecting[name] = false;
      this.scheduleReconnect(name, url, onMessage);
    }
  }

  scheduleReconnect(name, url, onMessage) {
    this.clearReconnectTimeout(name);
    console.log(`[WS Manager ${name}] Reconnecting in ${this.reconnectDelay}ms...`);
    this.reconnectTimeouts[name] = setTimeout(() => {
      this.connect(name, url, onMessage);
    }, this.reconnectDelay);
  }

  clearReconnectTimeout(name) {
    if (this.reconnectTimeouts[name]) {
      clearTimeout(this.reconnectTimeouts[name]);
      delete this.reconnectTimeouts[name];
    }
  }

  subscribe(name, listener) {
    if (!this.listeners[name]) {
      this.listeners[name] = new Set();
    }
    this.listeners[name].add(listener);
    return () => this.listeners[name]?.delete(listener);
  }

  notifyListeners(name, data) {
    this.listeners[name]?.forEach(listener => {
      try {
        listener(data);
      } catch (error) {
        console.error(`[WS Manager ${name}] Listener error:`, error);
      }
    });
  }

  disconnect(name) {
    this.clearReconnectTimeout(name);
    if (this.connections[name]) {
      this.connections[name].close();
      delete this.connections[name];
    }
  }

  disconnectAll() {
    Object.keys(this.connections).forEach(name => this.disconnect(name));
  }

  getState(name) {
    return this.connections[name]?.readyState ?? WebSocket.CLOSED;
  }

  send(name, data) {
    const ws = this.connections[name];
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
      return true;
    } else {
      console.error(`[WS Manager ${name}] Cannot send - not connected`);
      return false;
    }
  }

  getConnection(name) {
    return this.connections[name];
  }
}

// Export singleton instance
const wsManager = new WebSocketManager();
export default wsManager;
