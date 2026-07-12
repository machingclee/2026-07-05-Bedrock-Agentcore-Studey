import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchAuthSession } from 'aws-amplify/auth';
import { CopilotKit, CopilotChat } from '@copilotkit/react-core/v2';
import { HttpAgent } from '@ag-ui/client';
import { AGENT_ENDPOINT } from '../config/amplify';
import '@copilotkit/react-ui/v2/styles.css';

const AGENT_ID = 'restaurant_agent';

export default function CopilotChatInterface() {
  const threadIdRef = useRef(crypto.randomUUID());
  const [token, setToken] = useState<string | null>(null);
  const [tokenError, setTokenError] = useState<string | null>(null);

  // Fetch the Cognito JWT on mount (same as existing ChatInterface)
  useEffect(() => {
    fetchAuthSession()
      .then((session) => {
        const t =
          session.tokens?.accessToken?.toString() ||
          session.tokens?.idToken?.toString();
        if (!t) {
          setTokenError('No authentication token available.');
          return;
        }
        setToken(t);
      })
      .catch((err) => {
        setTokenError(err instanceof Error ? err.message : String(err));
      });
  }, []);

  // Build the HttpAgent once we have a token. The HttpAgent handles
  // the full AG-UI protocol: streaming, state, tool calls, reasoning.
  const agents = useMemo(() => {
    if (!token || !AGENT_ENDPOINT) return null;
    return {
      [AGENT_ID]: new HttpAgent({
        url: AGENT_ENDPOINT,
        threadId: threadIdRef.current,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }),
    };
  }, [token]);

  if (tokenError) {
    return (
      <div className="auth-error-card">
        <p>Authentication error: {tokenError}</p>
      </div>
    );
  }

  if (!agents) {
    return <div className="auth-screen"><p>Connecting to agent...</p></div>;
  }

  return (
    <CopilotKit selfManagedAgents={agents}>
      <CopilotChat
        agentId={AGENT_ID}
        labels={{
          chatInputPlaceholder: 'Ask about restaurants...',
        }}
      />
    </CopilotKit>
  );
}
