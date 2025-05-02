/*-----------------------------------------------------------------------------
Spoon Anti-Warping Reborn by Slashee the Cow
Copyright Slashee the Cow 2025-

A continuation of the "Spoon Anti-Warping" plugin by 5@xes 2023
https://github.com/5axes/SpoonAntiWarping

    QML Properties:
    "SpoonDiameter" : Diameter of circular part of spoon (float)
    "HandleLength"  : Length of spoon handle (float)
    "HandleWidth"   : Width of spoon handle (float)
    "LayerCount"    : Number of layers (int)
    "TeardropShape" : Create teardrop shaped "spoons" (bool)

-----------------------------------------------------------------------------*/

import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0

import UM 1.6 as UM
import Cura 1.1 as Cura

Item
{
    id: spoonRebornPanel

    function getCuraVersion(){
        if(CuraApplication.version){
            return CuraApplication.version();
        } else {
            return UM.Application.version;
        }
    }

    function compareVersions(version1, version2) {
        const v1 = String(version1).split(".");
        const v2 = String(version2).split(".");

        for (let i = 0; i < Math.max(v1.length, v2.length); i++) {
            const num1 = parseInt(v1[i] || 0); // Handle missing components
            const num2 = parseInt(v2[i] || 0);

            if (num1 < num2) return -1;
            if (num1 > num2) return 1;
        }
        return 0; // Versions are equal
    }

    function isVersion57OrGreater(){
        //let version = CuraApplication ? CuraApplication.version() : (UM.Application ? UM.Application.version : null);
        let version = getCuraVersion()
        if(version){
            return compareVersions(version, "5.7.0") >= 0;
        } else {
            return False;
        }
    }

    function getProperty(propertyName){
        if(isVersion57OrGreater()){
            return UM.Controller.properties.getValue(propertyName);
        } else {
            return UM.ActiveTool.properties.getValue(propertyName);
        }
    }

    function setProperty(propertyName, value){
        if(isVersion57OrGreater()){
            return UM.Controller.setProperty(propertyName, value);
        } else {
            return UM.ActiveTool.setProperty(propertyName, value);
        }
    }

    function triggerAction(action){
        if(isVersion57OrGreater()){
            return UM.Controller.triggerAction(action);
        } else {
            return UM.ActiveTool.triggerAction(action);
        }
    }

    function triggerActionWithData(action, data){
        if(isVersion57OrGreater()){
            return UM.Controller.triggerActionWithData(action, data);
        } else {
            return UM.ActiveTool.triggerActionWithData(action, data);
        }
    }

    function validateInt(test, min_value = -Infinity, max_value = Infinity){
        if (test === ""){return false;}
        let intTest = parseInt(test);
        if (isNaN(intTest)){return false;}
        if (intTest < min_value){return false;}
        if (intTest > max_value){return false;}
        return true;
    }

    function validateFloat(test, min_value = -Infinity, max_value = Infinity){
        if (test === ""){return false;}
        test = test.replace(",","."); // Use decimal separator computer expects
        let floatTest = parseFloat(test);
        if (isNaN(floatTest)){return false;}
        if (floatTest < min_value){return false;}
        if (floatTest > max_value){return false;}
        return true;
    }

    property var default_field_background: UM.Theme.getColor("detail_background")
    property var error_field_background: UM.Theme.getColor("setting_validation_error_background")

    function getBackgroundColour(valid){
        return valid ? default_field_background : error_field_background
    }

    function validateInputs(){
        let message = "";
        let spoon_diameter_valid = true;
        let handle_length_valid = true;
        let handle_width_valid = true;
        let layer_count_valid = true;

        if (!validateFloat(spoonDiameter, 1)){
            spoon_diameter_valid = false;
            message += catalog.i18nc("spoon_diameter_invalid", "Spoon diameter must be at least 1mm.\n");
        }
        if (!validateFloat(handleLength, 0.1)){
            handle_length_valid = false;
            message += catalog.i18nc("handle_length_invalid", "Handle length must be at least 0.1mm.\n");
        }
        if (!validateFloat(handleWidth, 0.1)){
            handle_width_valid = false;
            message += catalog.i18nc("handle_width_invalid", "Handle width must be at least 0.1mm.\n");
        }
        if (!validateInt(layerCount, 1, 100)){
            layer_count_valid = false;
            message += catalog.i18nc("layer_count_invalid", "Layer count must be between 1 and 100\n")
        }

        if (spoon_diameter_valid && handle_width_valid){
            if (parseFloat(handleWidth) >= parseFloat(spoonDiameter)){
                spoon_diameter_valid = false;
                handle_width_valid = false;
                message += catalog.i18nc("spoon_diameter_handle_width", "Spoon diameter must be higher than handle width.\n")
            }
        }

        if (spoon_diameter_valid && handle_length_valid && handle_width_valid && layer_count_valid){
            setProperty("SpoonDiameter", parseFloat(spoonDiameter))
            setProperty("HandleLength", parseFloat(handleLength))
            setProperty("HandleWidth", parseFloat(handleWidth))
            setProperty("LayerCount", parseInt(layerCount))
            inputsValid = true
            setProperty("InputsValid", inputsValid)
        } else {
            inputsValid = false
            setProperty("InputsValid", inputsValid)
        }
        errorMessage =  message
        diameterTextField.background.color = getBackgroundColour(spoon_diameter_valid)
        lengthTextField.background.color = getBackgroundColour(handle_length_valid)
        widthTextField.background.color = getBackgroundColour(handle_width_valid)
        layerTextField.background.color = getBackgroundColour(layer_count_valid)
    }

    property string errorMessage: ""

    property string spoonDiameter: ""
    property string handleLength: ""
    property string handleWidth: ""
    property string layerCount: ""
    property bool teardropShape: false
    property string notifications: getProperty("Notifications")
    
    property bool inputsValid: false

    width: childrenRect.width
    height: childrenRect.height
    UM.I18nCatalog { id: catalog; name: "spoonawreborn"}

    Component.onCompleted: {
        spoonDiameter = getProperty("SpoonDiameter")
        handleLength = getProperty("HandleLength")
        handleWidth = getProperty("HandleWidth")
        layerCount = getProperty("LayerCount")
        teardropShape = getProperty("TeardropShape")
        teardrop_checkbox.checked = teardropShape
        Qt.callLater(validateInputs)
        printOrderBox.currentIndex = printOrderBox.find(getProperty("PrintOrder"))
        autoDensityBox.currentIndex = autoDensityBox.find(getProperty("AutoDensity"))
    }
	
	property int localwidth: UM.Theme.getSize("setting_control").width
    property int textFieldMinWidth: 75

    RowLayout{
        id: mainRow
        anchors.top: parent.top
        anchors.left: parent.left

        ColumnLayout{
            id: mainColumn
            Layout.alignment: Qt.AlignLeft | Qt.AlignTop

            UM.Label{
                id: errorDisplay
                Layout.fillWidth: true
                Layout.maximumWidth: 175
                visible: errorMessage != ""
                text: errorMessage
                color: UM.Theme.getColor("error")
                wrapMode: Text.Wrap
            }

            GridLayout{
                id: textfields

                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop

                columns: 2
                columnSpacing: UM.Theme.getSize("default_margin").width
                rowSpacing: UM.Theme.getSize("default_margin").height

                UM.Label{
                    text: catalog.i18nc("@controls:label", "Spoon Diameter")
                }

                UM.TextFieldWithUnit
                {
                    id: diameterTextField
                    Layout.minimumWidth: textFieldMinWidth
                    height: UM.Theme.getSize("setting_control").height
                    unit: "mm"
                    text: spoonDiameter
                    validator: DoubleValidator
                    {
                        decimals: 1
                        bottom: 1
                        notation: DoubleValidator.StandardNotation
                    }

                    onTextChanged: {
                        spoonDiameter = text
                        Qt.callLater(validateInputs)
                    }
                }
                
                UM.Label
                {
                    text: catalog.i18nc("@controls:label", "Handle Length")
                }

                UM.TextFieldWithUnit
                {
                    id: lengthTextField
                    Layout.minimumWidth: textFieldMinWidth
                    height: UM.Theme.getSize("setting_control").height
                    unit: "mm"
                    text: handleLength
                    validator: DoubleValidator
                    {
                        decimals: 2
                        bottom: 0
                        notation: DoubleValidator.StandardNotation
                    }

                    onTextChanged: {
                        handleLength = text
                        Qt.callLater(validateInputs)
                    }
                }

                UM.Label
                {
                    text: catalog.i18nc("@controls:label", "Handle Width")
                }

                UM.TextFieldWithUnit
                {
                    id: widthTextField
                    Layout.minimumWidth: textFieldMinWidth
                    height: UM.Theme.getSize("setting_control").height
                    unit: "mm"
                    text: handleWidth
                    validator: DoubleValidator
                    {
                        decimals: 2
                        bottom: 0
                        notation: DoubleValidator.StandardNotation
                    }
                    onTextChanged: {
                        handleWidth = text
                        Qt.callLater(validateInputs)
                    }
                }
                
                UM.Label
                {
                    text: catalog.i18nc("@controls:label", "Number of Layers")
                }

                UM.TextFieldWithUnit
                {
                    id: layerTextField
                    Layout.minimumWidth: textFieldMinWidth
                    height: UM.Theme.getSize("setting_control").height
                    text: layerCount
                    validator: IntValidator
                    {
                        bottom: 1
                        top: 100
                    }

                    onTextChanged: {
                        layerCount = text
                        Qt.callLater(validateInputs)
                    }
                }

                UM.Label
                {
                    text: catalog.i18nc("@controls:label", "Print Order")
                }

                Cura.ComboBox
                {
                    id: printOrderBox
                    Layout.minimumWidth: textFieldMinWidth
                    Layout.minimumHeight: UM.Theme.getSize("setting_control").height
                    model: ["Unchanged", "Spoons first", "Spoons last"]
                    onActivated: {
                        setProperty("PrintOrder", currentText)
                    }
                }
                
                UM.CheckBox {
                    id: teardrop_checkbox
                    Layout.columnSpan: 2
                    text: catalog.i18nc("@option:check","Teardrop Shape")
                    checked: teardropShape
                    onClicked: {
                        teardropShape = checked
                        setProperty("TeardropShape", checked)
                    }
                }
            }
            
            Cura.TertiaryButton
            {
                id: removeAllButton
                height: UM.Theme.getSize("setting_control").height	
                text: catalog.i18nc("@button:remove_all", "Remove All")
                onClicked: triggerAction("removeAllSpoonMesh")
            }
                        
            Cura.SecondaryButton
            {
                id: addAutoButton
                height: UM.Theme.getSize("setting_control").height	
                text: catalog.i18nc("@label", "Add Automatically")
                onClicked: triggerAction("addAutoSpoonMesh")
            }

            RowLayout
            {
                spacing: UM.theme.getSize("default_margin").width
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignLeft | Qt.AlignTop
                
                UM.Label
                {
                    text: catalog.i18nc("@labels:auto_density", "Automatic Placement Density")
                }

                Cura.ComboBox
                {
                    id: autoDensityBox
                    Layout.minimumWidth: textFieldMinWidth
                    Layout.minimumHeight: UM.Theme.getSize("setting_control").height
                    model: ["Dense", "Normal", "Sparse"]
                    onActivated: {
                        setProperty("AutoDensity", currentText)
                    }
                }
            }
        }
        UM.Label {
            Layout.alignment: Qt.AlignTop
            Layout.leftMargin: UM.Theme.getSize("default_margin").width * 2
            text: notifications
            Layout.minimumWidth: notifications == "" ? 0 : 300
            Layout.maximumWidth: 300
            horizontalAlignment: Text.AlignLeft
            textFormat: Text.StyledText
            font.bold: true
            font.pointSize: 14
            wrapMode: Text.Wrap
        }
    }
}
