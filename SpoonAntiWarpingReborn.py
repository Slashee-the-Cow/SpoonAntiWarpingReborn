#--------------------------------------------------------------------------------------------------------------------------------------
# Spoon Anti-Warping Reborn by Slashee the Cow
# Copyright Slashee the Cow 2025-
#
# A continuation of the "Spoon Anti-Warping" plugin by 5@xes 2023
# https://github.com/5axes/SpoonAntiWarping
#--------------------------------------------------------------------------------------------------------------------------------------
# Version history (Reborn version)
# v1.0.0:
#   - Removed support for Qt 5 so I don't have to write everything twice. Errr I mean so it's easier to maintain and avoid making mistakes.
#   - There was some code in here that I found legitimately worrying... and an extremly convuluted way to do an extremely simple thing. It's been banished.
#   - Refactored the hell out of this thing. If you compared it to the original version, you wouldn't think the two were related. I don't think Git does, either.

from dataclasses import dataclass
import os.path
import math
from typing import Optional, List

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
from cura.Settings.SettingOverrideDecorator import SettingOverrideDecorator


from UM.Resources import Resources
from UM.Logger import Logger
from UM.Message import Message
from UM.Math.Vector import Vector
from UM.Math.Polygon import Polygon  # Not strictly needed; not bothering implementing imports just for type checking
from UM.Tool import Tool
from UM.Event import Event, MouseEvent
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Settings.SettingInstance import SettingInstance
from UM.Settings.SettingDefinition import SettingDefinition
from UM.Settings.DefinitionContainer import DefinitionContainer
from UM.Settings.ContainerRegistry import ContainerRegistry
from UM.Settings.InstanceContainer import InstanceContainer
from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from UM.Scene.Selection import Selection
from UM.Scene.SceneNode import SceneNode
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.i18n import i18nCatalog

from .slasheetools import log_debug as log

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

        # Stock Data
        self._all_created_spoons: List[SceneNode] = []

        # variable for menu dialog
        self._spoon_diameter = 10.0
        self._handle_length = 2.0
        self._handle_width = 2.0
        self._initial_layer_speed = 0.0
        self._layer_count = 1
        self._direct_shape = False

        # Shortcut
        self._shortcut_key = Qt.Key.Key_K

        self._controller = self.getController()

        self._selection_pass = None

        self._application = CuraApplication.getInstance()

        self.setExposedProperties("SSize", "SLength", "SWidth", "NLayer", "ISpeed", "DirectShape")

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
        self._preferences.addPreference("spoonawreborn/initial_layer_speed", 0)
        self._preferences.addPreference("spoonawreborn/layer_count", 1)
        self._preferences.addPreference("spoonawreborn/direct_shape", False)


        self._spoon_diameter = float(self._preferences.getValue("spoonawreborn/spoon_diameter"))
        self._handle_length = float(self._preferences.getValue("spoonawreborn/handle_length"))
        self._handle_width = float(self._preferences.getValue("spoonawreborn/handle_width"))
        self._initial_layer_speed = float(self._preferences.getValue("spoonawreborn/initial_layer_speed"))
        self._layer_count = int(self._preferences.getValue("spoonawreborn/layer_count"))
        self._direct_shape = bool(self._preferences.getValue("spoonawreborn/direct_shape"))


    def event(self, event) -> None:
        super().event(event)
        modifiers = QApplication.keyboardModifiers()
        ctrl_is_active = modifiers & Qt.KeyboardModifier.ControlModifier

        if event.type == Event.MousePressEvent and MouseEvent.LeftButton in event.buttons and self._controller.getToolsEnabled():
            if ctrl_is_active:
                self._controller.setActiveTool("RotateTool")
                return

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
                return

            node_stack: PerObjectContainerStack = picked_node.callDecoration("getStack")

            if node_stack:
                # if it's a spoon_mesh -> remove it
                if node_stack.getProperty("spoon_mesh", "value"):
                    self._removeSpoonMesh(picked_node)
                    return

                if not self._is_normal_object(node_stack):
                    # Only "normal" meshes can have spoon_mesh added to them
                    # Try to add also to support but as support got a X/Y distance/ part it's useless
                    return

            # Create a pass for picking a world-space location from the mouse location
            active_camera = self._controller.getScene().getActiveCamera()
            picking_pass = PickingPass(active_camera.getViewportWidth(), active_camera.getViewportHeight())
            picking_pass.render()

            picked_position = picking_pass.getPickedPosition(event.x, event.y)

            # Logger.log('d', "X : {}".format(picked_position.x))
            # Logger.log('d', "Y : {}".format(picked_position.y))
            # Logger.log('d', "Name : {}".format(node_stack.getName()))

            # Add the spoon_mesh at the picked location
            self._createSpoonMesh(picked_node, picked_position)


    def _createSpoonMesh(self, parent: CuraSceneNode, position: Vector):
        node = CuraSceneNode()

        # local_transformation = parent.getLocalTransformation()
        # Logger.log('d', "Parent local_transformation --> " + str(local_transformation))

        node.setName("SpoonTab")
        node.setSelectable(True)

        # long=Support Height
        height_offset=position.y

        # This function can be triggered in the middle of a machine change, so do not proceed if the machine change has not done yet.
        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        #extruder = global_container_stack.extruderList[int(_id_ex)]
        extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()[0]
        #self._Extruder_count=global_container_stack.getProperty("machine_extruder_count", "value")

        _layer_height_0 = extruder_stack.getProperty("layer_height_0", "value")
        _layer_height = extruder_stack.getProperty("layer_height", "value")
        _spoon_height = (_layer_height_0 * 1.2) + (_layer_height * (self._layer_count -1) )

        _angle = self.defineAngle(parent, position)
        # Logger.log('d', "Info createSpoonMesh Angle --> " + str(_angle))

        # Spoon creation Diameter , Length, Width, Increment angle 10°, length, layer_height_0*1.2
        mesh = self._createSpoon(self._spoon_diameter,self._handle_length,self._handle_width, 10, height_offset, _spoon_height, self._direct_shape, _angle)

        # new_transformation = Matrix()
        node.setMeshData(mesh.build())

        active_build_plate = CuraApplication.getInstance().getMultiBuildPlateModel().activeBuildPlate
        node.addDecorator(BuildPlateDecorator(active_build_plate))
        node.addDecorator(SliceableObjectDecorator())

        stack: PerObjectContainerStack = node.callDecoration("getStack") # created by SettingOverrideDecorator that is automatically added to CuraSceneNode
        settings: InstanceContainer = stack.getTop()
        settings.setProperty("spoon_mesh", "value", True)

        definition = stack.getSettingDefinition("meshfix_union_all")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", False)
        new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)

        # speed_layer_0
        if self._initial_layer_speed > 0 :
            definition = stack.getSettingDefinition("speed_layer_0")
            new_instance = SettingInstance(definition, settings)
            new_instance.setProperty("value", self._initial_layer_speed) # initial layer speed
            new_instance.resetState()  # Ensure that the state is not seen as a user state.
            settings.addInstance(new_instance)

        definition = stack.getSettingDefinition("infill_mesh_order")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", 49) #50 "maximum_value_warning": "50"
        new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)

        """definition = stack.getSettingDefinition("spoon_mesh")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", True)
        new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)"""

        #self._op = GroupedOperation()
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
        type_spoon_mesh = node_stack.getProperty("spoon_mesh", "value")
        type_anti_overhang_mesh = node_stack.getProperty("anti_overhang_mesh", "value")

        return not any((type_infill_mesh, type_cutting_mesh, type_support_mesh, type_spoon_mesh, type_anti_overhang_mesh))

    def _tangential_point_on_circle(self, center, radius, start_point):
        """Return 2 tangenital points of circle from a given point"""
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

    # SPOON creation
    def _createSpoon(self, size, handle_length, handle_width, segments,
                     height, max_y, direct_shape, angle):
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

        if direct_shape:
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

                    if direct_shape :
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
        if self._all_created_spoons:
            for node in self._all_created_spoons:
                node_stack: PerObjectContainerStack = node.callDecoration("getStack")
                if node_stack.getProperty("spoon_mesh", "value"):
                    self._removeSpoonMesh(node)
            self._all_created_spoons = []
            self.propertyChanged.emit()
        else:
            for node in DepthFirstIterator(self._application.getController().getScene().getRoot()):
                if node.callDecoration("getStack"):  # Has a SettingOverrideDecorator
                    node_stack: PerObjectContainerStack = node.callDecoration("getStack")
                    if node_stack.hasProperty("spoon_mesh", "value"):
                        self._removeSpoonMesh(node)

    # Source code from MeshTools Plugin
    # Copyright (c) 2020 Aldo Hoeben / fieldOfView
    def _getAllSelectedNodes(self) -> List[SceneNode]:
        selection = Selection.getAllSelectedObjects()[:]
        if selection:
            deep_selection = []  # type: List[SceneNode]
            for selected_node in selection:
                if selected_node.hasChildren():
                    deep_selection = deep_selection + selected_node.getAllChildren()
                if selected_node.getMeshData() is not None:
                    deep_selection.append(selected_node)
            if deep_selection:
                return deep_selection

        # Message(catalog.i18nc("@info:status", "Please select one or more models first"))

        return []


    def defineAngle(self, node: CuraSceneNode, spoon_position: Vector) -> float:
        """Computes the angle to a point on the convex hull for the spoon to point at."""
        hull_scale_factor: float = 1.1
        
        result_angle = 0
        min_length = math.inf
        # Set on the build plate for distance
        start_position = Vector(spoon_position.x, 0, spoon_position.z)

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

        hull_polygon = object_hull.scale(hull_scale_factor)
        
        hull_points = hull_polygon.getPoints()
        # nb_pt = point[0] / point[1] must be divided by 2
        # Angle Ref for angle / Y Dir
        angle_reference = Vector(0, 0, 1)
        start_index=0
        end_index=0

        # Find point closest to start position
        for index, point in enumerate(hull_points):
            # Logger.log('d', "Point : {}".format(point))
            test_position = Vector(point[0], 0, point[1])
            difference_vector = start_position - test_position
            length = difference_vector.length()

            if 0 < length < min_length:
                min_length = length
                start_index = index
                angle_vector = difference_vector.normalized()
                calculated_angle = math.asin(angle_reference.dot(angle_vector))
                #LeCos = math.acos(ref.dot(unit_vector2))

                if angle_vector.x >= 0:
                    result_angle = math.pi + calculated_angle  #angle in radian
                else :
                    result_angle = -calculated_angle

            if length == min_length and length > 0:
                if index > end_index + 1:
                    start_index = index
                    end_index = index
                else:
                    end_index = index

        # Sometimes automatic creation (rarely from a PickingPass) multiple "closest"
        if start_index != end_index :
            # Get the hull point halfway between the two closest indices
            index = round(start_index + 0.5 * (end_index - start_index))
            test_position = Vector(hull_points[index][0], 0, hull_points[index][1])
            difference_vector = start_position - test_position
            angle_vector = difference_vector.normalized()
            calculated_angle = math.asin(angle_reference.dot(angle_vector))
            # LeCos = math.acos(ref.dot(unit_vector2))

            if angle_vector.x >= 0:
                result_angle = math.pi + calculated_angle  #angle in radian
            else :
                result_angle = -calculated_angle

        # Logger.log('d', "Pick_position   : {}".format(calc_position))
        # Logger.log('d', "Close_position  : {}".format(Select_position))
        # Logger.log('d', "Unit_vector2    : {}".format(unit_vector2))
        # Logger.log('d', "Angle Sinus     : {}".format(math.degrees(LeSin)))
        # Logger.log('d', "Angle Cosinus   : {}".format(math.degrees(LeCos)))
        # Logger.log('d', "Chose Angle     : {}".format(math.degrees(Angle)))
        return result_angle
    
    # Automatic creation
    def addAutoSpoonMesh(self) -> None:

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
                # Make sure not to place spoons too close together
                first_to_last_distance = (first_point - point_position).length() if i == len(points) - 1 else 0

                if difference_length >= minimum_spoon_gap or first_to_last_distance >= minimum_spoon_gap:
                    self._createSpoonMesh(node, point_position)
                    last_spoon_position = point_position

    def getSSize(self) -> float:
        """
            return: global _UseSize  in mm.
        """
        return self._spoon_diameter

    def setSSize(self, SSize: str) -> None:
        """
        param SSize: Size in mm.
        """

        try:
            s_value = float(SSize)
        except ValueError:
            return

        if s_value <= 0:
            return
        #Logger.log('d', 's_value : ' + str(s_value))
        self._spoon_diameter = s_value
        self._preferences.setValue("spoonawreborn/spoon_diameter", s_value)

    def getSLength(self) -> float:
        """
            return: global _UseLength  in mm.
        """
        return self._handle_length

    def setSLength(self, SLength: str) -> None:
        """
        param SLength: SLength in mm.
        """

        try:
            s_value = float(SLength)
        except ValueError:
            return

        if s_value < 0:
            return
        #Logger.log('d', 's_value : ' + str(s_value))
        self._handle_length = s_value
        self._preferences.setValue("spoonawreborn/handle_length", s_value)

    def getSWidth(self) -> float:
        """
            return: global _UseWidth  in mm.
        """
        return self._handle_width

    def setSWidth(self, SWidth: str) -> None:
        """
        param SWidth : Width in mm.
        """

        try:
            s_value = float(SWidth)
        except ValueError:
            return

        if s_value < 0:
            return
        #Logger.log('d', 's_value : ' + str(s_value))
        self._handle_width = s_value
        self._preferences.setValue("spoonawreborn/handle_width", s_value)

    def getISpeed(self) -> float:
        """
            return: global _InitialLayerSpeed  in mm/s.
        """
        return self._initial_layer_speed

    def setISpeed(self, ISpeed: str) -> None:
        """
        param ISpeed : ISpeed in mm/s.
        """

        try:
            s_value = float(ISpeed)
        except ValueError:
            return

        if s_value < 0:
            return
        # Logger.log('d', 'ISpeed : ' + str(s_value))
        self._initial_layer_speed = s_value
        self._preferences.setValue("spoonawreborn/initial_layer_speed", s_value)

    def getNLayer(self) -> int:
        """
            return: global _Nb_Layer
        """
        return self._layer_count

    def setNLayer(self, NLayer: str) -> None:
        """
        param NLayer: NLayer as integer >1
        """

        try:
            i_value = int(NLayer)

        except ValueError:
            return

        if i_value < 1:
            return

        #Logger.log('d', 'i_value : ' + str(i_value))
        self._layer_count = i_value
        self._preferences.setValue("spoonawreborn/layer_count", i_value)

    def getDirectShape(self )-> bool:
        return self._direct_shape

    def setDirectShape(self, value: bool) -> None:
        # Logger.log("w", "setDirectShape {}".format(value))
        self._direct_shape = value
        self.propertyChanged.emit()
        self._preferences.setValue("spoonawreborn/direct_shape", self._direct_shape)
