/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_COGNITO_USER_POOL_ID: string;
  readonly VITE_COGNITO_CLIENT_ID: string;
  readonly VITE_AWS_REGION: string;
  readonly VITE_AGENT_ENDPOINT: string;
  readonly VITE_BOT_USERNAME: string;
  readonly VITE_BOT_PASSWORD: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
