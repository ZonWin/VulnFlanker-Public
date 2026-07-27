import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  type ReactNode
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getCurrentUser,
  getSetupStatus,
  login,
  logout,
  setupAdmin,
  type CurrentUser,
  type LoginPayload,
  type SetupAdminPayload
} from "@/api/auth";

interface AuthContextValue {
  user: CurrentUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  needsSetup: boolean;
  isSetupLoading: boolean;
  loginAsync: (payload: LoginPayload) => Promise<CurrentUser>;
  setupAdminAsync: (payload: SetupAdminPayload) => Promise<CurrentUser>;
  logoutAsync: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const userQuery = useQuery<CurrentUser | null>({
    queryKey: ["auth", "me"],
    queryFn: getCurrentUser,
    retry: false
  });
  const setupStatusQuery = useQuery({
    queryKey: ["auth", "setup-status"],
    queryFn: getSetupStatus,
    retry: false
  });

  useEffect(() => {
    const onUnauthorized = () => {
      queryClient.setQueryData(["auth", "me"], null);
    };
    window.addEventListener("vulnflanker:unauthorized", onUnauthorized);
    return () => {
      window.removeEventListener("vulnflanker:unauthorized", onUnauthorized);
    };
  }, [queryClient]);

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: (result) => {
      queryClient.setQueryData(["auth", "me"], result.user);
    }
  });

  const setupAdminMutation = useMutation({
    mutationFn: setupAdmin,
    onSuccess: (result) => {
      queryClient.setQueryData(["auth", "me"], result.user);
      queryClient.setQueryData(["auth", "setup-status"], {
        needs_setup: false,
        has_active_superuser: true
      });
    }
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.setQueryData(["auth", "me"], null);
      void queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    }
  });

  const value = useMemo<AuthContextValue>(
    () => ({
      user: userQuery.data ?? null,
      isLoading: userQuery.isLoading || setupStatusQuery.isLoading,
      isAuthenticated: Boolean(userQuery.data),
      needsSetup: Boolean(setupStatusQuery.data?.needs_setup),
      isSetupLoading: setupStatusQuery.isLoading,
      loginAsync: async (payload) => {
        const result = await loginMutation.mutateAsync(payload);
        return result.user;
      },
      setupAdminAsync: async (payload) => {
        const result = await setupAdminMutation.mutateAsync(payload);
        return result.user;
      },
      logoutAsync: async () => {
        await logoutMutation.mutateAsync();
      }
    }),
    [
      loginMutation,
      logoutMutation,
      setupAdminMutation,
      setupStatusQuery.data?.needs_setup,
      setupStatusQuery.isLoading,
      userQuery.data,
      userQuery.isLoading
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return value;
}
