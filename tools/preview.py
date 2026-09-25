#!/usr/bin/env python3
"""Render the real INDX GTK panel with offline fixtures (no printer connection)."""
import argparse
import builtins
import configparser
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--klipperscreen", type=Path,
                        default=ROOT.parent / "Screen Apps" / "KlipperScreen")
    parser.add_argument("--fixture", type=Path, default=ROOT / "tools" / "preview-state.json")
    parser.add_argument("--output", type=Path, default=ROOT / "preview" / "main.png")
    parser.add_argument("--view", choices=("main", "spool", "colour"), default="main")
    parser.add_argument("--state", choices=("ready", "printing", "paused"), default="ready")
    parser.add_argument("--tools", type=int, choices=range(1, 9), default=8)
    parser.add_argument("--selected", type=int, default=0)
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--theme", default="z-bolt")
    parser.add_argument("--no-spoolman", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.selected < args.tools:
        parser.error("--selected must be inside the tool count")
    if not (args.klipperscreen / "ks_includes" / "KlippyGtk.py").is_file():
        parser.error("pass --klipperscreen pointing to a KlipperScreen checkout")
    sys.path.insert(0, str(args.klipperscreen.resolve()))
    builtins._ = lambda text: text

    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk
    from ks_includes.KlippyGtk import KlippyGtk

    data = json.loads(args.fixture.read_text(encoding="utf-8"))
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.add_section("main")
    config = SimpleNamespace(get_config=lambda: cfg, get_main_config=lambda: cfg["main"])

    class Printer:
        state = args.state
        spoolman = not args.no_spoolman

        def get_stat(self, section, key):
            if section == "gcode_macro TOOL_POSITIONS":
                return args.tools
            return data.get(section, {}).get(key)

    def noop(*unused):
        pass

    title = Gtk.Label(label="INDX — offline preview", hexpand=True)
    screen = SimpleNamespace(
        width=args.width, height=args.height, vertical_mode=args.height > args.width,
        theme=args.theme, _config=config, files=None, printer=Printer(), wayland=False,
        screensaver=SimpleNamespace(reset_timeout=noop),
        lock_screen=SimpleNamespace(reset_timeout=noop),
        base_panel=SimpleNamespace(set_title=title.set_text),
        remove_keyboard=noop, show_keyboard=noop, show_popup_message=print,
        spoolman_api=SimpleNamespace(load_all_spools=lambda callback, **kw: callback(data["spools"])),
    )

    def send_method(method, params, callback, widget):
        # Deliberately no networking or macro emulation. Real callbacks still run.
        print(f"OFFLINE action: {method} {json.dumps(params)}", flush=True)
        callback({}, method, params, widget)

    screen._ws = SimpleNamespace(send_method=send_method)
    screen.gtk = KlippyGtk(screen)
    css = (args.klipperscreen / "styles" / "base.css").read_text()
    theme_css = args.klipperscreen / "styles" / args.theme / "style.css"
    if theme_css.is_file():
        css += "\n" + theme_css.read_text()
    css = css.replace("KS_FONT_SIZE", str(screen.gtk.font_size))
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode())
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    spec = importlib.util.spec_from_file_location("indx_preview_panel", ROOT / "panels" / "indx.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    panel = module.Panel(screen, "INDX")
    panel.selected = args.selected
    panel.activate()

    # Reserve the same action/title bar dimensions as KlippyGtk. The surrounding
    # shell is minimal; only the INDX content is the production panel.
    window = Gtk.Window(title="INDX offline preview")
    window.set_default_size(args.width, args.height)
    window.set_resizable(False)
    window.connect("destroy", Gtk.main_quit)
    frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if screen.vertical_mode
                    else Gtk.Orientation.HORIZONTAL)
    nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL if screen.vertical_mode
                  else Gtk.Orientation.VERTICAL, homogeneous=True)
    nav.set_hexpand(screen.vertical_mode)
    nav.set_vexpand(not screen.vertical_mode)
    nav.set_size_request(screen.gtk.action_bar_width, int(screen.gtk.action_bar_height))
    for icon, callback in (("back", lambda *a: panel.back()),
                           ("main", lambda *a: panel._show_main())):
        button = screen.gtk.Button(icon)
        button.connect("clicked", callback)
        nav.add(button)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
    title.set_size_request(-1, int(screen.gtk.titlebar_height))
    body.pack_start(title, False, False, 0)
    body.pack_start(panel.content, True, True, 0)
    frame.pack_start(nav, False, False, 0)
    frame.pack_start(body, True, True, 0)
    window.add(frame)
    if args.view == "spool":
        panel._show_spools(None)
    elif args.view == "colour":
        panel._show_filament(None)
    window.show_all()

    result = {"failed": False}

    def capture():
        width, height = window.get_size()
        if (width, height) != (args.width, args.height):
            print(f"WARNING: GTK minimum layout expanded to {width}x{height}; "
                  f"requested {args.width}x{args.height}", file=sys.stderr)
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            pixbuf = Gdk.pixbuf_get_from_window(window.get_window(), 0, 0, width, height)
            pixbuf.savev(str(args.output), "png", [], [])
            print(f"Saved {args.output} ({width}x{height})", flush=True)
        except Exception as exc:
            result["failed"] = True
            print(f"Capture failed: {exc}", file=sys.stderr)
        if not args.interactive:
            Gtk.main_quit()
        return False

    GLib.timeout_add(700, capture)
    Gtk.main()
    return int(result["failed"])


if __name__ == "__main__":
    sys.exit(main())
