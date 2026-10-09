import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

// Builds straight into ../docs so GitHub Pages can serve this repo with
// zero extra tooling: Settings -> Pages -> Deploy from a branch -> main,
// folder "/docs". `base` matches a GitHub Pages *project* site URL
// (https://<user>.github.io/yantrika-agent-patterns/) — update it if this
// repo is ever renamed, or if you deploy to a custom domain / user site
// instead (in which case base should just be "/").
export default defineConfig({
  base: "/yantrika-agent-patterns/",
  plugins: [tailwindcss()],
  build: {
    outDir: "../docs",
    emptyOutDir: true,
  },
});
