import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import enUS from "antd/locale/en_US";
import zhCN from "antd/locale/zh_CN";
import { QueryClientProvider } from "@tanstack/react-query";

import App from "@/app/App";
import { useI18n } from "@/app/i18n";
import { queryClient } from "@/app/queryClient";
import "@/styles/global.css";

function Root() {
  const { locale } = useI18n();

  return (
    <ConfigProvider
      locale={locale === "en-US" ? enUS : zhCN}
      theme={{
        token: {
          colorPrimary: "#1668dc",
          colorInfo: "#1668dc",
          colorSuccess: "#19a55a",
          colorWarning: "#f59f00",
          colorError: "#f5222d",
          colorText: "#172033",
          colorBgLayout: "#f5f8fc",
          borderRadius: 8,
          fontFamily:
            "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
        },
        components: {
          Button: {
            controlHeight: 34,
            borderRadius: 6
          },
          Card: {
            borderRadiusLG: 8
          },
          Table: {
            headerBg: "#f4f7fb",
            headerColor: "#273246"
          },
          Tabs: {
            inkBarColor: "#1668dc",
            itemSelectedColor: "#1668dc"
          }
        }
      }}
    >
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </ConfigProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
