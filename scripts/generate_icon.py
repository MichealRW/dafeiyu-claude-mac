"""Compose the app icon from the credited character frame and native Qt shapes."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import subprocess
import sys
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QImage,QPainter,QColor,QLinearGradient,QPen,QPainterPath
from PySide6.QtWidgets import QApplication

ROOT=Path(__file__).resolve().parents[1]
app=QApplication.instance() or QApplication([])
image=QImage(1024,1024,QImage.Format.Format_ARGB32_Premultiplied)
image.fill(Qt.GlobalColor.transparent)
p=QPainter(image)
p.setRenderHints(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.SmoothPixmapTransform)
for spread in range(16,0,-1):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(27,65,107,2))
    p.drawRoundedRect(QRectF(38-spread/2,45-spread/2,948+spread,944+spread),208,208)
gradient=QLinearGradient(80,40,920,970)
gradient.setColorAt(0,QColor('#f2fcff'))
gradient.setColorAt(.5,QColor('#c7e9fc'))
gradient.setColorAt(1,QColor('#7eb2ed'))
p.setBrush(gradient)
p.setPen(QPen(QColor('#f6fcff'),5))
p.drawRoundedRect(QRectF(40,32,944,944),206,206)
clip=QPainterPath();clip.addRoundedRect(QRectF(43,35,938,938),203,203)
p.setClipPath(clip)
p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(255,255,255,95))
p.drawEllipse(QRectF(-100,-130,1000,760))
p.setBrush(QColor(84,133,206,40));p.drawEllipse(QRectF(170,850,680,120))
character=QImage(str(ROOT/'animations/happy/0060.png'))
# Smile, cheeks and both little fists stay in one complete source frame.
p.drawImage(QRectF(68,125,888,850),character,QRectF(73,59,238,228))
p.setClipping(False)
p.setPen(QPen(QColor('#add0ed'),3));p.setBrush(QColor('#ffffff'))
p.drawRoundedRect(QRectF(745,78,172,126),43,43)
tail=QPainterPath();tail.moveTo(774,192);tail.lineTo(769,230);tail.lineTo(811,198)
p.fillPath(tail,QColor('#ffffff'))
p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#4a78b5'))
for x in [786,831,876]:p.drawEllipse(QPointF(x,141),9,9)
p.end()
(ROOT/'assets').mkdir(exist_ok=True)
image.setText('Attribution','Character: https://github.com/PC2005-cloud/dsh-pet ; non-commercial use. Icon composition: MichealRW.')
image.save(str(ROOT/'assets/app-icon.png'))
# Keep the original tray glyph as-is: menu bar icons need a small silhouette.
if sys.platform=='darwin':
    with tempfile.TemporaryDirectory() as tmp:
        iconset=Path(tmp)/'AppIcon.iconset';iconset.mkdir()
        for size in [16,32,128,256,512]:
            for factor in [1,2]:
                suffix='@2x' if factor==2 else ''
                image.scaled(size*factor,size*factor,Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation).save(str(iconset/f'icon_{size}x{size}{suffix}.png'))
        subprocess.run(['iconutil','-c','icns',str(iconset),'-o',str(ROOT/'assets/AppIcon.icns')],check=True)
print('Generated assets/app-icon.png and macOS AppIcon.icns.')
