import axios from 'axios';
import { clearAuthSession, getStoredToken } from '../utils/storage';

export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace(/\/+$/, '');

export function getBackendOrigin() {
  return API_BASE_URL.replace(/\/api$/, '');
}

let unauthorizedHandler = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
});

apiClient.interceptors.request.use(
  (config) => {
    const token = getStoredToken();
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const requestUrl = error.config?.url || '';
    const isLoginRequest = requestUrl.includes('/auth/login');

    if (status === 401 && !isLoginRequest) {
      clearAuthSession();
      if (typeof unauthorizedHandler === 'function') {
        unauthorizedHandler();
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
