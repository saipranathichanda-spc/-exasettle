# Open Source and Third-Party Notices

ExaSettle is licensed under the MIT License. See `LICENSE` for details.

## Third-Party Components & Licenses

### 1. MiroFish
- **Source Repository**: https://github.com/666ghj/MiroFish
- **Pinned Revision**: Commit `7657031ac01184afe2cb220f5ee3545573b5e843` (main branch, release v0.1.2+)
- **License**: GNU Affero General Public License v3.0 (AGPL-3.0)
- **License Text**: See `vendor/MiroFish/LICENSE`
- **Notice**: ExaSettle integrates with MiroFish across clearly defined process and network boundaries (REST/JSON API and standalone execution). MiroFish source code is NOT relicensed under MIT and retains its original AGPL-3.0 license and copyright notices.
- **Dependencies**: MiroFish requires an OpenAI-compatible LLM endpoint (`LLM_API_KEY`) and Zep Cloud for agent memory knowledge graph (`ZEP_API_KEY`).

### 2. PyExasol
- **Source**: Exasol AG (https://github.com/exasol/pyexasol)
- **License**: MIT License
- **Purpose**: Official Python driver for connecting to Exasol analytical database.

### 3. FastAPI & Starlette
- **License**: MIT License
- **Purpose**: Modern asynchronous REST API framework for the ExaSettle dashboard.
