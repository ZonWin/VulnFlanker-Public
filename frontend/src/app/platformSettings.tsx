import { t } from "@/app/i18n";
import { useQuery } from "@tanstack/react-query";
import {
  createContext,
  useContext,
  useEffect,
  type ReactNode
} from "react";

import { getPlatformSettings } from "@/api/platformSettings";
import type { PlatformSettings } from "@/api/types";

export const defaultLogoUrl = "/default-logo.svg";

export const defaultPlatformSettings: PlatformSettings = {
  id: "default",
  platform_name: "VulnFlanker",
  platform_subtitle: t("漏洞监测平台"),
  logo_data_url: null,
  ai_enabled: true,
  ai_auto_enrich_enabled: false,
  ai_auto_accept_enabled: false,
  ai_auto_accept_policy: "moderate",
  ai_auto_accept_confidence: 0.85,
  ai_web_auto_accept_confidence: 0.8,
  ai_layer2_daily_limit: 50,
  ai_batch_max_size: 100,
  ai_allow_web_enrichment_default: false,
  auto_match_on_new_asset: false,
  auto_match_on_new_vulnerability: false,
  updated_at: ""
};

export const platformSettingsQueryKey = ["platform-settings"] as const;

interface PlatformSettingsContextValue {
  settings: PlatformSettings;
  isLoading: boolean;
  isError: boolean;
}

const PlatformSettingsContext =
  createContext<PlatformSettingsContextValue | null>(null);

export function platformLogoSrc(settings: PlatformSettings) {
  return settings.logo_data_url || defaultLogoUrl;
}

export function PlatformSettingsProvider({ children }: { children: ReactNode }) {
  const query = useQuery({
    queryKey: platformSettingsQueryKey,
    queryFn: getPlatformSettings,
    staleTime: 5 * 60 * 1000
  });
  const settings = query.data ?? defaultPlatformSettings;

  useEffect(() => {
    document.title = settings.platform_name;
  }, [settings.platform_name]);

  return (
    <PlatformSettingsContext.Provider
      value={{
        settings,
        isLoading: query.isLoading,
        isError: query.isError
      }}
    >
      {children}
    </PlatformSettingsContext.Provider>
  );
}

export function usePlatformSettings() {
  return (
    useContext(PlatformSettingsContext) ?? {
      settings: defaultPlatformSettings,
      isLoading: false,
      isError: false
    }
  );
}
