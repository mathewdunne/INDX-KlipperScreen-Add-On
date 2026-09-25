# INDX KlipperScreen add-on

A KlipperScreen panel for the Bondtech INDX toolchanger: every tool at a
glance, and pick up, park, load, unload, Spoolman spool and colour per tool.
Out of tree: stock KlipperScreen, no fork.

![INDX panel](docs/panel.png)

- Up to 8 tools, count read from `gcode_macro TOOL_POSITIONS.tool_count`.
- Each tile shows the filament colour and material, and the Spoolman spool
  (name, ID, remaining weight) when one is assigned. The mounted tool
  carries an **ON** badge.
- The selected tool's actions: Pick up, Load, Unload, Spool, Colour. Park
  and the toolchange count sit under the grid.
- View only while printing; everything works while paused.
- When a load finishes, the screen opens the Spool picker for that tool,
  or the Colour picker without Spoolman. Back skips it.

## Requirements

- KlipperScreen with add-on support: commit `8abe645c` (PR #1770,
  2026-09-13) or newer. `install.sh` checks.
- The INDX macros from [mathewdunne/INDX](https://github.com/mathewdunne/INDX)
  (`indx/*.cfg`), not upstream Bondtech: the macros the panel runs live
  there. `[save_variables]` and `[respond]`, as INDX already requires.
- Optional: Moonraker's `[spoolman]` component, for spool assignment.

## Local UI preview

Render screenshots or open a clickable GTK preview with mock printer data.
See [setup and usage](tools/preview.md).

## Install on the printer

```bash
cd ~ && git clone https://github.com/mathewdunne/INDX-KlipperScreen-Add-On.git
```
```bash
~/INDX-KlipperScreen-Add-On/install.sh
```

The installer symlinks the panel, the add-on, the menu icon and the menu
conf into place, adds `[include indx_menu.conf]` and `enable_addons: True`
to `KlipperScreen.conf`, and hides its files from KlipperScreen's
`git status`. It never edits `printer.cfg`. Then restart KlipperScreen:

```bash
sudo systemctl restart KlipperScreen
```

The INDX button appears on the main menu and the print menu.

## The macros it uses

The panel only sends G-code; Klipper owns the data. These macros are in
the fork's `indx-cal.cfg`:

| Macro | |
|---|---|
| `UNLOAD_FILAMENT TOOL= [TEMP=]` | Ram and retract 85 mm (Prusa Core ONE sequence plus 30 mm). Also forgets the tool's material, colour and spool |
| `INDX_SET_SPOOL TOOL= SPOOL=` | Assign a Spoolman spool, `SPOOL=0` to unassign. Updates the active spool if the tool is mounted |
| `INDX_SET_FILAMENT TOOL= [MATERIAL=] [COLOR=]` | Material and colour by hand, shown when no spool is assigned |
| `INDX_LOAD`, `INDX_UNLOAD`, `INDX_TOGGLE TOOL=` | Tool and material pickers as Klipper prompts; work in Mainsail too |
| `_INDX_LOAD_PICK TOOL=` | The panel's Load: asks for the material, then runs `LOAD_FILAMENT` |
| `_LOAD_FILAMENT_FEED` | The feed after `LOAD_FILAMENT`'s Continue button; ends with `action:indx_loaded <tool>`, which opens the picker |
| `_INDX_TOOLCHANGE_SPOOL TOOL=` | Called by the toolchange macros so Moonraker's active spool follows the mounted tool |

Per-tool state lives in `save_variables`: `t<n>_fil_density` (set by
`LOAD_FILAMENT`; loaded when not null), `t<n>_fil_type` (recorded by
`LOAD_FILAMENT`), `t<n>_fil_color`, `t<n>__spool_id`. An assigned spool's
colour and material win over the hand-set ones, which show again once the
spool is unassigned.

The fork's `T<n>` macros declare `variable_spool_id`, so Mainsail's Change
Spool dialog lists them, and the panel and Mainsail read and write the same
assignment. If you add a tool, give its `T<n>` the same variable.

## Changing the buttons

Every button runs a Moonraker method with parameters, `printer.gcode.script`
by default. Override one in `KlipperScreen.conf` with a `[menu indx <action>]`
section; options you leave out keep their defaults. The actions are
`pickup`, `load`, `unload`, `spool`, `filament` and `park`. In `params` the
panel replaces `{tool}`, `{spool}`, `{material}` and `{color}`:

```
[menu indx unload]
params: {"script": "MY_UNLOAD TOOL={tool}"}
```

All defaults are listed in `klipperscreen/indx_menu.conf`. Do not edit that
file itself: it is a symlink into this repo, and local edits block updates.

## Updates with Moonraker

Add to `moonraker.conf`:

```
[update_manager indx_klipperscreen]
type: git_repo
path: ~/INDX-KlipperScreen-Add-On
origin: https://github.com/mathewdunne/INDX-KlipperScreen-Add-On.git
primary_branch: main
managed_services: KlipperScreen klipper
```

## Uninstall

```bash
~/INDX-KlipperScreen-Add-On/install.sh -u
```

## License

GPLv3. See `LICENSE`.
