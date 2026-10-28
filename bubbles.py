"""Soft comic speech and thought bubbles, drawn in the character's palette."""
import math
import time
from functools import lru_cache
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import (QPainterPath,QColor,QPen,QFont,QFontDatabase,
    QFontMetricsF,QLinearGradient)


@lru_cache(maxsize=1)
def round_families():
    available=set(QFontDatabase.families())
    return [name for name in ['Yuanti SC','Arial Rounded MT Bold','PingFang SC','sans-serif']
        if name in available or name=='sans-serif']


def round_font(pixels,number=False):
    font=QFont()
    families=round_families()
    if number and 'Arial Rounded MT Bold' in families:
        families=['Arial Rounded MT Bold',*families]
    font.setFamilies(families)
    font.setPixelSize(round(pixels))
    font.setWeight(QFont.Weight.DemiBold)
    return font


def ui_scale(pet):
    return max(.9,min(1.3,pet.cur_h/240))


@lru_cache(maxsize=48)
def bubble_path(width,height,thought):
    w,h=width,height
    path=QPainterPath()
    if thought:
        path.addRoundedRect(QRectF(w*.08,h*.12,w*.84,h*.78),h*.24,h*.24)
        for x,y,ew,eh in [(.10,0,.35,.43),(.36,-.01,.40,.44),(.65,.08,.29,.39),
                (0,.25,.28,.59),(.76,.25,.24,.59),(.14,.62,.41,.38),(.45,.65,.40,.34)]:
            lobe=QPainterPath();lobe.addEllipse(QRectF(x*w,y*h,ew*w,eh*h))
            path=path.united(lobe)
    else:
        path.moveTo(20,0)
        path.cubicTo(w*.36,-1,w*.69,1,w-20,0)
        path.cubicTo(w-5,-1,w+1,10,w,20)
        path.lineTo(w,h-19)
        path.cubicTo(w,h-4,w-9,h+1,w-21,h)
        path.cubicTo(w*.68,h+1,w*.35,h-1,20,h)
        path.cubicTo(5,h+1,-1,h-10,0,h-20)
        path.lineTo(0,20)
        path.cubicTo(-1,7,8,-1,20,0)
        path.closeSubpath()
        tail=QPainterPath()
        tail.moveTo(w*.56,h-2)
        tail.cubicTo(w*.58,h+5,w*.62,h+10,w*.69,h+13)
        tail.cubicTo(w*.66,h+6,w*.68,h+2,w*.71,h-2)
        tail.closeSubpath()
        path=path.united(tail)
    return path


def ease_pop(age):
    progress=max(0,min(1,age/.34))
    c=1.18
    return 1+(c+1)*(progress-1)**3+c*(progress-1)**2


def begin_bubble(p,x,y,width,height,age,remaining,thought=False):
    fade=min(1,max(0,age/.14),max(0,remaining/.28))
    p.save()
    p.setOpacity(fade)
    p.translate(x+width/2,y+height/2+math.sin(age*2.4)*1.4)
    p.rotate(math.sin(age*1.8)*.65)
    scale=max(.04,ease_pop(age))*(1-.025*(1-min(1,remaining/.28)))
    p.scale(scale,scale)
    p.translate(-width/2,-height/2)
    path=bubble_path(round(width,2),round(height,2),thought)
    p.save();p.translate(0,2.5)
    p.fillPath(path,QColor(83,106,151,28));p.restore()
    gradient=QLinearGradient(0,0,0,height)
    gradient.setColorAt(0,QColor('#fffdf8'));gradient.setColorAt(1,QColor('#edf4ff'))
    p.setBrush(gradient);p.setPen(QPen(QColor('#8291b2'),1.6))
    p.drawPath(path)
    # A small highlight keeps the outline soft rather than a system notification.
    p.setPen(QPen(QColor(255,255,255,210),2.3,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(width*.17,7),QPointF(width*.31,7))
    return fade


def thought_dots(p,width,height,age):
    for index,(x,y,r) in enumerate([(width*.67,height+5,4.8),(width*.64,height+15,2.9)]):
        pulse=.93+.09*math.sin(age*3-index*.7)
        p.setBrush(QColor('#f1f5ff'));p.setPen(QPen(QColor('#8796b5'),1.2))
        p.drawEllipse(QPointF(x,y),r*pulse,r*pulse)


def wrapped_lines(text,font,width,max_lines=3):
    metrics=QFontMetricsF(font)
    lines=[];line=''
    for char in text:
        if char=='\n':
            lines.append(line);line=''
        elif line and metrics.horizontalAdvance(line+char)>width:
            lines.append(line);line=char
        else:
            line+=char
    if line:lines.append(line)
    if len(lines)==2 and '\n' not in text:
        candidates=[]
        for split in range(1,len(text)):
            left,right=text[:split],text[split:]
            lw,rw=metrics.horizontalAdvance(left),metrics.horizontalAdvance(right)
            if max(lw,rw)<=width:
                score=abs(lw-rw)-(width*.28 if left[-1] in '，。…～！？：' else 0)
                candidates.append((score,left,right))
        if candidates:
            _,left,right=min(candidates)
            lines=[left,right]
    if len(lines)>max_lines:
        lines=lines[:max_lines-1]+[metrics.elidedText(''.join(lines[max_lines-1:]),
            Qt.TextElideMode.ElideRight,width)]
    return lines


def headroom_y(pet,height,thought):
    clips=getattr(getattr(pet,'motion',None),'clips',None)
    top=getattr(clips,'content_top',110)
    return max(6,min(64,top-height-(21 if thought else 14)-7))


def draw_speech(p,pet,now):
    if not pet.bubble_text or now>=pet.bubble_until:
        return
    age=max(.001,now-getattr(pet,'_bubble_started_tick',now-.5))
    thought=getattr(pet,'bubble_inner',False)
    text=pet.bubble_text
    if thought and text.startswith('（') and text.endswith('）'):text=text[1:-1]
    scale=ui_scale(pet)
    font=round_font(18*scale)
    padding=22 if thought else 15
    width=min(pet.width()-22,350,max(154,QFontMetricsF(font).horizontalAdvance(text)+2*padding))
    lines=wrapped_lines(text,font,width-padding*2)
    line_height=QFontMetricsF(font).height()+2
    height=max(42,min(86,len(lines)*line_height+18))
    # Three large-font lines still fit the reserved 104 px headroom.
    if len(lines)*line_height>height-12:
        lines=wrapped_lines(text,font,width-padding*2,max(1,int((height-12)/line_height)))
    x=(pet.width()-width)/2;y=headroom_y(pet,height,thought)
    begin_bubble(p,x,y,width,height,age,pet.bubble_until-now,thought)
    if thought:thought_dots(p,width,height,age)
    p.setFont(font);p.setPen(QColor('#405379'))
    text_top=(height-len(lines)*line_height)/2
    for i,line in enumerate(lines):
        p.drawText(QRectF(padding,text_top+i*line_height,width-2*padding,line_height),
            Qt.AlignmentFlag.AlignCenter,line)
    p.restore()


class BalanceThought:
    """One short thinking scene; late network replies never reopen a closed scene."""
    INTRO_SECONDS=1.15

    def __init__(self,clock=None):
        self.clock=clock or time.monotonic
        self.started=None
        self.expires=0
        self.rows=[]
        self.state='query'

    def begin(self,rows):
        self.started=self.clock()
        self.expires=self.started+8
        self.rows=list(rows)
        self.state='cached' if rows else 'query'

    def active(self):
        return self.started is not None and self.clock()<self.expires

    def cancel(self):
        self.expires=0

    def resolve(self,rows=None,error=False):
        if not self.active():return False
        if rows is not None:self.rows=list(rows)
        self.state='error' if error else 'ready'
        self.expires=min(self.started+12,max(self.started+6.2,self.clock()+4.4))
        return True

    def pose_elapsed(self):
        age=self.clock()-self.started
        # Only the early chin-touching pose: later original frames include
        # unrelated baked-in lunch chatter, so never play that section here.
        return age if age<.9 else .9+.7*(1-math.cos((age-.9)*2.4))/2

    def phase(self):
        return 'intro' if self.clock()-self.started<self.INTRO_SECONDS else self.state

    def draw(self,p,pet):
        if not self.active():return
        age=self.clock()-self.started
        remaining=self.expires-self.clock()
        width=min(pet.width()-24,250);height=80
        x=(pet.width()-width)/2;y=headroom_y(pet,height,True)
        begin_bubble(p,x,y,width,height,age-.06,remaining,True)
        thought_dots(p,width,height,age)
        scale=ui_scale(pet)
        phase=self.phase()
        loading=phase in ['intro','query']
        if loading:title='唔…还剩多少呢？'
        elif not self.rows:title='咦，没查出来…'
        elif self.state=='error':title='先记着上次的…'
        elif self.state=='cached':title='我记得还剩…'
        else:title='小鱼干余额还剩…'
        p.setFont(round_font(max(16,min(18,16*scale))));p.setPen(QColor('#53648b'))
        p.drawText(QRectF(12,12,width-24,23),Qt.AlignmentFlag.AlignCenter,title)
        if loading:
            for i in range(3):
                pulse=(math.sin(age*5-i*.8)+1)/2
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(115,145,193,round(100+155*pulse)))
                p.drawEllipse(QPointF(width/2+(i-1)*17,53-pulse*3),4,4)
        elif self.rows:
            row=self.rows[0]
            amount={'CNY':'¥','USD':'$'}.get(row['currency'],row['currency']+' ')+row['balance']
            font=round_font(max(30,min(34,30*scale)),True)
            p.setFont(font);p.setPen(QColor('#354c7c'))
            p.drawText(QRectF(16,34,width-32,38),Qt.AlignmentFlag.AlignCenter,
                QFontMetricsF(font).elidedText(amount,Qt.TextElideMode.ElideRight,width-32))
        else:
            p.setFont(round_font(18*scale));p.setPen(QColor('#53648b'))
            p.drawText(QRectF(15,34,width-30,28),Qt.AlignmentFlag.AlignCenter,'过会儿再看看～')
        p.restore()
