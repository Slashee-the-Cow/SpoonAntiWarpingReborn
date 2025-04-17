"""Contains helpful functions I use across different plugins"""
# slasheetools
# - log():
#       A wrapper function arount UM.Logger that allows debug level messages
#       to be removed by changing DEBUG_LOG_MODE.
# - log_debug():
#       A wrapper function around log() that forces debug mode to be on.
#       The idea is that you import it as log for debugging but switch
#       to regular log for release versions.
# - validate_int():
#       Tests a str value to make sure it casts to an int fine and optionally
#       constrain it to upper or lower bounds.
#------------
# v1: log() and log_debug() implementations including "dd" for debug that should show up anyway.

import math

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

def validate_int(value: str, minimum: int | None = None, maximum: int | None = None,
                clamp: bool = False, default: int | None = None) -> int | None:
    """Safely casts a str to an int and optionally keeps it within bounds"""
    try:
        int_value = int(value)
    except ValueError:
        log("e", "validateInt got something which won't cast to an int.")
        return default

    if minimum is not None and int_value < minimum:
        return minimum if clamp else default

    if maximum is not None and int_value > maximum:
        return maximum if clamp else default

    return int_value

def validate_float(value: str, minimum: float = -math.inf, maximum: float = math.inf,
                clamp: bool = False, default: float | None = None) -> float | None:
    """Safely casts a str to a float and optionally keeps it within bounds"""
    try:
        float_value = float(value)
    except ValueError:
        log("e", "validateFloat got something which won't cast to a float.")
        return default

    if float_value < minimum:
        return minimum if clamp else default

    if float_value > maximum:
        return maximum if clamp else default

    return float_value
