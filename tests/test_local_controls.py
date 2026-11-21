import copy
import asyncio
import os
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from backend import copy_plan
from controls import Recorder,TestPad
from test_ui import FixtureWindow
from test_backend import D,Fake

class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_record_and_test(self):
        r=Recorder(None); r.show(); self.app.processEvents()
        QTest.keyPress(r,Qt.Key_F14); QTest.keyRelease(r,Qt.Key_F14)
        self.assertEqual(r.value,'F14')
        p=TestPad(); p.show(); p.setFocus(); self.app.processEvents()
        QTest.keyClick(p,Qt.Key_F14)
        self.assertEqual(p.history,['F14  ·  pressed','F14  ·  released'])
        p.close()

    def test_map_and_strip(self):
        w=FixtureWindow(); self.app.processEvents()
        w.map_selected(3)
        self.assertEqual(w.button.currentData()['Index'],3)
        self.assertEqual(w.strip.count(),1)
        self.assertIn('Active',w.strip.itemAt(0).widget().text())
        w.close()

    def test_copy_and_undo_preconditions(self):
        target=copy.deepcopy(D['Profiles'][0])
        source=copy.deepcopy(target);source['path']='/source'
        source['Buttons'][1]['Mapping']=[1,2]
        source['Resolutions'][0]['Resolution']=1600
        plan=copy_plan(source,target)
        self.assertEqual(len(plan),2)
        f=Fake()
        f.data['Profiles'].append(source)
        req=dict(device='/device',profile='/profile',op='copy',source='/source',changes=plan,preview=target)
        result=asyncio.run(f.change(req))
        self.assertEqual(f.commits,1)
        self.assertEqual(copy_plan(source,result[0]['Profiles'][0]),[])
        with self.assertRaises(ValueError):
            asyncio.run(f.change(req))
        with self.assertRaisesRegex(ValueError,'changed'):
            asyncio.run(f.change(dict(device='/device',profile='/profile',op='button',target='/side',before=[1,4],mapping=[1,5])))
