import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// outDir "spa" deliberately avoids snapshot-excluded names (build/dist/out).
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: { outDir: "spa", emptyOutDir: true, sourcemap: false },
  server: { port: 5176, proxy: { "/api": "http://127.0.0.1:8001", "/health": "http://127.0.0.1:8001" } },
});
