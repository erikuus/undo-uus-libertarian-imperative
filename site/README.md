# Website App

The GitHub Pages website is isolated in this `site/` folder so archival source material remains separate.

## Local development

```bash
cd site
npm install
npm run dev
```

Open: <http://localhost:4321>

## Build and type-check

```bash
cd site
ASTRO_TELEMETRY_DISABLED=1 npm run build
ASTRO_TELEMETRY_DISABLED=1 npm run check
```

## Deployment

Deployment is handled by `.github/workflows/deploy-pages.yml`, which builds from `site/` and publishes `site/dist` to GitHub Pages.
