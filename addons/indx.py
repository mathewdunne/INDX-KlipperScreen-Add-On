# INDX KlipperScreen add-on: live INDX state for panels/indx.py
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
# KlipperScreen subscribes to a fixed object list. The INDX state lives in
# save_variables and gcode_macro TOOL_POSITIONS, so add them to that
# subscription. The initial values already arrive with KlipperScreen's
# query of every object at connect; only the updates were missing.
#
# Also opens the spool (or colour) picker when a load finishes:
# _LOAD_FILAMENT_FEED ends with "action:indx_loaded <tool>". KlipperScreen
# never passes action lines to panels, and ks_show does nothing when the
# panel is already on screen, so the action is caught here.

import logging

OBJECTS = {
    "save_variables": ["variables"],
    "gcode_macro TOOL_POSITIONS": ["tool_count"],
}


def init(screen):
    original = screen.ws_subscribe

    def ws_subscribe():
        api = screen._ws.api
        subscribe = api.object_subscription

        def object_subscription(updates):
            updates.setdefault("objects", {}).update(OBJECTS)
            return subscribe(updates)

        # Only for the duration of this call, so nothing else sees the patch
        api.object_subscription = object_subscription
        try:
            return original()
        finally:
            del api.object_subscription

    screen.ws_subscribe = ws_subscribe
    logging.info("INDX: save_variables added to the subscription")

    process_action = screen.process_action

    def indx_process_action(action):
        if not action.startswith("indx_loaded"):
            return process_action(action)
        try:
            tool = int(action.split()[1])
        except (IndexError, ValueError):
            logging.warning(f"INDX: bad action {action!r}")
            return
        if screen._cur_panels and screen._cur_panels[-1] == "indx":
            screen.panels["indx"].pick_filament(tool)
        else:
            screen.show_panel("indx", extra=tool)

    screen.process_action = indx_process_action
