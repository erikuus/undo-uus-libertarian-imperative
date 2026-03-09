import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";

const isCi = process.env.GITHUB_ACTIONS === "true";

export default defineConfig({
  site: "https://erikuus.github.io",
  base: isCi ? "/undo-uus-libertarian-imperative" : "/",
  output: "static",
  integrations: [mdx()],
  markdown: {
    syntaxHighlight: false
  }
});
