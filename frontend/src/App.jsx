import React, { useState, useRef, useEffect, useMemo } from 'react';
import { flushSync } from 'react-dom';
import './App.css';
import wsManager from './WebSocketManager';
import ChatInput from './ChatInput';
import ConfigPanel from './ConfigPanel';
import notificationSound from './assets/notification_sound.wav';

// Card dimensions
const CARD_WIDTH = 240;
const CARD_IMAGE_HEIGHT = 200;
const DEFAULT_TEXTAREA_HEIGHT = 46;
const DEFAULT_CARD_HEIGHT = 278; // Actual rendered card height (image 200px + content ~78px including borders)

// Convert index to letter-based ID (0='A', 1='B', ..., 25='Z', 26='AA', 27='AB', etc.)
const indexToLetterID = (index) => {
  let result = '';
  let num = index;
  while (num >= 0) {
    result = String.fromCharCode(65 + (num % 26)) + result;
    num = Math.floor(num / 26) - 1;
  }
  return result;
};

// Card creation - single source of truth for consistent structure
let cardIdCounter = 1; // Simple integer counter
let zIndexCounter = 1; // Z-index counter for stacking order

const createCard = (cardData = {}) => {
  const id = cardData.id ?? cardIdCounter++;

  return {
    id,
    title: cardData.title ?? null,
    text: cardData.text ?? null,
    imageId: cardData.imageId ?? null,
    x: cardData.x ?? 100,
    y: cardData.y ?? 100,
    width: cardData.width ?? CARD_WIDTH,
    textareaHeight: cardData.textareaHeight ?? DEFAULT_TEXTAREA_HEIGHT,
    zIndex: cardData.zIndex ?? zIndexCounter++
  };
};

// Preview item creation - single source of truth for consistent structure
let previewIdCounter = 1; // Start from timestamp to avoid conflicts

const createPreviewItem = (itemData = {}) => {
  const id = itemData.id ?? `preview-${previewIdCounter++}`;

  return {
    id,
    imageId: itemData.imageId ?? null,
    title: itemData.title ?? null
  };
};

// MiniMap Component
const MiniMap = ({ cards, zoom, panOffset, setPanOffset, canvasRef }) => {
  const miniMapRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });

  // Constants
  const MINIMAP_WIDTH = 190;
  const MINIMAP_HEIGHT = 140;
  const MINIMAP_PADDING = 10;
  const BOUNDS_EXPANSION = 2.5;

  // Calculate individual card height
  // - Card image: CARD_IMAGE_HEIGHT
  // - Card content top padding: 6px
  // - Card title (font-size 12px, line-height normal ~14px): ~14px
  // - Card title margin-bottom: 2px
  // - Textarea padding: 4px (2px top + 2px bottom)
  // - Textarea height: dynamic
  // - Card content bottom padding: 6px
  const getCardHeight = (card) => {
    return CARD_IMAGE_HEIGHT + 6 + 14 + 2 + 4 + (card.textareaHeight || DEFAULT_TEXTAREA_HEIGHT) + 6;
  };

  // Track canvas size
  useEffect(() => {
    if (!canvasRef.current) return;

    const updateCanvasSize = () => {
      const rect = canvasRef.current.getBoundingClientRect();
      setCanvasSize({ width: rect.width, height: rect.height });
    };

    updateCanvasSize();
    const resizeObserver = new ResizeObserver(updateCanvasSize);
    resizeObserver.observe(canvasRef.current);
    window.addEventListener('resize', updateCanvasSize);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', updateCanvasSize);
    };
  }, [canvasRef]);

  // Calculate bounds
  const bounds = useMemo(() => {
    if (cards.length === 0) {
      return { minX: 0, minY: 0, maxX: 1000, maxY: 800 };
    }

    const positions = cards.flatMap(c => [
      { x: c.x, y: c.y },
      { x: c.x + (c.width || CARD_WIDTH), y: c.y + getCardHeight(c) }
    ]);

    const minX = Math.min(...positions.map(p => p.x), 0);
    const minY = Math.min(...positions.map(p => p.y), 0);
    const maxX = Math.max(...positions.map(p => p.x), 1000);
    const maxY = Math.max(...positions.map(p => p.y), 800);

    const width = maxX - minX;
    const height = maxY - minY;
    const expandedWidth = width * BOUNDS_EXPANSION;
    const expandedHeight = height * BOUNDS_EXPANSION;
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    return {
      minX: centerX - expandedWidth / 2,
      minY: centerY - expandedHeight / 2,
      maxX: centerX + expandedWidth / 2,
      maxY: centerY + expandedHeight / 2
    };
  }, [cards]);

  const canvasWidth = bounds.maxX - bounds.minX;
  const canvasHeight = bounds.maxY - bounds.minY;

  const scale = useMemo(() => {
    return Math.min(
      (MINIMAP_WIDTH - 2 * MINIMAP_PADDING) / canvasWidth,
      (MINIMAP_HEIGHT - 2 * MINIMAP_PADDING) / canvasHeight
    );
  }, [canvasWidth, canvasHeight]);

  const viewportSize = useMemo(() => {
    if (canvasSize.width === 0 || canvasSize.height === 0) {
      return { width: 500, height: 400 };
    }
    return {
      width: canvasSize.width / zoom,
      height: canvasSize.height / zoom
    };
  }, [canvasSize, zoom]);

  const viewportX = MINIMAP_PADDING + (-panOffset.x / zoom - bounds.minX) * scale;
  const viewportY = MINIMAP_PADDING + (-panOffset.y / zoom - bounds.minY) * scale;
  const viewportWidth = viewportSize.width * scale;
  const viewportHeight = viewportSize.height * scale;

  const handleViewportMouseDown = (e) => {
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleMiniMapMouseMove = (e) => {
    if (!isDragging || !miniMapRef.current || !canvasRef.current) return;

    const rect = miniMapRef.current.getBoundingClientRect();
    const miniMapX = e.clientX - rect.left - MINIMAP_PADDING;
    const miniMapY = e.clientY - rect.top - MINIMAP_PADDING;

    const canvasX = miniMapX / scale + bounds.minX;
    const canvasY = miniMapY / scale + bounds.minY;

    const canvasRect = canvasRef.current.getBoundingClientRect();
    const newPanX = -canvasX * zoom + canvasRect.width / 2;
    const newPanY = -canvasY * zoom + canvasRect.height / 2;
    setPanOffset({ x: Math.floor(newPanX), y: Math.floor(newPanY) });
  };

  const handleMiniMapMouseUp = () => {
    setIsDragging(false);
  };

  const handleMiniMapClick = (e) => {
    if (isDragging || !miniMapRef.current || !canvasRef.current) return;

    const rect = miniMapRef.current.getBoundingClientRect();
    const miniMapX = e.clientX - rect.left - MINIMAP_PADDING;
    const miniMapY = e.clientY - rect.top - MINIMAP_PADDING;

    const canvasX = miniMapX / scale + bounds.minX;
    const canvasY = miniMapY / scale + bounds.minY;

    const canvasRect = canvasRef.current.getBoundingClientRect();
    const newPanX = -canvasX * zoom + canvasRect.width / 2;
    const newPanY = -canvasY * zoom + canvasRect.height / 2;
    setPanOffset({ x: Math.floor(newPanX), y: Math.floor(newPanY) });
  };

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMiniMapMouseMove);
      document.addEventListener('mouseup', handleMiniMapMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMiniMapMouseMove);
        document.removeEventListener('mouseup', handleMiniMapMouseUp);
      };
    }
  }, [isDragging, bounds, scale, zoom]);

  return (
    <div
      ref={miniMapRef}
      className="mini-map"
      onClick={handleMiniMapClick}
      style={{
        width: `${MINIMAP_WIDTH}px`,
        height: `${MINIMAP_HEIGHT}px`,
        userSelect: 'none'
      }}
    >
      {cards.map(card => {
        const x = MINIMAP_PADDING + (card.x - bounds.minX) * scale;
        const y = MINIMAP_PADDING + (card.y - bounds.minY) * scale;
        const width = (card.width || CARD_WIDTH) * scale;
        const height = getCardHeight(card) * scale;

        return (
          <div
            key={card.id}
            className="mini-map-card"
            style={{
              position: 'absolute',
              left: `${x}px`,
              top: `${y}px`,
              width: `${width}px`,
              height: `${height}px`
            }}
          />
        );
      })}

      <div
        className="mini-map-viewport"
        style={{
          position: 'absolute',
          left: `${viewportX}px`,
          top: `${viewportY}px`,
          width: `${viewportWidth}px`,
          height: `${viewportHeight}px`,
          cursor: isDragging ? 'grabbing' : 'grab'
        }}
        onMouseDown={handleViewportMouseDown}
      />
    </div>
  );
};

const App = () => {
  // Canvas state
  const [cards, setCards] = useState([]);

  // Zoom and pan state
  const [zoom, setZoom] = useState(1.0);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });

  // Drag state
  const [draggedCard, setDraggedCard] = useState(null);
  const [isPanning, setIsPanning] = useState(false);
  const [resizingCard, setResizingCard] = useState(null);

  const canvasRef = useRef(null);
  const dragStateRef = useRef({ cardId: null, offsetX: 0, offsetY: 0 });
  const panStartRef = useRef({ x: 0, y: 0, offsetX: 0, offsetY: 0 });
  const resizeStateRef = useRef({ cardId: null, startY: 0, startHeight: 0 });

  // Side panel state
  const [activePanel, setActivePanel] = useState(null);
  const [chatPaneActive, setChatPaneActive] = useState(false);

  // Right pane resize state
  const [rightPaneWidth, setRightPaneWidth] = useState(340);
  const [isResizingRightPane, setIsResizingRightPane] = useState(false);
  const rightPaneResizeRef = useRef({ startX: 0, startWidth: 0 });

  // Preview/agent split resize state
  const [previewFlex, setPreviewFlex] = useState(2); // Default flex for preview
  const [agentFlex, setAgentFlex] = useState(1); // Default flex for agent
  const [isResizingPreview, setIsResizingPreview] = useState(false);
  const previewResizeRef = useRef({ startY: 0, startPreviewFlex: 0, startAgentFlex: 0, containerHeight: 0 });

  // Audio state
  const [isListening, setIsListening] = useState(false);
  const audioSocketRef = useRef(null);
  const audioStreamRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioWorkletNodeRef = useRef(null);

  // Agent audio mode - the only config value App needs to track
  const [agentAudioMode, setAgentAudioMode] = useState(
    window.CONFIG_OPTIONS?.agentAudioMode?.default || 'none'
  );

  // Chat WebSocket state
  const chatSocketRef = useRef(null);

  // Bridge WebSocket state
  const bridgeSocketRef = useRef(null);

  // Preview pane state
  const [previewItems, setPreviewItems] = useState([]);
  const [draggedPreview, setDraggedPreview] = useState(null);
  const [dropTargetCard, setDropTargetCard] = useState(null);

  // Agent message state - accumulators for streaming
  const [thinkingVisible, setThinkingVisible] = useState(false);
  const [thinkingText, setThinkingText] = useState('');
  const [responseText, setResponseText] = useState('');
  const [responseVisible, setResponseVisible] = useState(false);
  const [responseIsComplete, setResponseIsComplete] = useState(false);
  const agentFeedRef = useRef(null);

  // Notification audio ref
  const notificationAudioRef = useRef(new Audio(notificationSound));

  // Control agent response visibility
  const toggleAgentResponseVisibility = (show) => {
    setResponseVisible(show);
  };

  // Play notification sound
  const playNotificationSound = () => {
    // Only play if notification mode is enabled
    if (stateRef.current.agentAudioMode === 'notification') {
      notificationAudioRef.current.currentTime = 0;
      notificationAudioRef.current.play().catch(err => {
        console.log('[Audio] Notification sound play failed:', err);
      });
    }
  };

  // Handle volume change from config panel (frontend only)
  const handleVolumeChange = (volume) => {
    notificationAudioRef.current.volume = volume;
  };

  // User transcript state (for bottom bar)
  const [userTranscript, setUserTranscript] = useState('');
  const transcriptRef = useRef(null);

  // Flush indicator refs
  const flushIndicatorRef = useRef(null);
  const chatFlushIndicatorRef = useRef(null);

  // State ref for WebSocket handlers to avoid closure issues
  const stateRef = useRef({
    cards,
    previewItems,
    zoom,
    panOffset,
    agentAudioMode
  });

  // Card operations ref for command handlers to call shared functions
  const cardOpsRef = useRef({
    addCards: null,
    deleteCards: null,
    updateCards: null
  });

  // Update stateRef whenever state changes
  useEffect(() => {
    stateRef.current = { cards, previewItems, zoom, panOffset, agentAudioMode };
  }, [cards, previewItems, zoom, panOffset, agentAudioMode]);

  // Auto-scroll agent feed when new messages arrive
  useEffect(() => {
    if ((thinkingText || responseText) && agentFeedRef.current) {
      // Use scrollTo with smooth behavior for better performance
      agentFeedRef.current.scrollTo({
        top: agentFeedRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [thinkingText, responseText]);

  // Auto-scroll transcript when it overflows
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTo({
        left: transcriptRef.current.scrollWidth,
        behavior: 'smooth'
      });
    }
  }, [userTranscript]);

  // Get canvas state with viewport info (for backend state requests)
  const getCanvasStateWithViewport = () => {
    const { cards, previewItems, zoom, panOffset } = stateRef.current;

    // Calculate card height based on internal textareaHeight
    // Card image: CARD_IMAGE_HEIGHT + content padding: 6px + title: 14px + title margin: 2px + textarea padding: 4px + textarea + bottom padding: 6px
    const getCardHeight = (card) => CARD_IMAGE_HEIGHT + 6 + 14 + 2 + 4 + (card.textareaHeight || DEFAULT_TEXTAREA_HEIGHT) + 6;

    // Calculate viewport bounds (what coordinate space is currently visible)
    // Get canvas dimensions from the canvas element
    let viewportBounds = null;
    if (canvasRef.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      viewportBounds = {
        minX: -panOffset.x / zoom,
        maxX: (-panOffset.x + rect.width) / zoom,
        minY: -panOffset.y / zoom,
        maxY: (-panOffset.y + rect.height) / zoom
      };
    }

    // Helper to round numbers to 2 decimal places
    const round2 = v => typeof v === 'number' ? Math.round(v * 100) / 100 : v;
    // Round panOffset
    const roundedPanOffset = {
      x: round2(panOffset.x),
      y: round2(panOffset.y)
    };
    // Round bounds if present
    let roundedBounds = undefined;
    if (viewportBounds) {
      roundedBounds = {
        minX: round2(viewportBounds.minX),
        maxX: round2(viewportBounds.maxX),
        minY: round2(viewportBounds.minY),
        maxY: round2(viewportBounds.maxY)
      };
    }
    return {
      canvasCards: cards.map((card, index) => ({
        id: card.id,
        title: card.title,
        text: card.text,
        imageId: card.imageId,
        x: card.x,
        y: card.y,
        width: card.width || CARD_WIDTH,
        height: getCardHeight(card),
        displayStr: indexToLetterID(index)
      })),
      previewImages: previewItems,
      viewport: {
        zoom: round2(zoom),
        panOffset: roundedPanOffset,
        ...(roundedBounds && { bounds: roundedBounds })
      }
    };
  };

  // Initialize WebSocket connections on mount
  useEffect(() => {
    // Connect to chat WebSocket
    console.log('[ChatSocket] Connecting to chat WebSocket...');
    const chatWs = new WebSocket('ws://localhost:8000/ws/chat');
    chatSocketRef.current = chatWs;

    chatWs.onopen = () => {
      console.log('[ChatSocket] ✓ Connected to chat WebSocket');
    };

    chatWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Note: Message handling now done via bridge WebSocket commands
      } catch (error) {
        console.error('[ChatSocket] Error parsing message:', error);
      }
    };

    chatWs.onerror = (error) => {
      console.error('[ChatSocket] WebSocket error:', error);
    };

    chatWs.onclose = () => {
      console.log('[ChatSocket] Disconnected from chat WebSocket');
    };

    // Connect to bridge WebSocket using wsManager
    console.log('[BridgeSocket] Connecting to bridge WebSocket...');

    // Command handlers for backend MCP tools
    const COMMAND_HANDLERS = {
      get_board_state: (params) => {
        return {
          ...getCanvasStateWithViewport()
        };
      },
      add_cards_to_canvas: (params) => {
        try {
          const { cards: newCards } = params || {};
          if (!newCards || !Array.isArray(newCards)) {
            return { success: false, error: 'Invalid cards parameter' };
          }

          const createdCards = cardOpsRef.current.addCards(newCards);

          return {
            success: true,
            added: createdCards.length,
            ids: createdCards.map(c => String(c.id))
          };
        } catch (error) {
          console.error('[BridgeSocket] Error in add_cards_to_canvas:', error);
          return { success: false, error: error.message };
        }
      },
      update_cards_in_canvas: (params) => {
        try {
          const { cards: updatedCards } = params || {};
          if (!updatedCards || !Array.isArray(updatedCards)) {
            return { success: false, error: 'Invalid cards parameter' };
          }

          cardOpsRef.current.updateCards(updatedCards);

          return {
            success: true,
            updated: updatedCards.length,
            ids: updatedCards.map(c => String(c.id))
          };
        } catch (error) {
          console.error('[BridgeSocket] Error in update_cards_in_canvas:', error);
          return { success: false, error: error.message };
        }
      },
      delete_cards_from_canvas: (params) => {
        try {
          const { cardIds } = params || {};
          if (!cardIds || !Array.isArray(cardIds)) {
            console.error('[BridgeSocket] Invalid cardIds:', cardIds, 'Full params:', params);
            return { success: false, error: 'Invalid cardIds parameter' };
          }

          cardOpsRef.current.deleteCards(cardIds);

          return {
            success: true,
            deleted: cardIds.length,
            ids: cardIds
          };
        } catch (error) {
          console.error('[BridgeSocket] Error in delete_cards_from_canvas:', error);
          return { success: false, error: error.message };
        }
      },
      add_preview_cards: (params) => {
        try {
          const { cards } = params || {};
          if (!cards || !Array.isArray(cards)) {
            return { success: false, error: 'Invalid cards parameter' };
          }

          // Create cards with IDs, appending to the end
          const newCards = cards.map(createPreviewItem);
          const newCardIds = newCards.map(c => c.id);

          flushSync(() => {
            setPreviewItems(prevItems => {
              const updated = [...newCards, ...prevItems];
              // Auto-trim to max 50 cards (remove oldest from end)
              if (updated.length > 50) {
                return updated.slice(0, 50);
              }
              return updated;
            });
          });

          // Trigger animation via DOM after React renders
          animatePreviewCards(newCardIds);

          return {
            success: true,
            added: newCards.length,
            ids: newCardIds
          };
        } catch (error) {
          console.error('[BridgeSocket] Error in add_preview_cards:', error);
          return { success: false, error: error.message };
        }
      },
      update_preview_cards: (params) => {
        try {
          const { updates } = params || {};
          if (!updates || !Array.isArray(updates)) {
            return { success: false, error: 'Invalid updates parameter' };
          }

          const updatedIds = [];
          flushSync(() => {
            setPreviewItems(prevItems => prevItems.map(item => {
              const update = updates.find(u => u.id === item.id);
              if (!update) return item;

              updatedIds.push(item.id);
              // Apply partial updates (only update provided fields)
              return {
                ...item,
                ...(update.imageId !== undefined && { imageId: update.imageId }),
                ...(update.title !== undefined && { title: update.title })
              };
            }));
          });

          // Trigger animation via DOM after React renders
          animatePreviewCards(updatedIds);

          return {
            success: true,
            updated: updatedIds.length,
            ids: updatedIds
          };
        } catch (error) {
          console.error('[BridgeSocket] Error in update_preview_cards:', error);
          return { success: false, error: error.message };
        }
      },
      remove_preview_cards: (params) => {
        try {
          const { cardIds } = params || {};
          if (!cardIds || !Array.isArray(cardIds)) {
            return { success: false, error: 'Invalid cardIds parameter' };
          }

          setPreviewItems(prevItems => prevItems.filter(item => !cardIds.includes(item.id)));

          return {
            success: true,
            removed: cardIds.length,
            ids: cardIds
          };
        } catch (error) {
          console.error('[BridgeSocket] Error in remove_preview_cards:', error);
          return { success: false, error: error.message };
        }
      },
      update_user_transcript: (params) => {
        // Handle user transcript from audio - full chunks from ElevenLabs
        if (params && params.text !== undefined) {
          setUserTranscript(params.text);
        }
        return { success: true };
      },
      show_agent_thinking: (params) => {
        setThinkingVisible(true);
        setThinkingText('');
        return { success: true };
      },
      update_agent_thinking: (params) => {
        if (params && params.text !== undefined) {
          setThinkingText(prev => prev + params.text);
        }
        return { success: true };
      },
      start_agent_response: (params) => {
        setResponseText('');
        setThinkingVisible(false);
        setResponseVisible(true);
        setResponseIsComplete(false);
        return { success: true };
      },
      update_agent_response: (params) => {
        if (params && params.text !== undefined) {
          setResponseText(prev => prev + params.text);
        }
        return { success: true };
      },
      play_notification_sound: () => {
        playNotificationSound();
        return { success: true };
      },
      end_agent_message: () => {
        setResponseIsComplete(true);
        playNotificationSound();
        return { success: true };
      },
      notify_transcripts_flushed: () => {
        // Trigger the mauve flash animation via DOM
        if (flushIndicatorRef.current) {
          flushIndicatorRef.current.classList.add('flash');
          setTimeout(() => {
            flushIndicatorRef.current?.classList.remove('flash');
          }, 1000);
        }
        return { success: true };
      },
      notify_chat_flushed: () => {
        // Trigger the mauve flash animation for chat via DOM
        if (chatFlushIndicatorRef.current) {
          chatFlushIndicatorRef.current.classList.add('flash');
          setTimeout(() => {
            chatFlushIndicatorRef.current?.classList.remove('flash');
          }, 1000);
        }
        return { success: true };
      },
      update_ai_status: (params) => {
        if (params.status === 'thinking') {
          setIsThinking(true);
        } else if (params.status === 'idle' || params.status === 'responding') {
          setIsThinking(false);
        }
        return { success: true };
      },
      set_canvas_zoom: (params) => {
        const { zoom: newZoom } = params;
        if (newZoom !== undefined) {
          const clampedZoom = Math.max(0.25, Math.min(2, newZoom));
          setZoom(clampedZoom);
          return { success: true, zoom: clampedZoom };
        }
        return { success: false, error: 'Missing zoom parameter' };
      },
      set_canvas_pan: (params) => {
        const { offset } = params;
        if (offset && offset.x !== undefined && offset.y !== undefined) {
          setPanOffset({ x: Math.floor(offset.x), y: Math.floor(offset.y) });
          return { success: true, offset: { x: Math.floor(offset.x), y: Math.floor(offset.y) } };
        }
        return { success: false, error: 'Missing or invalid offset parameter' };
      },
      focus_on_cards: (params) => {
        const { panelIds, options } = params;
        const padding = options?.padding || 50;

        if (!panelIds || panelIds.length === 0) {
          return { success: false, error: 'No panel IDs provided' };
        }

        // Get current cards state
        const { cards } = stateRef.current;

        // Find the cards to focus on
        const focusCards = cards.filter(card => panelIds.includes(String(card.id)));

        if (focusCards.length === 0) {
          return { success: false, error: 'No matching cards found' };
        }

        // Calculate bounding box
        const getCardHeight = (card) => CARD_IMAGE_HEIGHT + 6 + 14 + 2 + 4 + (card.textareaHeight || DEFAULT_TEXTAREA_HEIGHT) + 6;

        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        focusCards.forEach(card => {
          minX = Math.min(minX, card.x);
          minY = Math.min(minY, card.y);
          maxX = Math.max(maxX, card.x + (card.width || CARD_WIDTH));
          maxY = Math.max(maxY, card.y + getCardHeight(card));
        });

        // Add padding
        minX -= padding;
        minY -= padding;
        maxX += padding;
        maxY += padding;

        // Calculate canvas viewport size
        if (!canvasRef.current) {
          return { success: false, error: 'Canvas ref not available' };
        }

        const canvasRect = canvasRef.current.getBoundingClientRect();
        const viewportWidth = canvasRect.width;
        const viewportHeight = canvasRect.height;

        // Calculate zoom to fit
        const contentWidth = maxX - minX;
        const contentHeight = maxY - minY;
        const zoomX = viewportWidth / contentWidth;
        const zoomY = viewportHeight / contentHeight;
        const newZoom = Math.max(0.25, Math.min(2, Math.min(zoomX, zoomY)));

        // Calculate pan to center the content
        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;
        const newPanX = viewportWidth / 2 - centerX * newZoom;
        const newPanY = viewportHeight / 2 - centerY * newZoom;

        // Apply zoom and pan
        setZoom(newZoom);
        setPanOffset({ x: Math.floor(newPanX), y: Math.floor(newPanY) });

        return {
          success: true,
          zoom: newZoom,
          offset: { x: Math.floor(newPanX), y: Math.floor(newPanY) },
          focusedCards: focusCards.length
        };
      },
      create_card_grid: (params) => {
        try {
          const { rows, cols, hSpacing, vSpacing, startX, startY, includeCards = [] } = params;

          // Validate required parameters
          if (rows === undefined || cols === undefined) {
            return { success: false, error: 'Missing required parameters: rows and cols' };
          }
          if (hSpacing === undefined || vSpacing === undefined) {
            return { success: false, error: 'Missing required parameters: hSpacing and vSpacing' };
          }
          if (startX === undefined || startY === undefined) {
            return { success: false, error: 'Missing required parameters: startX and startY' };
          }
          if (includeCards && !Array.isArray(includeCards)) {
            return { success: false, error: 'includeCards parameter must be an array if provided' };
          }

          // Validate includeCards structure if provided
          if (includeCards && includeCards.length > 0) {
            for (const item of includeCards) {
              if (!item.cardId || item.row === undefined || item.col === undefined) {
                return { success: false, error: 'Each includeCards item must have cardId, row, and col' };
              }
            }
          }

          const result = createCardGrid(rows, cols, hSpacing, vSpacing, startX, startY, includeCards);

          return {
            success: true,
            ...result
          };
        } catch (error) {
          console.error('[BridgeSocket] Error in create_card_grid:', error);
          return { success: false, error: error.message };
        }
      }
    };

    const handleBridgeMessage = (data, ws) => {
      // Handle state requests from backend
      if (data.type === 'state_request') {
        const state = getCanvasStateWithViewport();
        wsManager.send('bridge', {
          type: 'state_response',
          requestId: data.requestId,
          state: state
        });
      } else if (data.command) {
        // Handle MCP tool commands
        const handler = COMMAND_HANDLERS[data.command];

        if (handler) {
          try {
            const result = handler(data.params || {});
            // Only send response if there's a requestId (some commands are notifications)
            if (data.requestId) {
              wsManager.send('bridge', {
                type: 'state_response',
                requestId: data.requestId,
                timestamp: Date.now(),
                state: result
              });
            }
          } catch (error) {
            console.error('[BridgeSocket] Error executing command:', error);
            if (data.requestId) {
              wsManager.send('bridge', {
                type: 'state_response',
                requestId: data.requestId,
                error: error.message
              });
            }
          }
        } else {
          console.warn('[BridgeSocket] Unknown command:', data.command);
        }
      }
    };

    wsManager.connect('bridge', 'ws://localhost:8000/ws/app_bridge', handleBridgeMessage);
    bridgeSocketRef.current = wsManager.getConnection('bridge');

    return () => {
      console.log('[App] Cleaning up WebSocket connections...');
      if (chatWs.readyState === WebSocket.OPEN) {
        chatWs.close();
      }
      wsManager.disconnect('bridge');

      // Cleanup audio resources
      stopAudioCapture();
      if (audioSocketRef.current?.readyState === WebSocket.OPEN) {
        audioSocketRef.current.close();
      }
    };
  }, []);

  // Audio WebSocket setup
  const setupAudioSocket = () => {
    if (audioSocketRef.current?.readyState === WebSocket.OPEN) {
      console.log('[AudioSocket] Already connected');
      return;
    }

    console.log('[AudioSocket] Connecting to audio WebSocket...');
    const audioWs = new WebSocket('ws://localhost:8000/ws/audio');
    audioSocketRef.current = audioWs;

    audioWs.onopen = () => {
      console.log('[AudioSocket] ✓ Connected to audio WebSocket');
    };

    audioWs.onerror = (error) => {
      console.error('[AudioSocket] WebSocket error:', error);
    };

    audioWs.onclose = () => {
      console.log('[AudioSocket] Disconnected from audio WebSocket');
    };
  };

  // Send audio chunk via WebSocket
  const sendAudioChunk = (pcmData) => {
    if (audioSocketRef.current?.readyState === WebSocket.OPEN) {
      audioSocketRef.current.send(pcmData);
    } else {
      console.warn('[AudioSocket] Cannot send - not connected');
    }
  };

  // Start audio capture
  const startAudioCapture = async () => {
    try {
      console.log('[Audio] Requesting microphone access...');

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        }
      });

      audioStreamRef.current = stream;
      console.log('[Audio] ✓ Microphone access granted');

      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;
      console.log('[Audio] AudioContext created with sample rate:', audioContext.sampleRate);

      await audioContext.audioWorklet.addModule(new URL('./pcm-processor.js', import.meta.url));
      console.log('[Audio] ✓ AudioWorklet module loaded');

      const source = audioContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioContext, 'pcm-processor');
      audioWorkletNodeRef.current = workletNode;

      workletNode.port.onmessage = (event) => {
        const pcmData = event.data;
        sendAudioChunk(pcmData);
      };

      source.connect(workletNode);
      workletNode.connect(audioContext.destination);

      console.log('[Audio] ✓ Audio pipeline connected');
      setIsListening(true);

      setupAudioSocket();
    } catch (error) {
      console.error('[Audio] Error setting up audio:', error);
      setIsListening(false);
    }
  };

  // Stop audio capture
  const stopAudioCapture = () => {
    console.log('[Audio] Stopping audio capture...');

    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach(track => track.stop());
      audioStreamRef.current = null;
    }

    if (audioWorkletNodeRef.current) {
      audioWorkletNodeRef.current.disconnect();
      audioWorkletNodeRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    setIsListening(false);

    wsManager.send('bridge', { type: 'audio_stopped' });

    console.log('[Audio] ✓ Audio capture stopped');
  };

  // Toggle audio recording
  const toggleAudioRecording = async () => {
    if (isListening) {
      stopAudioCapture();
    } else {
      await startAudioCapture();
    }
  };

  // Send chat message
  const sendChatMessage = (message) => {
    if (chatSocketRef.current?.readyState === WebSocket.OPEN) {
      chatSocketRef.current.send(JSON.stringify({ message }));
      console.log('[ChatSocket] Sent message:', message);
    } else {
      console.warn('[ChatSocket] Cannot send - not connected');
    }
  };

  // Handle configuration changes
  const handleConfigChange = (newConfig) => {
    // Extract and update only the agentAudioMode that App needs
    if (newConfig.agentAudioMode !== undefined) {
      setAgentAudioMode(newConfig.agentAudioMode);
    }

    console.log('Configuration updated:', newConfig);

    // Send full config to backend
    wsManager.send('bridge', {
      type: 'config_update',
      data: newConfig
    });
  };

  // Toggle side panels
  const togglePanel = (panelName) => {
    if (panelName === 'settings') {
      setActivePanel(activePanel === 'settings' ? null : 'settings');
    }
  };

  // Toggle chat pane in right sidebar
  const toggleChatPane = () => {
    setChatPaneActive(!chatPaneActive);
  };

  // Zoom with mouse wheel
  const handleWheel = (e) => {
    e.preventDefault();
    if (!canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const canvasX = (mouseX - panOffset.x) / zoom;
    const canvasY = (mouseY - panOffset.y) / zoom;

    const zoomDelta = e.deltaY < 0 ? 1.1 : 0.9;
    const newZoom = Math.max(0.25, Math.min(2, zoom * zoomDelta));

    const newPanOffsetX = mouseX - canvasX * newZoom;
    const newPanOffsetY = mouseY - canvasY * newZoom;

    setZoom(newZoom);
    setPanOffset({ x: Math.floor(newPanOffsetX), y: Math.floor(newPanOffsetY) });
  };

  // Card drag handlers
  const handleCardMouseDown = (e, card) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
      return;
    }

    e.preventDefault();
    e.stopPropagation();

    // Bring card to front by assigning new z-index
    setCards(prev => prev.map(c => 
      c.id === card.id ? { ...c, zIndex: zIndexCounter++ } : c
    ));

    const canvasRect = canvasRef.current.getBoundingClientRect();
    const mouseX = e.clientX - canvasRect.left;
    const mouseY = e.clientY - canvasRect.top;

    const canvasX = (mouseX - panOffset.x) / zoom;
    const canvasY = (mouseY - panOffset.y) / zoom;

    dragStateRef.current = {
      cardId: card.id,
      offsetX: canvasX - card.x,
      offsetY: canvasY - card.y
    };

    setDraggedCard(card.id);
  };

  const handleCardMouseMove = (e) => {
    if (!dragStateRef.current.cardId || !canvasRef.current) return;

    const canvasRect = canvasRef.current.getBoundingClientRect();
    const mouseX = e.clientX - canvasRect.left;
    const mouseY = e.clientY - canvasRect.top;

    const canvasX = (mouseX - panOffset.x) / zoom;
    const canvasY = (mouseY - panOffset.y) / zoom;

    const newX = Math.round(canvasX - dragStateRef.current.offsetX);
    const newY = Math.round(canvasY - dragStateRef.current.offsetY);

    setCards(prev => prev.map(card =>
      card.id === dragStateRef.current.cardId
        ? { ...card, x: newX, y: newY }
        : card
    ));
  };

  const handleCardMouseUp = () => {
    dragStateRef.current = { cardId: null, offsetX: 0, offsetY: 0 };
    setDraggedCard(null);
  };

  useEffect(() => {
    if (draggedCard) {
      document.addEventListener('mousemove', handleCardMouseMove);
      document.addEventListener('mouseup', handleCardMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleCardMouseMove);
        document.removeEventListener('mouseup', handleCardMouseUp);
      };
    }
  }, [draggedCard, zoom, panOffset]);

  // Resize handlers
  const handleResizeMouseDown = (e, card) => {
    e.preventDefault();
    e.stopPropagation();

    resizeStateRef.current = {
      cardId: card.id,
      startY: e.clientY,
      startHeight: card.textareaHeight || DEFAULT_TEXTAREA_HEIGHT
    };

    setResizingCard(card.id);
  };

  const handleResizeMouseMove = (e) => {
    if (!resizingCard || !resizeStateRef.current.cardId) return;

    const deltaY = e.clientY - resizeStateRef.current.startY;
    const newHeight = Math.max(20, resizeStateRef.current.startHeight + deltaY / zoom);

    // Only update if change is > 1px
    const currentCard = cards.find(c => c.id === resizeStateRef.current.cardId);
    if (currentCard && Math.abs(newHeight - (currentCard.textareaHeight || DEFAULT_TEXTAREA_HEIGHT)) > 1) {
      setCards(prev => prev.map(card =>
        card.id === resizeStateRef.current.cardId
          ? { ...card, textareaHeight: Math.round(newHeight) }
          : card
      ));
    }
  };

  const handleResizeMouseUp = () => {
    resizeStateRef.current = { cardId: null, startY: 0, startHeight: 0 };
    setResizingCard(null);
  };

  useEffect(() => {
    if (resizingCard) {
      document.addEventListener('mousemove', handleResizeMouseMove);
      document.addEventListener('mouseup', handleResizeMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleResizeMouseMove);
        document.removeEventListener('mouseup', handleResizeMouseUp);
      };
    }
  }, [resizingCard, zoom, cards]);

  // Canvas panning
  const handleCanvasMouseDown = (e) => {
    if (e.target === canvasRef.current) {
      setIsPanning(true);
      panStartRef.current = {
        x: e.clientX,
        y: e.clientY,
        offsetX: panOffset.x,
        offsetY: panOffset.y
      };
    }
  };

  const handleCanvasPanMove = (e) => {
    if (!isPanning) return;

    const deltaX = e.clientX - panStartRef.current.x;
    const deltaY = e.clientY - panStartRef.current.y;

    setPanOffset({
      x: panStartRef.current.offsetX + deltaX,
      y: panStartRef.current.offsetY + deltaY
    });
  };

  const handleCanvasPanEnd = () => {
    setIsPanning(false);
  };

  useEffect(() => {
    if (isPanning) {
      document.addEventListener('mousemove', handleCanvasPanMove);
      document.addEventListener('mouseup', handleCanvasPanEnd);
      return () => {
        document.removeEventListener('mousemove', handleCanvasPanMove);
        document.removeEventListener('mouseup', handleCanvasPanEnd);
      };
    }
  }, [isPanning]);

  // Wheel event listener
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.addEventListener('wheel', handleWheel, { passive: false });
    return () => {
      canvas.removeEventListener('wheel', handleWheel);
    };
  }, [zoom, panOffset]);

  // === SHARED CARD OPERATIONS ===
  // These are called by both UI handlers and command handlers

  // Calculate the center position of the viewport
  const getViewportCenter = () => {
    if (!canvasRef.current) return { x: 400, y: 300 };

    const rect = canvasRef.current.getBoundingClientRect();
    const centerScreenX = rect.width / 2;
    const centerScreenY = rect.height / 2;

    // Convert screen coordinates to canvas coordinates
    const centerCanvasX = (centerScreenX - panOffset.x) / zoom;
    const centerCanvasY = (centerScreenY - panOffset.y) / zoom;

    return { x: Math.round(centerCanvasX), y: Math.round(centerCanvasY) };
  };

  // Create a grid of cards
  const createCardGrid = (rows, cols, hSpacing, vSpacing, startX, startY, includeCards = []) => {
    const { cards } = stateRef.current;

    // Create a map of position to card ID from includeCards array
    const gridMap = new Map();
    includeCards.forEach(({ cardId, row, col }) => {
      // Convert 1-indexed to 0-indexed
      const key = `${row - 1},${col - 1}`;
      gridMap.set(key, cardId);
    });

    // Single loop: gather positions and count new cards needed
    const positions = [];
    let newCardsNeeded = 0;

    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const key = `${row},${col}`;
        const specifiedCardId = gridMap.get(key);
        const x = startX + col * (CARD_WIDTH + hSpacing);
        const y = startY + row * (DEFAULT_CARD_HEIGHT + vSpacing);

        let existingCard = null;
        if (specifiedCardId !== undefined) {
          // Check if specified card exists
          existingCard = cards.find(c => String(c.id) === String(specifiedCardId));
        }

        if (existingCard) {
          // Valid existing card found
          positions.push({
            x: Math.round(x),
            y: Math.round(y),
            cardId: existingCard.id,
            isExisting: true
          });
        } else {
          // Need a new card for this position
          positions.push({
            x: Math.round(x),
            y: Math.round(y),
            cardId: null, // Will be filled after creating cards
            isExisting: false
          });
          newCardsNeeded++;
        }
      }
    }

    // Create all needed new cards at once
    let createdCards = [];
    if (newCardsNeeded > 0) {
      const newCardsData = Array(newCardsNeeded).fill(null).map(() => ({}));
      createdCards = addCards(newCardsData);
    }

    // Assign new card IDs to positions that need them
    let newCardIndex = 0;
    for (const position of positions) {
      if (!position.isExisting) {
        position.cardId = createdCards[newCardIndex++].id;
      }
    }

    // Update all cards with their positions
    const allUpdates = positions.map(pos => ({
      id: pos.cardId,
      x: pos.x,
      y: pos.y
    }));

    if (allUpdates.length > 0) {
      updateCards(allUpdates, { animate: false });
    }

    return {
      positioned: allUpdates.length,
      created: createdCards.length,
      updated: positions.filter(p => p.isExisting).length,
      gridSize: { rows, cols }
    };
  };

  // Calculate a new card position centered in viewport
  const getNewCardPosition = () => {
    const center = getViewportCenter();
    return {
      x: center.x - CARD_WIDTH / 2,
      y: center.y - DEFAULT_CARD_HEIGHT / 2
    };
  };

  const addCards = (newCardData) => {
    const position = getNewCardPosition();
    const createdCards = newCardData.map(cardData =>
      createCard({
        ...cardData,
        x: cardData.x ?? position.x,
        y: cardData.y ?? position.y
      })
    );
    const cardIds = createdCards.map(c => c.id);

    flushSync(() => {
      setCards(prevCards => [...prevCards, ...createdCards]);
    });

    // Trigger animation via DOM after React renders
    requestAnimationFrame(() => {
      cardIds.forEach(id => {
        const element = document.querySelector(`[data-card-id="${id}"]`);
        if (element) {
          element.classList.add('animate-entry');
        }
      });
    });

    return createdCards;
  };

  const deleteCards = (cardIds) => {
    const idsToDelete = Array.isArray(cardIds) ? cardIds : [cardIds];
    setCards(prevCards => prevCards.filter(card => !idsToDelete.map(String).includes(String(card.id))));
  };

  const updateCards = (updates, { animate = true } = {}) => {
    const updatesArray = Array.isArray(updates) ? updates : [updates];

    // Detect content updates BEFORE calling setCards
    const contentUpdates = [];
    if (animate) {
      flushSync(() => {
        setCards(prevCards => {
          prevCards.forEach(card => {
            const update = updatesArray.find(u => String(u.id) === String(card.id));
            if (update) {
              const isContentUpdate =
                (update.text !== undefined && update.text !== card.text) ||
                (update.title !== undefined && update.title !== card.title) ||
                (update.imageId !== undefined && update.imageId !== card.imageId) ||
                (update.textareaHeight !== undefined && update.textareaHeight !== card.textareaHeight);

              if (isContentUpdate) {
                contentUpdates.push(card.id);
              }
            }
          });

          // Now apply the updates
          return prevCards.map(card => {
            const update = updatesArray.find(u => String(u.id) === String(card.id));
            if (!update) return card;
            return createCard({ ...card, ...update });
          });
        });
      });
    } else {
      setCards(prevCards => prevCards.map(card => {
        const update = updatesArray.find(u => String(u.id) === String(card.id));
        if (!update) return card;
        return createCard({ ...card, ...update });
      }));
    }

    // Trigger content animations via DOM after React renders (position animations handled via inline styles)
    if (animate && contentUpdates.length > 0) {
      requestAnimationFrame(() => {
        contentUpdates.forEach(id => {
          const element = document.querySelector(`[data-card-id="${id}"]`);
          if (element) {
            element.classList.add('animate-content');

            // Remove class after animation completes using animationend event
            const handleAnimationEnd = (e) => {
              if (e.animationName === 'edgeGlow') {
                element.classList.remove('animate-content');
                element.removeEventListener('animationend', handleAnimationEnd);
              }
            };
            element.addEventListener('animationend', handleAnimationEnd);
          }
        });
      });
    }
  };

  // Trigger animation for preview cards
  const animatePreviewCards = (previewIds) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        previewIds.forEach(id => {
          const element = document.querySelector(`[data-preview-id="${id}"]`);
          if (element) {
            element.classList.add('animate-preview-glow');
          }
        });
      });
    });
  };

  // Update cardOpsRef so command handlers can access these functions
  cardOpsRef.current = { addCards, deleteCards, updateCards };

  // Add new card (UI convenience wrapper)
  const addCard = () => {
    addCards([{}]);
  };

  // Delete card (UI convenience wrapper)
  const deleteCard = (cardId) => {
    deleteCards([cardId]);
  };

  // Preview item drag handlers
  const handlePreviewDragStart = (e, previewItem) => {
    setDraggedPreview(previewItem);
    e.dataTransfer.effectAllowed = 'copy';
  };

  const handlePreviewDragEnd = () => {
    setDraggedPreview(null);
    setDropTargetCard(null);
  };

  const handleCardDragOver = (e, card) => {
    if (draggedPreview) {
      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = 'copy';

      // Set drop target only if it's different to avoid unnecessary re-renders
      if (dropTargetCard !== card.id) {
        setDropTargetCard(card.id);
      }
    }
  };

  const handleCanvasDragOver = (e) => {
    if (draggedPreview && e.target === canvasRef.current) {
      // If we're over the canvas background (not a card), clear the drop target
      setDropTargetCard(null);
    }
  };

  const handleCardDrop = (e, card) => {
    if (!draggedPreview) return;

    e.preventDefault();
    e.stopPropagation();

    // Update the card with the preview image ID
    setCards(prev => prev.map(c =>
      c.id === card.id
        ? { ...c, imageId: draggedPreview.imageId }
        : c
    ));

    setDraggedPreview(null);
    setDropTargetCard(null);
  };

  // Right pane resize handlers
  const handleRightPaneResizeStart = (e) => {
    e.preventDefault();
    setIsResizingRightPane(true);
    rightPaneResizeRef.current = {
      startX: e.clientX,
      startWidth: rightPaneWidth
    };
  };

  const handleRightPaneResizeMove = (e) => {
    if (!isResizingRightPane) return;

    const deltaX = rightPaneResizeRef.current.startX - e.clientX;
    const newWidth = Math.max(200, Math.min(600, rightPaneResizeRef.current.startWidth + deltaX));
    setRightPaneWidth(newWidth);
  };

  const handleRightPaneResizeEnd = () => {
    setIsResizingRightPane(false);
  };

  useEffect(() => {
    if (isResizingRightPane) {
      document.addEventListener('mousemove', handleRightPaneResizeMove);
      document.addEventListener('mouseup', handleRightPaneResizeEnd);
      return () => {
        document.removeEventListener('mousemove', handleRightPaneResizeMove);
        document.removeEventListener('mouseup', handleRightPaneResizeEnd);
      };
    }
  }, [isResizingRightPane]);

  // Preview/agent resize handlers
  const handlePreviewResizeStart = (e) => {
    e.preventDefault();
    setIsResizingPreview(true);

    // Get the right column element to calculate container height
    const rightColumn = e.target.parentElement;
    const chatHeight = chatPaneActive ? 200 : 0; // Fixed chat height
    const resizeHandles = 4;
    const containerHeight = rightColumn.offsetHeight - chatHeight - resizeHandles;

    previewResizeRef.current = {
      startY: e.clientY,
      startPreviewFlex: previewFlex,
      startAgentFlex: agentFlex,
      containerHeight
    };
  };

  const handlePreviewResizeMove = (e) => {
    if (!isResizingPreview) return;

    const deltaY = e.clientY - previewResizeRef.current.startY;
    const { containerHeight, startPreviewFlex, startAgentFlex } = previewResizeRef.current;

    // Calculate the pixel height per flex unit
    const totalFlex = startPreviewFlex + startAgentFlex;
    const pixelsPerFlex = containerHeight / totalFlex;

    // Convert deltaY to flex change
    const flexChange = deltaY / pixelsPerFlex;

    // Update flex values, maintaining minimum sizes
    const newPreviewFlex = Math.max(0.5, startPreviewFlex + flexChange);
    const newAgentFlex = Math.max(0.5, startAgentFlex - flexChange);

    setPreviewFlex(newPreviewFlex);
    setAgentFlex(newAgentFlex);
  };

  const handlePreviewResizeEnd = () => {
    setIsResizingPreview(false);
  };

  useEffect(() => {
    if (isResizingPreview) {
      document.addEventListener('mousemove', handlePreviewResizeMove);
      document.addEventListener('mouseup', handlePreviewResizeEnd);
      return () => {
        document.removeEventListener('mousemove', handlePreviewResizeMove);
        document.removeEventListener('mouseup', handlePreviewResizeEnd);
      };
    }
  }, [isResizingPreview]);

  return (
    <div className="app-container">
      {/* SETTINGS BUTTON - Fixed Floating */}
      <button
        className={`settings-floating-btn ${activePanel === 'settings' ? 'active' : ''}`}
        onClick={() => togglePanel('settings')}
        title="Settings"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="3" y1="6" x2="12" y2="6"></line>
          <line x1="15" y1="6" x2="21" y2="6"></line>
          <circle cx="13.5" cy="6" r="1.5"></circle>
          <line x1="3" y1="12" x2="8" y2="12"></line>
          <line x1="11" y1="12" x2="21" y2="12"></line>
          <circle cx="9.5" cy="12" r="1.5"></circle>
          <line x1="3" y1="18" x2="14" y2="18"></line>
          <line x1="17" y1="18" x2="21" y2="18"></line>
          <circle cx="15.5" cy="18" r="1.5"></circle>
        </svg>
      </button>

      {/* SETTINGS PANEL */}
      <div className={`side-panel ${activePanel === 'settings' ? 'active' : ''}`}>
        <div className="panel-header">
          <div className="panel-title">Settings</div>
          <button className="close-btn" onClick={() => togglePanel('settings')}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
        <div className="panel-body">
          <ConfigPanel
            onConfigChange={handleConfigChange}
            onVolumeChange={handleVolumeChange}
          />
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div className="main-content">
        {/* LEFT SIDE - Canvas + Bottom Bar */}
        <div className="left-side">
          {/* CANVAS */}
          <div className="canvas-section">
            <div
              ref={canvasRef}
              className="canvas-scroll"
            onMouseDown={handleCanvasMouseDown}
            onDragOver={handleCanvasDragOver}
            style={{ cursor: isPanning ? 'grabbing' : 'grab' }}
          >
            <div
              className="canvas-viewport"
              style={{
                transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoom})`,
                transformOrigin: '0 0',
                transition: (isPanning || draggedCard) ? 'none' : 'transform 0.1s ease-out'
              }}
            >
              {cards.map((card, index) => (
                <div
                  key={card.id}
                  data-card-id={card.id}
                  className={`card ${dropTargetCard === card.id ? 'drop-target' : ''} ${draggedCard === card.id ? 'user-dragging' : ''}`}
                  style={{
                    position: 'absolute',
                    left: `${card.x}px`,
                    top: `${card.y}px`,
                    zIndex: card.zIndex || 0,
                    transition: draggedCard === card.id ? 'none' : 'left 0.5s cubic-bezier(0.34, 1.56, 0.64, 1), top 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)'
                  }}
                  onMouseDown={(e) => handleCardMouseDown(e, card)}
                  onDragOver={(e) => handleCardDragOver(e, card)}
                  onDrop={(e) => handleCardDrop(e, card)}
                  onAnimationEnd={(e) => {
                    // Auto-cleanup animation classes (for keyframe animations)
                    e.currentTarget.classList.remove('animate-entry', 'animate-content');
                  }}
                >
                  <div className="card-image">
                    {card.imageId ? (
                      <img
                        src={`http://localhost:8000/api/image/${card.imageId}`}
                        alt={`Card ${card.id}`}
                        className="card-image-content"
                      />
                    ) : (
                      <svg className="placeholder-icon" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                        <circle cx="8.5" cy="8.5" r="1.5"/>
                        <path d="M21 15l-5-5L5 21"/>
                      </svg>
                    )}
                    <div className="card-controls">
                      <div className="drag-indicator">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/>
                          <circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/>
                        </svg>
                      </div>
                      <div className="panel-number">{indexToLetterID(index)}</div>
                      <div className="delete-button" onClick={() => deleteCard(card.id)}>
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                        </svg>
                      </div>
                    </div>
                  </div>
                  <div className="card-content">
                    <input
                      type="text"
                      className="card-text-area card-title"
                      value={card.title || ''}
                      placeholder="Card Title"
                      onChange={(e) => setCards(cards.map(c =>
                        c.id === card.id ? { ...c, title: e.target.value || null } : c
                      ))}
                      onClick={(e) => e.stopPropagation()}
                    />
                    <div style={{ position: 'relative' }}>
                      <textarea
                        className="card-text-area card-description"
                        value={card.text || ''}
                        placeholder="Add your content here..."
                        onChange={(e) => setCards(cards.map(c =>
                          c.id === card.id ? { ...c, text: e.target.value || null } : c
                        ))}
                        onClick={(e) => e.stopPropagation()}
                        style={{ height: `${card.textareaHeight || 46}px` }}
                      />
                      <div
                        className="card-resize-handle"
                        onMouseDown={(e) => handleResizeMouseDown(e, card)}
                      >
                        <svg width="9" height="9" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                          <line x1="10" y1="14" x2="14" y2="10" />
                          <line x1="6" y1="14" x2="14" y2="6" />
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* MiniMap */}
            <MiniMap
              cards={cards}
              zoom={zoom}
              panOffset={panOffset}
              setPanOffset={setPanOffset}
              canvasRef={canvasRef}
            />
          </div>

          {/* FLOATING CONTROLS */}
          <div className="floating-controls">
            <button className="add-panel-btn" onClick={addCard} title="Add Card">
              <svg className="plus-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
              <svg className="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="10" width="18" height="11" rx="2" fill="#dbe7e1" stroke="none"></rect>
                <rect x="3" y="3" width="18" height="18" rx="2"></rect>
                <line x1="3" y1="10" x2="21" y2="10"></line>
              </svg>
            </button>

            <div className="zoom-control">
              <button
                className="zoom-btn"
                title="Zoom Out"
                onClick={() => setZoom(Math.max(0.25, zoom - 0.1))}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M5 12h14"/>
                </svg>
              </button>
              <div className="zoom-display">{Math.round(zoom * 100)}%</div>
              <button
                className="zoom-btn"
                title="Zoom In"
                onClick={() => setZoom(Math.min(2, zoom + 0.1))}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M12 5v14M5 12h14"/>
                </svg>
              </button>
              <button
                className="zoom-btn"
                title="Reset View (100%)"
                onClick={() => {
                  setZoom(1.0);
                  setPanOffset({ x: 0, y: 0 });
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                  <polyline points="9 22 9 12 15 12 15 22"/>
                </svg>
              </button>
            </div>

            <button
              className={`chat-toggle-btn ${chatPaneActive ? 'active' : ''}`}
              title="Toggle Chat"
              onClick={toggleChatPane}
            >
              <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
            </button>
          </div>
          </div>

          {/* BOTTOM BAR */}
          <div className="bottom-bar">
            <button
              className={`live-indicator ${isListening ? 'active' : ''}`}
              onClick={toggleAudioRecording}
            >
              {isListening ? (
                <>
                  <div className="waveform">
                    <div className="waveform-bar"></div>
                    <div className="waveform-bar"></div>
                    <div className="waveform-bar"></div>
                  </div>
                  Listening
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                    <line x1="12" y1="19" x2="12" y2="23"/>
                    <line x1="8" y1="23" x2="16" y2="23"/>
                  </svg>
                  Voice Mode
                </>
              )}
            </button>
            <div ref={transcriptRef} className={`live-text ${!userTranscript ? 'empty' : ''}`}>
              {userTranscript || 'Waiting for audio input...'}
            </div>
            {isListening && (
              <div
                ref={flushIndicatorRef}
                className="flush-indicator"
              ></div>
            )}
          </div>
        </div>

        {/* RIGHT PANE RESIZE HANDLE */}
        <div
          className="right-pane-resize-handle"
          onMouseDown={handleRightPaneResizeStart}
        />

        {/* RIGHT COLUMN - Split Pane */}
        <div className="right-column" style={{ flex: `0 0 ${rightPaneWidth}px` }}>
          {/* PREVIEW SECTION */}
          <div className="preview-section" style={{ flex: previewFlex, minHeight: '150px' }}>
            <div className="section-header">Preview Feed</div>
            <div className="preview-grid">
              {previewItems.map((item) => (
                <div
                  key={item.id}
                  data-preview-id={item.id}
                  className="preview-item"
                  draggable
                  onDragStart={(e) => handlePreviewDragStart(e, item)}
                  onDragEnd={handlePreviewDragEnd}
                  onAnimationEnd={(e) => {
                    if (e.animationName === 'previewEdgeGlow') {
                      e.currentTarget.classList.remove('animate-preview-glow');
                    }
                  }}
                >
                  {item.imageId ? (
                    <img
                      src={`http://localhost:8000/api/image/${item.imageId}`}
                      alt={`Preview ${item.id}`}
                      className="preview-image"
                      draggable={false}
                    />
                  ) : (
                    <svg className="placeholder-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <rect x="3" y="3" width="18" height="18" rx="2"/>
                      <circle cx="8.5" cy="8.5" r="1.5"/>
                      <path d="M21 15l-5-5L5 21"/>
                    </svg>
                  )}
                  <div className="preview-drag-hint">Drag to canvas</div>
                </div>
              ))}
            </div>
          </div>

          {/* RESIZE HANDLE */}
          <div
            className={`resize-handle ${isResizingPreview ? 'active' : ''}`}
            onMouseDown={handlePreviewResizeStart}
          ></div>

          {/* AGENT RESPONSE SECTION */}
          <div className="agent-section auto-scroll" ref={agentFeedRef} style={{ flex: agentFlex, minHeight: '150px' }}>
            <div className="section-header">Agent Responses</div>
            <div className="agent-feed">
              {responseVisible && responseText && (
                <div className="agent-message">
                  <div className="agent-message-header">🤖 Agent</div>
                  <div className={`agent-message-text ${responseIsComplete ? 'complete' : ''}`}>
                    {responseText}
                  </div>
                </div>
              )}
              {thinkingVisible && (
                <div className="agent-message">
                  <div className="agent-message-header">🤖 Agent</div>
                  <div className="agent-message-text thinking">
                    <div className="thinking-indicator">
                      <div className="thinking-dots">
                        <div className="thinking-dot"></div>
                        <div className="thinking-dot"></div>
                        <div className="thinking-dot"></div>
                      </div>
                    </div>
                    {thinkingText && <div className="thinking-content">{thinkingText}</div>}
                  </div>
                </div>
              )}
              {!thinkingVisible && !responseVisible && !responseText && (
                <div style={{ padding: '20px', textAlign: 'center', color: 'rgba(90, 85, 80, 0.4)', fontSize: '11px' }}>
                  No messages yet. Agent responses will appear here.
                </div>
              )}
            </div>
          </div>

          {/* CHAT SECTION - Conditional */}
          {chatPaneActive && (
            <div className="chat-section">
              <div className="section-header">Chat Input</div>
              <div className="chat-pane-content">
                <ChatInput
                  onSendMessage={sendChatMessage}
                  isConnected={true}
                  chatFlushIndicatorRef={chatFlushIndicatorRef}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default App;
