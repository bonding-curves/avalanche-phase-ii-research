---
title: Figures
description: "Find delivered Avalanche research figures by model, family, document, horizon and evidence status."
---

[Open the figure gallery](/Phase-II/Wiki/Figures/gallery.html) to browse at full width, combine filters, search captions and share the selected view. Every card links to its full-size image, available exports and the documents that use it.

<iframe src="/Phase-II/Wiki/Figures/gallery.html" title="Avalanche research figure gallery" width="100%" height="1100" style="border: 1px solid #dedede; border-radius: 6px;"></iframe>

The gallery begins with model v0.8.0. Clear the filters to include empirical observations, v0.7, historical v0.3.2 material and reference illustrations. A model label records the figure's stated context. It does not establish that a simulation or causal claim is validated. Historical results keep the qualifications in their source documents.

All listed images are delivered files. Missing model identities, horizons, commands and source receipts remain explicit. The document-use filter records embedded images in tracked Markdown, HTML image tags and wiki embeds. It does not count an ordinary link as an embedded use.

[Download the manifest](/Phase-II/Wiki/Figures/manifest.json) for paths, file hashes, source records and the figure-to-document index. The gallery works without a data connection and does not execute the model.

To rebuild or check it from a repository checkout:

```bash
python scripts/figure_gallery.py build
python scripts/figure_gallery.py check
python -m unittest discover -s scripts -p 'test_figure_gallery.py'
```

The maintained `registry.json` records explicit classifications. The generator derives available files, hashes and current document uses. PNG and SVG exports with the same stem share a card, and byte-identical copied images share one identity. Existing gallery IDs are retained where recorded. Other cards use their delivered bytes as the identity.
