import { Amplify } from 'aws-amplify';

const cognitoUserPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID;
const cognitoClientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
const awsRegion = import.meta.env.VITE_AWS_REGION;

if (!cognitoUserPoolId || !cognitoClientId || !awsRegion) {
  throw new Error(
    'Missing required environment variables: VITE_COGNITO_USER_POOL_ID, VITE_COGNITO_CLIENT_ID, VITE_AWS_REGION'
  );
}

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: cognitoUserPoolId,
      userPoolClientId: cognitoClientId,
      signUpVerificationMethod: 'code',
      loginWith: {
        username: true,
      },
    },
  },
});

export const AGENT_ENDPOINT = import.meta.env.VITE_AGENT_ENDPOINT || '';
export const BOT_USERNAME = import.meta.env.VITE_BOT_USERNAME || 'bot';
export const BOT_PASSWORD = import.meta.env.VITE_BOT_PASSWORD || '';
