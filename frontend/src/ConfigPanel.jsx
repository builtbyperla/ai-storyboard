import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import './ConfigPanel.css';

/**
 * ConfigPanel Component
 * Displays user configuration options and connection status
 */
const ConfigPanel = ({ onConfigChange, onVolumeChange }) => {
  const [userMode, setUserMode] = useState(null);
  const [imageStyle, setImageStyle] = useState(null);
  const [customStyle, setCustomStyle] = useState('');
  const [showCustomStyle, setShowCustomStyle] = useState(false);
  const [agentAudioMode, setAgentAudioMode] = useState(null);
  const [notificationVolume, setNotificationVolume] = useState(0.5);
  const [audioSensitivity, setAudioSensitivity] = useState(null);
  const [agentModel, setAgentModel] = useState(null);
  const [agentThinking, setAgentThinking] = useState(null);
  // tooltip portal state (hover-only)
  const [hoverHelp, setHoverHelp] = useState(null);
  const [portalTooltip, setPortalTooltip] = useState(null);
  // timers to debounce hover in/out to avoid flicker
  const enterTimerRef = useRef(null);
  const leaveTimerRef = useRef(null);

  const HOVER_ENTER_DELAY = 120; // ms
  const HOVER_LEAVE_DELAY = 80; // ms

  const handleHelpMouseEnter = (id) => {
    if (leaveTimerRef.current) {
      clearTimeout(leaveTimerRef.current);
      leaveTimerRef.current = null;
    }
    if (enterTimerRef.current) clearTimeout(enterTimerRef.current);
    enterTimerRef.current = setTimeout(() => {
      setHoverHelp(id);
      enterTimerRef.current = null;
    }, HOVER_ENTER_DELAY);
  };

  const handleHelpMouseLeave = (id) => {
    if (enterTimerRef.current) {
      clearTimeout(enterTimerRef.current);
      enterTimerRef.current = null;
    }
    if (leaveTimerRef.current) clearTimeout(leaveTimerRef.current);
    leaveTimerRef.current = setTimeout(() => {
      setHoverHelp((cur) => (cur === id ? null : cur));
      leaveTimerRef.current = null;
    }, HOVER_LEAVE_DELAY);
  };

  useEffect(() => {
    const id = hoverHelp;
    if (!id) {
      setPortalTooltip(null);
      return;
    }
    const el = document.querySelector(`.help-wrapper[data-id="${id}"]`);
    if (!el) {
      setPortalTooltip(null);
      return;
    }
    const rect = el.getBoundingClientRect();
    const top = rect.top + rect.height / 2;
    const left = rect.right + 12;
    setPortalTooltip({ id, top, left });
  }, [hoverHelp]);

  // cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (enterTimerRef.current) clearTimeout(enterTimerRef.current);
      if (leaveTimerRef.current) clearTimeout(leaveTimerRef.current);
    };
  }, []);

  const renderTooltipContent = (id) => {
    // Prefer tooltip metadata provided by backend if available
    const backendTooltip = window.CONFIG_OPTIONS && window.CONFIG_OPTIONS[id] && window.CONFIG_OPTIONS[id].tooltip;
    if (backendTooltip) {
      return (
        <div>
          {backendTooltip.title && <div className="help-title">{backendTooltip.title}</div>}
          {backendTooltip.body && <div className="help-body">{backendTooltip.body}</div>}
          {Array.isArray(backendTooltip.items) && backendTooltip.items.length > 0 && (
            <ul>
              {backendTooltip.items.map((it, idx) => (
                <li key={idx}>{it}</li>
              ))}
            </ul>
          )}
        </div>
      );
    }

    // Fallback to built-in tooltip content
    if (id === 'userMode') {
      return (
        <div>
          <div className="help-title">User Mode</div>
          <div className="help-body">Choose a mode that controls available features and permissions.</div>
          <ul>
            <li><strong>Creator</strong> — full editing and generation access</li>
            <li><strong>Viewer</strong> — read-only interface</li>
          </ul>
        </div>
      );
    }
    if (id === 'imageStyle') {
      return (
        <div>
          <div className="help-title">Image Style</div>
          <div className="help-body">Controls the visual treatment used when generating images.</div>
          <ul>
            <li>Photorealistic — natural lighting and detail</li>
            <li>Cartoon — stylized, bold lines and colors</li>
          </ul>
        </div>
      );
    }
    if (id === 'audioSensitivity') {
      return (
        <div>
          <div className="help-title">Audio Sensitivity</div>
          <div className="help-body">Sets how sensitive the system is to incoming audio; higher sensitivity picks up quieter sounds.</div>
          <ul>
            <li>Low — ignores background noise</li>
            <li>Medium — balanced detection</li>
            <li>High — captures quiet sounds</li>
          </ul>
        </div>
      );
    }
    return null;
  };

  // Initialize with default values from config
  useEffect(() => {
    if (window.CONFIG_OPTIONS) {
      setUserMode(window.CONFIG_OPTIONS.userMode.default);
      setImageStyle(window.CONFIG_OPTIONS.imageStyle.default);
      setAgentAudioMode(window.CONFIG_OPTIONS.agentAudioMode.default);
      setNotificationVolume(window.CONFIG_OPTIONS.notificationVolume?.default || 0.5);
      setAudioSensitivity(window.CONFIG_OPTIONS.audioSensitivity?.default || 'medium');
      setAgentModel(window.CONFIG_OPTIONS.agentModel?.default || 'sonnet-4.5');
      setAgentThinking(window.CONFIG_OPTIONS.agentThinking?.default || 'enabled');
    }
  }, []);

  // removed custom tooltip handlers — using browser-native `title` attribute

  // Handle user mode change
  const handleUserModeChange = (e) => {
    const newMode = e.target.value;
    setUserMode(newMode);
    notifyConfigChange({ userMode: newMode });
  };

  // Handle image style change
  const handleImageStyleChange = (e) => {
    const newStyle = e.target.value;
    setImageStyle(newStyle);
    setShowCustomStyle(newStyle === 'custom');

    // Only send update if it's not custom (instant update for preset styles)
    if (newStyle !== 'custom') {
      notifyConfigChange({ imageStyle: newStyle });
    }
  };

  // Handle custom style change (just update local state, don't notify backend yet)
  const handleCustomStyleChange = (e) => {
    const newCustomStyle = e.target.value;
    setCustomStyle(newCustomStyle);
  };

  // Handle "Set" button click for custom style
  const handleSetCustomStyle = () => {
    if (customStyle.trim()) {
      notifyConfigChange({ imageStyle: 'custom', customStylePrompt: customStyle });
    }
  };

  // Handle agent audio mode change
  const handleAgentAudioModeChange = (e) => {
    const newMode = e.target.value;
    setAgentAudioMode(newMode);
    notifyConfigChange({ agentAudioMode: newMode });
  };

  // Handle notification volume change (frontend only, not sent to backend)
  const handleVolumeChange = (e) => {
    const newVolume = parseFloat(e.target.value);
    setNotificationVolume(newVolume);
    if (onVolumeChange) {
      onVolumeChange(newVolume);
    }
  };

  // Handle audio sensitivity change
  const handleAudioSensitivityChange = (e) => {
    const newSensitivity = e.target.value;
    setAudioSensitivity(newSensitivity);
    notifyConfigChange({ audioSensitivity: newSensitivity });
  };

  // Handle agent model change
  const handleAgentModelChange = (e) => {
    const newModel = e.target.value;
    setAgentModel(newModel);
    notifyConfigChange({ agentModel: newModel });
  };

  // Handle agent thinking change
  const handleAgentThinkingChange = (e) => {
    const newThinking = e.target.value;
    setAgentThinking(newThinking);
    notifyConfigChange({ agentThinking: newThinking });
  };

  // Notify backend of configuration changes
  const notifyConfigChange = (changes) => {
    if (onConfigChange) {
      const config = {
        userMode,
        imageStyle,
        agentAudioMode,
        audioSensitivity,
        agentModel,
        agentThinking,
        ...changes
      };
      // Only include customStylePrompt if imageStyle is 'custom' (after applying changes)
      if (config.imageStyle === 'custom') {
        config.customStylePrompt = config.customStylePrompt || customStyle;
      }
      onConfigChange(config);
    }
  };

  if (!window.CONFIG_OPTIONS || !userMode || !imageStyle || !agentAudioMode || !audioSensitivity || !agentModel || !agentThinking) {
    return <div className="config-panel">Loading configuration...</div>;
  }

  return (
    <div className="config-panel">
      {portalTooltip && createPortal(
        <div
          className="help-tooltip"
          style={{ position: 'fixed', top: portalTooltip.top + 'px', left: portalTooltip.left + 'px', transform: 'translateY(-50%)' }}
        >
          {renderTooltipContent(portalTooltip.id)}
        </div>,
        document.body
      )}
      <div className="config-columns">
        <div className="config-column">
          <div className="control-group">
            <div className="label-row">
              <label htmlFor="userMode">User Mode 👤</label>
              <div
                className="help-wrapper"
                data-id="userMode"
                onMouseEnter={() => handleHelpMouseEnter('userMode')}
                onMouseLeave={() => handleHelpMouseLeave('userMode')}
              >
                <button
                  type="button"
                  className="help-icon"
                  aria-label="User Mode help"
                >
                  ?
                </button>
                {/* tooltip rendered via portal to avoid clipping */}
              </div>
            </div>
            <select
              id="userMode"
              value={userMode}
              onChange={handleUserModeChange}
            >
              {Object.entries(window.CONFIG_OPTIONS.userMode.options).map(([key, display]) => (
                <option key={key} value={key}>{display}</option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <div className="label-row">
              <label htmlFor="imageStyle">Image Style 🎨</label>
              <div
                className="help-wrapper"
                data-id="imageStyle"
                onMouseEnter={() => handleHelpMouseEnter('imageStyle')}
                onMouseLeave={() => handleHelpMouseLeave('imageStyle')}
              >
                <button
                  type="button"
                  className="help-icon"
                  aria-label="Image Style help"
                >
                  ?
                </button>
                {/* tooltip rendered via portal to avoid clipping */}
              </div>
            </div>
            <select
              id="imageStyle"
              value={imageStyle}
              onChange={handleImageStyleChange}
            >
              {Object.entries(window.CONFIG_OPTIONS.imageStyle.options).map(([key, display]) => (
                <option key={key} value={key}>{display}</option>
              ))}
            </select>
          </div>

          {showCustomStyle && (
            <div className="control-group custom-style-group">
              <label htmlFor="customStyle">Custom Style ✨</label>
              <div className="custom-style-input-wrapper">
                <textarea
                  id="customStyle"
                  value={customStyle}
                  onChange={handleCustomStyleChange}
                  placeholder="Enter custom style prompt..."
                  rows="3"
                />
                <button
                  className="custom-style-set-button"
                  onClick={handleSetCustomStyle}
                  disabled={!customStyle.trim()}
                >
                  Set Custom Style
                </button>
              </div>
            </div>
          )}

          <div className="control-group">
            <div className="label-row">
              <label htmlFor="audioSensitivity">Audio Sensitivity 🎤</label>
              <div
                className="help-wrapper"
                data-id="audioSensitivity"
                onMouseEnter={() => handleHelpMouseEnter('audioSensitivity')}
                onMouseLeave={() => handleHelpMouseLeave('audioSensitivity')}
              >
                <button
                  type="button"
                  className="help-icon"
                  aria-label="Audio Sensitivity help"
                >
                  ?
                </button>
                {/* tooltip rendered via portal to avoid clipping */}
              </div>
            </div>
            <select
              id="audioSensitivity"
              value={audioSensitivity}
              onChange={handleAudioSensitivityChange}
            >
              {window.CONFIG_OPTIONS.audioSensitivity && Object.entries(window.CONFIG_OPTIONS.audioSensitivity.options).map(([key, display]) => (
                <option key={key} value={key}>{display}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="config-column">
          <div className="control-group">
            <label htmlFor="agentModel">Agent Model 🤖</label>
            <select
              id="agentModel"
              value={agentModel}
              onChange={handleAgentModelChange}
            >
              {window.CONFIG_OPTIONS.agentModel && Object.entries(window.CONFIG_OPTIONS.agentModel.options).map(([key, display]) => (
                <option key={key} value={key}>{display}</option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <label htmlFor="agentThinking">Agent Thinking 💭</label>
            <select
              id="agentThinking"
              value={agentThinking}
              onChange={handleAgentThinkingChange}
            >
              {window.CONFIG_OPTIONS.agentThinking && Object.entries(window.CONFIG_OPTIONS.agentThinking.options).map(([key, display]) => (
                <option key={key} value={key}>{display}</option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <label htmlFor="agentAudioMode">Agent Response Mode 🔔</label>
            <select
              id="agentAudioMode"
              value={agentAudioMode}
              onChange={handleAgentAudioModeChange}
            >
              {Object.entries(window.CONFIG_OPTIONS.agentAudioMode.options).map(([key, display]) => (
                <option key={key} value={key}>{display}</option>
              ))}
            </select>
          </div>

          {agentAudioMode === 'notification' && (
            <div className="control-group">
              <label htmlFor="notificationVolume">
                Notification Volume 🔊 {Math.round(notificationVolume * 100)}%
              </label>
              <input
                type="range"
                id="notificationVolume"
                min="0"
                max="1"
                step="0.01"
                value={notificationVolume}
                onChange={handleVolumeChange}
                style={{ width: '100%' }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ConfigPanel;
