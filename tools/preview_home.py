"""Offline fixtures for the real KlipperScreen home panel."""
import configparser
import json
from types import SimpleNamespace

from jinja2 import Environment
from gi.repository import Gdk, Gtk
from panels.main_menu import Panel as HomePanel


def build_home(screen, checkout, root, theme):
    class Printer:
        state = "ready"
        extrudercount = 1
        config = {"extruder": {"max_temp": 300}, "heater_bed": {"max_temp": 120}}
        tempstore = {
            "extruder": {"temperatures": [24.5] * 300, "targets": [0] * 300},
            "heater_bed": {"temperatures": [23.8] * 300, "targets": [0] * 300},
        }

        def get_printer_status_data(self):
            return {"printer": {"temperature_devices": {"count": 2}, "extruders": {"count": 1}}}

        def get_temp_devices(self):
            return list(self.config)

        def get_config_section(self, section):
            return self.config[section]

        def get_stat(self, section, key):
            return {"temperature": self.tempstore[section]["temperatures"][-1],
                    "target": 0, "power": 0}.get(key)

        def device_has_target(self, device):
            return True

        def get_tempstore_size(self):
            return 300

        def get_temp_store(self, device, kind, count=0):
            return self.tempstore[device].get(kind, [])[-count:]

    def offline(*args, **kwargs):
        print("OFFLINE home control (preview only)", flush=True)

    class PreviewHome(HomePanel):
        hidden_sensors = []
        show_numpad = staticmethod(offline)
        toggle_visibility = staticmethod(offline)

        def _show_main(self):
            pass  # Already home; used by the preview shell's Home button.

    screen.printer = Printer()
    screen.state = SimpleNamespace(printer_name="Preview", connected=True)
    screen.env = Environment()
    screen.env.globals["gettext"] = lambda text: text
    screen.show_panel = offline
    screen._go_to_submenu = offline
    options = json.loads((checkout / "styles/base.conf").read_text())
    theme_options = checkout / "styles" / theme / "style.conf"
    if theme_options.is_file():
        options.update(json.loads(theme_options.read_text()))
    screen.gtk.color_list = options["graph_colors"]
    for colors in screen.gtk.color_list.values():
        if "base" in colors:
            colors["rgb"] = [int(colors["base"][i:i + 2], 16) for i in (0, 2, 4)]

    # Redirect just this icon to the working tree. No install or edits to the
    # neighbouring KlipperScreen checkout are needed to preview SVG changes.
    load_icon = screen.gtk.PixbufFromIcon
    icon = root / "icons" / ("indx-light.svg" if theme == "material-light" else "indx.svg")

    def preview_icon(filename, width=None, height=None):
        if filename == "indx":
            width = screen.gtk.img_width if width is None else width
            height = screen.gtk.img_height if height is None else height
            return screen.gtk.PixbufFromFile(str(icon), width, height)
        return load_icon(filename, width, height)

    screen.gtk.PixbufFromIcon = preview_icon
    menu = configparser.ConfigParser(interpolation=None)
    menu.read([checkout / "config/main_menu.conf", root / "klipperscreen/indx_menu.conf"])
    items = []
    for section in menu.sections():
        parts = section.split()
        if len(parts) != 3 or parts[:2] != ["menu", "__main"]:
            continue
        values = {"name": "", "icon": None, "style": None, "panel": None,
                  "method": None, "params": False, "confirm": None, "enable": "True"}
        values.update(dict(menu[section]))
        items.append({parts[2]: values})
    panel = PreviewHome(screen, "Home", items)
    # screen.py normally adds the matching graph colours to the heater labels.
    graph_css = Gtk.CssProvider()
    rules = []
    for device in panel.devices:
        rgb = panel.labels["da"].store[device]["temperatures"]["rgb"]
        color = "#" + "".join(f"{round(channel * 255):02x}" for channel in rgb)
        rules.append(f".{panel.devices[device]['class']} {{ border-left-color: {color}; }}")
    graph_css.load_from_data("\n".join(rules).encode())
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), graph_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
    )
    panel.activate()
    panel.process_update("notify_status_update", {device: {} for device in screen.printer.config})
    graph = panel.labels["da"]
    graph.disconnect_by_func(graph.event_cb)
    graph.connect("button_release_event", offline)
    return panel
