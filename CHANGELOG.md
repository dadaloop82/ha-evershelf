# Changelog

All notable changes to the EverShelf Home Assistant integration are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.3.1] - 2026-07-28

### Fixed
- Generated recipes are saved into EverShelf **Ricette** by default (`save: true`). Requires EverShelf ≥ 1.7.69.

## [1.3.0] - 2026-07-28

### Added
- **`evershelf.generate_recipe`** — structured recipe generation with the same options as the EverShelf app (`meal`, `persons`, `fuel` / a ritmo mio, `veloce`, `scadenze`, `pocafame`, `salutare`, `opened`, `zerowaste`, `meal_plan_type`, …). Returns `title` + `main_ingredients` via service response; fires bus event `evershelf_recipe_generated`; updates `sensor.evershelf_last_recipe`.
- Requires EverShelf **≥ 1.7.68** (`ha_generate_recipe` API).

### Fixed
- **Suggest Recipe button** — now creates a persistent notification (and uses structured generation with expiry priority).
- **`mark_used`** — reads `inventory` from `inventory_list` (was looking for missing `items` key); optional `unit` match.

---

## [1.2.3] - 2026-06-03

### Changed
- **API authentication**: supports EverShelf `API_TOKEN` (and legacy `SETTINGS_TOKEN`) via `X-API-Token`, `Authorization: Bearer`, and `api_token` query parameter
- Config flow now **requires the token** when the server reports `api_token_required`
- Updated strings/translations (IT, EN, DE, FR, ES)

### Fixed
- Integration broken after EverShelf security hardening (401 Unauthorized on all API calls)
- Discovery still works without token (`ha_info` returns minimal info); full sensors need `API_TOKEN`

---

## [1.2.1] - 2026-05-29

### Fixed
- **Coordinator safety-net** — `total_items` sensor value is guaranteed to be populated even if a future PHP API change moves the field out of `attributes`. Falls back to the response `state` value.
- **Confirmed non-issues** — audited and verified that `expiring_soon`/`expiring_items` key names, `shopping_total` float/currency handling, and product list pass-through are all correctly implemented and working as designed.


## [1.2.0] - 2026-05-29

### Added
- **`expired_list` attribute** on `sensor.evershelf_expired_items` — full per-item details for every expired product (location, brand, category, days_remaining, opened_at, vacuum_sealed, default_quantity, package_unit, product_id, inventory_id). Requires EverShelf ≥ v1.7.27.
- **`low_stock_list` attribute** on `sensor.evershelf_low_stock_items` — same full details for items with quantity ≤ 1.
- `expiring_list` on `sensor.evershelf_expiring_soon` now also includes `location`, `brand`, `category`, `days_remaining`, `opened_at`, `vacuum_sealed` and more (EverShelf ≥ v1.7.27 required; older EverShelf continues to work with the previous subset of fields).

### Notes
- Minimum EverShelf version for new attributes: **v1.7.27**
- No HA restart required after updating — entities update on the next poll

---

## [1.1.0] - 2026-05-24

### Changed
- **Setup UX**: when adding the integration, HA now automatically probes `http://evershelf.local` first instead of showing a blank URL form
- If auto-discovery fails, the UI shows a menu with **"Try auto-discovery again"** and **"Enter URL manually"** options
- Discovery failure message now explains that **avahi-daemon** (mDNS) must be installed and running on the EverShelf server for auto-discovery to work

### Fixed
- Removed `info.md` that was overriding `render_readme: true` and hiding the full README (with badges) in HACS
- GitHub repository description set — HACS validation now fully passing (8/8 checks)

---

## [1.0.0] - 2026-05-23

### Added
- Initial release
- Auto-discovery via Zeroconf/mDNS (`_evershelf._tcp.local.`) when `avahi-daemon` is running on the EverShelf host
- **4 sensors**: Expiring Soon, Expired Items, Total Items, Shopping List count
- **2 binary sensors**: Has Expired Items, Has Expiring Items
- **Todo entity**: bidirectional shopping list sync (add, delete, check off items)
- **Button entity**: force data refresh
- **3 services**: `evershelf.add_to_shopping`, `evershelf.mark_used`, `evershelf.refresh`
- Optional `SETTINGS_TOKEN` for write operations; read-only mode works without a token
- **5 languages**: English, Italian, German, French, Spanish
- Options flow: configurable expiry alert threshold (days) and polling interval (seconds)
- Supports EverShelf 1.7.0+ running on Docker or bare-metal Apache/PHP
