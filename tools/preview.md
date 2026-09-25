# Local UI preview

Render the real `panels/indx.py` with KlipperScreen's GTK widgets, icons and
theme, using offline data from `tools/preview-state.json`. No printer or
Spoolman server is needed. Actions print their method and parameters to the
terminal; they do not execute macros or change the fixture. Tool selection,
spool search and colour/material selection work in the interactive window.

On Windows, use Ubuntu under WSL (WSLg for interactive windows). Install the
rendering dependencies once inside Ubuntu:

```bash
sudo apt-get update
sudo apt-get install python3-gi python3-gi-cairo python3-jinja2 gir1.2-gtk-3.0 xvfb
```

Run these commands from the repository root in PowerShell:

```powershell
./tools/preview.ps1                         # screenshot: preview/main-ready.png
./tools/preview.ps1 -View spool
./tools/preview.ps1 -View colour
./tools/preview.ps1 -State printing
./tools/preview.ps1 -Interactive            # clickable GTK window
./tools/preview.ps1 -Tools 4 -Selected 2 -NoSpoolman
./tools/preview.ps1 -View home              # 800×480 home screen, local INDX SVG
./tools/preview.ps1 -View home -Theme material-light
```

The launcher defaults to the adjacent `../Screen Apps/KlipperScreen` checkout;
use `-KlipperScreen 'C:/path/to/KlipperScreen'` for another checkout. It also
accepts `-Width`, `-Height` and `-Theme`. Edit the fixture JSON for different
materials, spool names, weights and mounted tools. Rerun after editing the
panel; no deployment is involved. Screenshots are ignored by Git.

On Linux, run `GDK_BACKEND=x11 xvfb-run -a python3 tools/preview.py
--klipperscreen /path/to/KlipperScreen` (on one line), or omit `xvfb-run` and
add `--interactive` on a graphical desktop. `--fixture` accepts custom JSON.

The INDX content uses production code; the surrounding navigation/title bar
is a minimal preview shell. GTK, fonts, theme and checkout version can differ
from the printer. The target size defaults to 800×480; if the panel's minimum
size exceeds it, the screenshot uses the actual size and reports a warning
instead of silently scaling the UI. Macro execution, printer updates and the on-screen
keyboard still need integration testing on the printer.

## Home-screen icon preview

`-View home` uses the checkout's real `main_menu` panel, default menu entries,
temperature graph, button sizes and theme, plus this add-on's INDX menu entry.
It reads the SVG straight from this repository; no installation or changes to
the KlipperScreen checkout are needed. Rerun after editing the SVG.

Outputs are `preview/home-z-bolt.png` and `preview/home-material-light.png`,
so both themes can be compared. The light theme loads `icons/indx-light.svg`;
other themes load `icons/indx.svg`, matching the installer.

Use `-Width 1024 -Height 600` for another display size, or `-Interactive` to
open the window. Home-screen controls only log an offline message. The
temperature values are mock data, and the navigation/title bar is the same
minimal preview shell used by the other views. A printer with custom menu
entries, fonts or sensors can look different. `-Tools`, `-Selected`, `-State`
and `-NoSpoolman` apply to the INDX views, not the home-screen fixture.

On Linux, add `--view home --theme material-light` to the Python command above.
