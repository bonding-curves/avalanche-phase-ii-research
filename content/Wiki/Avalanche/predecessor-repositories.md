---
title: "Predecessor repositories: intake and timeline"
description: "Evidence-based intake of four preceding Avalanche repositories. They are sources and template candidates, not implementation baselines for the new Phase II workspace."
date: 2026-09-10
participants: [Shawn Anderson, Bonding Curve Research Group]
topics: [repository history, source intake, research lifecycle, software development lifecycle]
review_status: "Initial structural intake. No code, data, or historical claim has been adopted."
---

# Predecessor repositories: intake and timeline

The new Phase II workspace begins with a clean separation between client-facing deliverables and private research resources. The preceding repositories are valuable historical sources. They can supply evidence, templates, and lessons, but they do not define the new architecture or validate current research claims.

## Timeline

| Period | Repository | Observed role | Intake status |
| --- | --- | --- | --- |
| 2025-04-02 to 2025-09-04 | [`bonding-curves/avalanche`](https://github.com/bonding-curves/avalanche) | Early private Avalanche Economic Network Model, with Python model, tests, reports, results, and documentation. 22 commits. | Historical model source. Audit before any reuse. |
| 2025-08-25 to 2025-09-04 | [`bonding-curves/avalanche-data`](https://github.com/bonding-curves/avalanche-data) | Early private data repository with deliverables, documentation, and resources. Seven commits. | Historical data/documentation source. Do not assume the data are complete, current, or reproducible. |
| 2025-09-08 to 2026-04-17 | [`bonding-curves/avalanche-research`](https://github.com/bonding-curves/avalanche-research) | Public Phase I Quartz research portal. Its README describes taxonomies, systems analysis, a differential specification, and economic hypotheses. 68 commits. | Phase I publication and document source. Capture relevant source documents before relying on portal prose. |
| 2026-01-08 to 2026-02-04 | [`bonding-curves/Avalanche-Phase-II-`](https://github.com/bonding-curves/Avalanche-Phase-II-) | Private early Phase II Quartz repository containing proposal and cadCAD-oriented material. Eight commits. | Historical proposal/context source. Not the new Phase II repository. |

The commit windows above were retrieved from authenticated GitHub metadata on September 10, 2026. They show repository activity, not research quality, completion, or scientific validity.

## What each repository can contribute

### Early model repository

Potential inputs include model interfaces, test patterns, scenario-runner patterns, generated-report conventions, and an inventory of prior model assumptions. Treat every mechanism, calibration statement, result, and chart as a claim that needs source and reproducibility review.

### Early data repository

Potential inputs include data-source inventories, collection scripts, manifests, transformation notes, and examples of deliverable packaging. Reuse only after establishing source identity, capture time, license or access restriction, schema, lineage, and quality limits.

### Phase I research portal

Potential inputs include the Phase I taxonomy set, systems-engineering analysis, differential specification, ACP summaries, and published hypotheses. The portal is a useful navigation layer, but publication prose does not replace the underlying evidence, version, or authorship record.

### Early Phase II repository

Potential inputs include proposal iterations, meeting-derived framing, candidate research questions, documentation structures, and early cadCAD/model organization. It is a historical record of intent and exploration, not a warrant to continue an unreviewed implementation path.

## Reuse policy

1. Register a predecessor artifact as a source before copying, adapting, or citing it.
2. Preserve its repository, branch, commit, path, capture time, and hash when its bytes are captured.
3. Classify each candidate as evidence, template, historical claim, or deprecated implementation.
4. Extract the smallest useful unit. Do not import an entire repository, dependency graph, branch history, or AI-generated documentation corpus merely because part of it is useful.
5. Rebuild new code from an approved specification and current tests. A predecessor implementation can motivate a design review, but it is not a baseline by default.
6. Keep research claims separate from software facts. A test passing, chart rendering, or document existing does not validate a model assumption or recommendation.

## Initial template candidates

| Candidate | Why inspect it | Adoption gate |
| --- | --- | --- |
| Data manifests and lineage records | They may provide a starting vocabulary for source, transformation, and coverage metadata. | Compare against the new source and temporal-record contracts. |
| Model contracts and test layout | They may reveal useful interfaces and failure cases. | Re-express desired behavior as a new contract and prove it with independent tests. |
| Phase I taxonomy and differential-specification documents | They provide historical conceptual context. | Record edition, scope, definitions, and whether a term remains applicable to Phase II. |
| Proposal and milestone document structures | They may improve human navigation and delivery planning. | Keep only structures that map to the signed agreement and current research lifecycle. |
| Quartz publishing patterns | They may inform eventual client-facing presentation. | Keep private research, raw sources, and internal provenance outside any publication boundary. |

## Failure patterns to prevent

No causal audit of the predecessor repositories has been completed. The following are guardrails for the new workspace, not claims about any one predecessor:

- A repository may contain useful code and still lack a trustworthy scientific claim chain.
- A rendered portal, notebook, or chart may be useful for orientation without being evidence for a recommendation.
- Branch count, agent activity, or document volume are not progress measures.
- A large model or sweep should not run until its inputs, expected outputs, cost, and decision purpose are explicit.
- Agents should produce bounded evidence, tests, and reviewable drafts. Deterministic code should perform repeatable extraction, validation, rendering, and analysis.
- Every generated result must identify the source inputs, transformations, code revision, configuration, and validation state needed to reproduce or challenge it.

## Intake sequence

1. Build a commit-and-artifact timeline for the four repositories.
2. Identify the Phase I documents that define concepts still needed in Phase II.
3. Capture only approved documents, model contracts, and data manifests into the private sources area with hashes and source metadata.
4. Produce an evidence-linked crosswalk: historical concept or artifact -> current glossary term, requirement, research question, or explicitly deprecated item.
5. Turn reusable engineering patterns into small, tested templates in the new repository. Do not carry forward old workflow machinery without a current purpose and ownership model.

## Current conclusion

The predecessor corpus is large enough to accelerate orientation and avoid repeating old mistakes. Its proper role is controlled input to a new research lifecycle: evidence first, explicit boundaries, small validated software, reviewed interpretation, and only then larger computation or publication.
