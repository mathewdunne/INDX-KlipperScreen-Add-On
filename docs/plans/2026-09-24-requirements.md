# INDX KlipperScreen add-on: v1 requirements

Gathered 2026-09-24 by questioning Mathew (requirements session from
`notes/klipperscreen-addon-handoff.md` in the parent workspace). Everything
under "Decided" is his answer. "Open design risks" are Claude's findings,
not decisions. Implementation planning starts from this file.

## Decided

### Scope and audience

- Public from day one: any INDX owner, 1 to 8 tools
  (`gcode_macro TOOL_POSITIONS.tool_count`). GPLv3.
- Stock KlipperScreen, out-of-tree add-on (AFC model), no fork.
- v1: switch/park tools, load/unload filament, state at a glance, per-tool
  colour and Spoolman spool.
- Phase 2: recovery (MANUAL_TOOL_SEAT / MANUAL_TOOL_REMOVE /
  MANUAL_TOOLHEAD_RESET), top-bar active-tool badge.
- Never: calibration (Mainsail/console only), tool remapping (slicer tool =
  physical dock).

### Entry point

- One INDX button on both the `__main` and `__print` menus.
- One custom INDX icon (menu button), linked into every theme. All other
  buttons use stock KlipperScreen icons.

### Main panel: grid + side panel (layout C)

- Left: up to 8 tiles in a 4x2 grid. Per tile:
  - colour swatch and material, prominent;
  - Spoolman detail smaller: vendor/filament name, spool ID, remaining weight;
  - an unloaded tool shows "Unloaded" (text/icon) instead of filament
    details. No "Loaded" label: showing a material means loaded;
  - the mounted tool carries a badge.
- Right: the selected tool expanded, with its actions.
- Shared: Park button and toolchange count (`toolchange_count`). Nothing else
  global.
- Per-tool actions:
  - Pick up (`T<n>`), disabled on the mounted tool;
  - Load and Unload as two separate buttons, always shown, so a bad load or
    unload can be run again;
  - Assign spool;
  - Set colour/material (fallback).
- No confirmation dialogs.
- Printing: view-only, including spool and colour. Paused: everything allowed
  (e.g. reload after M600).

### Filament data

- Loaded = `save_variables` `t{n}_fil_density` is not null.
- Spoolman is first-class. Colour and material come from the assigned spool.
- Fallback when no spool is assigned: `t{n}_fil_type` / `t{n}_fil_color` in
  `save_variables`, written by a companion macro. Same pattern as Happy Hare
  (`MMU_GATE_MAP`) and AFC (`SET_COLOR` / `SET_MATERIAL`): Klipper owns the
  data, the panel sends G-code.
- Spool wins over fallback (Happy Hare style). Manual values stay underneath
  and show again if the spool is unassigned.
- Fallback colour picked from a fixed palette of preset swatches.
- Unload clears the fallback colour, `fil_type` and the spool assignment.
- Load always asks for the material, via the Klipper prompt
  (`_INDX_LOAD_PICK TOOL=n`). The spool's material is never used to skip it.
- Unload of a tool with unknown material: send the macro as-is, let its own
  fallback/error handle it.
- Spool picker: Spoolman spools, archived hidden, search/filter (on-screen
  keyboard), Unassign option. The same spool on two tools is allowed. Writes
  the same `T<n>.spool_id` + `t<n>__spool_id` Mainsail uses, so both UIs agree.

### Configurability

- Every action button (pick up, load, unload, park, assign spool, set
  colour/material) is a `[menu indx ...]` entry with `method` + `params`,
  read with `get_menu_items` (as `AFC.py` does). The panel substitutes
  `{tool}`, `{spool}`, `{color}`, `{material}`.
- Users override entries in `KlipperScreen.conf`. No `[indx]` section:
  `validate_config` rejects unknown sections and discards the whole file.
- Nothing else is configurable. Tool count from Klipper, labels always `T<n>`,
  swatch palette fixed.

### Live data

- `addons/indx.py` `init(screen)` wraps `screen.ws_subscribe` to add
  `save_variables` to the subscription. No polling fallback.
- Requires KlipperScreen with the add-on hook (PR #1770, commit `8abe645c`,
  2026-09-13) and `enable_addons: True` in `[main]`.

### Companion macros

- A Klipper cfg shipped in this repo is the single home of:
  - `UNLOAD_FILAMENT TOOL= [TEMP=]`;
  - recording `t{n}_fil_type` on load;
  - per-tool `spool_id` and the active spool following toolchanges;
  - `INDX_LOAD`, `INDX_UNLOAD`, `INDX_TOGGLE` prompt macros;
  - new set-spool and set-colour/material macros for the panel.
- Mathew's fork (`mathewdunne/INDX`) drops its copies once the companion cfg
  works.
- Installer symlinks it into `printer_data/config`. The user adds the
  `[include]` to `printer.cfg` themselves; the installer never edits
  `printer.cfg`.

### Install / update

- `install.sh`, AFC style:
  - symlinks the panel, addon and icon into KlipperScreen;
  - adds the menu conf `[include]` to `KlipperScreen.conf`;
  - sets `enable_addons`;
  - adds its paths to KlipperScreen's `.git/info/exclude`;
  - checks the minimum KlipperScreen version.
- `install.sh -u` reverses all of it.
- README documents a Moonraker `[update_manager]` snippet. The installer does
  not write `moonraker.conf`.

## Open design risks (for the implementation session)

- Klipper merges duplicate sections option by option (later wins), so the
  companion cannot wrap upstream `LOAD_FILAMENT` under the same name to
  record `fil_type`. Needs a differently named wrapper (then console
  `LOAD_FILAMENT` doesn't record it) or a full redefinition.
- Per-tool `variable_spool_id` via merged partial `[gcode_macro T<n>]`
  sections: fine for tools that exist, but a partial section for a tool the
  user doesn't have creates a macro with no `gcode:`, which is a config
  error. The companion can't know the tool count at config time.
- Active-spool follow lives in the fork's `_RECORD_TOOLCHANGE`. Moving it to
  the companion needs a hook point in upstream macros.
- Mathew's fork migration: remove the fork's copies only after the companion
  cfg is loaded and verified, or two definitions merge silently.

## Reference facts (verified 2026-09-24)

- Printer KlipperScreen `3f08a9f7` already has `_load_addons`
  (`screen.py:1008`). `~/KlipperScreen/addons/` does not exist,
  `enable_addons` not set.
- Printer display: HDMI 800x480, 108x62 mm.
- Upstream Bondtech `da20369` has `LOAD_FILAMENT TOOL= TYPE=`,
  `filament_presets`, `tool_count` (default 3), `active_tool`,
  `t{n}_fil_density`, `CHANGE_TOOL`, `PARK_TOOL`, `MANUAL_TOOL_SEAT`. It lacks
  `UNLOAD_FILAMENT`, `t{n}_fil_type`, `spool_id` on `T<n>`.
- No filament colour is stored anywhere yet.
- References studied: Happy Hare KS edition `panels/mmu_picker.py`,
  `mmu_recover.py`, `mmu_filaments.py` (spool ID overrides colour/material,
  lines 430-462); AFC add-on `install.sh`, `AFC.py` (`get_menu_items` at
  1364, manual spool edit clears the spool ID at 2532).
