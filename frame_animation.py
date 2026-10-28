"""Playback of complete alpha character poses; bounded on-demand frame cache."""
import json
import sys
import time
from pathlib import Path
from collections import OrderedDict
from PySide6.QtGui import QPixmap,QImage
from PySide6.QtCore import QRectF


class CharacterClips:
    def __init__(self):
        root = Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
        self.root = root/'animations'
        try:
            self.manifest=json.loads((self.root/'manifest.json').read_text())
        except (OSError,ValueError):
            self.manifest={}
        self.cache=OrderedDict()
        self.top_cache={}
        self.content_top=110
        self.previous=None
        self.current=None
        self.changed_at=0
        self.last_frame=None
        self.last_name=None
        self.idle_started=time.monotonic()

    def has(self,name):
        return name in self.manifest

    def duration(self,name):
        return self.manifest[name]['duration']

    def frame(self,name,elapsed,loop=False):
        data=self.manifest[name]
        count=data['frames']
        index=max(0,int(elapsed*data['fps']))
        index=index%count if loop else min(count-1,index)
        key=(name,index)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key],data,index
        pix=QPixmap(str(self.root/name/f'{index:04d}.png'))
        self.cache[key]=pix
        alpha=pix.toImage().convertToFormat(QImage.Format.Format_Alpha8)
        raw=bytes(alpha.constBits()) if not alpha.isNull() else b''
        stride=alpha.bytesPerLine()
        self.top_cache[key]=next((y for y in range(alpha.height())
            if any(raw[y*stride:y*stride+alpha.width()])),0)
        # At most about 16 MiB of decoded frames, rather than every clip in RAM.
        while len(self.cache)>30:
            old_key,_=self.cache.popitem(last=False)
            self.top_cache.pop(old_key,None)
        return pix,data,index

    def draw(self,p,pet,name,elapsed,loop=False):
        if not self.has(name):
            return False
        pix,data,index=self.frame(name,elapsed,loop)
        if pix.isNull():
            return False
        now=time.monotonic()
        if name!=self.current:
            self.previous=self.last_frame
            self.current=name
            self.changed_at=now
        scale=pet.cur_h/data['body_height']
        bottom=getattr(pet,'sprite_bottom',60+pet.cur_h)
        x=pet.width()/2-data['anchor'][0]*scale
        y=bottom-data['anchor'][1]*scale
        rect=QRectF(x,y,pix.width()*scale,pix.height()*scale)
        self.content_top=y+self.top_cache.get((name,index),0)*scale
        fade=min(1,(now-self.changed_at)/.13)
        if self.previous and fade<1:
            old,old_rect=self.previous
            p.save();p.setOpacity(1-fade);p.drawPixmap(old_rect,old,QRectF(0,0,old.width(),old.height()));p.restore()
        p.save();p.setOpacity(fade if self.previous else 1)
        p.drawPixmap(rect,pix,QRectF(0,0,pix.width(),pix.height()));p.restore()
        self.last_frame=(pix,rect)
        self.last_name=name
        return True
