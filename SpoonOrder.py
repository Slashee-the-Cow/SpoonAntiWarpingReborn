# Spoon Anti-Warping Reborn by Slashee the Cow
# Copyright Slashee the Cow 2025-
#
# Spoon Ordering script
# Designed to hack away at gcode to make all spoons print before main meshes
# "Hack" is a deliberate choice of words there, this ain't pretty.

from dataclasses import dataclass, field
import math

from cura.CuraApplication import CuraApplication

#from UM.Application import Application

from .script_helpers import *
from .slasheetools import log as log

@dataclass
class GcodeSection:
    """Holds all the info (and gcode) for each "section"
    (part of a model on each layer)."""
    lines: list[str] = field(default_factory = list)
    name: str = ""

    layer_index: int = 0
    start_line_index: int = 0
    first_section: bool = False
    last_section: bool = False

    start_x: float = 0.0
    start_y: float = 0.0
    start_z: float = 0.0

    start_e: float = 0.0
    end_e: float = 0.0

    start_has_move: bool = False
    start_travel_moves: int = 0
    start_has_zdown: bool = False
    start_has_prime: bool = False

    starts_retracted: bool = False
    ends_retracted: bool = False
    starts_hopped: bool = False
    ends_hopped: bool = False
    
class SpoonOrder:
    LINE_LAYER_START = ";LAYER:"
    LINE_MESH_START = ";MESH:"

    # The following lines are saved until the end of the layer (where you usually want them to take effect).
    END_CONTROL_LINES = ("M104", "M109", "M140", "M190", "M141", "M191")

    def __init__(self, target_name: str = "SpoonTab", spoons_first: bool = True) -> None:
        # Initialise all my variables in advance so that my linter doesn't yell at me for using variables which may not have been initialised.
        self.retract_enabled: bool = False
        self.retract_length: float = 0.0
        self.retract_speed: float = 0.0
        self.retract_prime_speed: float = 0.0
        
        self.hop_enabled: bool = False
        self.hop_height: float = 0.0
        self.hop_speed: float = 0.0

        self.feedrate_z: float = 0.0
        self.travel_speed: float = 0.0

        self.initial_layer_height: float = 0.0
        self.relative_extrusion: bool = False
        
        self.target_name: str = target_name

        self.spoons_first: bool = spoons_first

        self._global_stack = None
        self._extruder_stack = None

    def getStackProperty(self, key: str, key_property: str = "value"):
        """For some reason the extruder was giving me actual, in use values when the global stack wasn't.
        Other than those they're the same. Global stack remains as a fallback."""
        extruder_value = self._extruder_stack.getProperty(key, key_property)
        global_value = self._global_stack.getProperty(key, key_property)
        log("d", f"For key {key}, extruder value = {extruder_value}, global value = {global_value}")
        if extruder_value is not None:
            return extruder_value
        else:
            return global_value


    def execute(self, data: list[str]) -> list[str]:  # I know it doesn't need the same signature as a post. But it doesn't hurt.
        """Run the not-quite-a-post-processing-script script!"""

        # For some reason instantiating these here works when doing it in __init__() doesn't.
        self._global_stack = CuraApplication.getInstance().getGlobalContainerStack()
        self._extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()[0]
        log("d", "SpoonOrder.execute() running")

        # Get all the variables we're going to care about
        self.retract_enabled = bool(self.getStackProperty("retraction_enable", "value"))
        if self.retract_enabled:
            self.retract_length = float(self.getStackProperty("retraction_amount", "value"))
            self.retract_speed = float(self.getStackProperty("retraction_speed", "value")) * 60
            self.retract_prime_speed = float(self.getStackProperty("retraction_prime_speed", "value")) * 60
    
        self.hop_enabled = bool(self.getStackProperty("retraction_hop_enabled", "value"))
        if self.hop_enabled:
            self.hop_height = float(self.getStackProperty("retraction_hop", "value"))
            self.hop_speed = float(self.getStackProperty("speed_z_hop", "value")) * 60
        else:
            self.feedrate_z = float(self.getStackProperty("machine_max_feedrate_z", "value")) * 60
        self.travel_speed = float(self.getStackProperty("speed_travel", "value")) * 60
        self.relative_extrusion = bool(self.getStackProperty("relative_extrusion", "value"))

        self.initial_layer_height = float(self.getStackProperty("layer_height_0", "value"))

        # whole_gcode: str = ("\n".join(data)).splitlines()

        layer_process_markers: list[str] = [";LAYER:", self.target_name]  # All of these need to be present for it process a layer
        section_delimiters: tuple[str] = (";LAYER:", ";MESH:")
        start_line = ";LAYER:"
        end_line = ";TIME_"

        previous_layer_lines: list[str] = None
        previous_layer_lines_unaltered: list[str] = None
        spoon_key = self.target_name
        first_layer_processed: bool = False
        
        for layer_index, layer in enumerate(data):
            # Some basic checks to see if this is something we want to bother with
            if not all(marker in layer for marker in layer_process_markers):
                previous_layer_lines = None
                continue
            
            # Reset all the gcode sections
            layer_start_lines: GcodeSection = GcodeSection()
            spoon_lines: list[GcodeSection] = []
            non_spoon_lines: list[GcodeSection] = []
            layer_end_lines: GcodeSection = GcodeSection
            control_lines: list[str] = []

            current_section: GcodeSection = None

            layer_z: float = math.inf  # Starts at infinity because it needs to be whittled down
            travelled_first_z: bool = True

            done_first_section: bool = False
            in_last_section: bool = False
            layer_lines = layer.splitlines()
            for line in layer_lines:
                if line.strip().startswith(";LAYER:"):
                    if int(line.strip().split(":")[1]) < 0:
                        previous_layer_lines = None
                        continue
                    else:
                        break
            if previous_layer_lines is None:
                previous_layer_lines = data[layer_index - 1].splitlines()  # Yes I'm assuming this won't run on the first layer, because it isn't startup gcode
            if previous_layer_lines_unaltered is None:
                previous_layer_lines_unaltered = previous_layer_lines
            
            for line_index, line in enumerate(layer_lines):
                if line.startswith(section_delimiters) or line.startswith(end_line):
                    if current_section is not None:
                        # Add last line if it's the last line
                        if line.startswith(end_line):
                            current_section.lines.append(line)
                            current_section.last_section = True
                            in_last_section = False
                        elif line.startswith(start_line):
                            current_section.first_section = True

                        # Check to see if it retracts at the end of the startup gcode
                        if ";LAYER:0" in layer and self.retract_enabled and current_section.first_section:
                            for start_retract in reversed(data[layer_index - 1].splitlines()):
                                if start_retract.startswith("G1"):
                                    if is_retract_line(start_retract):
                                        current_section.starts_retracted = True
                                        log("d", ";LAYER:0 just got retract line from previous layer")
                                        break
                                    else:
                                        break
                        
                        # Filter out Z-hops and retracts at end of section
                        section_end_index: int = -1
                        for final_index, final_move in enumerate(current_section.lines):
                            if is_extrusion_move(final_move):
                                section_end_index = final_index
                            
                        filtered_section_lines: list[str] = []
                        for filter_index, filter_line in enumerate(current_section.lines):
                            if filter_index < section_end_index:
                                filtered_section_lines.append(filter_line)
                                continue
                            if self.hop_enabled:
                                if is_z_hop_line(filter_line, self.hop_speed):
                                    continue
                            if self.retract_enabled:
                                if is_retract_line(filter_line, self.retract_speed) \
                                    or is_retract_line(filter_line, self.retract_prime_speed):
                                    continue
                            filtered_section_lines.append(filter_line)
                        current_section.lines = filtered_section_lines

                        # Check to see if it's doing its own travel, Z-hop and retraction
                        section_extrude_start_index = 0
                        for extrude_start_index, extrude_start_line in enumerate(current_section.lines):
                            if is_extrusion_move(extrude_start_line):
                                section_extrude_start_index = extrude_start_index
                                log("d", f"section_extrude_start_index for {current_section.name} on layer {layer_index} is {section_extrude_start_index}")
                                break
                            
                        section_start_travel_count = 0
                        # This isn't changing any lines, just examining what we've got.
                        for start_line in current_section.lines[:section_extrude_start_index]:
                            if ((start_line.startswith("G0") and ("X" in start_line or "Y" in start_line))  # Cura generates moves straight along the Z axis with X and Y coordinates anyway. Some disagree.
                                or (start_line.startswith(("G2", "G3")) and "E" not in start_line)):
                                section_start_travel_count += 1
                               
                                start_line_x = get_value(start_line, "X")
                                start_line_y = get_value(start_line, "Y")
                                if start_line_x:
                                    current_section.start_x = start_line_x
                                if start_line_y:
                                    current_section.start_y = start_line_y
                            elif start_line.startswith("G1") or (start_line.startswith(("G2", "G3")) and "E" in start_line):
                                if not current_section.start_has_zdown:
                                    current_section.start_has_zdown = is_z_hop_line(start_line, self.hop_speed)
                                if not current_section.start_has_prime:
                                    current_section.start_has_prime = is_retract_line(start_line, self.retract_prime_speed)
                        # Check for coords to see if it contains a move
                        if current_section.start_x and current_section.start_y:
                            current_section.start_has_move = True

                        # Remove any combing G0 moves there might be
                        current_section.start_travel_moves = section_start_travel_count
                        if current_section.start_travel_moves > 1:
                            new_start_lines: list[str] = []
                            travel_count = 0
                            for start_line in current_section.lines[:section_extrude_start_index]:
                                if ((start_line.startswith("G0") and ("X" in start_line or "Y" in start_line))
                                    or (start_line.startswith(("G1", "G2", "G3")) and "E" not in start_line)):
                                    travel_count += 1
                                    if travel_count == current_section.start_travel_moves:
                                        new_start_lines.append(start_line)
                                else:
                                    new_start_lines.append(start_line)
                            current_section.lines[:section_extrude_start_index] = new_start_lines
                                
                        # Capture a ";TYPE" line if one exists
                        if current_section.start_line_index > 0:
                            if layer_lines[current_section.start_line_index - 1].startswith(";TYPE:"):
                                current_section.lines.insert(0, layer_lines[current_section.start_line_index - 1])
                        # Get rid of a ";TYPE" line at the end we don't want
                            if current_section.lines[-1].startswith(";TYPE:"):
                                current_section.lines.pop()

                        # Comment out moves in last section; we only need the coordinates
                        if current_section.last_section:
                            if layer_index < (len(data) - 1) and self.target_name in data[layer_index + 1]:
                                new_last_section: list[str] = []
                                for last_section_line in current_section.lines:
                                    if last_section_line.startswith(("G0", "G1", "G2", "G3")):
                                        new_last_section.append(f";{last_section_line}")
                                    else:
                                        new_last_section.append(last_section_line)
                                current_section.lines = new_last_section

                        if layer_z != math.inf:
                            current_section.start_z = layer_z
                        if current_section.first_section and ";LAYER:0" in layer and not first_layer_processed:
                            # Only use initial layer height if this is the initial layer
                            first_layer_processed = True
                            layer_z = self.initial_layer_height
                            current_section.start_z = layer_z
                        elif (self.hop_enabled or (not first_layer_processed and current_section.first_section)) and (layer_z == math.inf or layer_z is None):
                            # We need to get the layer Z as the lowest Z value
                            log("d", "SpoonOrder getting Z value from lowest on layer")
                            for z_line in layer_lines:
                                if z_line.startswith(("G0", "G1", "G2", "G3", ";G0", ";G1", ";G2", ";G3")):
                                    if "Z" in z_line.lstrip(";"):
                                        new_z = get_value(z_line.lstrip(";"), "Z")
                                        if new_z is not None:
                                            layer_z = min(layer_z, new_z)
                            if layer_z != math.inf and layer_z is not None:
                                current_section.start_z = layer_z
                                log("d", f"SpoonOrder got Z value from lowest on layer: {layer_z}")
                        if layer_z == math.inf or layer_z is None:
                            layer_z = get_last_z(previous_layer_lines_unaltered)
                            current_section.start_z = layer_z if layer_z else 0.0

                        if not current_section.start_x or not current_section.start_y:
                            start_coords = get_start_g0_xy_coords(current_section.lines)
                            if start_coords is None and not current_section.first_section:
                                start_coords = get_last_xy_coords(layer_lines[:current_section.start_line_index])
                            if start_coords is None:
                                start_coords = get_last_xy_coords(previous_layer_lines)

                            if start_coords is not None:
                                try:
                                    current_section.start_x = start_coords[0]
                                    current_section.start_y = start_coords[1]
                                except Exception as e:
                                    log("e", f"SpoonOrder can't set current_section.start_x or start_y because {e}")
                            else:
                                # Use defaults which are probably far from what we want but should be fairly safe
                                current_section.start_x = 0.0
                                current_section.start_y = 0.0
                            #log("w", f"Just couldn't get starting coords for section starting layer {current_section.layer_index} line {current_section.start_line_index}")
                        if not travelled_first_z and self.hop_enabled:
                            current_section.lines.insert(1, f"G1 F{self.hop_speed if self.hop_enabled else self.feedrate_z} Z{layer_z}")
                            travelled_first_z = True
                        # Get starting E co-ord
                        if self.relative_extrusion:
                            current_section.start_e = 0.0
                        else:
                            if current_section.start_line_index > 0:
                                new_e = get_last_e_non_retract(layer_lines[:current_section.start_line_index], self.retract_speed, self.retract_prime_speed)
                                if new_e is not None:
                                    current_section.start_e = new_e
                            if not current_section.start_e:
                                try:
                                    current_section.start_e = get_last_e_non_retract(previous_layer_lines_unaltered, self.retract_speed, self.retract_prime_speed)
                                except Exception as e:
                                    log("e", f"Problem where Pylint gets current_section.start_e wrong: {e}")
                            if not current_section.start_e:
                                current_section.start_e = 0.0
                        
                        # Add it to the proper pile
                        if current_section.first_section:
                            layer_start_lines = current_section
                        elif current_section.last_section:
                            layer_end_lines = current_section
                        elif spoon_key in current_section.name:
                            spoon_lines.append(current_section)
                        else:
                            non_spoon_lines.append(current_section)
                        current_section = None

                    if current_section is None:
                        current_section = GcodeSection()
                    if not done_first_section:
                        current_section.name = line.strip(";")  # Almost certainly ";LAYER:x"
                        current_section.first_section = True
                        done_first_section = True
                    elif "NONMESH" in line \
                        and not in_last_section \
                        and line_index + 1 < len(layer_lines):
                        in_last_section = is_another_nonmesh(layer_lines[line_index + 1:])
                        if in_last_section:
                            current_section.name = "LAST_NONMESH"
                            current_section.last_section = True
                        else:
                            current_section.name = line
                    else:
                        current_section.name = line
                    current_section.start_line_index = line_index
                    current_section.layer_index = layer_index

                if line.startswith(self.END_CONTROL_LINES):
                    control_lines.append(line)
                elif current_section is not None:
                    current_section.lines.append(line)
            # Put together the jigsaw pieces of the layer
            new_layer: list[str] = []
            if layer_start_lines.lines:
                new_layer.append(layer_start_lines.lines[0])  # Start with ";LAYER" heading
                # First layer only gets a travel if it has any extrusion moves
                if any(is_extrusion_move(initial_layer_line) for initial_layer_line in layer_start_lines.lines):
                    new_layer.append(make_travel(layer_start_lines.start_x, layer_start_lines.start_y, self.travel_speed, layer_start_lines.start_z,
                                             self.retract_enabled, layer_start_lines.start_e, self.retract_length, self.retract_speed, self.retract_prime_speed,
                                             self.hop_enabled, self.hop_height, self.hop_speed,
                                             layer_start_lines.start_has_move, layer_start_lines.start_has_zdown, layer_start_lines.start_has_prime, layer_start_lines.starts_retracted, self.relative_extrusion))
                new_layer.extend(layer_start_lines.lines[1:])
            if self.spoons_first:
                for spoon in spoon_lines:
                    new_layer.append(make_travel(spoon.start_x, spoon.start_y, self.travel_speed, spoon.start_z,
                                                 self.retract_enabled, spoon.start_e, self.retract_length, self.retract_speed, self.retract_prime_speed,
                                                 self.hop_enabled, self.hop_height, self.hop_speed,
                                                 spoon.start_has_move, spoon.start_has_zdown, spoon.start_has_prime, spoon.starts_retracted, self.relative_extrusion))
                    new_layer.extend(spoon.lines)
            for non_spoon in non_spoon_lines:
                new_layer.append(make_travel(non_spoon.start_x, non_spoon.start_y, self.travel_speed, non_spoon.start_z,
                                                self.retract_enabled, non_spoon.start_e, self.retract_length, self.retract_speed, self.retract_prime_speed,
                                                self.hop_enabled, self.hop_height, self.hop_speed,
                                                non_spoon.start_has_move, non_spoon.start_has_zdown, non_spoon.start_has_prime, non_spoon.starts_retracted, self.relative_extrusion))
                new_layer.extend(non_spoon.lines)
            if not self.spoons_first:
                for spoon in spoon_lines:
                    new_layer.append(make_travel(spoon.start_x, spoon.start_y, self.travel_speed, spoon.start_z,
                                                 self.retract_enabled, spoon.start_e, self.retract_length, self.retract_speed, self.retract_prime_speed,
                                                 self.hop_enabled, self.hop_height, self.hop_speed,
                                                 spoon.start_has_move, spoon.start_has_zdown, spoon.start_has_prime, spoon.starts_retracted, self.relative_extrusion))
                    new_layer.extend(spoon.lines)
            if control_lines:
                new_layer.extend(control_lines)
            if layer_end_lines.lines:
                #new_layer.append(make_travel(layer_end_lines.start_x, layer_end_lines.start_y, self.travel_speed, layer_end_lines.start_z,
                #                             self.retract_enabled, layer_end_lines.start_e, self.retract_length, self.retract_speed, self.retract_prime_speed,
                #                             self.hop_enabled, self.hop_height, self.hop_speed))
                new_layer.extend(layer_end_lines.lines)
                if not (layer_index < (len(data) - 1) and self.target_name in data[layer_index + 1]):
                    new_layer.append(f"G92 E{get_last_e_value(layer_lines)}  ; SpoonOrder resetting extruder for one last time")

            # Need the original version as well in case we played around with the end
            previous_layer_lines_unaltered = layer_lines

            data[layer_index] = "\n".join(new_layer) + "\n"
            # Only change this after we've processed it
            previous_layer_lines = data[layer_index].splitlines()
        return data