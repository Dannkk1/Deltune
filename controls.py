"""Local input tools and a schematic for the wired G502 X."""
from evdev import ecodes
from PySide6.QtCore import Qt, QEvent, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QDialog, QVBoxLayout, QLabel, QDialogButtonBox
from backend import shortcut

def event_key(event):
    # On xkbcommon desktops this distinguishes left/right modifiers and keypad keys.
    native = event.nativeScanCode() - 8
    name = ecodes.KEY.get(native)
    if isinstance(name, list):
        name = name[0]
    if name and name.startswith('KEY_'):
        return name[4:]
    modifiers = {Qt.Key_Control:'LEFTCTRL', Qt.Key_Shift:'LEFTSHIFT', Qt.Key_Alt:'LEFTALT', Qt.Key_Meta:'LEFTMETA'}
    if event.key() in modifiers:
        return modifiers[event.key()]
    name = QKeySequence(event.key()).toString().upper()
    return {'CTRL':'LEFTCTRL','SHIFT':'LEFTSHIFT','ALT':'LEFTALT','META':'LEFTMETA',
            'RETURN':'ENTER','ESC':'ESC','DEL':'DELETE','PGUP':'PAGEUP','PGDOWN':'PAGEDOWN'}.get(name,name)

class Recorder(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Record shortcut')
        self.names = []
        self.held = set()
        self.value = ''
        layout = QVBoxLayout(self)
        self.prompt = QLabel('Hold the keys together, then release.'); layout.addWidget(self.prompt)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def showEvent(self,event):
        super().showEvent(event)
        QApplication.instance().installEventFilter(self)

    def hideEvent(self,event):
        QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)

    def eventFilter(self,watched,event):
        if not isinstance(watched,QWidget) or watched.window() is not self:
            return False
        if event.type() not in (QEvent.KeyPress, QEvent.KeyRelease):
            return False
        if event.isAutoRepeat():
            return True
        name = event_key(event)
        if event.type() == QEvent.KeyPress:
            if name not in self.names:
                self.names.append(name)
            self.held.add(name)
            self.prompt.setText(' + '.join(self.names))
        else:
            self.held.discard(name)
            if self.names and not self.held:
                value = '+'.join(self.names)
                try:
                    shortcut(value)
                except ValueError as exc:
                    self.prompt.setText(str(exc)); self.names.clear()
                else:
                    self.value = value
                    self.accept()
        return True

class TestPad(QLabel):
    def __init__(self):
        super().__init__('Click here, then press a mapped button.')
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(150)
        self.setObjectName('testpad')
        self.history = []

    def report(self, text):
        self.history = (self.history + [text])[-5:]
        self.setText('\n'.join(self.history))

    def event(self, event):
        kind = event.type()
        if kind in (QEvent.KeyPress, QEvent.KeyRelease) and self.hasFocus():
            if not event.isAutoRepeat():
                state = 'pressed' if kind == QEvent.KeyPress else 'released'
                self.report(f'{event_key(event)}  ·  {state}')
            return True
        return super().event(event)

    def mousePressEvent(self,event):
        self.setFocus()
        self.report(f'{event.button().name}  ·  pressed')
        event.accept()

    def mouseReleaseEvent(self,event):
        self.report(f'{event.button().name}  ·  released')
        event.accept()

    def wheelEvent(self,event):
        delta = event.angleDelta()
        self.report('Wheel ' + ('right' if delta.x()>0 else 'left' if delta.x()<0 else 'up' if delta.y()>0 else 'down'))
        event.accept()

class MouseMap(QWidget):
    chosen = Signal(int)
    # Coordinates in the same logical space as the schematic.
    positions = {0:(104,65,'G1'),1:(181,65,'G2'),2:(141,96,'G3'),
                 9:(64,65,'G8'),10:(58,105,'G7'),6:(100,123,'◀'),7:(182,123,'▶'),
                 8:(142,157,'G9'),4:(335,148,'G6'),5:(371,108,'G5'),3:(425,115,'G4')}
    def __init__(self):
        super().__init__()
        self.setMinimumSize(470,210)
        self.picks = {}
        for slot, (_,_,name) in self.positions.items():
            button = QPushButton(name,self)
            button.setCheckable(True)
            button.setStyleSheet('padding:0;')
            button.clicked.connect(lambda checked=False,i=slot:self.chosen.emit(i))
            self.picks[slot]=button

    def scale_info(self):
        scale = min(self.width()/520,self.height()/220)
        return scale,(self.width()-520*scale)/2,(self.height()-220*scale)/2

    def resizeEvent(self,event):
        scale,x,y=self.scale_info()
        for slot,(px,py,_) in self.positions.items():
            self.picks[slot].setGeometry(round(x+(px-17)*scale),round(y+(py-11)*scale),
                                         round(34*scale),round(22*scale))

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        scale,x,y=self.scale_info(); p.translate(x,y); p.scale(scale,scale)
        p.setBrush(QColor('#221b2a')); p.setPen(QPen(QColor('#695474'),2))
        outline=QPainterPath(); outline.moveTo(57,52); outline.cubicTo(69,12,181,10,200,51)
        outline.cubicTo(225,116,226,198,154,202); outline.cubicTo(91,208,85,176,43,165)
        outline.cubicTo(29,152,47,88,57,52); p.drawPath(outline)
        p.drawRoundedRect(QRectF(128,45,27,68),12,12)
        side=QPainterPath(); side.moveTo(290,154); side.cubicTo(298,128,310,101,343,90)
        side.cubicTo(407,52,445,67,482,126); side.lineTo(498,154)
        side.cubicTo(463,174,342,169,290,154); p.drawPath(side)
        p.setPen(QColor('#c9bfd3')); p.drawText(108,218,'Top view'); p.drawText(353,202,'Left side')
