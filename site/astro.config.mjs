import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";

export default defineConfig({
  site: "https://libertarianimperative.org",
  output: "static",
  integrations: [mdx()],
  markdown: {
    syntaxHighlight: false
  }
});
