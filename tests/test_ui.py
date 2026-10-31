"""UI checks use a fixture, never claim that a real mouse is connected."""
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
