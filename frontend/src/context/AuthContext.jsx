import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { getCurrentUser, login as loginApi } from '../api/auth';
import { setUnauthorizedHandler } from '../api/client';
import {
  clearAuthSession,
  getStoredToken,
  getStoredUser,
  setAuthSession,
} from '../utils/storage';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => getStoredUser());
  const [isLoading, setIsLoading] = useState(() => Boolean(getStoredToken()));
  const [sessionExpiredMessage, setSessionExpiredMessage] = useState('');

  const handleSessionExpired = useCallback(() => {
    clearAuthSession();
    setUser(null);
    setSessionExpiredMessage('Your session has expired. Please sign in again.');
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(handleSessionExpired);
    return () => setUnauthorizedHandler(null);
  }, [handleSessionExpired]);

  useEffect(() => {
    let active = true;
    const token = getStoredToken();
    if (!token) {
      setIsLoading(false);
      return undefined;
    }

    getCurrentUser()
      .then((profile) => {
        if (!active) return;
        setAuthSession(token, profile);
        setUser(profile);
      })
      .catch(() => {
        if (!active) return;
        clearAuthSession();
        setUser(null);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const loginUser = useCallback(async (username, password) => {
    setSessionExpiredMessage('');
    const tokenData = await loginApi(username, password);
    const initialUser = {
      id: tokenData.user_id,
      username: tokenData.username,
      role: tokenData.role,
      full_name: null,
      is_active: true,
    };

    setAuthSession(tokenData.access_token, initialUser);

    try {
      const profile = await getCurrentUser();
      setAuthSession(tokenData.access_token, profile);
      setUser(profile);
      return profile;
    } catch {
      setUser(initialUser);
      return initialUser;
    }
  }, []);

  const logout = useCallback(() => {
    clearAuthSession();
    setUser(null);
    setSessionExpiredMessage('');
  }, []);

  const clearSessionMessage = useCallback(() => {
    setSessionExpiredMessage('');
  }, []);

  const value = {
    user,
    isAuthenticated: Boolean(user && getStoredToken()),
    isLoading,
    sessionExpiredMessage,
    loginUser,
    logout,
    clearSessionMessage,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
