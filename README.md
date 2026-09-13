# Avalanche Phase II Research

This repository contains the Avalanche Phase II research site, supporting studies, and milestone documentation.

## Local development

Install the pinned dependencies and start the Quartz development server:

```bash
npm ci
npm run dev
```

Open <http://127.0.0.1:8844>. Content changes rebuild automatically.

## Build

```bash
npm run build
```

The generated site is written to `public/`. Generated output and installed dependencies are not committed.

Run the independent content and publication-boundary checks with:

```bash
npm run verify
```

## Structure

- `content/Phase I/` preserves the earlier research publication.
- `content/Phase II/` contains the current scope, studies, and milestone pages.
- `content/Wiki/` contains Avalanche-specific reference material.
- `quartz/` contains the pinned site generator.

Research status and limitations are stated on the relevant pages. A rendered page is not evidence of contractual acceptance or independent empirical validation.

## Research navigation

`data/research-navigation.json` owns collection membership, canonical source titles, and source-to-study navigation. The Wiki and Studies collection indexes are generated from that file:

```bash
npm run collections:build
```

`npm run dev` rebuilds the indexes before starting Quartz. `npm run verify` rejects stale indexes, unresolved IDs, missing pages, title drift, broken reciprocal links, and publication-boundary violations.
