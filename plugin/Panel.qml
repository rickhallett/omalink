import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons

Item {
    id: root
    property var shell: null
    property var manifest: null
    property bool opened: false
    property var urls: []
    property string message: ""
    property string monitorName: ""
    readonly property string executable: Quickshell.env("HOME") + "/.local/bin/omalink"
    function open(payload) {
        var p = {}
        try { p = JSON.parse(payload || "{}") } catch(e) {}
        if (p.monitor) monitorName = p.monitor
        opened = true
        if (reader.running) {
            if (p.image) Quickshell.execDetached([executable, "discard", p.image])
        } else {
            urls = p.urls || []
            message = ""
            list.currentIndex = 0
            if (p.image) {
                reader.command = [executable, "ocr", p.image]
                reader.running = true
            }
        }
        Qt.callLater(function() { keys.forceActiveFocus() })
    }
    function close() { opened = false }
    function choose() {
        if (reader.running || opener.running || list.currentIndex < 0 || list.currentIndex >= urls.length) return
        opener.command = [executable, "open", urls[list.currentIndex]]
        opener.running = true
    }
    Process {
        id: reader
        stdout: StdioCollector {
            onStreamFinished: {
                try { var result = JSON.parse(text); root.urls = result.urls || []; root.message = result.note || ""; list.currentIndex = 0 }
                catch(e) { root.message = "Could not read the OCR result" }
            }
        }
        stderr: StdioCollector { onStreamFinished: if (text.trim()) root.message = text.trim() }
    }
    Process {
        id: opener
        stderr: StdioCollector { onStreamFinished: if (text.trim()) root.message = text.trim() }
        onExited: function(code) { if (code === 0) root.close() }
    }
    LinkPopup {
        id: panel
        anchorItem: null
        bar: null
        owner: root
        screen: Quickshell.screens.find(function(s) { return s.name === root.monitorName }) || Quickshell.screens[0]
        open: root.opened
        focusTarget: keys
        contentWidth: fittedContentWidth(Style.space(900))
        contentHeight: fittedContentHeight(Style.space(430))
        Item {
            id: keys
            anchors.fill: parent
            focus: true
            Keys.onPressed: function(event) {
                if (event.key === Qt.Key_Escape) root.close()
                else if (event.key === Qt.Key_J || event.key === Qt.Key_Down) list.currentIndex = Math.min(root.urls.length-1,list.currentIndex+1)
                else if (event.key === Qt.Key_K || event.key === Qt.Key_Up) list.currentIndex = Math.max(0,list.currentIndex-1)
                else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) root.choose()
                else return
                event.accepted = true
            }
            Column {
                anchors.fill: parent
                spacing: Style.space(16)
                PanelHero {
                    title: "omalink"
                    detail: reader.running ? "Scanning" : root.urls.length + " links"
                    iconComponent: Component { Text { text: "󰌷"; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.display } }
                    trailingControl: Component { PanelActionButton { iconText: "󰅖"; tooltipText: "Close"; onClicked: root.close() } }
                }
                PanelSeparator { width: parent.width }
                ListView {
                    id: list
                    width: parent.width
                    height: parent.height - y - footer.implicitHeight - Style.space(16)
                    model: root.urls
                    clip: true
                    spacing: Style.space(6)
                    onCurrentIndexChanged: positionViewAtIndex(currentIndex,ListView.Contain)
                    delegate: CursorSurface {
                        required property string modelData
                        required property int index
                        width: list.width
                        implicitHeight: urlText.implicitHeight + Style.space(24)
                        hasCursor: list.currentIndex === index
                        foreground: Color.foreground
                        fill: Style.hoverFillFor(Color.foreground, Color.accent)
                        Text {
                            id: urlText
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Style.space(12) }
                            text: modelData.startsWith("file://") ? "Local image · " + decodeURIComponent(modelData.substring(7)) : modelData
                            textFormat: Text.PlainText
                            wrapMode: Text.WrapAnywhere
                            color: Color.foreground
                            font.family: Style.font.family; font.pixelSize: Style.font.body
                        }
                        MouseArea {
                            anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onEntered: list.currentIndex = index
                            onClicked: { list.currentIndex = index; root.choose() }
                        }
                    }
                    Text {
                        width: parent.width
                        anchors.centerIn: parent
                        text: reader.running ? "Reading the screen locally…" : (root.urls.length ? "" : root.message || "No visible URLs found\nHidden link destinations and truncated URLs cannot be read from pixels.")
                        visible: text !== ""
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        horizontalAlignment: Text.AlignHCenter
                        color: Color.foreground; opacity: 0.7
                        font.family: Style.font.family; font.pixelSize: Style.font.body
                    }
                }
                Text {
                    id: footer
                    width: parent.width
                    wrapMode: Text.Wrap
                    text: root.message || "j / k  select   ·   Enter  open in Chrome   ·   Esc  close"
                    color: Color.foreground; opacity: 0.6
                    font.family: Style.font.family; font.pixelSize: Style.font.caption
                }
            }
        }
    }
}
