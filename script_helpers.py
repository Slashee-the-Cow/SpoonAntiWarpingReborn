#--------------------------------------------------------------------------------------------------
# Spoon Anti-Warping Reborn by Slashee the Cow
# Copyright Slashee the Cow 2025-
#
# The getValue and putValue functions are taken from Cura's PostProcessingPlugin.
# https://github.com/Ultimaker/Cura/blob/5.10.0/plugins/PostProcessingPlugin/Script.py
# Copyright (c) 2018 Ultimaker B.V.
# PostProcessingPlugin is released under the terms of the LGPLv3 or higher.
#--------------------------------------------------------------------------------------------------
from typing import Any
import re

from .slasheetools import log as log

def get_value(line: str, key: str, default = None) -> Any:
    """Convenience function that finds the value in a line of g-code.

    When requesting key = x from line "G1 X100" the value 100 is returned.
    """
    if not key in line or (';' in line and line.find(key) > line.find(';')):
        return default
    sub_part = line[line.find(key) + 1:]
    m = re.search(r'^-?[0-9]+\.?[0-9]*', sub_part)
    if m is None:
        return default
    try:
        return int(m.group(0))
    except ValueError: #Not an integer.
        try:
            return float(m.group(0))
        except ValueError: #Not a number at all.
            return default


def put_value(line: str = "", **kwargs) -> str:
    """Convenience function to produce a line of g-code.

    You can put in an original g-code line and it'll re-use all the values
    in that line.
    All other keyword parameters are put in the result in g-code's format.
    For instance, if you put ``G=1`` in the parameters, it will output
    ``G1``. If you put ``G=1, X=100`` in the parameters, it will output
    ``G1 X100``. The parameters will be added in order G M T S F X Y Z E.
    Any other parameters will be added in arbitrary order.

    :param line: The original g-code line that must be modified. If not
        provided, an entirely new g-code line will be produced.
    :return: A line of g-code with the desired parameters filled in.
    """
    # Strip the comment.
    if ";" in line:
        comment = line[line.find(";"):]
        line = line[:line.find(";")]
    else:
        comment = ""

    # Parse the original g-code line and add them to kwargs.
    for part in line.split(" "):
        if part == "":
            continue
        parameter = part[0]
        if parameter not in kwargs:
            value = part[1:]
            kwargs[parameter] = value

    # Start writing the new g-code line.
    line_parts = list()
    # First add these parameters in order
    for parameter in ["G", "M", "T", "S", "F", "X", "Y", "Z", "E"]:
        if parameter in kwargs:
            value = kwargs.pop(parameter)  # get the corresponding value and remove the parameter from kwargs
            line_parts.append(parameter + str(value))
    # Then add the rest of the parameters
    for parameter, value in kwargs.items():
        line_parts.append(parameter + str(value))

    # If there was a comment, put it at the end.
    if comment != "":
        line_parts.append(comment)

    # Add spaces and return the new line
    return " ".join(line_parts)

def is_z_hop_line(line: str, z_hop_speed: float = None) -> bool:
    """Returns if a line is (likely) a Z hop (up or down) based on Cura's usual pattern"""
    return ("G1" in line
            and ("F" if z_hop_speed is None else f"F{str(int(z_hop_speed)) if z_hop_speed % 1 == 0.0 else str(z_hop_speed)}") in line
            and "Z" in line
            and "E" not in line
            and "X" not in line
            and "Y" not in line)

def is_retract_line(line: str, retract_speed: float = None) -> bool:
    """Returns if a line is (likely) a retraction (or prime) based on Cura's usual pattern"""
    return ("G1" in line
            and ("F" if retract_speed is None else f"F{str(int(retract_speed)) if retract_speed % 1 == 0.0 else str(retract_speed)}") in line
            and "E" in line
            and "X" not in line
            and "Y" not in line
            and "Z" not in line)

def section_ends_retracted(section: list[str]) -> bool:
    """Detects if the last position on the E axis is lower than the
    previous one, indicating a retraction.
    """
    last_e = None
    for line in reversed(section):
        if get_value(line, "E") is not None:
            if last_e is None:
                last_e = get_value(line, "E")
            else:
                if last_e < get_value(line, "E"):
                    return True
                last_e = get_value(line, "E")
    return False

def section_ends_z_hopped(section: list[str]) -> bool:
    """Detects if the last position on the Z axis is higher than the
    previous one, indicating a Z hop.
    """
    last_z = None
    for line in reversed(section):
        if get_value(line, "Z") is not None:
            if last_z is None:
                last_z = get_value(line, "Z")
            else:
                if last_z > get_value(line, "Z"):
                    return True
                last_z = get_value(line, "Z")
    return False

def is_extrusion_move(line: str):
    """Checks to see if a line is an extrusion move
    (Starts with G1, G2 or G3, contains E property as well as X and/or Y)
    """
    return(line.startswith(("G1", "G2", "G3"))
           and "E" in line
           and ("X" in line or "Y" in line))

def get_last_xy_coords(section: list[str]) -> tuple[float, float] | None:
    last_x = None
    last_y = None
    for line in reversed(section):
        if line.startswith(("G0", "G1", "G2", "G3", ";G0", ";G1", ";G2", ";G3")):
            line = line.lstrip(";")
            if last_x is None:
                if get_value(line, "X") is not None:
                    last_x = get_value(line, "X")
            if last_y is None:
                if get_value(line, "Y") is not None:
                    last_y = get_value(line, "Y")
            if last_x is not None and last_y is not None:
                return last_x, last_y
    return None

def get_last_xyz_coords(section: list[str]) -> tuple[float, float, float] | None:
    
    last_x: float = None
    last_y: float = None
    last_z: float = None
    for line in reversed(section):
        if line.startswith(("G0", "G1", "G2", "G3", ";G0", ";G1", ";G2", ";G3")):
            line = line.lstrip(";")
            if last_x is None and "X" in line:
                last_x = get_value(line, "X")
            if last_y is None and "Y" in line:
                last_y = get_value(line, "Y")
            if last_z is None and "Z" in line:
                last_z = get_value(line, "Z")
        if last_x is not None and last_y is not None and last_z is not None:
            return last_x, last_y, last_z
    return None

def get_last_z(section: list[str]) -> float | None:
    for line in reversed(section):
        if get_value(line, "Z") is not None:
            return get_value(line, "Z")
    return None

def get_start_g0_z(section: list[str]) -> float | None:
    for line in section:
        if line.startswith(("G0", ";G0")):
            if "Z" in line:
                return get_value(line, "Z")
        elif line.startswith(("G1", "G2", "G3", ";G1", ";G2", ";G3")):
            return None
    return None


def get_start_g0_xy_coords(section: list[str]) -> tuple[float, float] | None:
    """Get X/Y coordinates from initial travel moves in a section.
    Bails if it encounters a G1 (or an extruwsion G2/G3) before having valid X and Y coordinates
    """
    first_x = None
    first_y = None
    for line in section:
        if ("G1" or ";G1") in line and ("X" in line or "Y" in line):
            if first_x is None or first_y is None:
                return None
        elif line.startswith(("G2", "G3", ";G2", ";G3")) and "E" in line:
            if first_x is None or first_y is None:
                return None
        elif ("G0" or ";G0") in line:
            line = line.lstrip(":")
            if first_x is None:
                first_x = get_value(line, "X")
            if first_y is None:
                first_y = get_value(line, "Y")
        if first_x is not None and first_y is not None:
            break
    if first_x is None or first_y is None:
        return None
    return first_x, first_y

def get_last_e_value(section: list[str]) -> float | None:
    for line in reversed(section):
        if get_value(line, "E") is not None:
            return get_value(line, "E")
    return None

def get_last_e_non_retract(section: list[str], retract_speed: float = None, prime_speed: float = None) -> float | None:
    for line in reversed(section):
        if get_value(line, "E") is not None \
            and not is_retract_line(line, retract_speed) \
            and not is_retract_line(line, prime_speed):
            return get_value(line, "E")
    return None

def is_another_nonmesh(section: list[str]) -> bool:
    return any("NONMESH" in line for line in section)

def make_travel(x: float, y: float, speed: float, z: float = None,
                retraction: bool = False, e: float = None, retract_distance: float = None, retract_speed: float = None, prime_speed: float = None,
                z_hop: bool = False, z_hop_height: float = None, z_hop_speed: float = None,
                has_start_move: bool = False, has_start_zdown: bool = False, has_start_prime: bool = False, starts_retracted: bool = False, relative_extrusion: bool = False) -> str:
    log("d", f"make_travel run with:\n"
          f"x: {x}, y: {y}, speed: {speed}, z: {z}, retraction: {retraction}, e: {e}, retract_distance: {retract_distance}, retract_speed: {retract_speed}, prime_speed: {prime_speed}\n"
          f"z_hop: {z_hop}, z_hop_height: {z_hop_height}, z_hop_speed: {z_hop_speed}\n"
          f"has_start_move: {has_start_move}, has_start_zdown: {has_start_zdown}, has_start_prime: {has_start_prime}, starts_retracted: {starts_retracted}, relative_extrusion: {relative_extrusion}")
    if relative_extrusion:
        e = 0.0
    output: str = "; SpoonOrder added travel\n"
    if e is not None and not relative_extrusion:
        # Reset extruder value
        output += f"G92 E{round(e,5) if not starts_retracted else round(e-retract_distance,5)}\n"
    if retraction and not starts_retracted:
        # Retract filament
        output += f"G1 F{str(int(retract_speed))} E{round(e - retract_distance, 5)}\n"
    if z_hop:
        # Hop up
        output += f"G1 F{str(int(z_hop_speed))} Z{round(z + z_hop_height,2)}\n"
    # Main movement
    if not has_start_move: output += f"G0 F{str(int(speed))} X{x} Y{y}\n"
    if z_hop and not has_start_zdown:
        # Hop down
        output += f"G1 F{str(int(z_hop_speed))} Z{round(z,2)}\n"
    if retraction and not has_start_prime:
        # Prime filament
        output += f"G1 F{str(int(prime_speed))} E{round(e,5) if not relative_extrusion else retract_distance}"
    log("d", f"make_travel output:\n{output}")
    return output
