/**
 * AuthProvider + useAuth hook
 *
 * Fixes vs. original:
 * - apiFetch() versucht bei 401 automatisch einen Token-Refresh
 *   bevor es zum Logout kommt (kein Unterbruch nach 15 Min.)
 * - logout() sendet den Refresh-Token ans Backend zur Revocation
 * - refresh_token wird nach erfolgreichem Refresh rotiert
 */
import { createContext, useCallback, useContext, useEffect, useState } from 'react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('els_access_token');
    if (token) {
      fetchMe(token).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  async function fetchMe(token) {
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setUser(await res.json());
      } else {
        _clearTokens();
      }
    } catch {
      _clearTokens();
    }
  }

  async function login(username, password) {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Login fehlgeschlagen');
    }
    const data = await res.json();
    localStorage.setItem('els_access_token', data.access_token);
    localStorage.setItem('els_refresh_token', data.refresh_token);
    await fetchMe(data.access_token);
    return data;
  }

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem('els_refresh_token');
    const accessToken = localStorage.getItem('els_access_token');
    if (refreshToken && accessToken) {
      // Revoke refresh token on backend (fire-and-forget)
      fetch(`${API_BASE}/api/auth/logout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => {});
    }
    _clearTokens();
    setUser(null);
  }, []);

  function _clearTokens() {
    localStorage.removeItem('els_access_token');
    localStorage.removeItem('els_refresh_token');
  }

  /** Try to get a new access token using the stored refresh token. */
  async function _tryRefresh() {
    const refreshToken = localStorage.getItem('els_refresh_token');
    if (!refreshToken) return false;
    try {
      const res = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      localStorage.setItem('els_access_token', data.access_token);
      localStorage.setItem('els_refresh_token', data.refresh_token); // rotated
      return data.access_token;
    } catch {
      return false;
    }
  }

  /**
   * Authenticated fetch wrapper.
   * Automatically retries with a fresh access token on 401.
   */
  const apiFetch = useCallback(async (path, options = {}) => {
    const doRequest = (token) => {
      const headers = {
        ...(options.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };
      if (!headers['Content-Type'] && options.body && typeof options.body === 'string') {
        headers['Content-Type'] = 'application/json';
      }
      return fetch(`${API_BASE}${path}`, { ...options, headers });
    };

    let token = localStorage.getItem('els_access_token');
    let res = await doRequest(token);

    if (res.status === 401) {
      // Token expired – try silent refresh
      const newToken = await _tryRefresh();
      if (newToken) {
        res = await doRequest(newToken);
      }
      if (res.status === 401) {
        // Refresh also failed → force logout
        await logout();
        window.location.href = '/login';
        throw new Error('Sitzung abgelaufen');
      }
    }

    return res;
  }, [logout]);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, apiFetch }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
