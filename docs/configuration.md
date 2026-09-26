# Configuration reference

## Macros the panel uses

The panel only sends G-code; Klipper owns the data. These macros are in the
INDX fork's `indx-cal.cfg`:

| Macro | Purpose |
| --- | --- |
| `UNLOAD_FILAMENT TOOL= [TEMP=]` | Ram and retract 85 mm (Prusa Core ONE sequence plus 30 mm). Also forgets the tool's material, colour and spool |
| `INDX_SET_SPOOL TOOL= SPOOL=` | Assign a Spoolman spool, `SPOOL=0` to unassign. Updates the active spool if the tool is mounted |
| `INDX_SET_FILAMENT TOOL= [MATERIAL=] [COLOR=]` | Material and colour by hand, shown when no spool is assigned |
| `INDX_LOAD`, `INDX_UNLOAD`, `INDX_TOGGLE TOOL=` | Tool and material pickers as Klipper prompts; work in Mainsail too |
| `_INDX_LOAD_PICK TOOL=` | The panel's Load: asks for the material, then runs `LOAD_FILAMENT` |
| `_LOAD_FILAMENT_FEED` | The feed after `LOAD_FILAMENT`'s Continue button; ends with `action:indx_loaded <tool>`, which opens the picker |
| `_INDX_TOOLCHANGE_SPOOL TOOL=` | Called by the toolchange macros so Moonraker's active spool follows the mounted tool |

The Recovery buttons use `indx-cal.cfg`: `MANUAL_TOOL_SEAT TOOL=` is supplied
by the fork; `MANUAL_TOOL_REMOVE` and `MANUAL_TOOLHEAD_RESET` are Bondtech
macros retained in the fork.

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
`pickup`, `load`, `unload`, `spool`, `filament`, `park`, `seat`, `remove`
and `reset`. In `params` the panel replaces `{tool}`, `{spool}`, `{material}`
and `{color}`:

```ini
[menu indx unload]
params: {"script": "MY_UNLOAD TOOL={tool}"}
```

All defaults are listed in `klipperscreen/indx_menu.conf`. Do not edit that
file itself: it is a symlink into this repo, and local edits block updates.
