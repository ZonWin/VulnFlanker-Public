import { RouterProvider } from "react-router";

import { AuthProvider } from "@/app/auth";
import { PlatformSettingsProvider } from "@/app/platformSettings";
import { router } from "@/app/router";

export default function App() {
  return (
    <PlatformSettingsProvider>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </PlatformSettingsProvider>
  );
}
