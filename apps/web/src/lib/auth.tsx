'use client';

/**
 * Client-side auth state. Session restoration happens via the httpOnly
 * refresh cookie on first mount; until that resolves, guarded layouts show
 * a loading state instead of flashing the login page.
 */

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  api,
  AuthOrganization,
  AuthResponse,
  AuthUser,
  setAccessToken,
} from './api-client';

interface AuthState {
  status: 'loading' | 'authenticated' | 'anonymous';
  user: AuthUser | null;
  organization: AuthOrganization | null;
  applyAuth: (auth: AuthResponse) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthState['status']>('loading');
  const [user, setUser] = useState<AuthUser | null>(null);
  const [organization, setOrganization] = useState<AuthOrganization | null>(null);

  const applyAuth = useCallback((auth: AuthResponse) => {
    setAccessToken(auth.accessToken);
    setUser(auth.user);
    setOrganization(auth.organization);
    setStatus('authenticated');
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setAccessToken(null);
      setUser(null);
      setOrganization(null);
      setStatus('anonymous');
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const restored = await api.refresh();
      if (cancelled) return;
      if (!restored) {
        setStatus('anonymous');
        return;
      }
      // refresh() stores the token; a second refresh call also returns the
      // user payload, but we already have it from the response envelope in
      // applyAuth flows. For restoration we fetch nothing extra in Phase 1:
      // the shell only needs authenticated status; profile data arrives with
      // the next login or a /me endpoint in Phase 2.
      setStatus('authenticated');
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo(
    () => ({ status, user, organization, applyAuth, logout }),
    [status, user, organization, applyAuth, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
