"""UI checks use a fixture, never claim that a real mouse is connected."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from PySide6.QtWidgets import QApplication
from app import Window, STYLE
from test_backend import D

class FixtureWindow(Window):
    def load(self, request=None):
        self.last_request = request
        self.loaded([D], '')

class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.window = FixtureWindow()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_loaded_controls(self):
        self.assertEqual(self.window.device.count(), 1)
        self.assertEqual(self.window.dpi.currentText(), '800')
        self.assertTrue(self.window.controls.isEnabled())
        self.assertEqual(self.window.button.count(), 2)

    def test_disconnect_disables_writes(self):
        self.window.loaded(None, 'Disconnected')
        self.assertFalse(self.window.controls.isEnabled())
        self.assertTrue(self.window.refresh.isEnabled())
        self.assertIn('Disconnected', self.window.details.toPlainText())

    def test_no_mouse(self):
        self.window.loaded([], '')
        self.assertFalse(self.window.controls.isEnabled())
        self.assertIn('No supported G502', self.window.status.text())

    def test_every_wired_control_saves_to_its_physical_slot(self):
        device = copy.deepcopy(D)
        device['Profiles'][0]['Buttons'] = [
            dict(Index=i, path=f'/button/{i}', Mapping=[1, 1], ActionTypes=[1])
            for i in reversed(range(11))
        ]
        self.window.loaded([device], '')
        controls = self.window.button
        self.assertEqual(controls.count(), 11)
        self.window.load = lambda request: setattr(self.window, 'last_request', request)
        for row, slot in enumerate([0, 1, 2, 3, 5, 4, 10, 9, 8, 6, 7]):
            controls.setCurrentIndex(row)
            name = f'G{row + 1} ·' if row < 9 else ['Wheel tilt left', 'Wheel tilt right'][row - 9]
            self.assertTrue(controls.currentText().startswith(name))
            self.window.action.setCurrentText('Mouse button 11')
            self.window.save_button.click()
            self.assertEqual(self.window.last_request['target'], f'/button/{slot}')
            self.assertEqual(self.window.last_request['mapping'], [1, 11])

    def test_aim_and_dpi_buttons_save_distinct_keys_on_active_profile(self):
        from backend import shortcut
        device = copy.deepcopy(D)
        device['Model'] = 'usb:046d:c099:0'
        profile = device['Profiles'][0]
        profile['Buttons'] = [
            dict(Index=i, path=f'/p0/b{i}', Mapping=mapping, ActionTypes=[0,1,2,4])
            for i, mapping in [(0, [1,1]), (4, [2, (1<<30)+11]),
                               (9, [2, (1<<30)+9]), (10, [2, (1<<30)+10])]
        ]
        self.window.loaded([device], '')
        def save(request):
            self.window.last_request = request
            button = next(b for b in profile['Buttons'] if b['path'] == request['target'])
            button['Mapping'] = request['mapping']
            self.window.loaded([device], '')
        self.window.load = save
        for slot, key in [(4, 'F13'), (10, 'F14'), (9, 'F15')]:
            self.window.quick_buttons[slot].click()
            self.window.action.setCurrentText(key)
            self.window.save_button.click()
            self.assertEqual(self.window.last_request['target'], f'/p0/b{slot}')
            self.assertEqual(self.window.last_request['mapping'], [4, shortcut(key)])
            self.assertEqual(self.window.current.text(), key)
