# INDX KlipperScreen add-on: tool overview and per-tool actions
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
# State comes from save_variables (kept live by addons/indx.py) and from
# Spoolman through Moonraker. Every button sends G-code built from an
# overridable [menu indx <action>] entry; the panel never writes state itself.

import json
import logging
import math

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango

from ks_includes.screen_panel import ScreenPanel

MAX_TOOLS = 8

# Scoped to this panel; use the host theme's colours for light/dark support.
PANEL_CSS = b"""
.indx-panel button {
    background-color: mix(@bg, @text, 0.035);
    border: 1px solid alpha(@text, 0.14);
    border-radius: 8px;
    padding: 6px;
    margin: 3px;
}
.indx-panel button.button_active {
    background-color: @active;
    border-color: alpha(@text, 0.8);
}
.indx-panel button:active {
    background-color: @active;
}
.indx-panel button:disabled {
    border: 1px solid alpha(@text, 0.09);
}
.indx-panel .indx-info { padding: 6px 6px 10px; }
.indx-panel .indx-dim { opacity: 0.7; }
.indx-panel .indx-badge {
    background-color: #2e7d32;
    color: #ffffff;
    border-radius: 5px;
    padding: 0 6px;
}
"""
_style_provider = None


def install_style():
    global _style_provider
    if _style_provider is None:
        _style_provider = Gtk.CssProvider()
        _style_provider.load_from_data(PANEL_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), _style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
        )

# Defaults for each button. [menu indx <key>] in KlipperScreen.conf overrides
# any of name, icon, method, params. A shipped conf cannot hold these: an
# included file is read after KlipperScreen.conf and would win over the user.
ACTIONS = {
    "pickup": {"name": "Pick up", "icon": "extruder", "params": '{"script": "T{tool}"}'},
    "load": {"name": "Load", "icon": "load", "params": '{"script": "_INDX_LOAD_PICK TOOL={tool}"}'},
    "unload": {
        "name": "Unload",
        "icon": "retract",
        "params": '{"script": "UNLOAD_FILAMENT TOOL={tool}"}',
    },
    "spool": {
        "name": "Spool",
        "icon": "spoolman",
        "params": '{"script": "INDX_SET_SPOOL TOOL={tool} SPOOL={spool}"}',
    },
    "filament": {
        "name": "Colour",
        "icon": "fine-tune",
        "params": '{"script": "INDX_SET_FILAMENT TOOL={tool} MATERIAL={material} COLOR={color}"}',
    },
    "park": {"name": "Park", "icon": "toolchanger", "params": '{"script": "PARK_TOOL"}'},
}

PALETTE = [
    "FFFFFF", "C0C0C0", "808080", "000000", "E53935", "FB8C00", "FDD835", "C0CA33",
    "43A047", "00897B", "1E88E5", "283593", "8E24AA", "EC407A", "6D4C41", "F5E6C8",
]  # fmt: skip


def esc(text):
    return GLib.markup_escape_text(str(text))


def spool_color(spool):
    fil = spool.get("filament") or {}
    if fil.get("color_hex"):
        return fil["color_hex"]
    multi = fil.get("multi_color_hexes") or ""
    return multi.split(",")[0] or None


def spool_title(spool):
    fil = spool.get("filament") or {}
    vendor = (fil.get("vendor") or {}).get("name") or ""
    return f"{vendor} {fil.get('name') or ''}".strip()


def spool_id_line(spool_id, spool):
    weight = spool.get("remaining_weight") if spool else None
    return f"#{spool_id}" if weight is None else f"#{spool_id} · {weight:.0f} g"


def rounded_rect(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def draw_swatch(area, ctx, holder):
    w, h = area.get_allocated_width(), area.get_allocated_height()
    if holder.get("square"):
        side = min(w, h)
        ctx.translate((w - side) / 2, (h - side) / 2)
        w = h = side
    rgba = Gdk.RGBA()
    if holder.get("color") and rgba.parse(f"#{holder['color']}"):
        rounded_rect(ctx, 0.5, 0.5, w - 1, h - 1, 4)
        ctx.set_source_rgb(rgba.red, rgba.green, rgba.blue)
        ctx.fill_preserve()
        ctx.set_source_rgba(0.5, 0.5, 0.5, 0.6)
        ctx.set_line_width(1)
        ctx.stroke()
    else:
        # No colour known: dashed outline
        rounded_rect(ctx, 1, 1, w - 2, h - 2, 4)
        ctx.set_source_rgb(0.5, 0.5, 0.5)
        ctx.set_line_width(2)
        ctx.set_dash([4, 4])
        ctx.stroke()


def swatch(holder, height, width=-1):
    area = Gtk.DrawingArea(hexpand=width < 0)
    area.set_size_request(width, height)
    area.connect("draw", draw_swatch, holder)
    return area


def badge(text):
    label = Gtk.Label(no_show_all=True, valign=Gtk.Align.CENTER)
    label.set_markup(f"<small><b>{text}</b></small>")
    label.get_style_context().add_class("indx-badge")
    return label


def section_label(text):
    label = Gtk.Label(xalign=0, margin_top=4)
    label.set_markup(f"<small><b>{text.upper()}</b></small>")
    label.get_style_context().add_class("indx-dim")
    return label


def small_label(lines=1, xalign=0.0, dim=False):
    label = Gtk.Label(xalign=xalign, hexpand=True)
    if dim:
        label.get_style_context().add_class("indx-dim")
    label.set_ellipsize(Pango.EllipsizeMode.END)
    # Let the parent allocate the width instead of requesting the full text.
    # Multiline spool names otherwise widen every column in the tool grid.
    label.set_max_width_chars(1)
    if lines > 1:
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_lines(lines)
    return label


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        title = title or "INDX"
        super().__init__(screen, title)
        install_style()
        self.content.get_style_context().add_class("indx-panel")
        self.actions = self._load_actions()
        self.spools = {}
        self.tool_count = 0
        self.selected = None
        self.tiles = []
        self.subview = None
        self.last_state = None

        self.grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, hexpand=True, vexpand=True)
        self.side = self._build_side()

        self.count = small_label(xalign=1.0, dim=True)
        self.count.set_margin_end(6)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
        left.pack_start(self.grid, True, True, 0)
        left.pack_start(self.count, False, False, 2)

        vertical = self._screen.vertical_mode
        self.main = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,
            spacing=5,
        )
        self.main.pack_start(left, True, True, 0)
        self.main.pack_start(self.side, False, True, 0)
        if not vertical:
            self.side.set_size_request(int(self._gtk.content_width * 0.36), -1)
        self.content.add(self.main)

    # ----- configuration -----

    def _load_actions(self):
        cfg = self._config.get_config()
        actions = {}
        for key, default in ACTIONS.items():
            action = {"method": "printer.gcode.script", **default}
            section = f"menu indx {key}"
            if cfg.has_section(section):
                for option in ("name", "icon", "method", "params"):
                    if cfg.has_option(section, option):
                        action[option] = cfg.get(section, option)
            actions[key] = action
        return actions

    def _action_button(self, key):
        action = self.actions[key]
        button = self._gtk.Button(
            action["icon"], action["name"], None, self.bts, Gtk.PositionType.LEFT, 1
        )
        return button

    # ----- printer state -----

    def _vars(self):
        return self._printer.get_stat("save_variables", "variables") or {}

    def _tool(self, n):
        svv = self._vars()
        spool_id = svv.get(f"t{n}__spool_id") or None
        spool = self.spools.get(spool_id) if spool_id else None
        material = color = None
        if spool:
            material = (spool.get("filament") or {}).get("material")
            color = spool_color(spool)
        return {
            "loaded": svv.get(f"t{n}_fil_density") is not None,
            "mounted": svv.get("active_tool", -1) == n,
            "spool_id": spool_id,
            "spool": spool,
            "material": material or svv.get(f"t{n}_fil_type"),
            "color": color or svv.get(f"t{n}_fil_color"),
            "fallback_material": svv.get(f"t{n}_fil_type"),
            "fallback_color": svv.get(f"t{n}_fil_color"),
        }

    def _can_act(self):
        return self._printer.state in ("ready", "paused")

    # ----- layout -----

    def _build_side(self):
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=False)
        self.side_title = Gtk.Label(xalign=0)
        self.side_badge = badge("ON HEAD")
        header = Gtk.Box(spacing=8)
        header.pack_start(self.side_title, False, False, 0)
        header.pack_start(self.side_badge, False, False, 0)
        self.side_note = small_label(dim=True)
        self.side_note.set_no_show_all(True)
        self.side_note.set_markup("<small>View only while printing</small>")
        self.side_color = {}
        self.side_material = small_label()
        self.side_detail = small_label(lines=3, dim=True)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        info.get_style_context().add_class("indx-info")
        info.pack_start(header, False, False, 0)
        info.pack_start(self.side_note, False, False, 0)
        info.pack_start(swatch(self.side_color, self._gtk.font_size), False, False, 0)
        info.pack_start(self.side_material, False, False, 0)
        info.pack_start(self.side_detail, False, False, 0)

        self.buttons = {}
        for key in ("pickup", "park", "load", "unload", "spool", "filament"):
            self.buttons[key] = self._action_button(key)
        self.buttons["pickup"].connect("clicked", self._run, "pickup")
        self.buttons["park"].connect("clicked", self._run, "park")
        self.buttons["load"].connect("clicked", self._run, "load")
        self.buttons["unload"].connect("clicked", self._run, "unload")
        self.buttons["spool"].connect("clicked", self._show_spools)
        self.buttons["filament"].connect("clicked", self._show_filament)

        grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, vexpand=True)
        # Pick up and Park share a cell; _update_side shows one of them.
        for key in ("pickup", "park"):
            self.buttons[key].show_all()
            self.buttons[key].set_no_show_all(True)
            grid.attach(self.buttons[key], 0, 0, 2, 1)
        grid.attach(self.buttons["load"], 0, 1, 1, 1)
        grid.attach(self.buttons["unload"], 1, 1, 1, 1)
        grid.attach(self.buttons["spool"], 0, 2, 1, 1)
        grid.attach(self.buttons["filament"], 1, 2, 1, 1)
        side.pack_start(info, False, False, 0)
        side.pack_start(grid, True, True, 0)
        return side

    def _build_tiles(self):
        for child in self.grid.get_children():
            self.grid.remove(child)
        self.tiles = []
        # One row up to 3 tools, then two rows: 4 -> 2x2, 6 -> 3x2, 8 -> 4x2.
        columns = self.tool_count if self.tool_count <= 3 else (self.tool_count + 1) // 2
        for n in range(self.tool_count):
            tile = {"color": None}
            tile["title"] = Gtk.Label(xalign=0, hexpand=True)
            tile["badge"] = badge("ON")
            tile["material"] = small_label()
            tile["detail"] = small_label(lines=2, dim=True)
            tile["meta"] = small_label(dim=True)
            header = Gtk.Box()
            header.pack_start(tile["title"], True, True, 0)
            header.pack_end(tile["badge"], False, False, 0)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, valign=Gtk.Align.START)
            box.pack_start(header, False, False, 0)
            box.pack_start(swatch(tile, self._gtk.font_size), False, False, 0)
            box.pack_start(tile["material"], False, False, 0)
            box.pack_start(tile["detail"], False, False, 0)
            box.pack_start(tile["meta"], False, False, 0)
            button = self._gtk.Button()
            button.add(box)
            button.connect("clicked", self._select, n)
            tile["button"] = button
            self.grid.attach(button, n % columns, n // columns, 1, 1)
            self.tiles.append(tile)
        self.grid.show_all()

    # ----- refresh -----

    def refresh(self):
        self.last_state = self._printer.state
        count = self._printer.get_stat("gcode_macro TOOL_POSITIONS", "tool_count")
        count = max(0, min(int(count or 0), MAX_TOOLS))
        if count != self.tool_count:
            self.tool_count = count
            self._build_tiles()
        if not self.tool_count:
            self.side_title.set_markup("<b>No INDX tools</b>")
            self.side_detail.set_text("gcode_macro TOOL_POSITIONS not found")
            return
        svv = self._vars()
        if self.selected is None or self.selected >= self.tool_count:
            active = svv.get("active_tool", -1)
            self.selected = active if 0 <= active < self.tool_count else 0

        for n, tile in enumerate(self.tiles):
            self._update_tile(n, tile, self._tool(n))
        self._update_side()
        self.count.set_markup(f"<small>Toolchanges: {svv.get('toolchange_count', 0)}</small>")

    def _update_tile(self, n, tile, tool):
        tile["title"].set_markup(f"<b>T{n}</b>")
        tile["badge"].set_visible(tool["mounted"])
        ctx = tile["button"].get_style_context()
        if n == self.selected:
            ctx.add_class("button_active")
        else:
            ctx.remove_class("button_active")
        if not tool["loaded"]:
            tile["color"] = None
            tile["material"].set_markup("<i>Unloaded</i>")
            tile["detail"].set_text("")
            tile["meta"].set_text("")
        else:
            tile["color"] = tool["color"]
            tile["material"].set_markup(f"<b>{esc(tool['material'] or '?')}</b>")
            title = spool_title(tool["spool"]) if tool["spool"] else ""
            tile["detail"].set_markup(f"<small>{esc(title)}</small>")
            meta = spool_id_line(tool["spool_id"], tool["spool"]) if tool["spool_id"] else ""
            tile["meta"].set_markup(f"<small>{esc(meta)}</small>")
        tile["button"].queue_draw()

    def _spool_markup(self, tool):
        if not tool["spool_id"]:
            return ""
        lines = [spool_title(tool["spool"])] if tool["spool"] else []
        lines.append(spool_id_line(tool["spool_id"], tool["spool"]))
        return f"<small>{esc(chr(10).join(line for line in lines if line))}</small>"

    def _update_side(self):
        n = self.selected
        tool = self._tool(n)
        state = self._printer.state
        self.side_title.set_markup(f"<big><b>T{n}</b></big>")
        self.side_badge.set_visible(tool["mounted"])
        self.side_note.set_visible(state == "printing")
        if tool["loaded"]:
            self.side_color["color"] = tool["color"]
            self.side_material.set_markup(f"<b>{esc(tool['material'] or 'Unknown material')}</b>")
        else:
            self.side_color["color"] = None
            self.side_material.set_markup("<i>Unloaded</i>")
        detail = self._spool_markup(tool) if tool["spool_id"] else "<small>No spool assigned</small>"
        self.side_detail.set_markup(detail)
        self.side.queue_draw()

        can = self._can_act()
        self.buttons["pickup"].set_visible(not tool["mounted"])
        self.buttons["park"].set_visible(tool["mounted"])
        self.buttons["pickup"].set_sensitive(can)
        self.buttons["park"].set_sensitive(can)
        for key in ("load", "unload", "filament"):
            self.buttons[key].set_sensitive(can)
        self.buttons["spool"].set_sensitive(can and self._printer.spoolman)

    # ----- KlipperScreen hooks -----

    def activate(self):
        self.refresh()
        self._fetch_spools()

    def set_extra(self, extra=None, **kwargs):
        # show_panel("indx", extra=tool) from addons/indx.py after a load. Idle,
        # because show_panel calls this before attaching, which resets the title.
        if extra is not None:
            GLib.idle_add(self.pick_filament, int(extra))

    def deactivate(self):
        if self.subview is not None:
            self._show_main()

    def process_update(self, action, data):
        if action == "notify_status_update":
            if "save_variables" in data:
                self._fetch_missing_spools()
            if (
                "save_variables" in data
                or "gcode_macro TOOL_POSITIONS" in data
                or self._printer.state != self.last_state
            ):
                self.refresh()
        elif action == "notify_active_spool_set":
            self._fetch_spools()

    def back(self):
        if self.subview is not None:
            self._show_main()
            return True
        return False

    # ----- actions -----

    def _select(self, widget, n):
        self.selected = n
        self.refresh()

    def _run(self, widget, key, **values):
        action = self.actions[key]
        values.setdefault("tool", self.selected)
        params = action["params"]
        for name, value in values.items():
            # Escaped for a JSON string, since that is where the placeholders sit
            params = params.replace(f"{{{name}}}", json.dumps(str(value))[1:-1])
        try:
            params = json.loads(params)
        except ValueError:
            logging.exception(f"INDX: bad params in [menu indx {key}]: {action['params']}")
            self._screen.show_popup_message(f"INDX: [menu indx {key}] params is not valid JSON")
            return
        logging.info(f"INDX {key}: {action['method']} {params}")
        if isinstance(widget, Gtk.Button):
            self._gtk.Button_busy(widget, True)
        self._screen._ws.send_method(action["method"], params, self._run_done, widget)

    def _run_done(self, result, method, params, widget):
        if isinstance(widget, Gtk.Button):
            self._gtk.Button_busy(widget, False)
        self.refresh()

    # ----- Spoolman -----

    def _fetch_spools(self):
        if self._printer.spoolman:
            self._screen.spoolman_api.load_all_spools(allow_archived=True, callback=self._got_spools)

    def _fetch_missing_spools(self):
        svv = self._vars()
        ids = {svv.get(f"t{n}__spool_id") for n in range(self.tool_count)}
        if any(i and i not in self.spools for i in ids):
            self._fetch_spools()

    def _got_spools(self, spools):
        if not isinstance(spools, list):
            logging.warning("INDX: could not load spools from Spoolman")
            return
        self.spools = {s["id"]: s for s in spools if "id" in s}
        self.refresh()

    # ----- sub-views -----

    def pick_filament(self, tool):
        """After a load: the spool picker for tool, or the colour picker without Spoolman."""
        self.selected = tool
        if not self._printer.spoolman:
            self._show_filament(None)
            return

        def got(spools):
            # Reloaded so a spool just added in Spoolman is listed
            self._got_spools(spools)
            if self.selected == tool:
                self._show_spools(None)

        self._screen.spoolman_api.load_all_spools(allow_archived=True, callback=got)

    def _show(self, widget, name=None):
        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(widget)
        self.content.show_all()
        self.subview = name
        title = f"{self.title} | T{self.selected} {name}" if name else self.title
        self._screen.base_panel.set_title(title)

    def _show_main(self, *args):
        self._screen.remove_keyboard()
        self._show(self.main)
        self.refresh()

    def _show_spools(self, widget):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        entry = Gtk.Entry(hexpand=True, placeholder_text="Search spools")
        entry.connect("button-press-event", self._screen.show_keyboard)
        entry.connect("touch-event", self._screen.show_keyboard)
        unassign = self._gtk.Button("cancel", "Unassign", "color2", self.bts, Gtk.PositionType.LEFT, 1)
        unassign.set_hexpand(False)
        unassign.set_vexpand(False)
        unassign.connect("clicked", self._assign, 0)
        current = self._tool(self.selected)["spool_id"]
        unassign.set_sensitive(bool(current))
        top = Gtk.Box(spacing=5)
        top.pack_start(entry, True, True, 0)
        top.pack_start(unassign, False, False, 0)

        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        spools = sorted(
            (s for s in self.spools.values() if not s.get("archived")), key=lambda s: s["id"]
        )
        found = []
        for spool in spools:
            fil = spool.get("filament") or {}
            text = f"#{spool['id']} {spool_title(spool)} {fil.get('material') or ''}"
            holder = {"color": spool_color(spool)}
            label = Gtk.Label(xalign=0, hexpand=True)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_markup(
                f"<b>{esc(spool_title(spool) or 'Spool')}</b>  {esc(fil.get('material') or '')}\n"
                f"<small><span alpha='70%'>{esc(spool_id_line(spool['id'], spool))}</span></small>"
            )
            row = Gtk.Box(spacing=10)
            row.pack_start(swatch(holder, self._gtk.font_size * 2, self._gtk.font_size * 2), False, False, 0)
            row.pack_start(label, True, True, 0)
            button = self._gtk.Button()
            button.add(row)
            button.set_vexpand(False)
            button.connect("clicked", self._assign, spool["id"])
            if spool["id"] == current:
                button.get_style_context().add_class("button_active")
            rows.pack_start(button, False, False, 0)
            found.append((text.lower(), button))
        if not spools:
            rows.pack_start(Gtk.Label(label="No spools in Spoolman"), False, False, 10)
        entry.connect("changed", self._filter_spools, found)

        scroll = self._gtk.ScrolledWindow()
        scroll.add(rows)
        box.pack_start(top, False, False, 0)
        box.pack_start(scroll, True, True, 0)
        self._show(box, "spool")

    @staticmethod
    def _filter_spools(entry, found):
        words = entry.get_text().lower().split()
        for text, button in found:
            button.set_visible(all(w in text for w in words))

    def _assign(self, widget, spool_id):
        self._run(widget, "spool", spool=spool_id)
        self._show_main()

    def _show_filament(self, widget):
        tool = self._tool(self.selected)
        choice = {"material": tool["fallback_material"], "color": tool["fallback_color"]}
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        if tool["spool_id"]:
            note = Gtk.Label(xalign=0, wrap=True)
            note.get_style_context().add_class("indx-dim")
            note.set_markup(
                f"<small>Spool #{tool['spool_id']} supplies the material and colour. "
                "These choices apply when it is unassigned.</small>"
            )
            box.pack_start(note, False, False, 0)

        presets = self._printer.get_stat("gcode_macro LOAD_FILAMENT", "filament_presets") or {}
        materials = list(presets)
        if choice["material"] and choice["material"] not in materials:
            materials.append(choice["material"])
        mat_buttons = {}
        mat_grid = Gtk.Grid(column_homogeneous=True)
        for i, material in enumerate(materials):
            button = self._gtk.Button(None, material, None, self.bts, Gtk.PositionType.LEFT, 1)
            button.set_vexpand(False)
            button.connect("clicked", self._pick, choice, "material", material, mat_buttons)
            mat_buttons[material] = button
            mat_grid.attach(button, i % 4, i // 4, 1, 1)

        color_buttons = {}
        color_grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=True, vexpand=True)
        for i, color in enumerate(PALETTE):
            button = self._gtk.Button()
            button.add(swatch({"color": color, "square": True}, self._gtk.font_size * 2))
            button.connect("clicked", self._pick, choice, "color", color, color_buttons)
            color_buttons[color] = button
            color_grid.attach(button, i % 8, i // 8, 1, 1)

        apply = self._gtk.Button("complete", "Apply", "color1", self.bts, Gtk.PositionType.LEFT, 1)
        apply.set_vexpand(False)
        apply.connect("clicked", self._apply_filament, choice)

        box.pack_start(section_label("Material"), False, False, 0)
        box.pack_start(mat_grid, False, False, 0)
        box.pack_start(section_label("Colour"), False, False, 0)
        box.pack_start(color_grid, True, True, 0)
        box.pack_start(apply, False, False, 0)
        self._mark(mat_buttons, choice["material"])
        self._mark(color_buttons, (choice["color"] or "").upper())
        self._show(box, "colour")

    @staticmethod
    def _mark(buttons, chosen):
        for value, button in buttons.items():
            ctx = button.get_style_context()
            if value == chosen:
                ctx.add_class("button_active")
            else:
                ctx.remove_class("button_active")

    def _pick(self, widget, choice, field, value, buttons):
        choice[field] = value
        self._mark(buttons, value)

    def _apply_filament(self, widget, choice):
        self._run(
            widget, "filament", material=choice["material"] or "", color=choice["color"] or ""
        )
        self._show_main()
