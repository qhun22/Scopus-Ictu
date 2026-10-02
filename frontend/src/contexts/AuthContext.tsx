import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";
import { getCurrentUser, login as apiLogin, logout as apiLogout, LoginCredentials, User } from "../api/auth";
import {
  ApiError,
  SessionAuthErrorCode,
  subscribeToSessionAuthErrors,
} from "../api/client";
import { useToast } from "./ToastContext";

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
  forceLogout: (reason?: SessionAuthErrorCode) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const { warning } = useToast();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const mountedRef = useRef(true);
  const authenticatedRef = useRef(false);
  const sessionGenerationRef = useRef(0);
  const refreshPromiseRef = useRef<Promise<User | null> | null>(null);
  const handledSessionErrorRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const clearAuthState = useCallback(() => {
    sessionGenerationRef.current += 1;
    refreshPromiseRef.current = null;
    authenticatedRef.current = false;

    if (mountedRef.current) {
      setUser(null);
      setIsLoading(false);
    }
  }, []);

  const forceLogout = useCallback(
    (reason?: SessionAuthErrorCode) => {
      if (reason && handledSessionErrorRef.current) return;

      if (reason) {
        handledSessionErrorRef.current = true;

        if (reason === "ACCOUNT_LOCKED") {
          warning(
            "Tài khoản đang bị khóa",
            "Quản trị viên đã khóa tài khoản của bạn. Vui lòng liên hệ quản trị viên.",
          );
        } else if (reason === "PASSWORD_RESET_BY_ADMIN") {
          warning(
            "Mật khẩu đã được thay đổi",
            "Quản trị viên vừa cập nhật mật khẩu của bạn. Vui lòng liên hệ quản trị viên để nhận mật khẩu mới.",
          );
        } else {
          warning("Phiên đăng nhập đã thay đổi", "Vui lòng đăng nhập lại.");
        }
      }

      clearAuthState();
      navigate("/login", { replace: true });
    },
    [clearAuthState, navigate, warning],
  );

  useEffect(
    () =>
      subscribeToSessionAuthErrors((error) => {
        // Anonymous bootstrap requests can legitimately receive an old-cookie
        // SESSION_REVOKED response; there is no active session to interrupt.
        if (!authenticatedRef.current) return;

        // The client only publishes the three SessionAuthErrorCode values.
        forceLogout(error.code as SessionAuthErrorCode);
      }),
    [forceLogout],
  );

  const refreshUser = useCallback(async () => {
    if (refreshPromiseRef.current) return refreshPromiseRef.current;

    const requestGeneration = sessionGenerationRef.current;
    let refreshRequest: Promise<User | null>;

    refreshRequest = getCurrentUser()
      .then((currentUser) => {
        if (mountedRef.current && requestGeneration === sessionGenerationRef.current) {
          authenticatedRef.current = true;
          setUser(currentUser);
        }
        return currentUser;
      })
      .catch((error: unknown) => {
        // A plain 401 means that no usable cookie exists. Network errors and
        // ordinary 403 authorization failures must not erase a valid session.
        if (
          error instanceof ApiError &&
          error.status === 401 &&
          requestGeneration === sessionGenerationRef.current
        ) {
          clearAuthState();
        }
        throw error;
      })
      .finally(() => {
        if (refreshPromiseRef.current === refreshRequest) {
          refreshPromiseRef.current = null;
        }
      });

    refreshPromiseRef.current = refreshRequest;
    return refreshRequest;
  }, [clearAuthState]);

  useEffect(() => {
    let active = true;

    void refreshUser()
      .catch(() => null)
      .finally(() => {
        if (active && mountedRef.current) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [refreshUser]);

  const login = useCallback(async (credentials: LoginCredentials): Promise<User> => {
    const authenticatedUser = await apiLogin(credentials);
    sessionGenerationRef.current += 1;
    refreshPromiseRef.current = null;
    handledSessionErrorRef.current = false;
    authenticatedRef.current = true;

    if (mountedRef.current) {
      setUser(authenticatedUser);
      setIsLoading(false);
    }
    return authenticatedUser;
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    try {
      await apiLogout();
    } finally {
      clearAuthState();
    }
  }, [clearAuthState]);

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      login,
      logout,
      refreshUser,
      forceLogout,
    }),
    [forceLogout, isLoading, login, logout, refreshUser, user],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
