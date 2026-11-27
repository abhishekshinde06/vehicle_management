import apiClient from './client';

/**
 * Authenticates via FastAPI OAuth2 password-flow (application/x-www-form-urlencoded).
 */
export async function login(username, password) {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  const response = await apiClient.post('/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  return response.data;
}

export async function getCurrentUser() {
  const response = await apiClient.get('/auth/me');
  return response.data;
}

export async function getOperators() {
  const response = await apiClient.get('/auth/operators');
  return response.data;
}

export async function createOperator({ username, password, full_name }) {
  const payload = {
    username: username.trim(),
    password,
    ...(full_name && full_name.trim() ? { full_name: full_name.trim() } : {}),
  };
  const response = await apiClient.post('/auth/create-operator', payload);
  return response.data;
}
