import { Loader } from '@aws-amplify/ui-react';
import { signIn, signOut, getCurrentUser } from 'aws-amplify/auth';
import { useEffect, useState } from 'react';
import './config/amplify';
import { BOT_USERNAME, BOT_PASSWORD } from './config/amplify';
import ChatInterface from './components/ChatInterface';
import './App.css';

type AuthState = 'loading' | 'authenticated' | 'error';

export default function App() {
  const [authState, setAuthState] = useState<AuthState>('loading');
  const [authError, setAuthError] = useState<string>('');
  const [username, setUsername] = useState<string>('');

  const doLogin = () => {
    setAuthState('loading');
    setAuthError('');
    signIn({ username: BOT_USERNAME, password: BOT_PASSWORD })
      .then(({ nextStep }) => {
        if (nextStep.signInStep === 'DONE') {
          setUsername(BOT_USERNAME);
          setAuthState('authenticated');
        } else {
          setAuthError(`Unexpected sign-in step: ${nextStep.signInStep}`);
          setAuthState('error');
        }
      })
      .catch((err) => {
        setAuthError(err instanceof Error ? err.message : String(err));
        setAuthState('error');
      });
  };

  useEffect(() => {
    // Try existing session first, otherwise auto-login with bot credentials
    getCurrentUser()
      .then((user) => {
        setUsername(user.username);
        setAuthState('authenticated');
      })
      .catch(() => doLogin());
  }, []);

  // ── Loading ──
  if (authState === 'loading') {
    return (
      <div className="auth-screen">
        <Loader size="large" />
        <p className="auth-message">Authenticating as <strong>{BOT_USERNAME}</strong>…</p>
      </div>
    );
  }

  // ── Error ──
  if (authState === 'error') {
    return (
      <div className="auth-screen">
        <div className="auth-error-card">
          <h2>🔐 Authentication Failed</h2>
          <p className="auth-error-text">{authError}</p>
          <button className="auth-retry-btn" onClick={doLogin}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  // ── Authenticated ──
  return (
    <div className="app-shell">
      <header className="app-header">
        <h2 className="app-title">🍽️ Restaurant Agent</h2>
        <div className="app-header-right">
          <span className="app-username">{username}</span>
          <button
            className="app-signout-btn"
            onClick={() => signOut().then(() => setAuthState('loading'))}
          >
            Sign Out
          </button>
        </div>
      </header>
      <main className="app-main">
        <ChatInterface />
      </main>
    </div>
  );
}
