/* 
 * Path of Trading - PoE2 Price Checker UI
 * Copyright (C) 2026 brendancohan
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Quickshell.Io

PanelWindow {
    id: window
    color: "transparent"
    anchors.top: true
    anchors.bottom: true
    anchors.left: true
    anchors.right: true
    exclusiveZone: 0

    function s(val) { return val; } // Standard 1:1 scaling for standalone

    readonly property color base: "#1e1e2e"
    readonly property color text: "#cdd6f4"
    readonly property color blue: "#89b4fa"
    readonly property color yellow: "#f9e2af"
    readonly property color surface2: "#585b70"
    readonly property color subtext0: "#a6adc8"

    property real introMain: 0
    SequentialAnimation {
        running: true
        PauseAnimation { duration: 20 }
        NumberAnimation { target: window; property: "introMain"; from: 0; to: 1.0; duration: 800; easing.type: Easing.OutQuart }
    }

    Shortcut {
        sequence: "Escape"
        onActivated: Qt.quit()
    }

    property var priceData: ({ "status": "loading", "item": "Loading...", "listings": [], "parsed_stats": [], "leagues": [], "selected_league": "" })

    Process {
        id: dataReader
        command: ["cat", Quickshell.env("HOME") + "/.cache/pathoftrading-v1.0/price_data.json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    window.priceData = JSON.parse(this.text);
                } catch (e) {
                    console.log("Error parsing price JSON: " + e);
                }
            }
        }
    }

    Timer {
        interval: 300 
        running: window.visible && window.priceData.status === "loading"
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            dataReader.running = false;
            dataReader.running = true;
        }
    }

    // Process to trigger the backend requery
    Process {
        id: requeryProcess
        onExited: {
            dataReader.running = false;
            dataReader.running = true;
        }
    }

    Item {
        anchors.fill: parent
        scale: 0.95 + (0.05 * introMain)
        opacity: introMain

        // Root MouseArea to close on click-outside
        MouseArea {
            anchors.fill: parent
            onClicked: Qt.quit()
        }

        Rectangle {
            id: innerBg
            width: window.s(950)
            height: window.s(500)
            
            // Stable centering logic
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            
            radius: window.s(20)
            color: window.base
            border.color: window.surface2
            border.width: 1
            clip: true

            // Drag Logic
            property point lastMousePos
            MouseArea {
                anchors.fill: parent
                onPressed: (mouse) => innerBg.lastMousePos = Qt.point(mouse.x, mouse.y)
                onPositionChanged: (mouse) => {
                    if (pressed) {
                        innerBg.x += mouse.x - innerBg.lastMousePos.x
                        innerBg.y += mouse.y - innerBg.lastMousePos.y
                    }
                }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: window.s(25)
                spacing: window.s(15)

                RowLayout {
                    Layout.fillWidth: true
                    spacing: window.s(10)

                    Flow {
                        Layout.fillWidth: true
                        spacing: window.s(8)
                        visible: window.priceData && window.priceData.base_properties && window.priceData.base_properties.length > 0
                        
                        Repeater {
                            model: (window.priceData && window.priceData.base_properties) ? window.priceData.base_properties : []
                            delegate: Rectangle {
                                color: modelData.active ? window.blue : "transparent"
                                border.color: window.blue
                                border.width: 1
                                radius: window.s(15)
                                height: window.s(26)
                                width: propText.implicitWidth + window.s(20)

                                Text {
                                    id: propText
                                    anchors.centerIn: parent
                                    text: modelData.text !== undefined ? modelData.text : ""
                                    color: modelData.active ? window.base : window.text
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: window.s(12)
                                    font.bold: true
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        var newData = JSON.parse(JSON.stringify(window.priceData));
                                        newData.base_properties[index].active = !newData.base_properties[index].active;
                                        window.priceData = newData;
                                    }
                                }
                            }
                        }
                    }

                    // --- Game & League Dropdowns ---
                    RowLayout {
                        spacing: window.s(10)
                        Layout.alignment: Qt.AlignRight | Qt.AlignTop

                        ComboBox {
                            id: gameBox
                            Layout.preferredWidth: window.s(100)
                            model: ["PoE 2", "PoE 1"]
                            currentIndex: 0
                            
                            delegate: ItemDelegate {
                                width: gameBox.width
                                text: modelData
                                highlighted: gameBox.highlightedIndex === index
                                enabled: index === 0 // PoE 1 disabled
                                contentItem: Text {
                                    text: gameBox.textRole ? (Array.isArray(gameBox.model) ? modelData[gameBox.textRole] : model[gameBox.textRole]) : modelData
                                    color: index === 0 ? window.text : window.subtext0
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: window.s(11)
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            background: Rectangle {
                                color: window.surface2
                                radius: window.s(5)
                            }
                            contentItem: Text {
                                text: gameBox.displayText
                                color: window.text
                                font.family: "JetBrains Mono"
                                font.pixelSize: window.s(11)
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: window.s(10)
                            }
                        }

                        ComboBox {
                            id: leagueBox
                            Layout.preferredWidth: window.s(160)
                            model: (window.priceData && window.priceData.leagues) ? window.priceData.leagues : []
                            
                            currentIndex: {
                                if (!window.priceData || !window.priceData.leagues || !window.priceData.selected_league) return 0;
                                return window.priceData.leagues.indexOf(window.priceData.selected_league);
                            }

                            onActivated: (index) => {
                                var newData = JSON.parse(JSON.stringify(window.priceData));
                                newData.selected_league = leagueBox.model[index];
                                window.priceData = newData;
                            }

                            background: Rectangle {
                                color: window.surface2
                                radius: window.s(5)
                            }
                            contentItem: Text {
                                text: leagueBox.displayText
                                color: window.text
                                font.family: "JetBrains Mono"
                                font.pixelSize: window.s(11)
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: window.s(10)
                            }
                        }
                    }
                }

                Text {
                    text: (window.priceData && window.priceData.item) ? window.priceData.item.toUpperCase() : "UNKNOWN ITEM"
                    color: window.text
                    font.family: "JetBrains Mono"
                    font.weight: Font.Black
                    font.pixelSize: window.s(20)
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    visible: !window.priceData || !window.priceData.base_properties || window.priceData.base_properties.length === 0
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: window.s(2)
                    color: Qt.alpha(window.surface2, 0.4)
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: window.s(20)

                    // LEFT COLUMN: Listings
                    Rectangle {
                        Layout.fillHeight: true
                        Layout.preferredWidth: window.s(300)
                        color: "transparent"

                        Text {
                            id: statusText
                            text: {
                                if (window.priceData && (window.priceData.status === "loading" || window.priceData.status === "requerying")) {
                                    return "Searching market...";
                                }
                                if (window.priceData && window.priceData.listings && window.priceData.listings.length > 0) {
                                    return "Top Listings";
                                }
                                return window.priceData.price || "No matching listings";
                            }
                            color: window.yellow
                            font.family: "JetBrains Mono"
                            font.pixelSize: window.s(14)
                            font.bold: true
                            anchors.top: parent.top
                            anchors.horizontalCenter: parent.horizontalCenter
                            horizontalAlignment: Text.AlignHCenter
                            width: parent.width
                            wrapMode: Text.Wrap
                        }

                        ScrollView {
                            anchors.top: statusText.bottom
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.topMargin: window.s(10)
                            clip: true

                            ColumnLayout {
                                width: parent.width
                                spacing: window.s(8)

                                Repeater {
                                    model: (window.priceData && window.priceData.listings) ? window.priceData.listings : []
                                    delegate: Rectangle {
                                        Layout.fillWidth: true
                                        height: window.s(35)
                                        color: Qt.alpha(window.surface2, 0.2)
                                        radius: window.s(8)
                                        border.color: Qt.alpha(window.surface2, 0.4)
                                        border.width: 1
                                        
                                        Text {
                                            anchors.centerIn: parent
                                            text: {
                                                var txt = modelData.display !== undefined ? modelData.display : "?";
                                                if (modelData.age) {
                                                    txt += " • " + modelData.age;
                                                }
                                                return txt;
                                            }
                                            color: window.yellow
                                            font.family: "JetBrains Mono"
                                            font.weight: Font.Bold
                                            font.pixelSize: window.s(13)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Divider
                    Rectangle {
                        Layout.fillHeight: true
                        width: window.s(2)
                        color: Qt.alpha(window.surface2, 0.4)
                        visible: !(window.priceData && window.priceData.raw_item && window.priceData.raw_item.isBulk)
                    }

                    // RIGHT COLUMN: Stat Modifiers
                    ColumnLayout {
                        Layout.fillHeight: true
                        Layout.fillWidth: true
                        spacing: window.s(10)
                        visible: !(window.priceData && window.priceData.raw_item && window.priceData.raw_item.isBulk)

                        Text {
                            text: "Stat Filters"
                            color: window.yellow
                            font.family: "JetBrains Mono"
                            font.pixelSize: window.s(14)
                            font.bold: true
                            Layout.alignment: Qt.AlignHCenter
                        }

                        ScrollView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true

                            ColumnLayout {
                                width: parent.width
                                spacing: window.s(10)

                                Repeater {
                                    model: (window.priceData && window.priceData.parsed_stats) ? window.priceData.parsed_stats : []
                                    delegate: Rectangle {
                                        Layout.fillWidth: true
                                        height: window.s(50)
                                        color: Qt.alpha(window.surface2, 0.1)
                                        radius: window.s(8)
                                        
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: window.s(5)
                                            spacing: window.s(10)

                                            CheckBox {
                                                checked: modelData.active !== undefined ? modelData.active : true
                                                onCheckedChanged: {
                                                    window.priceData.parsed_stats[index].active = checked;
                                                }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: window.s(8)

                                                MouseArea {
                                                    anchors.fill: parent
                                                    onClicked: {
                                                        // Toggle the active state
                                                        var newData = JSON.parse(JSON.stringify(window.priceData));
                                                        newData.parsed_stats[index].active = !newData.parsed_stats[index].active;
                                                        window.priceData = newData;
                                                    }
                                                }

                                                Rectangle {
                                                    visible: modelData.tier !== undefined && modelData.tier !== null
                                                    Layout.preferredWidth: window.s(30)
                                                    Layout.preferredHeight: window.s(20)
                                                    radius: window.s(4)
                                                    color: modelData.tier === 1 ? "#FFD700" : (modelData.tier === 2 ? window.blue : window.surface2)
                                                    
                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "T" + modelData.tier
                                                        color: modelData.tier === 1 ? "black" : (modelData.tier === 2 ? window.base : window.text)
                                                        font.family: "JetBrains Mono"
                                                        font.pixelSize: modelData.tier === 1 ? window.s(12) : window.s(10)
                                                        font.bold: modelData.tier <= 2
                                                    }
                                                }

                                                Text {
                                                    textFormat: Text.RichText
                                                    text: {
                                                        if (modelData.text === undefined) return "";
                                                        return modelData.text.replace(/([+-]?\d+(?:\.\d+)?)(?:\([^)]+\))?/g, function(match, p1) {
                                                            var remainder = match.substring(p1.length);
                                                            return "<span style=\"color: " + window.blue + "; font-size: " + window.s(13) + "px;\"><b>" + p1 + "</b></span>" + remainder;
                                                        });
                                                    }
                                                    color: window.text
                                                    font.family: "JetBrains Mono"
                                                    font.pixelSize: window.s(12)
                                                    Layout.fillWidth: true
                                                    elide: Text.ElideRight
                                                    wrapMode: Text.Wrap
                                                }
                                            }

                                            TextField {
                                                Layout.preferredWidth: window.s(55)
                                                placeholderText: "Min"
                                                text: modelData.min !== undefined ? modelData.min : ""
                                                font.family: "JetBrains Mono"
                                                font.pixelSize: window.s(12)
                                                selectByMouse: true
                                                onActiveFocusChanged: if (activeFocus) selectAll()
                                                onTextChanged: { window.priceData.parsed_stats[index].min = text; }
                                                onAccepted: requeryButton.clicked()
                                            }

                                            TextField {
                                                Layout.preferredWidth: window.s(55)
                                                placeholderText: "Max"
                                                text: modelData.max !== undefined ? modelData.max : ""
                                                font.family: "JetBrains Mono"
                                                font.pixelSize: window.s(12)
                                                selectByMouse: true
                                                onActiveFocusChanged: if (activeFocus) selectAll()
                                                onTextChanged: { window.priceData.parsed_stats[index].max = text; }
                                                onAccepted: requeryButton.clicked()
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Button {
                            id: requeryButton
                            Layout.fillWidth: true
                            Layout.preferredHeight: window.s(40)
                            text: "REQUERY TRADES"
                            font.family: "JetBrains Mono"
                            font.bold: true
                            onClicked: {
                                var payload = JSON.stringify(window.priceData);
                                
                                // Completely reassign the object to force the UI to recognize the state change
                                var newData = JSON.parse(payload);
                                newData.status = "requerying";
                                window.priceData = newData;
                                
                                requeryProcess.command = ["python3", Quickshell.env("HOME") + "/.local/share/pathoftrading-v1.0/backend.py", "--requery-data", payload];
                                requeryProcess.running = false;
                                requeryProcess.running = true;
                            }
                        }
                    }
                }
            }
        }
    }
}
