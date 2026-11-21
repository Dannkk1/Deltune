#!/usr/bin/env python3
import asyncio
import json
import sys
from PySide6.QtCore import QThread, Signal, QTimer, QSettings
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QGroupBox, QFormLayout, QTabWidget,
    QPlainTextEdit, QMessageBox, QInputDialog, QDialog)
from backend import Backend, shortcut, copy_plan
from controls import MouseMap, Recorder, TestPad
from evdev import ecodes

SPECIAL = {1:'Double click', 2:'Wheel left', 3:'Wheel right', 4:'Wheel up', 5:'Wheel down',
           7:'Cycle DPI up', 8:'Cycle DPI down', 9:'DPI up', 10:'DPI down',
           11:'DPI shift', 12:'Default DPI', 13:'Cycle profile up', 14:'Cycle profile down'}
# Physical slots for the corded G502 X (046d:c099), independent of saved actions.
WIRED_G502X_BUTTONS = {
    0: 'G1 · Left click', 1: 'G2 · Right click', 2: 'G3 · Wheel click',
    3: 'G4 · Back thumb button', 5: 'G5 · Forward thumb button',
    4: 'G6 · Aim paddle (DPI Shift)', 10: 'G7 · DPI down button', 9: 'G8 · DPI up button',
    8: 'G9 · Profile button', 6: 'Wheel tilt left', 7: 'Wheel tilt right',
}

STYLE = '''
QWidget { color:#f5f1fa; font-family:"Noto Sans"; font-size:14px; }
QDialog {background:#151217;}
QLabel#testpad {background:#211c26;border:1px dashed #aa80c5;border-radius:12px;}
QLabel#testpad:focus {border:2px solid #c9a0ff;}
QMainWindow, QWidget#root { background:#080709; }
QLabel { background:transparent; }
QLabel#title { font-size:28px; font-weight:750; }
QLabel#section { font-size:25px; font-weight:700; }
QLabel#readout { color:#d3abff; font-size:52px; font-weight:750; }
QLabel#muted { color:#b1a9ba; font-size:13px; }
QWidget#rail { background:#141116; border:1px solid #302935; border-radius:14px; }
QGroupBox { background:#151217; border:1px solid #302935; border-radius:12px; padding:18px; }
QComboBox,QLineEdit,QPlainTextEdit { background:#211c26; border:1px solid #483c51; border-radius:6px; padding:7px; selection-background-color:#7747a7; }
QComboBox QAbstractItemView { background:#211c26; color:#f5f1fa; selection-background-color:#5a367a; }
QPushButton { background:#251e2b; border:1px solid #483a53; border-radius:7px; padding:8px 12px; }
QPushButton:hover,QPushButton:checked { background:#392841; border-color:#a476c6; }
QPushButton#primary { background:#c9a0ff; border-color:#c9a0ff; color:#180c24; font-weight:700; }
QPushButton#primary:hover { background:#dbbfff; }
QPushButton:disabled,QComboBox:disabled,QLineEdit:disabled { color:#8b8292; background:#1b181e; border-color:#342e39; }
QPushButton:focus,QComboBox:focus,QLineEdit:focus { border:1px solid #cf9eff; }
QTabWidget::pane { border:0; }
QTabBar::tab { background:#080709; color:#b3aaba; padding:10px 17px; border-bottom:2px solid #322a38; }
QTabBar::tab:selected { color:#d7b3ff; border-bottom:2px solid #bc87ff; font-weight:700; }
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
        self.resize(1000, 700)
        self.settings = QSettings("Deltune","G502 X Control")
        self.undo_request = None
        self.data = []
        self.worker = None
        root = QWidget(); root.setObjectName('root'); self.setCentralWidget(root)
        layout = QVBoxLayout(root); layout.setContentsMargins(24,20,24,20); layout.setSpacing(16)
        header = QHBoxLayout()
        title = label('G502 X Control'); title.setObjectName('title')
        header.addWidget(title); header.addStretch()
        self.status = label('Connecting…', True); self.status.setWordWrap(False); header.addWidget(self.status)
        layout.addLayout(header)
        body = QHBoxLayout(); body.setSpacing(22); layout.addLayout(body,1)
        rail = QWidget(); rail.setObjectName('rail'); rail.setFixedWidth(238)
        side = QVBoxLayout(rail); side.setContentsMargins(16,20,16,16); side.setSpacing(9)
        side.addWidget(label('Mouse', True))
        self.device = QComboBox(); side.addWidget(self.device)
        self.refresh = QPushButton('Refresh devices'); self.refresh.clicked.connect(lambda:self.load())
        side.addWidget(self.refresh); side.addSpacing(15)
        side.addWidget(label('Onboard profile', True))
        self.profile = QComboBox(); side.addWidget(self.profile)
        self.activate = QPushButton('Activate profile'); self.activate.clicked.connect(lambda:self.submit('profile'))
        side.addWidget(self.activate)
        self.rename = QPushButton('Rename locally'); self.rename.clicked.connect(self.rename_profile)
        self.copy = QPushButton('Copy profile…'); self.copy.clicked.connect(self.copy_profile)
        side.addWidget(self.rename); side.addWidget(self.copy); side.addStretch()
        self.diag = QPushButton('Connection details'); self.diag.setCheckable(True); side.addWidget(self.diag)
        body.addWidget(rail)
        self.controls = QWidget(); cl = QVBoxLayout(self.controls); cl.setContentsMargins(0,0,0,0)
        body.addWidget(self.controls,1)
        tabs = QTabWidget(); cl.addWidget(tabs)
        dpi = QWidget(); dl = QVBoxLayout(dpi); dl.setContentsMargins(0,20,0,0); dl.setSpacing(13)
        dl.addWidget(label('Selected stage sensitivity',True))
        self.readout = label('—'); self.readout.setObjectName('readout'); dl.addWidget(self.readout)
        box = QGroupBox(); form = QFormLayout(box)
        self.stage = QComboBox(); form.addRow('DPI stage',self.stage)
        self.dpi = QComboBox(); self.dpi.setEditable(True); form.addRow('DPI value',self.dpi)
        self.strip = QHBoxLayout(); dl.addLayout(self.strip)
        presets = QHBoxLayout()
        for value in [400,800,1600,3200]:
            btn = QPushButton(str(value)); btn.clicked.connect(lambda checked=False,v=value:self.dpi.setCurrentText(str(v))); presets.addWidget(btn)
        form.addRow('Presets',presets); dl.addWidget(box)
        actions = QHBoxLayout()
        self.save_dpi = QPushButton('Save DPI'); self.save_dpi.setObjectName('primary'); self.save_dpi.clicked.connect(self.write_dpi)
        self.active_stage = QPushButton('Use this DPI stage'); self.active_stage.clicked.connect(lambda:self.submit('resolution',target=self.stage.currentData()['path']))
        actions.addWidget(self.save_dpi); actions.addWidget(self.active_stage); actions.addStretch()
        dl.addLayout(actions); dl.addStretch(); tabs.addTab(dpi,'Sensitivity')
        buttons = QWidget(); bl = QVBoxLayout(buttons); bl.setContentsMargins(0,20,0,0); bl.setSpacing(14)
        heading = label('Button assignments'); heading.setObjectName('section'); bl.addWidget(heading)
        box = QGroupBox(); bf = QFormLayout(box)
        self.button = QComboBox(); bf.addRow('Physical control',self.button)
        quick = QHBoxLayout()
        self.quick_buttons = {}
        for slot, name in [(4, 'G6 · Aim paddle'), (10, 'G7'), (9, 'G8')]:
            pick = QPushButton(name)
            pick.clicked.connect(lambda checked=False, slot=slot: self.select_slot(slot))
            self.quick_buttons[slot] = pick
            quick.addWidget(pick)
        bf.addRow('Quick select', quick)
        self.current = label(''); bf.addRow('Current assignment',self.current)
        self.action = QComboBox(); bf.addRow('New assignment',self.action)
        self.keys = QLineEdit(); self.keys.setPlaceholderText('LEFTCTRL+C, F13, SPACE, LEFTSHIFT…'); bf.addRow('Keyboard shortcut',self.keys)
        self.record = QPushButton('Record shortcut…'); self.record.clicked.connect(self.record_keys)
        bf.addRow('',self.record)
        bl.addWidget(box)
        self.save_button = QPushButton('Save button assignment'); self.save_button.setObjectName('primary'); self.save_button.clicked.connect(self.write_button); bar = QHBoxLayout(); bar.addWidget(self.save_button)
        self.undo = QPushButton('Undo last assignment'); self.undo.clicked.connect(self.undo_button)
        bar.addWidget(self.undo); bar.addStretch(); bl.addLayout(bar)
        bl.addWidget(label('To move left click, assign it to another button first.',True)); bl.addStretch()
        tabs.addTab(buttons,'Buttons')
        map_page = QWidget(); ml = QVBoxLayout(map_page)
        ml.addWidget(label('Select a control to edit its assignment.',True))
        self.mouse_map = MouseMap(); ml.addWidget(self.mouse_map,1)
        self.map_tab = tabs.addTab(map_page,'Button map')
        self.tabs = tabs
        self.mouse_map.chosen.connect(self.map_selected)
        tester = QWidget(); tl = QVBoxLayout(tester)
        tl.addWidget(label('Focus the pad to see keyboard and mouse events delivered to this window.',True))
        self.pad = TestPad(); tl.addWidget(self.pad); tl.addStretch()
        tabs.addTab(tester,'Input tester')
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); self.details.setMaximumHeight(115)
        self.details.setPlaceholderText('Connection diagnostics')
        layout.addWidget(self.details)
        self.details.hide(); self.diag.toggled.connect(self.details.setVisible)
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
        self.rename.setEnabled(False); self.copy.setEnabled(False)
        self.profile.setEnabled(False); self.activate.setEnabled(False)
        self.controls.setEnabled(False); self.refresh.setEnabled(False); self.device.setEnabled(False)
        self.status.setText('Writing and checking settings…' if request else 'Looking for your G502 X…')
        self.worker = Worker(request)
        self.worker.done.connect(self.loaded)
        self.worker.start()

    def loaded(self, result, error):
        self.refresh.setEnabled(True); self.device.setEnabled(True)
        self.profile.setEnabled(bool(result) and not error)
        self.rename.setEnabled(bool(result) and not error); self.copy.setEnabled(bool(result) and not error)
        if error:
            self.activate.setEnabled(False); self.diag.setChecked(True)
            self.status.setText('Could not save settings.' if self.last_request else 'Mouse connection unavailable.')
            self.details.setPlainText(error+'\n\nTry: sudo systemctl restart ratbagd\nThen reconnect your mouse and click Refresh. For wireless variants, try a USB data cable.\nDo not run this app with sudo. Close Piper or other mouse configuration tools.')
            self.controls.setEnabled(False)
            return
        req = self.last_request or {}
        if req.get('op')=='button' and 'before' in req and req['mapping']!=req['before']:
            self.undo_request = None if req.get('undo') else dict(req,before=req['mapping'],mapping=req['before'],undo=True)
        elif req.get('op')=='copy' or not result:
            self.undo_request = None
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
        if self.last_request and self.last_request['op'] == 'button':
            for row in range(self.button.count()):
                if self.button.itemData(row)['path'] == self.last_request['target']:
                    self.button.setCurrentIndex(row)
                    break
        if not result: self.diag.setChecked(True)
        self.controls.setEnabled(bool(result))
        self.status.setText(('Saved · verified by driver' if self.last_request else 'Connected') if result else 'No supported G502 detected')
        self.details.setPlainText('Driver connected. Changes are checked after each save.\nSelect a profile, then change its sensitivity or button assignments.\nRefresh after reconnecting the mouse or switching profiles with its buttons.' if result else 'Check that the mouse is connected and awake.\nRun ratbagctl list to check driver detection.\nWireless G502 X models may need a newer libratbag version; try configuring over a USB data cable first.\nUpdate CachyOS normally, restart ratbagd, then Refresh. No device IDs or permissions are modified by this app.')

    def nick_key(self,d,p):
        return f"profiles/{d.get('Model') or d['Name']}/{p['Index']}"

    def profile_name(self,d,p):
        nick = self.settings.value(self.nick_key(d,p),'')
        return f"Profile {p['Index']}" + (f" · {nick}" if nick else '')

    def rename_profile(self):
        d,p = self.device.currentData(),self.profile.currentData()
        if not p: return
        key = self.nick_key(d,p)
        name,ok = QInputDialog.getText(self,'Profile nickname','Local nickname',text=self.settings.value(key,''))
        if ok:
            self.settings.setValue(key,name.strip())
            row = self.profile.currentIndex()
            self.show_device(); self.profile.setCurrentIndex(row)

    def copy_profile(self):
        d,source = self.device.currentData(),self.profile.currentData()
        if not source: return
        targets = {self.profile_name(d,p):p for p in d['Profiles'] if p['path']!=source['path'] and not p.get('Disabled')}
        if not targets:
            QMessageBox.information(self,'Copy profile','A second enabled onboard slot is required.')
            return
        name,ok = QInputDialog.getItem(self,'Copy profile','Destination slot',list(targets),0,False)
        if not ok: return
        target = targets[name]
        try:
            changes = copy_plan(source,target)
        except ValueError as exc:
            QMessageBox.warning(self,'Copy profile',str(exc)); return
        if not changes:
            QMessageBox.information(self,'Copy profile','DPI stages, polling rate and assignments already match.'); return
        lines = []
        for group,index,key,value in changes:
            entry = target if group=='Profile' else next(x for x in target[group] if x['Index']==index)
            old = entry.get(key)
            if key=='Mapping':
                old,value = self.describe(old),self.describe(value)
            lines.append(f'{group} {index} · {key}: {old} → {value}')
        answer = QMessageBox.question(self,'Review copy',f"Copy {self.profile_name(d,source)} to {name}?"+'\n\n'+'\n'.join(lines),QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)
        if answer==QMessageBox.Yes:
            self.load(dict(op='copy',device=d['path'],profile=target['path'],source=source['path'],changes=changes,preview=target))

    def record_keys(self):
        dialog = Recorder(self)
        if dialog.exec()==QDialog.Accepted:
            self.action.setCurrentText('Keyboard shortcut…')
            self.keys.setText(dialog.value)

    def undo_button(self):
        if self.undo_request:
            self.load(dict(self.undo_request))

    def map_selected(self,slot):
        self.select_slot(slot)
        self.tabs.setCurrentIndex(1)

    def show_device(self):
        self.profile.blockSignals(True); self.profile.clear()
        d = self.device.currentData()
        if d:
            for p in d['Profiles']:
                self.profile.addItem(self.profile_name(d,p)+(' • active' if p['IsActive'] else '')+(' • disabled' if p.get('Disabled') else ''),p)
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
            device = self.device.currentData()
            wired = device.get('Model', '').startswith('usb:046d:c099:') or device['Name'] == 'Logitech G502 X'
            names = WIRED_G502X_BUTTONS if wired else {}
            order = {slot: position for position, slot in enumerate(names)}
            for button in sorted(p['Buttons'], key=lambda b: order.get(b['Index'], len(order) + b['Index'])):
                index = button['Index']
                control = names.get(index, f'Driver button {index}')
                self.button.addItem(f"{control} — {self.describe(button['Mapping'])}", button)
        self.stage.blockSignals(False); self.button.blockSignals(False)
        self.activate.setEnabled(bool(p) and not p.get('Disabled',False))
        slots = {b['Index'] for b in p['Buttons']} if p and names else set()
        for slot, pick in self.quick_buttons.items():
            pick.setVisible(slot in slots)
        self.copy.setEnabled(bool(p and not p.get('Disabled')))
        self.tabs.setTabEnabled(self.map_tab,bool(slots))
        for slot,pick in self.mouse_map.picks.items():
            pick.setEnabled(slot in slots)
        while self.strip.count():
            self.strip.takeAt(0).widget().deleteLater()
        for row in range(self.stage.count()):
            stage = self.stage.itemData(row)
            flags = [name for prop,name in [('IsActive','Active'),('IsDefault','Default'),('IsDisabled','Off')] if stage.get(prop)]
            dpi = stage['Resolution']
            if isinstance(dpi,list): dpi = '×'.join(map(str,dpi))
            pick = QPushButton(f"{stage['Index']+1} · {dpi}"+ ('\n'+' / '.join(flags) if flags else ''))
            pick.setCheckable(True); pick.setAutoExclusive(True)
            pick.clicked.connect(lambda checked=False,i=row:self.stage.setCurrentIndex(i))
            self.strip.addWidget(pick)
        self.show_stage(); self.show_button()

    def select_slot(self, slot):
        for row in range(self.button.count()):
            if self.button.itemData(row)['Index'] == slot:
                self.button.setCurrentIndex(row)
                return

    def show_stage(self):
        for row in range(self.strip.count()):
            self.strip.itemAt(row).widget().setChecked(row==self.stage.currentIndex())
        r = self.stage.currentData(); self.dpi.clear()
        if r:
            for n in r.get('Resolutions',[]): self.dpi.addItem(str(n))
            value = r['Resolution']; self.dpi.setCurrentText(str(value[0] if isinstance(value,list) else value))
        self.readout.setText(f'{self.dpi.currentText()} DPI' if r else '—')
        self.save_dpi.setEnabled(bool(r) and bool(r.get('Resolutions')))
        self.active_stage.setEnabled(bool(r) and not r.get('IsDisabled',False))

    @staticmethod
    def describe(mapping):
        k,v = mapping
        if k==0:return 'Disabled'
        if k==1:return {1:'Left click',2:'Right click',3:'Middle click',4:'Back',5:'Forward'}.get(v,f'Mouse button {v}')
        if k==2:return SPECIAL.get(v-(1<<30),f'Special {v}')
        for key in ('F13', 'F14', 'F15'):
            events = shortcut(key)
            if mapping in ([4, events], [3, events[0][1]]):
                return key
        if k==4:
            presses = [code for event,code in v if event==1]
            if v == [[1,x] for x in presses]+[[2,x] for x in reversed(presses)]:
                return ' + '.join(str(ecodes.KEY.get(x,x)).removeprefix('KEY_') for x in presses)
            return f'Macro {v}'
        return f'Keyboard key {v}' if k==3 else f'Action {k}'

    def show_button(self):
        b = self.button.currentData(); self.action.clear(); self.keys.clear()
        self.current.setText(self.describe(b['Mapping']) if b else '')
        if b:
            choices = [('Disabled',[0,0])]+[(self.describe([1,n]),[1,n]) for n in range(1,max(8, len(self.profile.currentData()['Buttons'])) + 1)]
            choices += [(name,[2,(1<<30)+n]) for n,name in SPECIAL.items()]
            for key in ('F13', 'F14', 'F15'):
                events = shortcut(key)
                if 4 in b['ActionTypes']:
                    choices.append((key, [4, events]))
                elif 3 in b['ActionTypes']:
                    choices.append((key, [3, events[0][1]]))
            choices += [('Keyboard shortcut…',[4,None])]
            for name,data in choices:
                if data[0] in b['ActionTypes']: self.action.addItem(name,data)
            for i in range(self.action.count()):
                if self.action.itemData(i)==b['Mapping']: self.action.setCurrentIndex(i)
        for slot,pick in self.mouse_map.picks.items():
            pick.setChecked(bool(b and slot==b['Index']))
        self.record.setEnabled(bool(b and 4 in b['ActionTypes']))
        p = self.profile.currentData()
        self.undo.setEnabled(bool(self.undo_request and p and self.undo_request['profile']==p['path']
                                  and self.undo_request['device']==self.device.currentData()['path']))
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
            if mapping == [4, None]: mapping = [4, shortcut(self.keys.text())]
            self.submit('button',target=self.button.currentData()['path'],mapping=mapping,before=self.button.currentData()['Mapping'])
        except (ValueError,TypeError) as e: QMessageBox.warning(self,'Button assignment',str(e))

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.status.setText('Please wait for the current device operation to finish.'); event.ignore()
        else:event.accept()

if __name__=='__main__':
    app = QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    window = Window(); window.show(); sys.exit(app.exec())
