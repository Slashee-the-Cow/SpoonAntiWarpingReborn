#--------------------------------------------------------------------------------------------------------------------------------------
# Spoon Anti-Warping Reborn by Slashee the Cow
# Copyright Slashee the Cow 2025-
#
# A continuation of the "Spoon Anti-Warping" plugin by 5@xes 2023
# https://github.com/5axes/SpoonAntiWarping
#--------------------------------------------------------------------------------------------------------------------------------------
# Version history (Reborn version)
# v1.1.0:
#   - Added print order setting built into the plugin that allows you print all spoons before or after models. Doesn't require changing any print settings to work.
#       Gets rid of unnessecary travel moves to potentially the wrong place. Doesn't require setting up (other than picking something from a dropdown).
#   - Second bullet point to make it not seem like such a minor update. That thing was **a lot** of work.
#   - Added GUI control for print order script. Look, this is a big deal, alright? I need to pad the changelog out a bit.
# v1.0.0:
#   - Refactored the hell out of this thing. If you compared it to the original version, you wouldn't think the two were related. I don't think Git does, either.
#   - Qt 5 wasn't cute enough to be worth the effort maintaining it. Sorry :( This also means Cura 5.0 is required as a minimum.
#   - Translated a bunch of variable names from... I'm guessing Klingon? To English.
#   - The "remove all" function now steps on tiptoes so as not to break anything. It might leave behind things which are spoons instead of deleting things which aren't spoons.
#   - Removed the "initial layer speed" setting. Why should a plugin set that?
#   - Calculating the spoon angle no requires build plate adhesion to be on. It doesn't have to be off either. It's up to you!
#   - Removed the bundled post-processing scripts to focus on core functionality and shamelessly self-promoting my own scripts.
#   - Renamed "Direct Shape" to "Teardrop shape". Dear pedants: I know it's not a proper teardrop shape, but "plectrum" isn't well enough known, however I am open to suggestions.
#   - Renamed everything internally so you can have this and a different version installed side by side.
#   - Replaced icon on toolbar with something that doesn't look like a Rorschach test with only incorrect answers.
#   - Fixed logic that just made me go :/ in some functions. I'm reasonably sure it was wrong. It can be hard to tell.
#   - Deleted "logic" which seemed to not meet the definition of the term from several functions.
#   - Implemented input validation on the backend.
#   - Implemented "robust" amounts of input validation (with live feedback!) on the frontend. You can never have too much input validation, right?
#   - This validation makes it so you can't create spoons with invalid settings. I'm very sorry to the both of you who did that for good reason.
#   - Added version check and function wrappers to the QML file so the log doesn't get spammed with stuff that got deprecated in 5.7.
#   - Redid layout of control panel so it should respond better to different screen resolutions or whatever.
#   - The control panel UI should now better match the active theme. And if it did it right, no longer has visual glitches.
#   - Did I mention refactoring? Becuase I definitely did some of that. In the QML file. And more in the Python file.
#   - Added best workaround I've figured out so far for https://github.com/Ultimaker/Cura/issues/20488
#   - Rolled my own "notifications" system because I can't use UM.Messages ^^^^^. It's not pretty, but it vaguely works.
#   - Added checks to prevent spoons being added off the build plate if the ^^^^^ terror above strikes.
#   - Added completedness to a few functions which aren't completely used but are *technically* correct, the best kind of correct.
#   - Put in a bunch of type hints. Whether or not I'm running type checking is unimportant. What's important is that I'm less unprepared for it.
#   - Spoons will now automatically point at points (no pun intended) spread along the model's edges instead of just the corners.
#   - Went low-tech in my spoon detection system. Doing it by name. If you trip it up, there's about a 102% chance it was deliberate, so don't submit a bug report.
#   - No longer uses non-public parts of the Cura API. I've always been a stickler for the rules.
#   - Lots of calculations are now more precise. It's one of those things where you can't tell it's working, you can tell if it isn't.
#   - Implemented a legitimate use of seven different functions in a single line of code. That isn't a feature; I'm just bragging.
#   - Added enough logging to fill the Great Library of Alexandria. Twice. At least.
#   - Removed existing translation files. It can still be translated, but everything I've changed broke the existing one. Help gladly accepted!

from dataclasses import dataclass
import os.path
import math
import random  # To make node names reasonably unique

import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication


from cura.CuraApplication import CuraApplication
from cura.PickingPass import PickingPass
from cura.Operations.SetParentOperation import SetParentOperation
from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from cura.Scene.CuraSceneNode import CuraSceneNode
from cura.Settings.PerObjectContainerStack import PerObjectContainerStack


from UM.Resources import Resources
from UM.Message import Message
from UM.Math.Vector import Vector
from UM.Math.Polygon import Polygon  # Not strictly needed; not bothering implementing imports just for type checking
from UM.Tool import Tool
from UM.Event import Event, MouseEvent
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Settings.SettingInstance import SettingInstance
from UM.Settings.InstanceContainer import InstanceContainer
from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from UM.Scene.Selection import Selection
from UM.Scene.SceneNode import SceneNode
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.i18n import i18nCatalog

from .slasheetools import log as log, validate_int, validate_float
from .SpoonOrder import SpoonOrder

@dataclass
class Notification:
    """Holds info for a notification message since I can't use UM.Message"""
    text: str  # If I need to explain this you're probably not qualified to work with this code.
    lifetime: float  # Notification lifetime in seconds
    id: int  # Becasue we've all gotten our notifications mixed up while out shopping... right?

Resources.addSearchPath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)))
)  # Plugin translation file import

catalog = i18nCatalog("spoonawreborn")

if catalog.hasTranslationLoaded():
    log("i", "Spoon Anti-Warping Reborn translation loaded")

class SpoonAntiWarpingReborn(Tool):
    def __init__(self) -> None:
        super().__init__()

        # List of created spoons (for delete all function)
        self._all_created_spoons: list[SceneNode] = []

        self._node_name_prefix: str = "<SpoonTab:"
        self._node_name_suffix: str = ">"

        # Spoon creation settings
        self._spoon_diameter: float = 10.0
        self._handle_length: float = 2.0
        self._handle_width: float = 2.0
        self._layer_count: float = 1
        self._teardrop_shape: bool = False

        self._inputs_valid: bool = False

        self._default_reference_distance: float = 5

        self._are_messages_hidden: bool = False
        self._hidden_messages: list[Message] = []

        self._default_message_title = catalog.i18nc("@message:title", "Spoon Anti-Warping Reborn")

        self._notifications: list[Notification] = []
        self._notification_next_id: int = 0
        self._notifications_string: str = ""

        # Keyboard shortcut
        self._shortcut_key = Qt.Key.Key_K

        self._controller = self.getController()

        self._selection_pass = None

        self._application: CuraApplication = CuraApplication.getInstance()

        self._order_script = SpoonOrder()

        self.setExposedProperties("SpoonDiameter", "HandleLength", "HandleWidth", "LayerCount", "TeardropShape", "InputsValid", "Notifications", "PrintOrder")

        # Note: if the selection is cleared with this tool active, there is no way to switch to
        # another tool than to reselect an object (by clicking it) because the tool buttons in the
        # toolbar will have been disabled. That is why we need to ignore the first press event
        # after the selection has been cleared.
        Selection.selectionChanged.connect(self._onSelectionChanged)
        self._had_selection: bool = False
        self._skip_press: bool = False

        self._had_selection_timer = QTimer()
        self._had_selection_timer.setInterval(0)
        self._had_selection_timer.setSingleShot(True)
        self._had_selection_timer.timeout.connect(self._selectionChangeDelay)

        # set the preferences to store the default value
        self._preferences = self._application.getPreferences()
        self._preferences.addPreference("spoonawreborn/spoon_diameter", 10)
        self._preferences.addPreference("spoonawreborn/handle_length", 2)
        self._preferences.addPreference("spoonawreborn/handle_width", 2)
        self._preferences.addPreference("spoonawreborn/layer_count", 1)
        self._preferences.addPreference("spoonawreborn/print_order", "Unchanged")
        self._preferences.addPreference("spoonawreborn/teardrop_shape", False)


        self._spoon_diameter = float(self._preferences.getValue("spoonawreborn/spoon_diameter"))
        self._handle_length = float(self._preferences.getValue("spoonawreborn/handle_length"))
        self._handle_width = float(self._preferences.getValue("spoonawreborn/handle_width"))
        self._layer_count = int(self._preferences.getValue("spoonawreborn/layer_count"))
        self._print_order = self._preferences.getValue("spoonawreborn/print_order")
        self._teardrop_shape = bool(self._preferences.getValue("spoonawreborn/teardrop_shape"))

        self._last_picked_node: SceneNode = None
        self._last_event: Event = None

        # Connect order script to write start
        self._application.getOutputDeviceManager().writeStarted.connect(self._run_spoon_order)

    def event(self, event: Event) -> None:
        super().event(event)
        modifiers = QApplication.keyboardModifiers()
        ctrl_is_active: bool = modifiers & Qt.KeyboardModifier.ControlModifier

        if event.type == Event.MousePressEvent and MouseEvent.LeftButton in event.buttons and self._controller.getToolsEnabled():
            if ctrl_is_active:
                self._controller.setActiveTool("RotateTool")
                return

            log("d", "You clicked with SpoonAntiWarpingReborn active!")

            if self._skip_press:
                # The selection was previously cleared, do not add/remove an support mesh but
                # use this click for selection and reactivating this tool only.
                self._skip_press = False
                return

            if self._selection_pass is None:
                # The selection renderpass is used to identify objects in the current view
                self._selection_pass = CuraApplication.getInstance().getRenderer().getRenderPass("selection")
            picked_node = self._controller.getScene().findObject(self._selection_pass.getIdAtPosition(event.x, event.y))
            if not picked_node:
                # There is no slicable object at the picked location
                log("d", "SpoonAntiWarpingReborn.event() has no selected node")
                return
            log("d", f"SpoonAntiWarpingReborn.event has picked node {picked_node.getName()}")

            # if it's a spoon_mesh -> remove it
            if self._is_spoon_by_name(picked_node.getName()):
                log("d", f"SpoonAntiWarpingReborn.event() > {picked_node.getName()} is a spoon so will be deleted.")
                self._removeSpoonMesh(picked_node)
                return
            node_stack: PerObjectContainerStack = picked_node.callDecoration("getStack")

            if node_stack:
                log("d", "SpoonAntiWarpingReborn.event > testing node_stack")
                try:
                    if not self._is_normal_object(picked_node):
                        # Only "normal" meshes can have spoon_mesh added to them
                        log("d", f"SpoonAntiWarpingReborn.event() > picked_node {picked_node.getName()} isn't a normal mesh.")
                        return
                    log("d", f"SpoonAntiWarpingReborn.event just passed \"abnormal object\" check")
                except Exception as e:
                    log("e", f"SpoonAntiWarpingReborn.event had exception on _is_normal_object check: {e}")

            if not self._inputs_valid:
                log("d", "Tried to create a spoon with invalid inputs")
                self._notification_add(catalog.i18nc("add_spoon_invalid_input", "Cannot create a tab while some of the settings are not valid. Please check the tool's settings."), 10)
                log("d", f"SpoonAntiWarpingReborn.event() > _self.inputs_valid is False")
                return
            log("d", f"SpoonAntiWarpingReborn.event() just passed invalid settings check")


            log("d", "SpoonAntiWarpingReborn.event() just passed all checks.")
            self._last_picked_node = picked_node
            self._last_event = event

            # Hide all currently shown messages
            try:  # In a try...except for now at least, just to make sure anything gets caught
                self._hide_messages()
            except Exception as e:
                log("e", f"Exception trying to run _hide_messages: {e}")
            # Defer PickingPass until messags have faded (if required)
            QTimer.singleShot(250 if self._are_messages_hidden else 0, self._picking_pass)
            log("d", "event() set the timer")
            return

    def _picking_pass(self):
        picked_node = self._last_picked_node
        event = self._last_event
        # Create a pass for picking a world-space location from the mouse location
        active_camera = self._controller.getScene().getActiveCamera()
        picking_pass = PickingPass(active_camera.getViewportWidth(), active_camera.getViewportHeight())
        picking_pass.render()

        picked_position = picking_pass.getPickedPosition(event.x, event.y)
        log("dd", f"picked_position = {repr(picked_position)} on {picked_node}")

        if not self._check_valid_placement(picked_position):
            log("d", f"picked_position {picked_position} deemed invalid")
            try:
                self._show_messages()
            except Exception as e:
                log("e", f"_show_messages raised {e}")
            return

        # Add the spoon_mesh at the picked location
        self._createSpoonMesh(picked_node, picked_position)

        try:
            self._show_messages()
        except Exception as e:
            log("e", f"Exception trying to run _show_messages(): {e}")

    def _hide_messages(self):
        log("d", f"_hide_messages is running with an _application.getVisibleMessages() of {self._application.getVisibleMessages()}")
        message_count: int = len(self._application.getVisibleMessages())
        if message_count == 0:
            self._are_messages_hidden = False
            return

        self._are_messages_hidden = True
        self._notification_add("<font color='red'>Do not move the camera until the click location is recorded.</font>", 1)
        self._hidden_messages = list(self._application.getVisibleMessages())
        log("d", f"_hide_messages just set _hidden_messages to {self._hidden_messages}")
        for message in self._hidden_messages:
            message.hide()

    def _show_messages(self):
        if not self._are_messages_hidden:
            return

        self._notification_add("<font color='green'>Click position has been recorded.</font>", 3)
        for message in self._hidden_messages:
            message.show()

        self._are_messages_hidden = False
        self._hidden_messages = []

    def _notification_add(self, text: str, lifetime: float) -> None:
        notification = Notification(text, lifetime, self._notification_next_id)
        self._notifications.append(notification)
        self._notification_next_id += 1
        self._notifications_set_property()
        QTimer.singleShot(int(lifetime * 1000), lambda: self._notification_remove(notification))

    def _notification_remove(self, notification: Notification) -> None:
        if notification in self._notifications:
            self._notifications.remove(notification)
            self._notifications_set_property()
        else:
            log("d", f"_notification_remove could not find notification with text {notification.text} and ID {notification.id}")

    def _notifications_set_property(self) -> None:
        self._notifications_string = "<br><br>".join(notification.text for notification in self._notifications)
        self.propertyChanged.emit()

    def _check_valid_placement(self, picked_position) -> bool:
        # Check to see if Cura picked a spot off the build plate
        global_stack = CuraApplication.getInstance().getGlobalContainerStack()
        machine_width = float(global_stack.getProperty("machine_width", "value"))
        machine_depth = float(global_stack.getProperty("machine_depth", "value"))
        log("d", f"machine width = {machine_width}, depth = {machine_depth}")
        if (picked_position.x < -(machine_width / 2)
            or picked_position.x > (machine_width / 2)
            or picked_position.z < -(machine_depth / 2)
            or picked_position.z > (machine_depth / 2)
        ):
            self._notification_add(catalog.i18nc("spoon_off_build_plate", "Oops! Looks like Cura picked an invalid position for the spoon :( Please try again."), 7.5)
            return False

        left_edge: float = -(machine_width / 2) + (self._spoon_diameter / 2)
        right_edge: float = (machine_width / 2) - (self._spoon_diameter / 2)
        front_edge: float = (-machine_depth / 2) + (self._spoon_diameter / 2)
        rear_edge: float = (machine_depth / 2) - (self._spoon_diameter / 2)
        log("d", f"left_edge = {left_edge}, right_edge = {right_edge}, front_edge = {front_edge}, rear_edge = {rear_edge}")
        if(
            picked_position.x < left_edge
            or picked_position.x > right_edge
            or picked_position.z < front_edge
            or picked_position.z > rear_edge
        ):
            self._notification_add(catalog.i18nc("spoon_on_plate_edge", "A spoon can't be that close to edge of the build plate. You should move your object in a bit."), 7.5)
            return False

        #TODO: Use SceneNode.collidesWithBbox()
        return True

    def _random_name_part(self) -> str:
        """Returns a 4 digit hexadecimal number."""
        # I'll be honest here. The hex parts of the name are mostly to make it
        # look technical to give the user a "don't mess with this" vibe.
        return str(hex(round(random.random()*65535))).lstrip("0x").upper().zfill(4)

    def _generate_node_name(self) -> str:
        return f"{self._node_name_prefix}{self._random_name_part()}{self._node_name_suffix}"

    def _is_spoon_by_name(self, node_name: str) -> bool:
        """Returns a bool of whether a name meets the criteria to belong to a spoon object"""
        # If I wanted to be really thorough, I'd use a regex to check the hex digits.
        # But this should be close enough.
        return node_name.startswith(self._node_name_prefix) and node_name.rstrip("()0123456790 ").endswith(self._node_name_suffix)

    def _createSpoonMesh(self, parent: CuraSceneNode, position: Vector):
        node = CuraSceneNode()

        # local_transformation = parent.getLocalTransformation()
        # Logger.log('d', "Parent local_transformation --> " + str(local_transformation))

        node.setName(self._generate_node_name())
        node.setSelectable(True)

        # Offset for height of click to position spoon on plate
        height_offset=position.y

        extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()[0]
        #self._Extruder_count=global_container_stack.getProperty("machine_extruder_count", "value")

        _layer_height_0: float = extruder_stack.getProperty("layer_height_0", "value")
        _layer_height: float = extruder_stack.getProperty("layer_height", "value")
        _spoon_height: float = (_layer_height_0 * 1.2) + (_layer_height * (self._layer_count -1) )

        _angle: float = self.defineAngle(parent, position)
        # Logger.log('d', "Info createSpoonMesh Angle --> " + str(_angle))

        mesh = self._createSpoon(self._spoon_diameter,self._handle_length,self._handle_width, 10, height_offset, _spoon_height, self._teardrop_shape, _angle)

        node.setMeshData(mesh.build())

        active_build_plate = CuraApplication.getInstance().getMultiBuildPlateModel().activeBuildPlate
        node.addDecorator(BuildPlateDecorator(active_build_plate))
        node.addDecorator(SliceableObjectDecorator())

        stack: PerObjectContainerStack = node.callDecoration("getStack") # created by SettingOverrideDecorator that is automatically added to CuraSceneNode
        settings: InstanceContainer = stack.getTop()

        definition = stack.getSettingDefinition("meshfix_union_all")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", False)
        new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)

        definition = stack.getSettingDefinition("infill_mesh_order")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", 49) #50 "maximum_value_warning": "50"
        new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)

        # First add node to the scene at the correct position/scale, before parenting, so the Spoon mesh does not get scaled with the parent
        scene_op = GroupedOperation()
        scene_op.addOperation(AddSceneNodeOperation(node, self._controller.getScene().getRoot())) # This one will set the model with the right transformation
        scene_op.addOperation(SetParentOperation(node, parent)) # This one will link the tab with the parent ( Scale)

        node.setPosition(position, CuraSceneNode.TransformSpace.World)  # Set the World Transformmation

        self._all_created_spoons.append(node)
        self.propertyChanged.emit()
        scene_op.push()

        CuraApplication.getInstance().getController().getScene().sceneChanged.emit(node)

    def _removeSpoonMesh(self, node: CuraSceneNode):
        parent = node.getParent()
        if parent == self._controller.getScene().getRoot():
            parent = None

        remove_op = RemoveSceneNodeOperation(node)
        remove_op.push()

        if parent and not Selection.isSelected(parent):
            Selection.add(parent)

        CuraApplication.getInstance().getController().getScene().sceneChanged.emit(node)

    def _onSelectionChanged(self):
        # When selection is passed from one object to another object, first the selection is cleared
        # and then it is set to the new object. We are only interested in the change from no selection
        # to a selection or vice-versa, not in a change from one object to another. A timer is used to
        # "merge" a possible clear/select action in a single frame
        if Selection.hasSelection() != self._had_selection:
            self._had_selection_timer.start()

    def _selectionChangeDelay(self):
        has_selection = Selection.hasSelection()
        if not has_selection and self._had_selection:
            self._skip_press = True
        else:
            self._skip_press = False

        self._had_selection = has_selection

    def _is_normal_object(self, node: SceneNode) -> bool:
        """Check to make sure a SceneNode is a regular object and not support or whatever."""
        node_stack: PerObjectContainerStack = node.callDecoration("getStack")
        if not node_stack:
            return False
        
        type_infill_mesh = node_stack.getProperty("infill_mesh", "value")
        type_cutting_mesh = node_stack.getProperty("cutting_mesh", "value")
        type_support_mesh = node_stack.getProperty("support_mesh", "value")
        type_spoon_mesh = self._is_spoon_by_name(node.getName())
        type_anti_overhang_mesh = node_stack.getProperty("anti_overhang_mesh", "value")

        return not any((type_infill_mesh, type_cutting_mesh, type_support_mesh, type_spoon_mesh, type_anti_overhang_mesh))

    def _tangential_point_on_circle(self, center, radius, start_point):
        """Return 2 tangenital points of circle from a given point
        ...even though only the first one is ever used."""
        # Calculation of the distance between point_fix and (center[0], center[1])
        start_distance = math.sqrt((center[0] - start_point[0])**2 + (center[1] - start_point[1])**2)

        # Search for the points of tangency of the line with the circle
        tangency_points = []

        # If point_fix is on the circle, there is only one point of tangency
        if start_distance == radius:
            tangency_points.append((start_point[0], start_point[1]))

        else:
            # Calculation of the angle between the line and the radius of the circle passing through the point of tangency
            theta = math.asin(radius / start_distance)
            # Calculation of the angle of the line
            alpha = math.atan2(center[1] - start_point[1] , center[0] - start_point[0] )
            # Calculation of the angles of the two rays passing through the points of tangency
            beta1 = alpha + theta
            beta2 = alpha - theta
            # Calculation of the coordinates of the tangency points
            tan_x_1 = center[0] - radius* math.sin(beta1)
            tan_y_1 = center[1] + radius* math.cos(beta1)
            tangency_points.append((tan_x_1, tan_y_1))

            tan_x_2 = center[0] - radius* math.sin(beta2)
            tan_y_2 = center[1] + radius* math.cos(beta2)
            tangency_points.append((tan_x_2, tan_y_2))
        return tangency_points

    # Spoon creation
    def _createSpoon(self, size, handle_length, handle_width, segments,
                     height, max_y, teardrop_shape, angle):
        mesh = MeshBuilder()
        # Per-vertex normals require duplication of vertices
        circle_radius = size / 2
        # First layer length
        max_y = -height + max_y
        negative_height = -height

        segment_degrees = round((360 / segments),4)
        segment_radians = math.radians(segments)

        vertices = []

        # Add the handle of the spoon
        half_handle_width = handle_width / 2

        if teardrop_shape:
            circle_start = [0, half_handle_width]
            circle_center = [(circle_radius + handle_length), 0]
            tangent_points = self._tangential_point_on_circle(circle_center, circle_radius, circle_start)
            log("d", f"Tangent points: {tangent_points}")
            vertex_count = 20
            vertices = [ # 5 faces with 4 corners each
                [-half_handle_width, negative_height,  half_handle_width], [-half_handle_width,  max_y,  half_handle_width], [ tangent_points[0][0],  max_y,  tangent_points[0][1]], [ tangent_points[0][0], negative_height,  tangent_points[0][1]],
                [-half_handle_width,  max_y, -half_handle_width], [-half_handle_width, negative_height, -half_handle_width], [ tangent_points[0][0], negative_height, -tangent_points[0][1]], [ tangent_points[0][0],  max_y, -tangent_points[0][1]],
                [ tangent_points[0][0], negative_height, -tangent_points[0][1]], [-half_handle_width, negative_height, -half_handle_width], [-half_handle_width, negative_height,  half_handle_width], [ tangent_points[0][0], negative_height,  tangent_points[0][1]],
                [-half_handle_width,  max_y, -half_handle_width], [ tangent_points[0][0],  max_y, -tangent_points[0][1]], [ tangent_points[0][0],  max_y,  tangent_points[0][1]], [-half_handle_width,  max_y,  half_handle_width],
                [-half_handle_width, negative_height,  half_handle_width], [-half_handle_width, negative_height, -half_handle_width], [-half_handle_width,  max_y, -half_handle_width], [-half_handle_width,  max_y,  half_handle_width]
            ]
            max_width=tangent_points[0][1]
            max_length=tangent_points[0][0]
        else:
            vertex_count = 20
            vertices = [ # 5 faces with 4 corners each
                [-half_handle_width, negative_height,  half_handle_width], [-half_handle_width,  max_y,  half_handle_width], [ handle_length,  max_y,  half_handle_width], [ handle_length, negative_height,  half_handle_width],
                [-half_handle_width,  max_y, -half_handle_width], [-half_handle_width, negative_height, -half_handle_width], [ handle_length, negative_height, -half_handle_width], [ handle_length,  max_y, -half_handle_width],
                [ handle_length, negative_height, -half_handle_width], [-half_handle_width, negative_height, -half_handle_width], [-half_handle_width, negative_height,  half_handle_width], [ handle_length, negative_height,  half_handle_width],
                [-half_handle_width,  max_y, -half_handle_width], [ handle_length,  max_y, -half_handle_width], [ handle_length,  max_y,  half_handle_width], [-half_handle_width,  max_y,  half_handle_width],
                [-half_handle_width, negative_height,  half_handle_width], [-half_handle_width, negative_height, -half_handle_width], [-half_handle_width,  max_y, -half_handle_width], [-half_handle_width,  max_y,  half_handle_width]
            ]
            max_width=half_handle_width
            max_length=handle_length

        # Add Round Part of the Spoon
        vertex_count_round = 0
        # Used to fill in any gaps if the division of the circle into segments didn't quite add up
        remainder_1 = 0
        remainder_2 = 0

        for i in range(0, math.ceil(segment_degrees)):
            if (circle_radius*math.cos((i+1)*segment_radians)) >= 0 or (abs(circle_radius*math.sin((i+1)*segment_radians)) > max_width and abs(circle_radius*math.sin(i*segment_radians)) > max_width)  :
                vertex_count_round += 1
                # Top
                vertices.append([handle_length+circle_radius, max_y, 0])
                vertices.append([handle_length+circle_radius+circle_radius*math.cos((i+1)*segment_radians), max_y, circle_radius*math.sin((i+1)*segment_radians)])
                vertices.append([handle_length+circle_radius+circle_radius*math.cos(i*segment_radians), max_y, circle_radius*math.sin(i*segment_radians)])
                #Side 1a
                vertices.append([handle_length+circle_radius+circle_radius*math.cos(i*segment_radians), max_y, circle_radius*math.sin(i*segment_radians)])
                vertices.append([handle_length+circle_radius+circle_radius*math.cos((i+1)*segment_radians), max_y, circle_radius*math.sin((i+1)*segment_radians)])
                vertices.append([handle_length+circle_radius+circle_radius*math.cos((i+1)*segment_radians), negative_height, circle_radius*math.sin((i+1)*segment_radians)])
                #Side 1b
                vertices.append([handle_length+circle_radius+circle_radius*math.cos((i+1)*segment_radians), negative_height, circle_radius*math.sin((i+1)*segment_radians)])
                vertices.append([handle_length+circle_radius+circle_radius*math.cos(i*segment_radians), negative_height, circle_radius*math.sin(i*segment_radians)])
                vertices.append([handle_length+circle_radius+circle_radius*math.cos(i*segment_radians), max_y, circle_radius*math.sin(i*segment_radians)])
                #Bottom
                vertices.append([handle_length+circle_radius, negative_height, 0])
                vertices.append([handle_length+circle_radius+circle_radius*math.cos(i*segment_radians), negative_height, circle_radius*math.sin(i*segment_radians)])
                vertices.append([handle_length+circle_radius+circle_radius*math.cos((i+1)*segment_radians), negative_height, circle_radius*math.sin((i+1)*segment_radians)])
            else :
                if remainder_1 == 0 :
                    remainder_1 = i*segment_radians
                    remainder_2 = 2*math.pi-remainder_1

                    if teardrop_shape :
                        vertex_count_round += 1
                        # Top
                        vertices.append([handle_length+circle_radius, max_y, 0])
                        vertices.append([max_length, max_y, max_width])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_1), max_y, circle_radius*math.sin(remainder_1)])
                        #Side 1a
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_1), max_y, circle_radius*math.sin(remainder_1)])
                        vertices.append([max_length, max_y, max_width])
                        vertices.append([max_length, negative_height, max_width])
                        #Side 1b
                        vertices.append([max_length, negative_height, max_width])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_1), negative_height, circle_radius*math.sin(remainder_1)])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_1), max_y, circle_radius*math.sin(remainder_1)])
                        #Bottom
                        vertices.append([handle_length+circle_radius, negative_height, 0])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_1), negative_height, circle_radius*math.sin(remainder_1)])
                        vertices.append([max_length, negative_height, max_width])

                        vertex_count_round += 1
                        # Top
                        vertices.append([handle_length+circle_radius, max_y, 0])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_2), max_y, circle_radius*math.sin(remainder_2)])
                        vertices.append([max_length, max_y, -max_width])
                        #Side 1a
                        vertices.append([max_length, max_y, -max_width])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_2), max_y, circle_radius*math.sin(remainder_2)])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_2), negative_height, circle_radius*math.sin(remainder_2)])
                        #Side 1b
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_2), negative_height, circle_radius*math.sin(remainder_2)])
                        vertices.append([max_length, negative_height, -max_width])
                        vertices.append([max_length, max_y, -max_width])
                        #Bottom
                        vertices.append([handle_length+circle_radius, negative_height, 0])
                        vertices.append([max_length, negative_height, -max_width])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_2), negative_height, circle_radius*math.sin(remainder_2)])
                    else:
                        vertex_count_round += 1
                        # Top
                        vertices.append([handle_length+circle_radius, max_y, 0])
                        vertices.append([handle_length, max_y, max_width])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_1), max_y, circle_radius*math.sin(remainder_1)])
                        #Side 1a
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_1), max_y, circle_radius*math.sin(remainder_1)])
                        vertices.append([handle_length, max_y, max_width])
                        vertices.append([handle_length, negative_height, max_width])
                        #Side 1b
                        vertices.append([handle_length, negative_height, max_width])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_1), negative_height, circle_radius*math.sin(remainder_1)])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_1), max_y, circle_radius*math.sin(remainder_1)])
                        #Bottom
                        vertices.append([handle_length+circle_radius, negative_height, 0])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_1), negative_height, circle_radius*math.sin(remainder_1)])
                        vertices.append([handle_length, negative_height, max_width])

                        vertex_count_round += 1
                        # Top
                        vertices.append([handle_length+circle_radius, max_y, 0])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_2), max_y, circle_radius*math.sin(remainder_2)])
                        vertices.append([handle_length, max_y, -max_width])
                        #Side 1a
                        vertices.append([handle_length, max_y, -max_width])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_2), max_y, circle_radius*math.sin(remainder_2)])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_2), negative_height, circle_radius*math.sin(remainder_2)])
                        #Side 1b
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_2), negative_height, circle_radius*math.sin(remainder_2)])
                        vertices.append([handle_length, negative_height, -max_width])
                        vertices.append([handle_length, max_y, -max_width])
                        #Bottom
                        vertices.append([handle_length+circle_radius, negative_height, 0])
                        vertices.append([handle_length, negative_height, -max_width])
                        vertices.append([handle_length+circle_radius+circle_radius*math.cos(remainder_2), negative_height, circle_radius*math.sin(remainder_2)])

        # Add link part between handle and Round Part
        # Top center
        vertices.append([max_length, max_y, max_width])
        vertices.append([handle_length+circle_radius, max_y, 0])
        vertices.append([max_length, max_y, -max_width])

        # Bottom  center
        vertices.append([max_length, negative_height, -max_width])
        vertices.append([handle_length+circle_radius, negative_height, 0])
        vertices.append([max_length, negative_height, max_width])

        # Rotate the mesh
        vertex_total = vertex_count_round * 12 + 6 + vertex_count
        rotated_vertices = []
        # Logger.log('d', "Angle Rotation : {}".format(angle))
        for i in range(0,vertex_total) :
            xr = (vertices[i][0] * math.cos(angle)) - (vertices[i][2] * math.sin(angle))
            yr = (vertices[i][0] * math.sin(angle)) + (vertices[i][2] * math.cos(angle))
            zr = vertices[i][1]
            rotated_vertices.append([xr, zr, yr])

        mesh.setVertices(np.asarray(rotated_vertices, dtype=np.float32))

        indices = []
        for i in range(0, vertex_count, 4): # All 6 quads (12 triangles)
            indices.append([i, i+2, i+1])
            indices.append([i, i+3, i+2])

        # for every angle increment 12 Vertices
        vertex_total = vertex_count_round * 12 + 6 + vertex_count
        for i in range(vertex_count, vertex_total, 3): #
            indices.append([i, i+1, i+2])
        mesh.setIndices(np.asarray(indices, dtype=np.int32))

        mesh.calculateNormals()
        return mesh

    def removeAllSpoonMesh(self):
        log("d", f"removeAllSpoonMesh run with _all_created_spoons of {self._all_created_spoons}")
        if self._all_created_spoons:
            for node in self._all_created_spoons:
                if self._is_spoon_by_name(node.getName()):
                    self._removeSpoonMesh(node)
            self._all_created_spoons.clear()
        # The list has no persistence so we need to check by name anyway
        for node in DepthFirstIterator(self._application.getController().getScene().getRoot()):
            if self._is_spoon_by_name(node.getName()):
                self._removeSpoonMesh(node)
            self.propertyChanged.emit()

    # Source code from MeshTools Plugin
    # Copyright (c) 2020 Aldo Hoeben / fieldOfView
    def _getAllSelectedNodes(self) -> list[SceneNode]:
        selection = Selection.getAllSelectedObjects()[:]
        if selection:
            deep_selection = []  # type: list[SceneNode]
            for selected_node in selection:
                if selected_node.hasChildren():
                    deep_selection = deep_selection + selected_node.getAllChildren()
                if selected_node.getMeshData() is not None:
                    deep_selection.append(selected_node)
            if deep_selection:
                return deep_selection

        # Message(catalog.i18nc("@info:status", "Please select one or more models first"))

        return []

    def get_hull_bounds(self, hull_points: np.ndarray) -> tuple[float, float]:
        """Calculates the width and height of a set of hull points."""
        min_x = np.min(hull_points[:, 0])
        max_x = np.max(hull_points[:, 0])
        min_y = np.min(hull_points[:, 1])
        max_y = np.max(hull_points[:, 1])
        width = max_x - min_x
        height = max_y - min_y
        return width, height

    def get_hull_bounds_center(self, hull_points: np.ndarray) -> np.ndarray:
        """Calculates the center of the bounding box of a set of hull points."""
        min_x = np.min(hull_points[:, 0])
        max_x = np.max(hull_points[:, 0])
        min_y = np.min(hull_points[:, 1])
        max_y = np.max(hull_points[:, 1])
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        return np.array([center_x, center_y])

    def get_corner_scale_factor(self, hull_points: np.ndarray, main_outset: float) -> float:
        """Calculates a scaling factor for corner outset."""
        width, height = self.get_hull_bounds(hull_points)
        larger_dimension = max(width, height)
        if larger_dimension == 0:  # Avoid division by zero for degenerate cases
            return 1.0 + (0.70 * main_outset)
        return 1.0 + (0.70 * main_outset) / larger_dimension

    def line_segment_length_numpy(self, point1: np.ndarray, point2: np.ndarray) -> float:
        """
        Calculates the Euclidean distance between two 2D points using NumPy.

        Args:
            point1 (np.ndarray): A NumPy array of shape (2,) representing the first point [x1, y1].
            point2 (np.ndarray): A NumPy array of shape (2,) representing the second point [x2, y2].

        Returns:
            float: The length of the line segment.
        """
        return np.linalg.norm(point2 - point1)

    def _generate_reference_points(self, hull_points: np.ndarray, desired_spacing_mm: float) -> np.ndarray:
        """
        Generates a series of reference points along the edges of a convex hull
        for nearest-point calculations. Avoids duplicate vertices.

        Args:
            hull_points (np.ndarray): A NumPy array of shape (n, 2) representing the vertices of the convex hull in order.
            desired_spacing_mm (float): The desired spacing between reference points along the edges in millimeters.

        Returns:
            np.ndarray: A NumPy array of shape (m, 2) containing all the reference points.
        """
        if desired_spacing_mm is None:
            desired_spacing_mm = self._default_reference_distance
        all_edge_points = []
        num_hull_points = len(hull_points)

        for i in range(num_hull_points):
            start_point = hull_points[i]
            end_point = hull_points[(i + 1) % num_hull_points]

            edge_length = self.line_segment_length_numpy(start_point, end_point)
            num_points = max(2, int(edge_length / desired_spacing_mm) + 1)

            edge_points = np.linspace(start_point, end_point, num_points)[:-1]
            all_edge_points.append(edge_points)

        combined_points = np.concatenate(all_edge_points, axis=0)
        return combined_points

    def defineAngle(self, node: CuraSceneNode, spoon_position: Vector) -> float:
        """Computes the angle to a point on the convex hull for the spoon to point at."""
        result_angle = 0  # Needs to be declared at the top in case of an emergency exit.

        if not node.callDecoration("isSliceable"):
            log("w", f"{node.getName} is not sliceable")
            return result_angle

        # hull_polygon = node.callDecoration("getAdhesionArea")
        # hull_polygon = node.callDecoration("getConvexHull")
        # hull_polygon = node.callDecoration("getConvexHullBoundary")
        # hull_polygon = node.callDecoration("_compute2DConvexHull")
        object_hull: Polygon = node.callDecoration("getConvexHullBoundary")
        if object_hull is None:
            object_hull = node.callDecoration("getConvexHull")

        if not object_hull or object_hull.getPoints is None:
            log("w", f"{node.getName()} cannot be calculated because a convex hull cannot be generated.")
            return result_angle

        object_points = object_hull.getPoints()

        log("d", f"object_points = {object_points}")

        spoon_outset = round((self._spoon_diameter + self._handle_length) * 1.1, 4)
        log("d", f"spoon_circle_radius = {spoon_outset}")
        #minkowski_circle = Polygon.approximatedCircle(spoon_outset)
        #outer_minkowski_circle = minkowski_circle.translate(object_points[0][0], object_points[0][1])

        minkowski_square_points = [[spoon_outset, -spoon_outset],
                            [-spoon_outset, -spoon_outset],
                            [-spoon_outset, spoon_outset],
                            [spoon_outset, spoon_outset]]

        minkowski_square = Polygon(minkowski_square_points)
        log("d", f"minkowski_square = {repr(minkowski_square)}")

        minkowski_points = object_hull.getMinkowskiHull(minkowski_square).getPoints()
        log("d", f"minkowski_hull_points = {repr(minkowski_points)}")

        reference_points = self._generate_reference_points(minkowski_points, self._default_reference_distance)
        log("d", f"reference_points = {repr(reference_points)}")

        # Create a convex hull smaller than the Minkowski hull so points on the convex hull have a point close to them perpendicularly
        scaled_convex_hull_points = Polygon.scale(object_hull, self.get_corner_scale_factor(object_hull.getPoints(), spoon_outset), self.get_hull_bounds_center(object_hull.getPoints()))
        log("d", f"scaled_convex_hull_points = {repr(scaled_convex_hull_points)}")

        combined_points = np.concatenate((reference_points, scaled_convex_hull_points.getPoints()), axis=0)

        # Angle Ref for angle / Y Dir
        angle_reference = Vector(0, 0, 1)
        min_length = math.inf
        # Set on the build plate for distance
        start_position = Vector(spoon_position.x, 0, spoon_position.z)
        closest_point: Vector = None  # Not actually using this at the moment; could be useful in the future
        
        # Find point closest to start position
        for point in combined_points:
            # Logger.log('d', "Point : {}".format(point))
            test_position = Vector(point[0], 0, point[1])
            difference_vector = start_position - test_position
            length = difference_vector.length()

            if 0 < length < min_length:
                min_length = length
                closest_point = test_position
                angle_vector = difference_vector.normalized()
                calculated_angle = math.asin(angle_reference.dot(angle_vector))

                if angle_vector.x >= 0:
                    result_angle = math.pi + calculated_angle
                else :
                    result_angle = -calculated_angle

        return result_angle

    def addAutoSpoonMesh(self) -> None:
        """Automatically adds spoons to points on the convex hull of the selected object"""

        minimum_spoon_gap = self._spoon_diameter * 0.8

        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            nodes_list = DepthFirstIterator(self._application.getController().getScene().getRoot())

        for node in nodes_list:
            if not node.callDecoration("isSliceable"):
                continue
            node_stack=node.callDecoration("getStack")
            if not node_stack:
                continue

            if not self._is_normal_object(node):
                continue
            # and Selection.isSelected(node)
            # Logger.log('d', "Mesh : {}".format(node.getName()))

            hull_polygon: Polygon = node.callDecoration("getConvexHullBoundary")
            if hull_polygon is None:
                hull_polygon = node.callDecoration("getConvexHull")

            if not hull_polygon or not hull_polygon.isValid():
                log("w", f"Object {node.getName()} cannot be calculated because it has no convex hull.")
                continue

            points = hull_polygon.getPoints()

            first_point: Vector = Vector(points[0][0],0,points[0][1])
            last_spoon_position: Vector = None

            log("d", "About to list points in convex hull")
            for point in points:
                log("d", point)

            for i, point in enumerate(points):
                point_position = Vector(point[0], 0, point[1])
                if not last_spoon_position:
                    self._createSpoonMesh(node, point_position)
                    last_spoon_position = point_position
                    continue

                difference_vector = last_spoon_position - point_position
                difference_length = round(difference_vector.length(),4)

                first_to_last_distance = (first_point - point_position).length() if i == len(points) - 1 else 0

                # Make sure not to place spoons too close together
                if difference_length >= minimum_spoon_gap or first_to_last_distance >= minimum_spoon_gap:
                    self._createSpoonMesh(node, point_position)
                    last_spoon_position = point_position

    def _run_spoon_order(self, output_device) -> None:
        log("d", f"_run_spoon_order running with _print_order of {self._print_order}")
        match self._print_order:
            case "Unchanged":
                return
            case "Spoons first":
                self._order_script.spoons_first = True
            case "Spoons last":
                self._order_script.spoons_first = False
            case _:
                log("w", "_run_spoon_order got unmatched string for _print_order")
        
        scene = self._application.getController().getScene()
        gcode_dict = getattr(scene, "gcode_dict", {})
        for plate_id in gcode_dict:
            for layer in gcode_dict[plate_id]:
                log("i", layer.replace("\n",","))
            gcode_dict[plate_id] = self._order_script.execute(gcode_dict[plate_id])

    def getSpoonDiameter(self) -> float:
        """_spoon_diameter setter for QML"""
        return self._spoon_diameter

    def setSpoonDiameter(self, SpoonDiameter: str) -> None:
        """_spoon_diameter setter for QML"""
        self._spoon_diameter = validate_float(SpoonDiameter, minimum=0.1, clamp=True, default=self._spoon_diameter)
        self._preferences.setValue("spoonawreborn/spoon_diameter", self._spoon_diameter)
        self.propertyChanged.emit()

    def getHandleLength(self) -> float:
        """_handle_length getter for QML"""
        return self._handle_length

    def setHandleLength(self, HandleLength: str) -> None:
        """_handle_length setter for QML"""

        self._handle_length = validate_float(HandleLength, minimum=0.1, clamp=True, default=self._handle_length)
        self._preferences.setValue("spoonawreborn/handle_length", self._handle_length)
        self.propertyChanged.emit()

    def getHandleWidth(self) -> float:
        """_handle_width getter for QML"""
        return self._handle_width

    def setHandleWidth(self, HandleWidth: str) -> None:
        """_handle_width setter for QML"""
        self._handle_width = validate_float(HandleWidth, minimum=0.1, clamp=True, default=self._handle_width)
        self._preferences.setValue("spoonawreborn/handle_width", self._handle_width)
        self.propertyChanged.emit()

    def getLayerCount(self) -> int:
        """_layer_count getter for QML"""
        return self._layer_count

    def setLayerCount(self, LayerCount: str) -> None:
        """_layer_count setter for QML"""
        self._layer_count = validate_int(LayerCount, minimum=1, clamp=True)
        self._preferences.setValue("spoonawreborn/layer_count", self._layer_count)
        self.propertyChanged.emit()

    def getTeardropShape(self) -> bool:
        """_teardrop_shape getter for QML"""
        return self._teardrop_shape

    def setTeardropShape(self, value: bool) -> None:
        """_teardrop_shape setter for QML"""
        self._teardrop_shape = value
        self._preferences.setValue("spoonawreborn/teardrop_shape", self._teardrop_shape)
        self.propertyChanged.emit()

    def getInputsValid(self) -> bool:
        """_inputs_valid getter for QML.
        Not likely to be run that much because it's set by the QML."""
        return self._inputs_valid

    def setInputsValid(self, value: bool) -> None:
        """_inputs_valid setter for QML"""
        self._inputs_valid = value

    def getNotifications(self) -> str:
        """_notififcations getter for QML"""
        return self._notifications_string

    def setNotifications(self, value: str) -> None:
        """The QML should never run this. But it probably will.
        So it does nothing."""
        log("d", f"Something ran setNotifications with {value}")
        return

    def getPrintOrder(self) -> str:
        """_print_order getter for QML"""
        log("d", f"Getting Print Order of {self._print_order}")
        return self._print_order

    def setPrintOrder(self, value: str) -> None:
        """_print_order setter for QML"""
        log("d", f"Setting Print Order to {value}")
        self._print_order = value
        self._preferences.setValue("spoonawreborn/print_order", self._print_order)
        self.propertyChanged.emit()
