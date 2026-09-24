# INDX KlipperScreen add-on: live INDX state for panels/indx.py
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
# KlipperScreen subscribes to a fixed object list. The INDX state lives in
# save_variables and gcode_macro TOOL_POSITIONS, so add them to that
# subscription. The initial values already arrive with KlipperScreen's
# query of every object at connect; only the updates were missing.

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
