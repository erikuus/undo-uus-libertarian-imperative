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

## Analytics

The site now ships with GoatCounter analytics enabled for:

`https://erikuus.goatcounter.com/count`

### Local testing

If you need to override the default provider or endpoint for local testing, you
can still export these public environment variables before `npm run dev` or
`npm run build`:

- `PUBLIC_ANALYTICS_PROVIDER`
- `PUBLIC_PLAUSIBLE_DOMAIN`
- `PUBLIC_PLAUSIBLE_API_HOST`
- `PUBLIC_GOATCOUNTER_ENDPOINT`

## Deployment

Deployment is handled by `.github/workflows/deploy-pages.yml`, which builds from `site/` and publishes `site/dist` to GitHub Pages.
