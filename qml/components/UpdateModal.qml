import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: updateModalRoot
    visible: opacity > 0
    anchors.fill: parent
    color: "#CC0B0D12"
    z: 1100

    property var updater: null
    property bool isOpen: false

    opacity: isOpen ? 1.0 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: {} // Prevent click-through
    }

    Rectangle {
        id: dialogBox
        width: Math.min(updateModalRoot.width - 40, 520)
        height: Math.min(updateModalRoot.height - 40, 420)
        anchors.centerIn: parent
        radius: 12
        color: "#131722"
        border.color: "#38BDF8"
        border.width: 1

        scale: updateModalRoot.isOpen ? 1.0 : 0.9
        Behavior on scale {
            NumberAnimation { duration: 240; easing.type: Easing.OutBack }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 14

            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: "✨ " + (updater && updater.isReady ? "Update Ready to Install" : "Update Available")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 18
                    font.weight: Font.Bold
                    color: "#F8FAFC"
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    width: 24; height: 24; radius: 12
                    color: closeM.containsMouse ? "#334155" : "transparent"
                    Text { anchors.centerIn: parent; text: "×"; font.pixelSize: 16; color: "#94A3B8" }
                    MouseArea {
                        id: closeM
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            updateModalRoot.isOpen = false;
                        }
                    }
                }
            }

            // Version Comparison Row
            Rectangle {
                Layout.fillWidth: true
                height: 56
                radius: 8
                color: "#1A202C"
                border.color: "#2D3748"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12

                    Column {
                        Layout.fillWidth: true
                        Text {
                            text: "CURRENT"
                            font.pixelSize: 10
                            font.weight: Font.Bold
                            color: "#64748B"
                        }
                        Text {
                            text: updater ? updater.currentVersion : "--"
                            font.pixelSize: 14
                            font.family: "Cascadia Code, monospace"
                            font.weight: Font.DemiBold
                            color: "#94A3B8"
                        }
                    }

                    Text {
                        text: "➔"
                        font.pixelSize: 16
                        color: "#38BDF8"
                    }

                    Column {
                        Layout.fillWidth: true
                        Text {
                            text: "LATEST ON GITHUB"
                            font.pixelSize: 10
                            font.weight: Font.Bold
                            color: "#38BDF8"
                        }
                        Text {
                            text: updater ? updater.latestVersion : "--"
                            font.pixelSize: 14
                            font.family: "Cascadia Code, monospace"
                            font.weight: Font.Bold
                            color: "#34D399"
                        }
                    }
                }
            }

            // Commit / Release Message Box
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: "WHAT'S NEW"
                    font.pixelSize: 10
                    font.weight: Font.Bold
                    color: "#94A3B8"
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 68
                    radius: 6
                    color: "#0F131C"
                    border.color: "#242C3D"
                    border.width: 1

                    ScrollView {
                        anchors.fill: parent
                        anchors.margins: 8
                        clip: true

                        Text {
                            width: parent.width
                            text: updater && updater.commitMessage ? updater.commitMessage : "Maintenance and feature updates."
                            font.pixelSize: 12
                            color: "#CBD5E1"
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }

            // Download Progress / Status Section
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                visible: updater && (updater.isDownloading || updater.isReady)

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: updater ? updater.statusMessage : ""
                        font.pixelSize: 12
                        color: updater && updater.isReady ? "#34D399" : "#38BDF8"
                        Layout.fillWidth: true
                    }
                    Text {
                        text: updater ? updater.downloadSpeed : ""
                        font.pixelSize: 11
                        font.family: "Cascadia Code, monospace"
                        color: "#94A3B8"
                        visible: updater && updater.isDownloading
                    }
                }

                // Progress Bar
                Rectangle {
                    Layout.fillWidth: true
                    height: 8
                    radius: 4
                    color: "#1E293B"
                    clip: true

                    Rectangle {
                        width: parent.width * (updater ? updater.downloadProgress : 0)
                        height: parent.height
                        radius: 4
                        color: updater && updater.isReady ? "#10B981" : "#38BDF8"
                        Behavior on width {
                            NumberAnimation { duration: 150 }
                        }
                    }
                }
            }

            // Idle status label when not downloading
            Text {
                text: updater ? updater.statusMessage : ""
                font.pixelSize: 12
                color: "#94A3B8"
                Layout.fillWidth: true
                visible: updater && !updater.isDownloading && !updater.isReady
            }

            Item { Layout.fillHeight: true }

            // Action Buttons Footer
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Later / Dismiss
                Rectangle {
                    height: 36
                    implicitWidth: 100
                    radius: 6
                    color: laterM.containsMouse ? "#273142" : "#1E2430"
                    border.color: "#374151"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "Later"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: "#94A3B8"
                    }

                    MouseArea {
                        id: laterM
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: updateModalRoot.isOpen = false
                    }
                }

                Item { Layout.fillWidth: true }

                // Action Button: Download OR Apply & Restart
                Rectangle {
                    height: 36
                    implicitWidth: actionText.implicitWidth + 28
                    radius: 6
                    color: {
                        if (actionM.containsMouse) {
                            return (updater && updater.isReady) ? "#059669" : "#0284C7";
                        }
                        return (updater && updater.isReady) ? "#10B981" : "#0EA5E9";
                    }

                    Text {
                        id: actionText
                        anchors.centerIn: parent
                        text: "🚀 Update Now"
                        font.pixelSize: 13
                        font.weight: Font.Bold
                        color: "#0F172A"
                    }

                    MouseArea {
                        id: actionM
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        enabled: updater && !updater.isDownloading
                        onClicked: {
                            if (updater) {
                                if (updater.isReady) {
                                    updater.applyAndRestart();
                                } else {
                                    updater.startDownload();
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
