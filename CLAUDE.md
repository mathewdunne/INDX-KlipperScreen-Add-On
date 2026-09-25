# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Out-of-tree KlipperScreen add-on for the Bondtech INDX toolchanger: one panel
showing every tool (colour, material, Spoolman spool, mounted badge) plus
per-tool Pick up / Park / Load / Unload / Spool / Colour. Stock KlipperScreen,
no fork. Public repo (`origin` = github.com/mathewdunne/INDX-KlipperScreen-Add-On);
the printer's `~/INDX-KlipperScreen-Add-On` is a clone that updates with `git pull`.
Printer access, sync workflow and boundaries are in the parent workspace's
`CLAUDE.md`.

## Commands

No build, lint or test suite. Verification is the offline preview, then the
printer.

Preview (PowerShell, repo root; runs in WSL Ubuntu, needs a KlipperScreen
checkout at `../Screen Apps/KlipperScreen` or `-KlipperScreen <path>`):

```powershell
./tools/preview.ps1                                   # preview/main-ready.png
./tools/preview.ps1 -View spool                       # also: colour, home
./tools/preview.ps1 -State printing                   # also: paused
./tools/preview.ps1 -Tools 4 -Selected 2 -NoSpoolman
./tools/preview.ps1 -View home -Theme material-light  # menu icon, light theme
./tools/preview.ps1 -Interactive                      # clickable window (WSLg)
```

Output PNGs land in `preview/` (git-ignored); read them to check a UI change.
Button actions only print `OFFLINE action: <method> <params>`. Mock data is
`tools/preview-state.json`. Details and WSL setup: `tools/preview.md`.

On the printer after a change is pushed:

```bash
cd ~/INDX-KlipperScreen-Add-On && git pull
```
```bash
sudo systemctl restart KlipperScreen
```

Rerun `install.sh` only when the set of linked files changes (new file, new
theme icon). `install.sh -u` uninstalls.

## Architecture

Four pieces, all symlinked into place by `install.sh` (never copied):

- `panels/indx.py` -> `~/KlipperScreen/panels/indx.py`. The panel. Reads
  state, sends G-code, never writes state itself.
- `addons/indx.py` -> `~/KlipperScreen/addons/indx.py`. Loaded by
  KlipperScreen's add-on hook (`_load_addons`, PR #1770, needs
  `enable_addons: True`). Its `init(screen)` monkeypatches two things:
  - `screen.ws_subscribe`: adds `save_variables` and
    `gcode_macro TOOL_POSITIONS` to the Moonraker object subscription, which is
    otherwise a fixed list. Without it the panel gets initial values but no
    live updates.
  - `screen.process_action`: catches `action:indx_loaded <tool>` (emitted at
    the end of the fork's `_LOAD_FILAMENT_FEED`) and opens the spool picker,
    via `panel.pick_filament()` if the panel is showing, else
    `show_panel("indx", extra=tool)` -> `Panel.set_extra`.
- `klipperscreen/indx_menu.conf` -> `printer_data/config/indx_menu.conf`,
  included from `KlipperScreen.conf`. Holds only the two INDX menu entries
  (`__main`, `__print`); the rest is comments.
- `icons/indx.svg` / `indx-light.svg` -> `styles/<theme>/images/indx.svg` in
  every theme (`material-light` gets the light one). KlipperScreen rasterizes
  SVGs, so CSS cannot tint them; hence per-theme links.

### Data model

All state lives in Klipper, read via `self._printer.get_stat`:

- `gcode_macro TOOL_POSITIONS.tool_count` -> number of tiles (capped at 8).
- `save_variables`: `active_tool`, `toolchange_count`, and per tool
  `t<n>_fil_density` (non-null = loaded), `t<n>_fil_type`, `t<n>_fil_color`,
  `t<n>__spool_id` (double underscore, Mainsail's name).
- Spoolman spools via `screen.spoolman_api.load_all_spools`. An assigned
  spool's material/colour override the hand-set `fil_type`/`fil_color`
  (`Panel._tool`).

The macros the panel calls (`INDX_SET_SPOOL`, `INDX_SET_FILAMENT`,
`_INDX_LOAD_PICK`, `UNLOAD_FILAMENT`, `PARK_TOOL`, `T<n>`) live in Mathew's
INDX fork (`indx-cal.cfg`), not in this repo and not upstream Bondtech. The
Recovery button's `MANUAL_TOOL_SEAT` is also supplied by the fork;
`MANUAL_TOOL_REMOVE` and `MANUAL_TOOLHEAD_RESET` are upstream Bondtech's. A
change to what a button does is usually a macro change in the fork
(`../INDX-repo`), not a panel change.

### Button configuration

`ACTIONS` in `panels/indx.py` holds the defaults (name, icon, params). A
`[menu indx <key>]` section in the user's `KlipperScreen.conf` overrides
per option, read from the raw config section in `_load_actions`. Deliberate
constraints:

- Defaults must stay in Python, not in `indx_menu.conf`: an `[include]`d file
  is read after `KlipperScreen.conf` and would beat the user's overrides.
- Not `get_menu_items`: it fills missing options with defaults and clobbers
  partial overrides.
- No `[indx]` config section: KlipperScreen's `validate_config` rejects
  unknown sections and discards the whole file.

`_run` substitutes `{tool}`, `{spool}`, `{material}`, `{color}` into the params
string JSON-escaped, then parses it and calls `send_method`.

### Panel structure

`Panel.main` (tile grid left, selected-tool side panel right; stacked in
vertical mode) is swapped out of `self.content` by `_show` for the Spool,
Colour and Recovery sub-views (Recovery opens from the footer under the
grid); `back()` and `deactivate()` return to it. `refresh()`
rebuilds tiles only when `tool_count` changes, otherwise updates in place.
Actions are enabled only in `ready` and `paused` (view-only while printing).
Styling is a panel-scoped CSS provider (`.indx-panel`) using theme colours
(`@bg`, `@text`, `@active`) so it works in light and dark themes.

## Conventions

- Target display is 800x480 (printer's HDMI screen). Check layouts there
  first, then other tool counts (`-Tools 1..8`) and `material-light`.
- Other buttons use stock KlipperScreen icons only; the INDX menu icon is the
  one custom asset.
- No confirmation dialogs (product decision).
- LF line endings everywhere (`.gitattributes`); `install.sh` runs on the
  printer.
- `docs/plans/2026-09-24-requirements.md` records the v1 decisions and the
  planned phase 2 (recovery sub-view, top-bar tool badge). Check it before
  changing behaviour; it says which choices were Mathew's.
- Keep `README.md` in sync when changing actions, macros used, or install
  steps; it is the public user documentation.
