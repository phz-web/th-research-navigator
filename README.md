# Tourism & Hospitality Research Navigator (THRN)

© 2026 Hongbo Zhang. Licensed under **AGPL-3.0**.

**Author / Maintainer:** Hongbo Zhang 
**Contact:** phzhang2025@gmail.com
**Affiliation:** The Hong Kong Polytechnic University (former)  
**Created:** April 2026  
**First public release:** 21 April 2026

---

## What it is

A field-specific scholarly discovery platform for **tourism and hospitality research**.
THRN curates a whitelist of 36 core tourism/hospitality journals, ingests their
metadata from OpenAlex, and offers paper, author, and journal search with
Typesense + PostgreSQL. A disabled AI-synthesis layer is scaffolded for future
activation.

## Current status (v1)

- 36 curated journals (16 core + 20 extended)
- ~22,000 papers (2018–present)
- ~27,500 authors
- Search UI for papers / authors / journals
- Related-paper suggestion, journal and author detail pages
- AI synthesis **intentionally disabled** in v1 (see `docs/future-ai.md`)

## Stack

- **Data source:** OpenAlex (polite pool)
- **Canonical store:** PostgreSQL 16
- **Search:** Typesense 0.25
- **Ingestion:** Python 3.12 + Typer
- **Frontend:** Next.js 14 App Router + TypeScript + Tailwind v3

## Quickstart

See `README` inside the repo and `docs/` folder.

## Intellectual property & attribution

This project is licensed under **GNU Affero General Public License v3.0**
(AGPL-3.0). If you fork, host, or derive this project, you must:

1. Retain this copyright notice and author attribution.
2. Disclose your modifications and make the complete source code of any
   network-accessible derivative publicly available under the same license.
3. Not remove or alter the "Tourism & Hospitality Research Navigator"
   attribution on the public interface without written permission.

A Software Copyright Registration is in progress (China).
Trademark application for "THRN / Tourism & Hospitality Research Navigator"
is planned in China and Hong Kong.

## Citation

If you use THRN in academic work, please cite:

> Zhang, H. (2026). *Tourism & Hospitality Research Navigator: A Field-Specific
> Scholarly Discovery Platform (Version 1.0)* [Computer software].
> https://github.com/phz-web/th-research-navigator

## License

[AGPL-3.0](LICENSE)
