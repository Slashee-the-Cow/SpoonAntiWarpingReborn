"""Contains helpful functions I use across different plugins"""
# slasheetools
# - log():
#       A wrapper function arount UM.Logger that allows debug level messages
#       to be removed by changing DEBUG_LOG_MODE.
# - log_debug():
#       A wrapper function around log() that forces debug mode to be on.
#       The idea is that you import it as log for debugging but switch
#       to regular log for release versions.
#------------
# v1: log() and log_debug() implementations including "dd" for debug that should show up anyway.

from UM.Logger import Logger

DEBUG_LOG_MODE = False

def log(level: str, message: str, debug: bool = DEBUG_LOG_MODE) -> None:
    """Wrapper function for logging messages using Cura's Logger,
    but with debug mode so as not to spam you."""
    if level == "d" and debug:
        Logger.log("d", message)
    elif level == "dd":
        Logger.log("d", message)
    elif level == "i":
        Logger.log("i", message)
    elif level == "w":
        Logger.log("w", message)
    elif level == "e":
        Logger.log("e", message)
    elif debug:
        Logger.log("w", f"Invalid log level: {level} for message {message}")

def log_debug(level: str, message: str) -> None:
    """Wrapper function for logging messages which ensures debug level messages will be logged"""
    log(level, message, True)
