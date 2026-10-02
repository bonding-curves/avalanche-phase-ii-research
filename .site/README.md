# Research site

This directory contains the pinned Quartz application and Node environment used to publish the repository's Markdown content. It is secondary infrastructure; the research source remains in [`../content/`](../content/).

## Run locally

```bash
cd .site
npm ci
npm run dev
```

Open <http://127.0.0.1:8844>.

## Verify

```bash
cd .site
npm run verify
```

Verification checks the client content registry, Python tests, Quartz build, required routes and assets, and publication boundary. Generated output is written to `.site/public/` and is not committed.
