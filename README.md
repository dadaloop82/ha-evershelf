# EverShelf for Home Assistant

> **Requires a self-hosted [EverShelf](https://github.com/dadaloop82/EverShelf) instance.**
> This integration does **not** work with any cloud service — EverShelf runs on your own server.

[![HACS Integration](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/dadaloop82/ha-evershelf)](https://github.com/dadaloop82/ha-evershelf/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![HA Minimum Version](https://img.shields.io/badge/HA-2024.1%2B-41BDF5.svg)](https://www.home-assistant.io)
[![Platforms](https://img.shields.io/badge/platforms-sensor%20|%20binary__sensor%20|%20button%20|%20todo%20|%20calendar%20|%20text-blue.svg)](#entities)

Bring your pantry into Home Assistant.
**EverShelf for HA** auto-discovers your self-hosted pantry server, exposes expiry dates as a native calendar, syncs your shopping list as a todo entity, fires automations when products expire, and lets you ask the AI for recipes — all without leaving HA.

---

## Quick install

### Step 1 — Add via HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dadaloop82&repository=ha-evershelf&category=integration)

> Don't have HACS yet? [Install HACS first](https://hacs.xyz/docs/setup/download/).

1. Click the badge above (or go to **HACS → Integrations → ⋮ → Custom repositories** and add `https://github.com/dadaloop82/ha-evershelf` with category **Integration**)
2. Find **EverShelf** and click **Download**
3. Restart Home Assistant

### Step 2 — Add the integration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=evershelf)

Click the badge above, or go to **Settings → Devices & Services → Add Integration → EverShelf**.

If your EverShelf server is on the same network and runs `avahi-daemon`, it will be **discovered automatically** — a notification will appear in HA.

---

## What you need

| Requirement | Details |
|---|---|
| **EverShelf** (self-hosted) | v1.7.0+ — [installation guide](https://github.com/dadaloop82/EverShelf#-quick-start) |
| **Home Assistant** | 2024.1.0 or newer |
| **Network** | HA host must be able to reach the EverShelf server (same LAN or routed) |
| **SETTINGS_TOKEN** | Optional — needed only for write operations (add to shopping, mark used) |

---

## Features at a glance

| Category | What you get |
|---|---|
| **16 Sensors** | Expiry counts, stock levels, location breakdown, shopping total, AI usage, last backup, days to next expiry |
| **6 Binary Sensors** | Expired items, expiring items, expiring today, shopping list active, price tracking, backup overdue, Bring! connected |
| **5 Buttons** | Refresh, Refresh Prices, Suggest Recipe (AI), Sync Smart Shopping, Clear Expired |
| **1 Todo entity** | Shopping list — bidirectional sync (add, remove, check off) |
| **1 Calendar entity** | All product expiry dates as calendar events |
| **1 Text entity** | Quick-add a product to the shopping list by typing its name |
| **7 Services** | `add_to_shopping`, `mark_used`, `refresh`, `generate_recipe`, `suggest_recipe`, `refresh_prices`, `clear_expired` |
| **Auto-discovery** | Zeroconf/mDNS — no manual URL entry needed if `avahi-daemon` runs on EverShelf host |
| **5 languages** | English, Italian, German, French, Spanish |
| **Read-only mode** | All sensors work without a token; write operations need `SETTINGS_TOKEN` |

---

## Entities

### Sensors (16)

| Entity ID | Name | Unit | Notes |
|---|---|---|---|
| `sensor.evershelf_expiring_soon` | Expiring Soon | items | Threshold configurable (default 3 days). Attribute `expiring_list` contains per-item details. |
| `sensor.evershelf_expiring_today` | Expiring Today | items | Items whose expiry date is today |
| `sensor.evershelf_expiring_3d` | Expiring in 3 Days | items | Always uses a 3-day window regardless of threshold |
| `sensor.evershelf_expired_items` | Expired Items | items | Items past their expiry date with stock > 0 |
| `sensor.evershelf_total_items` | Total Items | items | All products currently in inventory |
| `sensor.evershelf_opened_items` | Opened Items | items | Partially-opened packages being tracked |
| `sensor.evershelf_shopping_items` | Shopping List | items | Number of items on the shopping list |
| `sensor.evershelf_shopping_total` | Shopping Total | — | Estimated cost of the shopping list (e.g. `€12.40`) |
| `sensor.evershelf_items_dispensa` | Items in Pantry | items | Stock count for the pantry location |
| `sensor.evershelf_items_frigo` | Items in Fridge | items | Stock count for the fridge location |
| `sensor.evershelf_items_freezer` | Items in Freezer | items | Stock count for the freezer location |
| `sensor.evershelf_low_stock_items` | Low Stock Items | items | Items below their reorder threshold |
| `sensor.evershelf_zero_stock_items` | Out of Stock Items | items | Items with quantity = 0 |
| `sensor.evershelf_ai_calls_month` | AI Calls This Month | calls | Gemini API calls used in the current billing month |
| `sensor.evershelf_last_backup` | Last Backup | — | Timestamp of the latest EverShelf backup |
| `sensor.evershelf_days_to_next_expiry` | Days to Next Expiry | d | Days until the soonest upcoming expiry across all locations |

### Binary Sensors (6)

| Entity ID | Name | Device Class | ON when |
|---|---|---|---|
| `binary_sensor.evershelf_has_expired_items` | Has Expired Items | `problem` | At least one product is expired |
| `binary_sensor.evershelf_has_expiring_items` | Has Expiring Items | `problem` | At least one product expires within the threshold |
| `binary_sensor.evershelf_has_expiring_today` | Expiring Today (Urgent) | `problem` | At least one product expires today |
| `binary_sensor.evershelf_has_shopping_items` | Shopping List Active | — | Shopping list has at least one item |
| `binary_sensor.evershelf_price_tracking_enabled` | Price Tracking | — | Price estimation is enabled in EverShelf |
| `binary_sensor.evershelf_backup_overdue` | Backup Overdue | `problem` | No backup in the last 7 days, or no backup ever taken |
| `binary_sensor.evershelf_bring_connected` | Bring! Connected | `connectivity` | Bring! shopping app is linked and authenticated |

### Buttons (5)

| Entity ID | Name | What it does |
|---|---|---|
| `button.evershelf_refresh` | Refresh | Forces an immediate poll of all sensor data |
| `button.evershelf_refresh_prices` | Refresh Prices | Recomputes shopping list estimated total from price cache — no AI calls |
| `button.evershelf_suggest_recipe` | Suggest Recipe | Generates a structured recipe (expiry priority) and shows a **persistent notification**; also updates `sensor.evershelf_last_recipe` |
| `button.evershelf_sync_smart_shopping` | Sync Smart Shopping | Triggers the EverShelf smart shopping AI analysis |
| `button.evershelf_clear_expired` | Clear Expired | Removes expired zero-stock inventory rows from EverShelf |

### Todo entity

`todo.evershelf_shopping_list` — Native HA todo, bidirectional sync.

- **Add** items from the HA interface → they appear in EverShelf (and Bring!, if connected)
- **Delete** items → removed from EverShelf
- **Check off** items → removed from the active shopping list

### Calendar entity

`calendar.evershelf_expiry_calendar` — Every product's expiry date is a calendar event.

- Works with the standard HA calendar card and any calendar integration
- Trigger automations on specific expiry dates
- Event title = product name; description includes location and quantity
- Supports arbitrary date ranges — great for a month-ahead food planning view

### Text entity

`text.evershelf_quick_add` — Type a product name to instantly add it to the shopping list.

- Set the value from a Lovelace text card, an automation, or a voice assistant blueprint
- The field clears automatically after each submission
- Ideal for Assist / voice: *"Add eggs"* → set text → item appears on shopping list

---

## Services

### `evershelf.add_to_shopping`

```yaml
service: evershelf.add_to_shopping
data:
  name: "Milk"
  quantity: 2      # optional
  unit: "l"        # optional
```

### `evershelf.mark_used`

Reduce the stock of an inventory item (case-insensitive name match).

```yaml
service: evershelf.mark_used
data:
  name: "Olive Oil"
  quantity: 0.1
  unit: "l"
```

### `evershelf.refresh`

```yaml
service: evershelf.refresh
```

### `evershelf.generate_recipe`

Generate a full pantry recipe with the **same options as the EverShelf app**. Returns a service response (`title`, `main_ingredients`, `summary`, …), fires event `evershelf_recipe_generated`, and updates `sensor.evershelf_last_recipe`. Requires EverShelf ≥ 1.7.68.

```yaml
service: evershelf.generate_recipe
data:
  meal: pranzo          # or auto / colazione / cena / …
  persons: 2
  fuel: true            # a ritmo mio (Health)
  veloce: true
  scadenze: true
  # options: [veloce, fuel, scadenze, salutare, opened, zerowaste, pocafame]
  # meal_plan_type: pesce
response_variable: recipe
```

### `evershelf.suggest_recipe`

Legacy free-text suggestion focused on expiring items. Prefer `generate_recipe` for automations.

```yaml
service: evershelf.suggest_recipe
data:
  location: "frigo"   # optional — focus on fridge, freezer, or any location name
```

### `evershelf.refresh_prices`

Recompute the shopping list estimated total from the EverShelf price cache. No AI calls are triggered.

```yaml
service: evershelf.refresh_prices
```

### `evershelf.clear_expired`

Remove expired inventory rows whose quantity is zero.

```yaml
service: evershelf.clear_expired
```

---

## Configuration

### Auto-discovery (Zeroconf/mDNS)

If `avahi-daemon` runs on the EverShelf server, HA detects it automatically and shows a notification.

**Enable mDNS on your EverShelf server:**

```bash
sudo apt-get install -y avahi-daemon
sudo cp /var/www/html/evershelf/docker/avahi-evershelf.xml /etc/avahi/services/evershelf.xml
sudo systemctl restart avahi-daemon
```

### Manual setup

Go to **Settings → Devices & Services → Add Integration → EverShelf** and enter the URL of your EverShelf server, e.g. `http://192.168.1.100`.

### Authentication

Set `SETTINGS_TOKEN` in your EverShelf `.env` file:

```ini
SETTINGS_TOKEN=your-strong-random-string
```

Enter the same value in HA when configuring the integration.
Without a token the integration runs **read-only** — all 16 sensors, the calendar, and the todo entity (read) still work. Write operations need the token.

### Options

After setup click **Configure** on the integration card:

| Option | Default | Description |
|---|---|---|
| Expiry alert threshold | 3 days | Products expiring within N days count as "expiring soon" |
| Update interval | 300 s | How often HA polls EverShelf (60–3600 s) |

---

## Automation examples

### Alert when something expires today

```yaml
automation:
  - alias: "EverShelf — Expiring today alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.evershelf_has_expiring_today
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Use it today!"
          message: >
            {{ state_attr('sensor.evershelf_expiring_today', 'expiring_list')
               | map(attribute='name') | join(', ') }} expire today.
```

### Ask for a recipe every evening

```yaml
automation:
  - alias: "EverShelf — Evening recipe"
    trigger:
      - platform: time
        at: "18:30:00"
    action:
      - service: evershelf.generate_recipe
        data:
          meal: cena
          scadenze: true
          veloce: true
        response_variable: recipe
      - service: notify.mobile_app_YOUR_PHONE
        data:
          title: "Cena: {{ recipe.title }}"
          message: "{{ recipe.main_ingredients | join(', ') }}"
```

### Arrive home near lunch → generate recipe

```yaml
automation:
  - alias: "EverShelf — Lunch when I arrive"
    trigger:
      - platform: state
        entity_id: person.YOUR_NAME
        to: "home"
    condition:
      - condition: time
        after: "11:30:00"
        before: "14:00:00"
    action:
      - service: evershelf.generate_recipe
        data:
          meal: pranzo
          fuel: true          # a ritmo mio (if Health enabled)
          scadenze: true
          veloce: true
          persons: 2
        response_variable: recipe
      - service: tts.speak
        data:
          media_player_entity_id: media_player.YOUR_SPEAKER
          message: >
            Benvenuto. Per pranzo propongo {{ recipe.title }}.
            Ingredienti principali: {{ recipe.main_ingredients | join(', ') }}.
```

You can also listen for the event:

```yaml
automation:
  - alias: "EverShelf — on recipe event"
    trigger:
      - platform: event
        event_type: evershelf_recipe_generated
    action:
      - service: notify.mobile_app_YOUR_PHONE
        data:
          title: "{{ trigger.event.data.title }}"
          message: "{{ trigger.event.data.main_ingredients | join(', ') }}"
```

### Add to shopping via voice / Assist

```yaml
script:
  add_to_evershelf_shopping:
    alias: "Add product to EverShelf"
    fields:
      product_name:
        description: "Product name"
    sequence:
      - service: text.set_value
        target:
          entity_id: text.evershelf_quick_add
        data:
          value: "{{ product_name }}"
```

### Expiry calendar card (Lovelace)

```yaml
type: calendar
entities:
  - calendar.evershelf_expiry_calendar
initial_view: listWeek
title: Pantry Expiry Calendar
```

### Backup overdue notification

```yaml
automation:
  - alias: "EverShelf — Backup overdue"
    trigger:
      - platform: state
        entity_id: binary_sensor.evershelf_backup_overdue
        to: "on"
        for: "00:10:00"
    action:
      - service: notify.persistent_notification
        data:
          title: "EverShelf backup overdue"
          message: "No EverShelf backup in the last 7 days. Check Settings → Backup."
```

### Low stock daily digest

```yaml
automation:
  - alias: "EverShelf — Low stock digest"
    trigger:
      - platform: time
        at: "08:00:00"
    condition:
      - condition: numeric_state
        entity_id: sensor.evershelf_low_stock_items
        above: 0
    action:
      - service: evershelf.refresh_prices
      - service: notify.mobile_app_your_phone
        data:
          title: "EverShelf — Shopping reminder"
          message: >
            {{ states('sensor.evershelf_low_stock_items') }} item(s) are running low.
            Estimated total: {{ states('sensor.evershelf_shopping_total') }}.
```

---

## Troubleshooting

**Integration not found after install** — Restart Home Assistant.

**Cannot connect**
```bash
curl http://YOUR_EVERSHELF_IP/api/index.php?action=ha_info
# Expected: JSON with {"version":...,"items":...}
```

**Zeroconf not working** — Install `avahi-daemon`, copy the service file, restart avahi. HA and EverShelf must be on the same LAN (mDNS does not cross routers).

**Token error** — `SETTINGS_TOKEN` in EverShelf `.env` must match exactly what you entered in HA.

**Shopping total shows "Unknown"** — Open EverShelf → Shopping List → click **€** to fill the price cache, then press **Refresh Prices** in HA.

**Suggest Recipe times out** — Verify `GEMINI_API_KEY` is set in EverShelf `.env`. The AI call can take up to 30 seconds on first use.

**Calendar shows no events** — Only items with expiry dates set in EverShelf appear in the calendar.

**Write operations fail (403)** — Configure `SETTINGS_TOKEN` in EverShelf `.env` and re-enter it via **Settings → Integrations → EverShelf → Reconfigure**.

---

## Manual installation

1. Download the [latest release](https://github.com/dadaloop82/ha-evershelf/releases/latest)
2. Copy `custom_components/evershelf/` to `<your HA config>/custom_components/`
3. Restart Home Assistant
4. **Settings → Devices & Services → Add Integration → EverShelf**

---

## About EverShelf

EverShelf is a free, open-source, self-hosted pantry manager — no cloud, no subscription, no account required.
👉 [github.com/dadaloop82/EverShelf](https://github.com/dadaloop82/EverShelf)

---

## License

MIT © [dadaloop82](https://github.com/dadaloop82)
