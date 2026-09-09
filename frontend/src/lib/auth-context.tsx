"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { api, setAuthTokens, getAccessToken } from "./api";

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: any;
  login: (username_or_email: string, password: string) => Promise<void>;
  register: (username: string, email?: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  isAuthenticated: false,
  isLoading: true,
  user: null,
  login: async () => {},
  register: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<any>(null);

  // On mount, test silent refresh from httpOnly cookie
  useEffect(() => {
    async function checkAuth() {
      try {
        const res = await api.refreshToken();
        setAuthTokens(res.access_token, res.csrf_token);
        setIsAuthenticated(true);
      } catch (err) {
        if (!getAccessToken()) {
          setIsAuthenticated(false);
          setUser(null);
          setAuthTokens(null, null);
        }
      } finally {
        setIsLoading(false);
      }
    }
    checkAuth();
  }, []);

  const login = async (username_or_email: string, password: string) => {
    const res = await api.login(username_or_email, password);
    setAuthTokens(res.access_token, res.csrf_token);
    setUser(res.user);
    setIsAuthenticated(true);
  };

  const register = async (username: string, email?: string, password: string) => {
    const res = await api.register(username, email, password);
    setAuthTokens(res.access_token, res.csrf_token);
    setUser(res.user);
    setIsAuthenticated(true);
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // Ignore logout errors
    } finally {
      setAuthTokens(null, null);
      setIsAuthenticated(false);
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
