"""Regression tests for the no-popup-on-left-click interaction contract."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QImage
import main


class InteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.patches=[patch.object(main,'DATA',root),patch.object(main.base,'CONFIG_PATH',str(root/'config.json')),
            patch.object(main,'AUTOSTART',root/'autostart.plist'),patch.object(main,'keep_on_top',lambda w:{}),
            patch.object(main.Pet,'refresh_usage',lambda w:None),patch.object(main.Pet,'refresh_balance',lambda w:None)]
        for p in self.patches:p.start()
        self.pet=main.Pet()
        self.pet.poll.stop();self.pet.balance_timer.stop()
        self.pet.hud.hide()

    def tearDown(self):
        self.pet.timer.stop();self.pet.tray.hide()
        for widget in [self.pet.hud,self.pet.palette,self.pet.conversation,self.pet.food_panel,self.pet]:
            widget.hide();widget.deleteLater()
        self.app.processEvents()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def assert_no_panel(self):
        self.assertFalse(self.pet.conversation.isVisible())
        self.assertFalse(self.pet.palette.isVisible())
        self.assertFalse(self.pet.food_panel.isVisible())

    def test_left_click_only_reacts(self):
        QTest.mouseClick(self.pet,Qt.MouseButton.LeftButton,pos=QPoint(self.pet.width()//2,150))
        QTest.qWait(self.pet.click_interval_ms+80)
        self.assert_no_panel()
        self.assertIn(self.pet.motion.name,['hearts','happy','shy','angry','wave'])
        self.assertFalse(self.pet.chat_paused)

    def test_double_click_only_reacts(self):
        point=QPoint(self.pet.width()//2,150)
        QTest.mouseClick(self.pet,Qt.MouseButton.LeftButton,pos=point)
        QTest.mouseDClick(self.pet,Qt.MouseButton.LeftButton,pos=point)
        QTest.mouseRelease(self.pet,Qt.MouseButton.LeftButton,pos=point)
        QTest.qWait(self.pet.click_interval_ms+80)
        self.assert_no_panel()
        self.assertIn(self.pet.motion.name,['hearts','happy','shy','angry','wave'])

    def triple_click(self):
        point=QPoint(self.pet.width()//2,150)
        QTest.mouseClick(self.pet,Qt.MouseButton.LeftButton,pos=point)
        QTest.mouseDClick(self.pet,Qt.MouseButton.LeftButton,pos=point)
        QTest.mouseRelease(self.pet,Qt.MouseButton.LeftButton,pos=point)
        QTest.mouseClick(self.pet,Qt.MouseButton.LeftButton,pos=point)

    def test_triple_click_shows_cached_balance_and_refreshes_without_panel(self):
        self.pet.balance_snapshot=[{'currency':'CNY','balance':'12.34','spent':'0.01'}]
        with patch.object(self.pet,'refresh_balance') as refresh:
            self.triple_click()
            refresh.assert_called_once()
        self.assertEqual(self.pet.bubble_text,'余额 ¥12.34')
        image=QImage(self.pet.size(),QImage.Format.Format_ARGB32)
        self.pet.render(image)
        self.assertEqual(self.pet.motion.clips.last_name,'think')
        self.assert_no_panel()
        self.assertFalse(self.pet._click_timer.isActive())
        self.pet.say('ordinary idle message')
        self.assertEqual(self.pet.bubble_text,'余额 ¥12.34')
        self.pet.on_balance([{'currency':'CNY','balance':'12.30','spent':'0.05'}])
        self.assertEqual(self.pet.bubble_text,'余额 ¥12.30')
        self.assertFalse(self.pet.balance_bubble_pending)

    def test_manual_action_interrupts_thought_and_late_reply_keeps_its_speech(self):
        self.triple_click()
        self.pet.start_action('wave')
        speech=self.pet.bubble_text
        self.pet.on_balance([{'currency':'CNY','balance':'12.30','spent':'0.00'}])
        self.assertFalse(self.pet.balance_thought.active())
        self.assertEqual(self.pet.motion.name,'wave')
        self.assertEqual(self.pet.bubble_text,speech)

    def test_triple_click_handles_missing_cache_and_refresh_failure(self):
        self.triple_click()
        self.assertEqual(self.pet.bubble_text,'正在查余额…')
        with patch.object(main,'write_private'):
            self.pet.on_balance_error('network unavailable')
        self.assertIn('稍后再试',self.pet.bubble_text)
        self.assert_no_panel()

    def test_drag_does_not_count_as_a_click(self):
        point=QPoint(100,150)
        QTest.mouseClick(self.pet,Qt.MouseButton.LeftButton,pos=point)
        QTest.mousePress(self.pet,Qt.MouseButton.LeftButton,pos=point)
        self.pet.dragging=True
        QTest.mouseRelease(self.pet,Qt.MouseButton.LeftButton,pos=point)
        self.assertEqual(self.pet._click_count,0)
        self.assertFalse(self.pet._click_timer.isActive())

    def test_right_click_exposes_all_extra_interactions(self):
        result=[]
        def inspect_menu():
            menu=self.app.activePopupWidget()
            if isinstance(menu,QMenu):
                result.extend(a.text() for a in menu.actions())
                menu.close()
        QTest.mouseClick(self.pet,Qt.MouseButton.RightButton,pos=QPoint(20,120))
        QTest.qWait(80)
        inspect_menu()
        self.assertTrue(any('聊天' in x for x in result))
        self.assertTrue(any('投喂' in x for x in result))
        self.assertTrue(any('动作与表情' in x for x in result))

    def test_complete_character_clips_are_available(self):
        for name in ['idle','drag',*main.ACTIONS.keys()]:
            self.assertTrue(self.pet.motion.clips.has(name))
            pix,info,index=self.pet.motion.clips.frame(name,2.0)
            self.assertFalse(pix.isNull())
            self.assertGreater(info['frames'],100)


if __name__=='__main__':
    unittest.main()
