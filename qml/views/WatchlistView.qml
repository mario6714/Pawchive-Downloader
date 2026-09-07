import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: root
    property var bridge: null

    // ── Helpers ────────────────────────────────────────────────────────────────
    function tr(key, fallback) {
        if (typeof appWindow !== "undefined") return appWindow.tr(key, fallback)
        return fallback !== undefined ? fallback : key
    }

    function serviceColor(svc) {
        var s = (svc || "").toLowerCase()
        if (s === "onlyfans")    return "#00AFF0"
        if (s === "fansly")      return "#FF6B9D"
        if (s === "patreon")     return "#FF424D"
        if (s === "fanbox")      return "#007AFF"
        if (s === "gumroad")     return "#36C5AB"
        if (s === "subscribestar") return "#5C9DFF"
        if (s === "fantia")      return "#E84393"
        if (s === "boosty")      return "#F76A23"
        return "#64748B"
    }

    // ── Watchlist check state ──────────────────────────────────────────────────
    property bool isChecking: false
    property int  lastNewCount: -1  // -1 = never checked
    property var  checkingArtists: ({})

    Connections {
        target: bridge
        function onWatchlistCheckStarted() { root.isChecking = true }
        function onWatchlistCheckFinished(n) {
            root.isChecking = false
            root.lastNewCount = n
            if (n > 0) resultToast.show(n)
        }
        function onWatchlistArtistChecking(uid, svc, checking) {
            var key = uid + "_" + svc
            var copy = Object.assign({}, root.checkingArtists)
            if (checking) {
                copy[key] = true
            } else {
                delete copy[key]
            }
            root.checkingArtists = copy
        }
        function onWatchlistArtistChecked(uid, svc, count) {
            if (count > 0) {
                resultToast.show(count)
            }
        }
        function onWatchlistChanged() {
            if (bridge && bridge.watchlistModel) {
                bridge.watchlistModel.refresh()
            }
        }
    }

    // ── Layout ─────────────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ──────────────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 52
            color: "#0C0F18"
            border.color: "#1A2035"
            border.width: 1
            radius: 8

            // Gradient accent line
            Rectangle {
                width: parent.width * 0.6
                height: 1
                anchors.top: parent.top
                anchors.horizontalCenter: parent.horizontalCenter
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.3; color: "#A78BFA" }
                    GradientStop { position: 0.7; color: "#38BDF8" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 12
                spacing: 10

                // Icon + Title
                Text { text: "\uD83D\uDCCC"; font.pixelSize: 18 }
                Text {
                    text: root.tr("tab_watchlist", "Watchlist")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    color: "#E2E8F0"
                }

                // Subtitle / entry count
                Text {
                    text: bridge && bridge.watchlistModel
                          ? (bridge.watchlistModel.count + " " + root.tr("watchlist_artists", "artist(s)"))
                          : ""
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#4B5563"
                    Layout.alignment: Qt.AlignVCenter
                }

                Item { Layout.fillWidth: true }

                // "New posts" result toast inline badge
                Rectangle {
                    id: resultBadge
                    visible: root.lastNewCount > 0
                    height: 26
                    implicitWidth: resultBadgeText.implicitWidth + 20
                    radius: 13
                    color: "#0D2A1A"
                    border.color: "#10B981"
                    border.width: 1

                    Text {
                        id: resultBadgeText
                        anchors.centerIn: parent
                        text: "+" + root.lastNewCount + " " + root.tr("watchlist_new_badge", "new")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        color: "#34D399"
                    }
                }

                // Check All button
                Rectangle {
                    id: checkAllBtn
                    height: 32
                    implicitWidth: checkAllRow.implicitWidth + 24
                    radius: 7
                    color: checkAllMouse.containsMouse ? "#1E1B3D" : "#141228"
                    border.color: root.isChecking ? "#6D28D9" : "#4C1D95"
                    border.width: 1

                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    scale: checkAllMouse.pressed ? 0.94 : (checkAllMouse.containsMouse ? 1.035 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: checkAllRow
                        anchors.centerIn: parent
                        spacing: 6

                        // Spinner or icon
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.isChecking ? "\u21BB" : "\uD83D\uDD0D"
                            font.pixelSize: root.isChecking ? 14 : 12
                            color: "#A78BFA"

                            RotationAnimator on rotation {
                                from: 0; to: 360
                                duration: 900
                                loops: Animation.Infinite
                                running: root.isChecking
                            }
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.isChecking
                                  ? root.tr("watchlist_checking", "Checking…")
                                  : root.tr("watchlist_check_all", "Check All")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: "#A78BFA"
                        }
                    }

                    MouseArea {
                        id: checkAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        enabled: !root.isChecking
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: root.tr("watchlist_check_all_tip", "Check all followed artists for new posts")
                        onClicked: if (bridge) bridge.checkWatchlist()
                    }
                }
            }
        }

        // ── Thin divider ─────────────────────────────────────────────────────
        Rectangle { Layout.fillWidth: true; height: 1; color: "#1A2035" }

        // ── Content: empty state OR entry list ────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // ── Empty state (no watchlist entries) ─────────────────────────────
            Column {
                anchors.centerIn: parent
                spacing: 14
                visible: !bridge || !bridge.watchlistModel || bridge.watchlistModel.count === 0

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "\uD83D\uDCCC"
                    font.pixelSize: 52
                    color: "#2D3748"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.tr("watchlist_empty_title", "No artists tracked yet")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    color: "#4B5563"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 340
                    horizontalAlignment: Text.AlignHCenter
                    text: root.tr("watchlist_empty", "Artists you download will appear here automatically.\nTrack new posts and download updates in one click.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#374151"
                    wrapMode: Text.WordWrap
                    lineHeight: 1.5
                }
            }

            // ── Entry list ────────────────────────────────────────────────────
            ListView {
                id: watchListView
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8
                clip: true
                visible: bridge && bridge.watchlistModel && bridge.watchlistModel.count > 0
                model: bridge ? bridge.watchlistModel : null

                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                    contentItem: Rectangle {
                        radius: 3
                        color: "#2D3A52"
                        opacity: 0.8
                    }
                }

                delegate: Rectangle {
                    id: entryCard
                    width: watchListView.width
                    height: cardCol.implicitHeight + 20
                    radius: 10
                    color: cardMouse.containsMouse ? "#111827" : "#0D1117"
                    border.color: (model.newPostCount > 0) ? "#1F4B2E" : "#1E2330"
                    border.width: 1
                    clip: true

                    readonly property bool isArtistChecking: !!(root.checkingArtists[model.userId + "_" + model.service])

                    // Left accent bar — shows new-post color
                    Rectangle {
                        width: 3
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        radius: 3
                        color: isArtistChecking ? "#8B5CF6" : (model.newPostCount > 0 ? "#10B981" : root.serviceColor(model.service))
                        opacity: 0.8
                    }

                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    MouseArea {
                        id: cardMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                    }

                    Column {
                        id: cardCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 14
                        anchors.leftMargin: 18
                        spacing: 8

                        // ── Row 1: Name + service badge + new badge ───────────────
                        RowLayout {
                            width: parent.width
                            spacing: 8

                            Text {
                                text: model.creatorName || model.userId
                                font.family: "Segoe UI, Inter, sans-serif"
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                                color: "#E2E8F0"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            // Service pill
                            Rectangle {
                                height: 20
                                implicitWidth: svcPillText.implicitWidth + 14
                                radius: 10
                                color: Qt.rgba(
                                    parseInt(root.serviceColor(model.service).substring(1,3),16)/255,
                                    parseInt(root.serviceColor(model.service).substring(3,5),16)/255,
                                    parseInt(root.serviceColor(model.service).substring(5,7),16)/255,
                                    0.15
                                )
                                border.color: root.serviceColor(model.service)
                                border.width: 1

                                Text {
                                    id: svcPillText
                                    anchors.centerIn: parent
                                    text: model.service.toUpperCase()
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: root.serviceColor(model.service)
                                }
                            }

                            // New-post badge (only when new posts found)
                            Rectangle {
                                visible: model.newPostCount > 0
                                height: 20
                                implicitWidth: newBadgeText.implicitWidth + 14
                                radius: 10
                                color: "#0D2A1A"
                                border.color: "#10B981"
                                border.width: 1

                                Text {
                                    id: newBadgeText
                                    anchors.centerIn: parent
                                    text: "+" + model.newPostCount + " new"
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: "#34D399"
                                }
                            }
                        }

                        // ── Row 2: Last download date + auto-check toggle ─────────
                        RowLayout {
                            width: parent.width
                            spacing: 12

                            Text {
                                text: "\uD83D\uDCC5 " + root.tr("watchlist_last_dl", "Last downloaded:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#4B5563"
                            }
                            Text {
                                text: model.lastPostDate || root.tr("watchlist_never", "Never")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: model.lastPostDate ? "#94A3B8" : "#4B5563"
                            }

                            Item { Layout.fillWidth: true }

                            // Auto-check toggle with fluid animations
                            Row {
                                spacing: 6
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: root.tr("watchlist_auto_check", "Auto-check")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: toggleMouse.containsMouse ? "#94A3B8" : "#64748B"
                                    Behavior on color { ColorAnimation { duration: 150 } }
                                }
                                Rectangle {
                                    id: autoCheckToggle
                                    width: 38; height: 20
                                    radius: 10
                                    color: model.autoCheck 
                                           ? (toggleMouse.containsMouse ? "#105C38" : "#0D4C2F") 
                                           : (toggleMouse.containsMouse ? "#263047" : "#1C2233")
                                    border.color: model.autoCheck 
                                                  ? (toggleMouse.containsMouse ? "#34D399" : "#10B981") 
                                                  : (toggleMouse.containsMouse ? "#475569" : "#2E3A56")
                                    border.width: 1
                                    anchors.verticalCenter: parent.verticalCenter
                                    scale: toggleMouse.pressed ? 0.88 : (toggleMouse.containsMouse ? 1.08 : 1.0)
                                    transformOrigin: Item.Center

                                    Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.4 } }
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                    Behavior on border.color { ColorAnimation { duration: 180 } }

                                    Rectangle {
                                        id: toggleKnob
                                        width: toggleMouse.pressed ? 18 : 14
                                        height: 14
                                        radius: 7
                                        anchors.verticalCenter: parent.verticalCenter
                                        x: model.autoCheck ? parent.width - width - 3 : 3
                                        color: model.autoCheck 
                                               ? (toggleMouse.containsMouse ? "#6EE7B7" : "#34D399") 
                                               : (toggleMouse.containsMouse ? "#94A3B8" : "#64748B")

                                        Behavior on x { NumberAnimation { duration: 220; easing.type: Easing.OutBack; easing.overshoot: 1.6 } }
                                        Behavior on width { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
                                        Behavior on color { ColorAnimation { duration: 180 } }
                                    }

                                    MouseArea {
                                        id: toggleMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 350
                                        ToolTip.text: model.autoCheck
                                                      ? root.tr("watchlist_autocheck_on", "Auto-check enabled on launch")
                                                      : root.tr("watchlist_autocheck_off", "Auto-check disabled")
                                        onClicked: {
                                            if (bridge) bridge.setWatchlistAutoCheck(model.userId, model.service, !model.autoCheck)
                                        }
                                    }
                                }
                            }
                        }

                        // ── Row 3: Action buttons ─────────────────────────────────
                        Row {
                            spacing: 8
                            bottomPadding: 2

                            // Check Single Artist Button
                            Rectangle {
                                height: 28
                                implicitWidth: checkArtistRow.implicitWidth + 20
                                radius: 6
                                color: checkArtistMouse.containsMouse ? "#1E1B3D" : "#121024"
                                border.color: isArtistChecking ? "#8B5CF6" : (checkArtistMouse.containsMouse ? "#6D28D9" : "#4C1D95")
                                border.width: 1
                                Behavior on color { ColorAnimation { duration: 100 } }
                                Behavior on border.color { ColorAnimation { duration: 100 } }
                                scale: checkArtistMouse.pressed ? 0.94 : (checkArtistMouse.containsMouse ? 1.04 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                                Row {
                                    id: checkArtistRow
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Text {
                                        text: isArtistChecking ? "\u21BB" : "\uD83D\uDD0D"
                                        font.pixelSize: isArtistChecking ? 12 : 10
                                        color: isArtistChecking ? "#C4B5FD" : "#A78BFA"
                                        anchors.verticalCenter: parent.verticalCenter
                                        RotationAnimator on rotation {
                                            from: 0; to: 360
                                            duration: 800
                                            loops: Animation.Infinite
                                            running: isArtistChecking
                                        }
                                    }
                                    Text {
                                        text: isArtistChecking
                                              ? root.tr("watchlist_checking", "Checking…")
                                              : root.tr("watchlist_check_artist", "Check")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: Font.DemiBold
                                        color: isArtistChecking ? "#DDD6FE" : "#C4B5FD"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea {
                                    id: checkArtistMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    enabled: !isArtistChecking && !root.isChecking
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: root.tr("watchlist_check_artist_tip", "Check only this artist for new posts")
                                    onClicked: {
                                        if (bridge) bridge.checkWatchlistArtist(model.userId, model.service)
                                    }
                                }
                            }

                            // Download New
                            Rectangle {
                                height: 28
                                implicitWidth: dlNewRow.implicitWidth + 20
                                radius: 6
                                visible: model.newPostCount > 0
                                color: dlNewMouse.containsMouse ? "#0D2A1A" : "#071A12"
                                border.color: "#10B981"
                                border.width: 1
                                Behavior on color { ColorAnimation { duration: 100 } }
                                scale: dlNewMouse.pressed ? 0.94 : (dlNewMouse.containsMouse ? 1.04 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                                Row {
                                    id: dlNewRow
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Text { text: "\u2B07\uFE0F"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                                    Text {
                                        text: root.tr("watchlist_download_new", "Download New")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: Font.DemiBold
                                        color: "#34D399"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea {
                                    id: dlNewMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: root.tr("watchlist_download_new_tip", "Queue only the new posts since last download")
                                    onClicked: if (bridge) bridge.downloadNewPosts(model.userId, model.service)
                                }
                            }

                            // Re-download All
                            Rectangle {
                                height: 28
                                implicitWidth: redownloadRow.implicitWidth + 20
                                radius: 6
                                color: redownloadMouse.containsMouse ? "#1A1430" : "#100E22"
                                border.color: "#4C1D95"
                                border.width: 1
                                Behavior on color { ColorAnimation { duration: 100 } }
                                scale: redownloadMouse.pressed ? 0.94 : (redownloadMouse.containsMouse ? 1.04 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                                Row {
                                    id: redownloadRow
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Text { text: "\uD83D\uDD04"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                                    Text {
                                        text: root.tr("watchlist_redownload", "Re-download All")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: Font.DemiBold
                                        color: "#A78BFA"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea {
                                    id: redownloadMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: root.tr("watchlist_redownload_tip", "Re-queue the entire artist's catalog for download")
                                    onClicked: if (bridge) bridge.redownloadWatchlistEntry(model.userId, model.service)
                                }
                            }

                            // Remove
                            Rectangle {
                                height: 28
                                implicitWidth: removeRow.implicitWidth + 20
                                radius: 6
                                color: removeMouse.containsMouse ? "#2A0D0D" : "#1A0808"
                                border.color: "#7F1D1D"
                                border.width: 1
                                Behavior on color { ColorAnimation { duration: 100 } }
                                scale: removeMouse.pressed ? 0.94 : (removeMouse.containsMouse ? 1.04 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                                Row {
                                    id: removeRow
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Text { text: "\uD83D\uDDD1"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                                    Text {
                                        text: root.tr("watchlist_remove", "Remove")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: Font.DemiBold
                                        color: "#FCA5A5"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea {
                                    id: removeMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: root.tr("watchlist_remove_tip", "Stop tracking this artist and remove from watchlist")
                                    onClicked: if (bridge) bridge.removeFromWatchlist(model.userId, model.service)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ── Toast notification (fades in/out when new posts found) ─────────────────
    Item {
        id: resultToast
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 24
        width: toastText.implicitWidth + 40
        height: 40
        visible: opacity > 0
        opacity: 0

        function show(n) {
            toastText.text = "✅ " + n + " new " + (n === 1 ? "post" : "posts") + " found!"
            opacity = 1.0
            toastTimer.restart()
        }

        Behavior on opacity { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }

        Timer {
            id: toastTimer
            interval: 4000
            onTriggered: resultToast.opacity = 0
        }

        Rectangle {
            anchors.fill: parent
            radius: 20
            color: "#0D2A1A"
            border.color: "#10B981"
            border.width: 1

            Text {
                id: toastText
                anchors.centerIn: parent
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: Font.DemiBold
                color: "#34D399"
            }
        }
    }
}
