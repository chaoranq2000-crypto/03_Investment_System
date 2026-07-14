import { defineConfig } from "vite";

export default defineConfig({
  base: "/",
  build: {
    outDir: "../web_assets",
    emptyOutDir: false,
    cssCodeSplit: false,
    minify: false,
    rollupOptions: {
      output: {
        codeSplitting: false,
        entryFileNames: "app.js",
        chunkFileNames: "[name].js",
        assetFileNames: (assetInfo) =>
          assetInfo.names?.some((name) => name.endsWith(".css"))
            ? "app.css"
            : "[name][extname]",
      },
    },
  },
  test: {
    environment: "node",
  },
});
