# Copyright (c) 2023 5@xes
# Based on the TabPlus plugin  and licensed under LGPLv3 or higher.

from . import SpoonAntiWarpingReborn

from UM.i18n import i18nCatalog
i18n_catalog = i18nCatalog("spoonawreborn")

def getMetaData():
    _qml_file="qml/spoonawreborn.qml"

    return {
        "tool": {
            "name": i18n_catalog.i18nc("@label", "Spoon Anti-Warping Reborn"),
            "description": i18n_catalog.i18nc("@info:tooltip", "Add spoons to help prevent warping."),
            "icon": "tool_icon.svg",
            "tool_panel": _qml_file,
            "weight": 11
        }
    }

def register(app):
    return { "tool": SpoonAntiWarpingReborn.SpoonAntiWarpingReborn() }
