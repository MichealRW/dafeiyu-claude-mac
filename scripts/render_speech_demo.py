"""Render speech / inner-thought styling with fictional, local-only dialogue."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys,tempfile,time,math
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from PySide6.QtGui import QImage,QColor,QPainter,QFont
from PySide6.QtCore import Qt,QRectF
from PySide6.QtWidgets import QApplication
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import monitor

with tempfile.TemporaryDirectory() as tmp:
    monitor.DATA=Path(tmp)
    import main
    app=QApplication([])
    with patch.object(main,'keep_on_top',lambda w:{}), \
         patch.object(main.Pet,'refresh_usage',lambda w:None), \
         patch.object(main.Pet,'refresh_balance',lambda w:None):
        pet=main.Pet();pet.timer.stop();pet.poll.stop();pet.balance_timer.stop()
        pet.hud.hide();pet.set_size(.55)
        frames=[];samples=[]
        for i in range(96):
            t=i/12;pet.t=int(t*1000/main.base.TICK)
            if i==4:
                pet.start_action('happy',speak=False);pet.say('嘿嘿，被你戳到啦～')
            if i==47:
                pet.start_action('think',speak=False);pet.say('让我想想…午饭吃什么呢？',inner=True)
            if i<47:
                pet.motion.started=time.monotonic()-max(0,t-.33)
            else:
                pet.motion.started=time.monotonic()-(.9+.65*(1-math.cos((t-3.9)*2))/2)
            pet.motion.clips.previous=None
            pet.motion.clips.current=pet.motion.name or 'idle'
            image=QImage(pet.size(),QImage.Format.Format_RGBA8888);image.fill(QColor('#edf5fb'))
            pet.render(image)
            frame=Image.frombytes('RGBA',(image.width(),image.height()),bytes(image.constBits())).convert('RGB')
            frames.append(frame)
            if i in [16,64]:samples.append(frame.copy())
        frames[0].save(ROOT/'docs/media/speech-bubbles.gif',save_all=True,append_images=frames[1:],
            duration=83,loop=0,optimize=True,
            comment=b'Character: https://github.com/PC2005-cloud/dsh-pet ; non-commercial use. Synthetic dialogue.')
        for i,im in enumerate(samples):im.save(ROOT/f'docs/media/bubble-style-{i}.png')
        for w in [pet.hud,pet.palette,pet.conversation,pet.food_panel,pet]:w.hide()
        pet.tray.hide()
print('Rendered matching speech and inner-thought bubble styles.')
