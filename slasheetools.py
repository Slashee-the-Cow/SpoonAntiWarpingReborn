"""Contains helpful functions I use across different plugins"""
# slasheetools
# - log(): A wrapper function arount UM.Logger that allows debug level messages
#          to be removed from release versions by just changing DEBUG_LOG_MODE
#------------
# v1: log() implementation including "dd" for debug that should show up anyway

from UM.Logger import Logger

DEBUG_LOG_MODE = False

def log(level: str, message: str) -> None:
    """Wrapper function for logging messages using Cura's Logger, but with debug mode so as not to spam you."""
    if level == "d" and DEBUG_LOG_MODE:
        Logger.log("d", message)
    elif level == "dd":
        Logger.log("d", message)
    elif level == "i":
        Logger.log("i", message)
    elif level == "w":
        Logger.log("w", message)
    elif level == "e":
        Logger.log("e", message)
    elif DEBUG_LOG_MODE:
        Logger.log("w", f"Invalid log level: {level} for message {message}")
