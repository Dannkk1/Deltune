#!/usr/bin/env python3
import asyncio
import json
import sys
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QGroupBox, QFormLayout, QTabWidget,
    QPlainTextEdit, QMessageBox)
from backend import Backend, shortcut

SPECIAL = {1:'Double click', 2:'Wheel left', 3:'Wheel right', 4:'Wheel up', 5:'Wheel down',
           7:'Cycle DPI up', 8:'Cycle DPI down', 9:'DPI up', 10:'DPI down',
           11:'DPI shift', 12:'Default DPI', 13:'Cycle profile up', 14:'Cycle profile down'}
STYLE = '''
QWidget { background:#10151f; color:#e7eef9; font-family:"Noto Sans"; font-size:14px; }
QMainWindow { background:#10151f; }
QLabel#title {font-size:32px;font-weight:700;color:#8cdbff;}
QLabel#muted {color:#a1afc5;}
QGroupBox {border:1px solid #2a384e;border-radius:12px;margin-top:18px;padding:22px 16px 12px;}
QGroupBox::title {subcontrol-origin:margin;left:16px;color:#8cdbff;}
QComboBox,QLineEdit,QPlainTextEdit {background:#1b2433;border:1px solid #35455c;border-radius:6px;padding:9px;}
QPushButton {background:#23344a;border:1px solid #38516e;border-radius:7px;padding:10px 18px;}
QPushButton:hover {background:#314d69;}
QPushButton#primary {background:#85d8ff;color:#09121c;font-weight:700;}
QPushButton:disabled {background:#202631;color:#657084;border-color:#2a303a;}
QTabWidget::pane {border:0;}
QTabBar::tab {padding:12px 24px;background:#182130;}
QTabBar::tab:selected {color:#8cdbff;border-bottom:2px solid #8cdbff;}
'''

class Worker(QThread):
    done = Signal(object, str)
    def __init__(self, request):
        super().__init__()
        self.request = request
    def run(self):
        try:
            result = asyncio.run(Backend().run(self.request))
            self.done.emit(result, '')
        except Exception as exc:
            self.done.emit(None, str(exc) or type(exc).__name__)


def label(text, muted=False):
    w = QLabel(text)
    w.setWordWrap(True)
    if muted: w.setObjectName('muted')
    return w

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('G502 X Control')
        self.resize(920, 750)
        self.data = []
        self.worker = None
        root = QWidget(); self.setCentralWidget(root)
        layout = QVBoxLayout(root); layout.setContentsMargins(32,24,32,24); layout.setSpacing(14)
        title = label('G502 X  /  CONTROL'); title.setObjectName('title'); layout.addWidget(title)
        layout.addWidget(label('Your mouse. Your settings.   •   CachyOS / Linux', True))
        self.status = label('Connecting to mouse…'); layout.addWidget(self.status)
        top = QHBoxLayout(); self.device = QComboBox(); top.addWidget(self.device,1)
        self.refresh = QPushButton('Refresh'); self.refresh.clicked.connect(lambda:self.load()); top.addWidget(self.refresh)
        layout.addLayout(top)
        self.controls = QWidget(); cl = QVBoxLayout(self.controls); cl.setContentsMargins(0,0,0,0)
        row = QHBoxLayout(); row.addWidget(label('Onboard profile'))
        self.profile = QComboBox(); row.addWidget(self.profile,1)
        self.activate = QPushButton('Activate profile'); self.activate.clicked.connect(lambda:self.submit('profile'))
        row.addWidget(self.activate); cl.addLayout(row)
        tabs = QTabWidget(); cl.addWidget(tabs)
        dpi = QWidget(); dl = QVBoxLayout(dpi)
        box = QGroupBox('Sensitivity'); form = QFormLayout(box)
        self.stage = QComboBox(); form.addRow('DPI stage', self.stage)
        self.dpi = QComboBox(); self.dpi.setEditable(True); form.addRow('DPI value',self.dpi)
        dl.addWidget(box)
        presets = QHBoxLayout()
        for value in [400,800,1600,3200]:
            btn = QPushButton(str(value)); btn.clicked.connect(lambda checked=False,v=value:self.dpi.setCurrentText(str(v))); presets.addWidget(btn)
        dl.addLayout(presets)
        self.save_dpi = QPushButton('Save DPI'); self.save_dpi.setObjectName('primary'); self.save_dpi.clicked.connect(self.write_dpi)
        dl.addWidget(self.save_dpi)
        self.active_stage = QPushButton('Use this DPI stage'); self.active_stage.clicked.connect(lambda:self.submit('resolution',target=self.stage.currentData()['path']))
        dl.addWidget(self.active_stage)
        dl.addWidget(label('Save changes the selected stage. “Use this DPI stage” selects it. Values are checked against the range reported by your mouse.',True)); dl.addStretch()
        tabs.addTab(dpi,'Sensitivity')
        buttons = QWidget(); bl = QVBoxLayout(buttons)
        box = QGroupBox('Button assignments'); bf = QFormLayout(box)
        self.button = QComboBox(); bf.addRow('Physical button index',self.button)
        self.current = label(''); bf.addRow('Current assignment',self.current)
        self.action = QComboBox(); bf.addRow('New assignment',self.action)
        self.keys = QLineEdit(); self.keys.setPlaceholderText('LEFTCTRL+C, F13, SPACE, LEFTSHIFT…'); bf.addRow('Keyboard shortcut',self.keys)
        bl.addWidget(box)
        self.save_button = QPushButton('Save button assignment'); self.save_button.setObjectName('primary'); self.save_button.clicked.connect(self.write_button); bl.addWidget(self.save_button)
        bl.addWidget(label('Indexes come from the driver, not Logitech’s printed G numbers. Existing assignments help identify each button. The mechanical free-spin wheel latch is not a software control.',True)); bl.addStretch()
        tabs.addTab(buttons,'Buttons')
        layout.addWidget(self.controls,1)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); self.details.setMaximumHeight(115)
        self.details.setPlaceholderText('Connection diagnostics')
        layout.addWidget(self.details)
        layout.addWidget(label('Native device configuration via libratbag • No account • No background input capture',True))
        self.device.currentIndexChanged.connect(self.show_device)
        self.profile.currentIndexChanged.connect(self.show_profile)
        self.stage.currentIndexChanged.connect(self.show_stage)
        self.button.currentIndexChanged.connect(self.show_button)
        self.action.currentIndexChanged.connect(lambda:self.keys.setEnabled(self.action.currentData()==[4,None]))
        self.controls.setEnabled(False)
        QTimer.singleShot(0,self.load)

    def load(self, request=None):
        if self.worker and self.worker.isRunning(): return
        self.last_request = request
        self.controls.setEnabled(False); self.refresh.setEnabled(False); self.device.setEnabled(False)
        self.status.setText('Writing and checking settings…' if request else 'Looking for your G502 X…')
        self.worker = Worker(request)
        self.worker.done.connect(self.loaded)
        self.worker.start()

    def loaded(self, result, error):
        self.refresh.setEnabled(True); self.device.setEnabled(True)
        if error:
            self.status.setText('Could not save settings.' if self.last_request else 'Mouse connection unavailable.')
            self.details.setPlainText(error+'\n\nTry: sudo systemctl restart ratbagd\nThen reconnect your mouse and click Refresh. For wireless variants, try a USB data cable.\nDo not run this app with sudo. Close Piper or other mouse configuration tools.')
            self.controls.setEnabled(False)
            return
        old_d = self.device.currentData(); old_p = self.profile.currentData()
        dp = old_d.get('path') if old_d else None; pp = old_p.get('path') if old_p else None
        self.data = result
        self.device.blockSignals(True); self.device.clear()
        for d in result: self.device.addItem(d['Name'],d)
        for i,d in enumerate(result):
            if d['path']==dp: self.device.setCurrentIndex(i)
        self.device.blockSignals(False)
        self.show_device()
        if pp:
            for i in range(self.profile.count()):
                if self.profile.itemData(i)['path']==pp: self.profile.setCurrentIndex(i)
        self.controls.setEnabled(bool(result))
        self.status.setText(('Saved • driver readback matches' if self.last_request else 'Connected • settings read from your mouse') if result else 'No supported G502 detected')
        self.details.setPlainText('Driver connected. Changes are checked after each save.\nSelect a profile, then change its sensitivity or button assignments.\nRefresh after reconnecting the mouse or switching profiles with its buttons.' if result else 'Check that the mouse is connected and awake.\nRun ratbagctl list to check driver detection.\nWireless G502 X models may need a newer libratbag version; try configuring over a USB data cable first.\nUpdate CachyOS normally, restart ratbagd, then Refresh. No device IDs or permissions are modified by this app.')

    def show_device(self):
        self.profile.blockSignals(True); self.profile.clear()
        d = self.device.currentData()
        if d:
            for p in d['Profiles']:
                self.profile.addItem(f"Profile {p['Index']+1}"+(' • active' if p['IsActive'] else '')+(' • disabled' if p.get('Disabled') else ''),p)
            active = next((i for i,p in enumerate(d['Profiles']) if p['IsActive']),0); self.profile.setCurrentIndex(active)
        self.profile.blockSignals(False); self.show_profile()

    def show_profile(self):
        p = self.profile.currentData()
        self.stage.blockSignals(True); self.stage.clear()
        self.button.blockSignals(True); self.button.clear()
        if p:
            for r in p['Resolutions']:
                self.stage.addItem(f"Stage {r['Index']+1} — {r['Resolution']} DPI"+(' • active' if r['IsActive'] else '')+(' • disabled' if r.get('IsDisabled') else ''),r)
            self.stage.setCurrentIndex(next((i for i,r in enumerate(p['Resolutions']) if r['IsActive']),0))
            for b in p['Buttons']: self.button.addItem(f"Button {b['Index']} — {self.describe(b['Mapping'])}",b)
        self.stage.blockSignals(False); self.button.blockSignals(False)
        self.activate.setEnabled(bool(p) and not p.get('Disabled',False))
        self.show_stage(); self.show_button()

    def show_stage(self):
        r = self.stage.currentData(); self.dpi.clear()
        if r:
            for n in r.get('Resolutions',[]): self.dpi.addItem(str(n))
            value = r['Resolution']; self.dpi.setCurrentText(str(value[0] if isinstance(value,list) else value))
        self.save_dpi.setEnabled(bool(r) and bool(r.get('Resolutions')))
        self.active_stage.setEnabled(bool(r) and not r.get('IsDisabled',False))

    @staticmethod
    def describe(mapping):
        k,v = mapping
        if k==0:return 'Disabled'
        if k==1:return {1:'Left click',2:'Right click',3:'Middle click',4:'Back',5:'Forward'}.get(v,f'Mouse button {v}')
        if k==2:return SPECIAL.get(v-(1<<30),f'Special {v}')
        return f'Keyboard key {v}' if k==3 else 'Keyboard macro'

    def show_button(self):
        b = self.button.currentData(); self.action.clear(); self.keys.clear()
        self.current.setText(self.describe(b['Mapping']) if b else '')
        if b:
            choices = [('Disabled',[0,0])]+[(self.describe([1,n]),[1,n]) for n in range(1,9)]
            choices += [(name,[2,(1<<30)+n]) for n,name in SPECIAL.items()]
            choices += [('Keyboard shortcut…',[4,None])]
            for name,data in choices:
                if data[0] in b['ActionTypes']: self.action.addItem(name,data)
            for i in range(self.action.count()):
                if self.action.itemData(i)==b['Mapping']: self.action.setCurrentIndex(i)
        self.keys.setEnabled(self.action.currentData()==[4,None])
        self.save_button.setEnabled(bool(b) and self.action.count()>0)

    def submit(self, op, **kwargs):
        d = self.device.currentData(); p = self.profile.currentData()
        if d and p: self.load(dict(device=d['path'],profile=p['path'],op=op,**kwargs))

    def write_dpi(self):
        try:
            value = int(self.dpi.currentText())
            r = self.stage.currentData()
            if value not in r.get('Resolutions',[]): raise ValueError('Choose a DPI value supported by your mouse.')
            self.submit('dpi',target=r['path'],dpi=value)
        except (ValueError,TypeError) as e: QMessageBox.warning(self,'DPI value',str(e))

    def write_button(self):
        try:
            mapping = self.action.currentData()
            if mapping[0]==4: mapping=[4,shortcut(self.keys.text())]
            self.submit('button',target=self.button.currentData()['path'],mapping=mapping)
        except (ValueError,TypeError) as e: QMessageBox.warning(self,'Button assignment',str(e))

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.status.setText('Please wait for the current device operation to finish.'); event.ignore()
        else:event.accept()

if __name__=='__main__':
    app = QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    window = Window(); window.show(); sys.exit(app.exec())
