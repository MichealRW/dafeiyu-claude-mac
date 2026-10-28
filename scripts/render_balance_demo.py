"""Render the actual triple-click UI using synthetic balance data only."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from PySide6.QtCore import Qt,QPoint,QPointF
from PySide6.QtGui import QImage,QPainter,QColor,QPen
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import monitor

with tempfile.TemporaryDirectory() as tmp:
    monitor.DATA=Path(tmp)
    import main
    app=QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with patch.object(main,'keep_on_top',lambda w:{}), \
         patch.object(main.Pet,'refresh_usage',lambda w:None), \
         patch.object(main.Pet,'refresh_balance',lambda w:None):
        pet=main.Pet()
        pet.timer.stop();pet.poll.stop();pet.balance_timer.stop()
        pet.hud.hide();pet.set_size(.9);pet.setFixedWidth(400)
        pet.bubble_text='';pet.bubble_until=0
        clock=[100.0]
        pet.balance_thought.clock=lambda:clock[0]
        pet.balance_snapshot=[{'currency':'CNY','balance':'12.34','spent':'0.00'}]
        point=QPoint(200,245)
        frames=[];clicked=0
        for i in range(108):
            t=i/12
            clock[0]=100+t
            pet.t=int(t*1000/main.base.TICK)
            for click_time in [.65,.82,.99]:
                if clicked==[.65,.82,.99].index(click_time) and t>=click_time:
                    QTest.mouseClick(pet,Qt.MouseButton.LeftButton,pos=point)
                    clicked+=1
            if i==20:
                pet.on_balance([{'currency':'CNY','balance':'12.34','spent':'0.00'}])
            pet.motion.clips.idle_started=time.monotonic()-t
            pet.motion.clips.previous=None
            pet.motion.clips.current='think' if pet.balance_thought.active() else 'idle'
            canvas=QImage(pet.size(),QImage.Format.Format_RGBA8888)
            canvas.fill(QColor('#edf5fb'))
            pet.render(canvas)
            if .55<t<1.32:
                painter=QPainter(canvas)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setPen(QPen(QColor('#418ee8'),3))
                painter.setBrush(QColor(115,189,255,70))
                painter.drawEllipse(QPointF(point),15+((t*6)%1)*10,15+((t*6)%1)*10)
                painter.end()
            frames.append(Image.frombytes('RGBA',(canvas.width(),canvas.height()),
                bytes(canvas.constBits())).convert('RGB'))
        frames[0].save(ROOT/'docs/media/triple-click-balance.gif',save_all=True,
            append_images=frames[1:],duration=83,loop=0,optimize=True,
            comment=b'Synthetic balance demo. Character: https://github.com/PC2005-cloud/dsh-pet ; non-commercial use.')
        for w in [pet.hud,pet.palette,pet.conversation,pet.food_panel,pet]:w.hide()
        pet.tray.hide()
print('Rendered triple-click demo with a fictional balance of 12.34 CNY.')
