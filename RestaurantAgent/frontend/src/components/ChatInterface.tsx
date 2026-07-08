import { useState, useRef, useEffect, useCallback } from 'react';
import { fetchAuthSession } from 'aws-amplify/auth';
import { AGENT_ENDPOINT } from '../config/amplify';
import './ChatInterface.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

function sanitizeAssistantText(text: string): string {
  return text
    // DSML markers: handle both ｜ (U+FF5C, fullwidth) and | (U+007C, ASCII)
    // With braces:   <｜DSML｜function_calls{...}>
    // Without braces: <｜DSML｜function_calls (bleeds directly into text)
    .replace(/<[｜|]DSML[｜|]function_calls(\{[^}]*\})?/g, '')
    .replace(/function_calls\{[^}]*\}/g, '')
    .trim();
}

// Same DSML stripping but without trim — safe for streaming chunks
// so leading/trailing spaces between tokens aren't lost.
function sanitizeChunk(text: string): string {
  return text
    .replace(/<[｜|]DSML[｜|]function_calls(\{[^}]*\})?/g, '')
    .replace(/function_calls\{[^}]*\}/g, '');
}

// Stable thread ID for the conversation
const THREAD_ID = generateId();

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        "Hello! I'm the Restaurant Agent. I can help you find restaurants based on city and dining preferences. Tell me where you'd like to eat and what kind of experience you're looking for!",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  interface Activity {
    type: 'reasoning' | 'tool_call' | 'step';
    text: string;
  }

  const [agentState, setAgentState] = useState<Record<string, unknown>>({});
  const [activities, setActivities] = useState<Activity[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    setInput('');
    setError(null);

    const msgId = generateId();
    const runId = generateId();

    const userMessage: Message = {
      id: msgId,
      role: 'user',
      content: trimmed,
      timestamp: new Date(),
    };

    const assistantMessage: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setActivities([]);
    setIsLoading(true);

    try {
      const session = await fetchAuthSession();
      const token = session.tokens?.accessToken?.toString() || session.tokens?.idToken?.toString();

      if (!token) {
        throw new Error('No authentication token available. Sign out and back in.');
      }

      if (!AGENT_ENDPOINT) {
        throw new Error('Agent endpoint not configured. Set VITE_AGENT_ENDPOINT in .env');
      }

      // Build the full conversation history to send to the agent.
      // The agent needs ALL prior messages to maintain conversation context/memory.
      const conversationMessages = messages
        .filter((m) => m.id !== 'welcome') // skip the welcome placeholder
        .map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
        }));

      // Append the new user message
      conversationMessages.push({
        id: msgId,
        role: 'user' as const,
        content: trimmed,
      });

      const requestBody = {
        threadId: THREAD_ID,
        runId,
        messages: conversationMessages,
        state: agentState,
        tools: [],
        context: [],
        forwardedProps: {},
      };

      const response = await fetch(AGENT_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error');
        throw new Error(`Agent error (${response.status}): ${errorText}`);
      }

      const contentType = response.headers.get('content-type') || '';

      if (contentType.includes('text/event-stream')) {
        const reader = response.body?.getReader();
        if (!reader) throw new Error('Response body is not readable');

        const decoder = new TextDecoder();
        let buffer = '';
        let accumulatedContent = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6).trim();
              if (!dataStr || dataStr === '[DONE]') continue;

              try {
                const event = JSON.parse(dataStr);
                let chunk = '';

                // Capture agent state for conversation continuity
                if (
                  event.type === 'STATE_SNAPSHOT' ||
                  event.type === 'STATE_DELTA' ||
                  event.type === 'state'
                ) {
                  const newState = event.state || event.snapshot || event.delta || event;
                  if (newState && typeof newState === 'object') {
                    setAgentState((prev) => ({ ...prev, ...newState }));
                  }
                  continue;
                }

                // Capture reasoning/thinking text
                if (event.type === 'REASONING_MESSAGE_CONTENT') {
                  setActivities((prev) => {
                    const last = prev[prev.length - 1];
                    if (last && last.type === 'reasoning') {
                      return [...prev.slice(0, -1), { ...last, text: last.text + (event.delta || '') }];
                    }
                    return [...prev, { type: 'reasoning', text: event.delta || '' }];
                  });
                  continue;
                }

                // Track tool calls — show the agent's internal work
                if (event.type === 'TOOL_CALL_START') {
                  const toolName = event.tool_call_name || event.toolCallName || 'tool';
                  setActivities((prev) => [...prev, { type: 'tool_call' as const, text: `Calling ${toolName}...` }]);
                  continue;
                }
                if (event.type === 'TOOL_CALL_ARGS') {
                  const delta = event.delta || '';
                  if (delta) {
                    setActivities((prev) => {
                      const last = prev[prev.length - 1];
                      if (last && last.type === 'tool_call') {
                        // Show first 120 chars of args as a preview
                        const current = last.text.replace(/^Calling.*\.\.\.\n?/, '');
                        const preview = (current + delta).slice(0, 120);
                        const suffix = (current + delta).length > 120 ? '...' : '';
                        return [...prev.slice(0, -1), { ...last, text: `${last.text.split('\n')[0]}\n${preview}${suffix}` }];
                      }
                      return prev;
                    });
                  }
                  continue;
                }
                if (event.type === 'TOOL_CALL_RESULT') {
                  const content = event.content || '';
                  setActivities((prev) => {
                    const last = prev[prev.length - 1];
                    if (last && last.type === 'tool_call') {
                      // Show first 150 chars of result
                      const preview = content.slice(0, 150).replace(/^"|"$/g, '');
                      return [...prev.slice(0, -1), { ...last, text: `${last.text}\n→ ${preview}${content.length > 150 ? '...' : ''}` }];
                    }
                    return prev;
                  });
                  continue;
                }

                // Track sub-agent transitions
                if (event.type === 'STEP_STARTED') {
                  const stepName = event.step_name || event.stepName || '';
                  setActivities((prev) => [...prev, { type: 'step' as const, text: stepName }]);
                  continue;
                }
                if (event.type === 'STEP_FINISHED') {
                  setActivities((prev) => prev.filter((a) => a.type !== 'step'));
                  continue;
                }

                // Handle different AG-UI event types
                if (event.type === 'text' || event.type === 'TEXT_MESSAGE_CONTENT') {
                  chunk = event.content || event.delta || '';
                } else if (event.type === 'message' && event.content) {
                  chunk = event.content;
                } else if (event.delta) {
                  chunk = event.delta;
                } else if (typeof event.content === 'string') {
                  chunk = event.content;
                }

                // Strip DSML from each chunk (no trim — preserve word spacing)
                accumulatedContent += sanitizeChunk(chunk);
                const sanitized = sanitizeAssistantText(accumulatedContent);

                setMessages((prev) => {
                  const updated = [...prev];
                  const lastMsg = updated[updated.length - 1];
                  if (lastMsg && lastMsg.role === 'assistant') {
                    updated[updated.length - 1] = {
                      ...lastMsg,
                      content: sanitized,
                    };
                  }
                  return updated;
                });
              } catch {
                // Non-JSON data — strip DSML, preserve word spacing
                if (dataStr) {
                  accumulatedContent += sanitizeChunk(dataStr);
                  const sanitized = sanitizeAssistantText(accumulatedContent);
                  setMessages((prev) => {
                    const updated = [...prev];
                    const lastMsg = updated[updated.length - 1];
                    if (lastMsg && lastMsg.role === 'assistant') {
                      updated[updated.length - 1] = {
                        ...lastMsg,
                        content: sanitized,
                      };
                    }
                    return updated;
                  });
                }
              }
            }
          }
        }

        // Ensure content is set if the stream was empty
        setMessages((prev) => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg && lastMsg.role === 'assistant' && lastMsg.content === '') {
            updated[updated.length - 1] = {
              ...lastMsg,
              content: sanitizeAssistantText(accumulatedContent) || '(No response)',
            };
          }
          return updated;
        });
      } else {
        // JSON response (non-streaming fallback)
        const data = await response.json();
        const responseContent =
          data.content || data.response || data.message || JSON.stringify(data);

        setMessages((prev) => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            updated[updated.length - 1] = {
              ...lastMsg,
              content: sanitizeAssistantText(responseContent),
            };
          }
          return updated;
        });
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(errorMessage);

      setMessages((prev) => {
        const updated = [...prev];
        const lastMsg = updated[updated.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
          updated[updated.length - 1] = {
            ...lastMsg,
            content: sanitizeAssistantText(`⚠️ Error: ${errorMessage}`),
          };
        }
        return updated;
      });
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }, [input, isLoading, messages, agentState]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`chat-message ${msg.role === 'user' ? 'chat-message--user' : 'chat-message--assistant'}`}
          >
            <div className="chat-message__avatar">
              {msg.role === 'user' ? '👤' : '🤖'}
            </div>
            <div className="chat-message__bubble">
              <div className="chat-message__content">
                {msg.content || (isLoading && msg === messages[messages.length - 1] ? 'Thinking...' : '')}
              </div>
              <div className="chat-message__time">
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>
        ))}

        {isLoading && activities.length > 0 && (
          <div className="chat-message chat-message--assistant">
            <div className="chat-message__avatar">🔍</div>
            <div className="chat-message__bubble chat-message__bubble--thinking">
              {activities.map((a, i) => (
                <div key={i} className={`chat-thinking__item chat-thinking__item--${a.type}`}>
                  <span className="chat-thinking__label">
                    {a.type === 'tool_call' ? 'TOOL' : a.type === 'reasoning' ? 'THINK' : 'STEP'}
                  </span>
                  <span className="chat-thinking__text">{a.text}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="chat-error">
            ❌ {error}
            <button onClick={() => setError(null)}>✕</button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input
          ref={inputRef}
          type="text"
          className="chat-input"
          placeholder="Ask about restaurants..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          autoFocus
        />
        <button
          className="chat-send-button"
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
        >
          {isLoading ? '⏳' : '➤'}
        </button>
      </div>
    </div>
  );
}
