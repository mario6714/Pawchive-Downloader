import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: tutorialRoot
    visible: opacity > 0
    anchors.fill: parent
    color: "#D90B0D12"
    z: 1150

    property bool isOpen: false
    property int currentSectionIndex: 0
    property string searchQuery: ""

    opacity: isOpen ? 1.0 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: {} // Prevent click-through
    }

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    // Dynamic Localized Sections Data
    property var sections: (Lang && Lang.tutorialSections && Lang.tutorialSections.length > 0) ? Lang.tutorialSections : []
    readonly property var currentSection: (sections && sections.length > currentSectionIndex) ? sections[currentSectionIndex] : null

    // Main Modal Card
    Rectangle {
        id: dialogBox
        width: Math.min(tutorialRoot.width - 32, 980)
        height: Math.min(tutorialRoot.height - 32, 700)
        anchors.centerIn: parent
        radius: 12
        color: "#111622"
        border.color: "#28344E"
        border.width: 1
        clip: true

        scale: tutorialRoot.isOpen ? 1.0 : 0.92
        Behavior on scale {
            NumberAnimation { duration: 240; easing.type: Easing.OutBack }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ── Modal Header Bar ─────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                height: 54
                color: "#161D2C"
                border.color: "#222B3D"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 18
                    anchors.rightMargin: 18
                    spacing: 12

                    Text {
                        text: "📖"
                        font.pixelSize: 20
                    }

                    Column {
                        spacing: 1
                        Text {
                            text: tutorialRoot.tr("tutorial_modal_title", "Pawchive Downloader — Complete Manual & Feature Guide")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                        }
                        Text {
                            text: tutorialRoot.tr("tutorial_modal_subtitle", "In-depth documentation, tooltip reference, and workflow tutorials")
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                    }

                    Item { Layout.fillWidth: true }

                    // Close Button
                    Rectangle {
                        width: 28; height: 28; radius: 14
                        color: closeMouse.containsMouse ? "#334155" : "#1E293B"
                        Text { anchors.centerIn: parent; text: "×"; font.pixelSize: 18; color: "#94A3B8" }
                        MouseArea {
                            id: closeMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: tutorialRoot.isOpen = false
                        }
                    }
                }
            }

            // ── Main Content Area: Sidebar + Reading Pane ────────────────────
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                // ── Left Sidebar Navigation ──────────────────────────────────
                Rectangle {
                    Layout.fillHeight: true
                    width: 260
                    color: "#0D111A"
                    border.color: "#1E2638"
                    border.width: 1

                    SmoothListView {
                        id: navListView
                        anchors.fill: parent
                        anchors.margins: 6
                        spacing: 4
                        clip: true
                        model: tutorialRoot.sections

                        delegate: Rectangle {
                            width: navListView.width - 4
                            height: 48
                            radius: 6
                            color: {
                                if (index === tutorialRoot.currentSectionIndex) return "#1E293B";
                                if (itemMouse.containsMouse) return "#141C2B";
                                return "transparent";
                            }
                            border.color: index === tutorialRoot.currentSectionIndex ? "#38BDF8" : "transparent"
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 10

                                Text {
                                    text: modelData.icon || "📄"
                                    font.pixelSize: 18
                                }

                                Column {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        text: modelData.title || ""
                                        font.pixelSize: 12
                                        font.weight: index === tutorialRoot.currentSectionIndex ? Font.Bold : Font.Medium
                                        color: index === tutorialRoot.currentSectionIndex ? "#38BDF8" : "#E2E8F0"
                                        elide: Text.ElideRight
                                        width: parent.width
                                    }
                                    Text {
                                        text: modelData.summary || ""
                                        font.pixelSize: 10
                                        color: "#64748B"
                                        elide: Text.ElideRight
                                        width: parent.width
                                    }
                                }
                            }

                            MouseArea {
                                id: itemMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    tutorialRoot.currentSectionIndex = index;
                                    contentFlick.contentY = 0;
                                }
                            }
                        }
                    }
                }

                // ── Right Reading Pane ───────────────────────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#111622"

                    SmoothFlickable {
                        id: contentFlick
                        anchors.fill: parent
                        anchors.margins: 20
                        contentWidth: width
                        contentHeight: contentCol.implicitHeight + 40
                        clip: true

                        ColumnLayout {
                            id: contentCol
                            width: parent.width
                            spacing: 16

                            // Section Title Banner
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10
                                visible: tutorialRoot.currentSection !== null

                                Text {
                                    text: tutorialRoot.currentSection ? tutorialRoot.currentSection.icon : ""
                                    font.pixelSize: 26
                                }

                                Column {
                                    Layout.fillWidth: true
                                    Text {
                                        text: tutorialRoot.currentSection ? tutorialRoot.currentSection.title : ""
                                        font.pixelSize: 20
                                        font.bold: true
                                        color: "#F8FAFC"
                                    }
                                    Text {
                                        text: tutorialRoot.currentSection ? tutorialRoot.currentSection.summary : ""
                                        font.pixelSize: 12
                                        color: "#94A3B8"
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                height: 1
                                color: "#1F293D"
                                visible: tutorialRoot.currentSection !== null
                            }

                            // Content Cards Repeater
                            Repeater {
                                model: tutorialRoot.currentSection ? tutorialRoot.currentSection.content : []

                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: cardCol.implicitHeight + 24
                                    radius: 8
                                    color: {
                                        if (modelData.type === "tip") return "#064E3B18";
                                        if (modelData.type === "warning") return "#451A0318";
                                        return "#161D2C";
                                    }
                                    border.color: {
                                        if (modelData.type === "tip") return "#05966955";
                                        if (modelData.type === "warning") return "#D9770655";
                                        return "#222D42";
                                    }
                                    border.width: 1

                                    ColumnLayout {
                                        id: cardCol
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 8

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: {
                                                    if (modelData.type === "tip") return "💡 " + tutorialRoot.tr("tutorial_tag_tip", "TIP");
                                                    if (modelData.type === "warning") return "⚠️ " + tutorialRoot.tr("tutorial_tag_important", "IMPORTANT");
                                                    if (modelData.type === "intro") return "📌 " + tutorialRoot.tr("tutorial_tag_overview", "OVERVIEW");
                                                    return "ℹ️ " + tutorialRoot.tr("tutorial_tag_detail", "DETAIL");
                                                }
                                                font.pixelSize: 10
                                                font.weight: Font.Bold
                                                color: {
                                                    if (modelData.type === "tip") return "#34D399";
                                                    if (modelData.type === "warning") return "#FBBF24";
                                                    return "#38BDF8";
                                                }
                                            }

                                            Text {
                                                text: "• " + (modelData.heading || "")
                                                font.pixelSize: 14
                                                font.weight: Font.Bold
                                                color: "#F1F5F9"
                                            }
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            text: modelData.body || ""
                                            font.pixelSize: 12
                                            lineHeight: 1.4
                                            color: "#CBD5E1"
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
