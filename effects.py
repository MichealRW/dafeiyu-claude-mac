"""Code-native SVG props with layered, time-based animation for the whale.

Uses the transform/prop layering pattern of open-source SVG desktop companions;
all vector paths below are drawn for this local adaptation.
"""
import math
import time
from pathlib import Path
from PySide6.QtCore import QRectF, QPointF, Qt, QByteArray
from PySide6.QtGui import QPainter, QPainterPath, QColor, QPen, QFont
from PySide6.QtSvg import QSvgRenderer
from frame_animation import CharacterClips

ACTIONS = {
    'dance': ('🎵 跳舞', 13, '来一段小鲸鱼摇摆舞～'),
    'rice': ('🍚 干饭', 11, '代码写完啦，开饭！'),
    'hearts': ('💕 摸摸头', 6, '嘿嘿，摸头会变聪明吗？'),
    'celebrate': ('🎉 庆祝', 8, '完成啦！今天也超厉害！'),
    'sleep': ('🌙 打个盹', 18, '我眯一小会儿，叫我就醒。'),
    'wave': ('👋 打招呼', 6, '嗨！你的小鲸鱼已上线。'),
    'stretch': ('🙆 伸懒腰', 7, '伸个懒腰，再战三百行～'),
    'dizzy': ('💫 转圈圈', 7, '晕鱼啦，世界怎么在转？'),
    'fish': ('🐟 摸鱼', 10, '我是在巡逻，才不是摸鱼。'),
    'tea': ('🥐 早餐时间', 10, '先吃点早餐，再一起开工～'),
    'coding': ('💻 陪你敲代码', 12, '敲敲敲，今天也是努力的小鱼。'),
    'think': ('💡 思考一下', 9, '让我用聪明的小脑袋想一想。'),
    'happy': ('😊 开心眨眼', 8, '被你发现我的好心情啦！'),
    'shy': ('😳 害羞脸红', 8, '别一直盯着我看呀～'),
    'angry': ('😤 鼓脸生气', 8, '哼，给点小鱼干就原谅你。'),
    'look': ('👀 左顾右盼', 9, '我就看看，真的没有摸鱼。'),
    'talk': ('💬 开口说话', 9, '今天也想听你说说话～'),
    'snack': ('🍪 吃小零食', 10, '嗷呜，一口吃掉！'),
}

PROPS = {
 'heart': '<path d="M32 55S4 39 5 22C6 6 25 6 32 20C39 6 58 6 59 22C60 39 32 55 32 55Z" fill="#ff84a8" stroke="#e26190" stroke-width="2.5"/><path d="M14 20Q17 14 23 18" stroke="white" stroke-width="3" fill="none" stroke-linecap="round"/>',
 'note': '<path d="M25 45V13L53 7V39" fill="none" stroke="#8b78d9" stroke-width="7" stroke-linejoin="round"/><path d="M26 22L53 16" stroke="#8b78d9" stroke-width="6"/><ellipse cx="18" cy="47" rx="11" ry="8" fill="#a08be7"/><ellipse cx="46" cy="41" rx="11" ry="8" fill="#a08be7"/>',
 'bowl': '<ellipse cx="32" cy="56" rx="18" ry="4" fill="#6271a8" opacity=".15"/><path d="M7 28Q10 53 32 53Q54 53 57 28Z" fill="#edf7ff" stroke="#3e6391" stroke-width="2.5"/><path d="M22 51L20 57H44L42 51" fill="#a9d8ee" stroke="#3e6391" stroke-width="2"/><path d="M9 27Q8 19 16 19Q17 10 25 14Q30 5 37 13Q47 8 49 19Q58 18 56 28Z" fill="#fffdf0" stroke="#cbd8e7" stroke-width="2"/><ellipse cx="32" cy="29" rx="26" ry="6" fill="#fffdf4" stroke="#3e6391" stroke-width="2"/><path d="M27 40Q32 35 39 40Q34 47 28 42L22 44V37Z" fill="#7abfdc"/><path d="M18 21L22 23M28 18L32 20M39 20L43 22" stroke="#e8dfc2" stroke-width="2"/>',
 'chopsticks': '<path d="M10 51L53 8M15 55L58 12" stroke="#a67151" stroke-width="4" stroke-linecap="round"/><path d="M13 48L23 38M18 52L28 42" stroke="#ebcfa3" stroke-width="4" stroke-linecap="round"/>',
 'star': '<path d="M32 4L39 23L60 25L44 38L49 59L32 47L15 59L20 38L4 25L25 23Z" fill="#ffdc73" stroke="#d8a955" stroke-width="2.5"/><path d="M22 26L28 24" stroke="white" stroke-width="3" stroke-linecap="round"/>',
 'fish': '<path d="M13 32Q32 5 53 32Q32 59 13 32Z" fill="#8bcfe7" stroke="#467d9d" stroke-width="2.5"/><path d="M14 32L3 19V45Z" fill="#adcce9" stroke="#467d9d" stroke-width="2.5"/><circle cx="43" cy="28" r="3" fill="#33566d"/><path d="M28 26L36 32L28 39" fill="#c5eaf4"/>',
 'moon': '<path d="M43 7A25 25 0 1 0 57 43A23 23 0 0 1 43 7Z" fill="#ffe6a0" stroke="#d2b974" stroke-width="2"/><circle cx="13" cy="12" r="2" fill="#9d9fdd"/><circle cx="54" cy="17" r="3" fill="#9d9fdd"/>',
 'cup': '<path d="M11 21H46V43Q44 54 29 54Q13 54 11 43Z" fill="#b9e2ed" stroke="#467a9c" stroke-width="2.5"/><path d="M46 25H53Q63 36 47 41" fill="none" stroke="#467a9c" stroke-width="4"/><ellipse cx="29" cy="21" rx="18" ry="5" fill="#fff5db" stroke="#467a9c" stroke-width="2"/><path d="M8 57H53" stroke="#9ac6dc" stroke-width="4" stroke-linecap="round"/>',
 'laptop': '<rect x="8" y="9" width="48" height="34" rx="4" fill="#425e87" stroke="#273d60" stroke-width="2"/><rect x="12" y="13" width="40" height="25" rx="2" fill="#c8eafb"/><path d="M8 44L2 55Q32 61 62 55L56 44Z" fill="#bdcbe4" stroke="#526d95" stroke-width="2"/><path d="M21 21L16 25L21 29M42 21L47 25L42 29M35 18L28 32" stroke="#5f84aa" stroke-width="2" fill="none"/>',
 'bulb': '<path d="M21 43C20 35 12 32 14 22C17 4 47 4 50 22C52 32 44 35 43 43Z" fill="#ffe48d" stroke="#b89950" stroke-width="2.5"/><path d="M21 45H43M23 51H41M27 57H37" stroke="#6f8ca6" stroke-width="4" stroke-linecap="round"/><path d="M32 18Q22 17 21 26" stroke="white" stroke-width="3" fill="none" stroke-linecap="round"/>',
}


class Motion:
    def __init__(self):
        self.name = None
        self.started = 0
        self.duration = 0
        self.intensity = 1.0
        self.clips = CharacterClips()
        self.rate = 1.0
        self.svg = {k:QSvgRenderer(QByteArray(('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'+v+'</svg>').encode())) for k,v in PROPS.items()}

    def start(self, name, intensity=1.0):
        self.name = name
        self.started = time.monotonic()
        self.duration = ACTIONS[name][1]
        self.intensity = intensity
        self.rate = max(.65,min(1.4,intensity)) if name=='dance' else 1.0
        if self.clips.has(name):
            self.duration = self.clips.duration(name)/self.rate

    def active(self):
        if self.name and time.monotonic()-self.started >= self.duration:
            self.name = None
        return self.name

    def prop(self,p,name,x,y,size,rotation=0,opacity=1):
        p.save()
        p.setOpacity(opacity)
        p.translate(x,y)
        p.rotate(rotation)
        self.svg[name].render(p,QRectF(-size/2,-size/2,size,size))
        p.restore()

    def render(self,pet):
        """Render props behind/front of an independently transformed character."""
        p=QPainter(pet)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        now=pet.t*0.02
        name=self.active()
        t=time.monotonic()-self.started if name else 0
        strength=self.intensity
        h=pet.cur_h
        cx=pet.width()/2
        bottom=getattr(pet,'sprite_bottom',60+h)
        top=bottom-h
        # Complete character frames include actual eyes, mouth, cheeks, hands,
        # and food movement. No static mouth / bowl is composited over this path.
        clip = name if self.clips.has(name) else None
        elapsed=t*self.rate
        loop=False
        if pet.dragging and self.clips.has('drag'):
            clip='drag';elapsed=now;loop=True
        elif name is None and pet.target is None and self.clips.has('idle'):
            clip='idle';elapsed=time.monotonic()-self.clips.idle_started;loop=True
        if clip and self.clips.draw(p,pet,clip,elapsed,loop):
            self.draw_caption(p,pet,now,name)
            p.end()
            return
        breath=1+0.012*math.sin(now*2.5)
        rot=math.sin(now*2.5)*1.2
        dx=dy=0
        sx=sy=breath
        if pet.target is not None and not pet.dragging:
            dy=-abs(math.sin(now*4.5))*6
            rot=math.sin(now*9)*3
        if name=='dance':
            beat=t*math.tau*1.8
            rot=math.sin(beat/2)*9*strength
            dx=math.sin(beat/2)*h*.035*strength
            dy=-abs(math.sin(beat))*h*.045*strength
            sx=breath+.025*math.cos(beat)
            sy=breath-.025*math.cos(beat)
            if 4<t<5.1 or 9<t<10.1:
                sx*=max(.17,abs(math.cos((t%5-4)*math.pi)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(162,147,228,55))
            p.drawEllipse(QRectF(cx-h*.35,bottom-7,h*.7,12))
            for i in range(4):
                phase=(t*.42+i*.23)%1
                x=cx+(1 if i%2 else -1)*h*(.27+.04*math.sin(t*2+i))
                self.prop(p,'note',x,top+h*(.75-phase*.65),h*.16,math.sin(t*3+i)*18,1-phase*.6)
        elif name=='rice':
            rot=math.sin(t*9)*2.8
            dy=abs(math.sin(t*9))*3
            sx+=.022*abs(math.sin(t*9))
        elif name=='hearts':
            rot=math.sin(t*3)*3
            dy=-abs(math.sin(t*4))*5
        elif name=='celebrate':
            dy=-abs(math.sin(t*5))*h*.08
            rot=math.sin(t*5)*4
        elif name=='sleep':
            rot=10+math.sin(t*1.4)*2
            sy=.92+.022*math.sin(t*1.4)
            dy=h*.07
        elif name=='wave':
            rot=math.sin(t*5)*5
            dy=-abs(math.sin(t*3))*3
        elif name=='stretch':
            k=math.sin(min(1,t/7)*math.pi)
            sy=breath+k*.08
            sx=breath-k*.035
            rot=math.sin(t*1.3)*2
        elif name=='dizzy':
            dx=math.sin(t*5)*7
            rot=math.sin(t*5)*13
            sx=abs(math.cos(t*3))*.8+.2
        elif name=='fish':
            rot=math.sin(t*3)*8
            dy=math.sin(t*3)*4
        elif name=='tea':
            rot=math.sin(t*1.7)*3
        elif name=='coding':
            dy=abs(math.sin(t*11))*2
            rot=math.sin(t*5)*1.5
        elif name=='think':
            rot=8+math.sin(t*2)*2
        if pet.jump_t>0:
            dy-=abs(math.sin(pet.jump_t*math.pi))*14*pet.jump_t
        if pet.dragging:
            rot=math.sin(now*7)*5
        key=pet._sprite_key()
        if name and not pet.dragging:
            key=('正面',h,1)
        pix=pet.sprites[key[:2]]
        pw=pix.width()
        p.save()
        p.translate(cx+dx,bottom+dy)
        p.rotate(rot)
        p.scale(sx*key[2],sy)
        p.drawPixmap(QRectF(-pw/2,-h,pw,h),pix,QRectF(0,0,pw,h))
        p.restore()
        if name=='rice':
            self.prop(p,'bowl',cx,top+h*.70,h*.36)
            cyc=(t*1.8)%1
            k=math.sin(cyc*math.pi)
            self.prop(p,'chopsticks',cx+h*(.18-.08*k),top+h*(.59-.20*k),h*.29,-15+25*k)
            p.setPen(QPen(QColor('#d5b58a'),1.6,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            if k>.45:
                p.drawLine(QPointF(cx+h*.04,top+h*(.52-.14*k)),QPointF(cx+h*.07,top+h*(.53-.14*k)))
            for i in range(3):
                phase=(t*.45+i*.33)%1
                p.setPen(QPen(QColor(166,190,207,int((1-phase)*180)),1.6))
                path=QPainterPath(QPointF(cx+(i-1)*h*.075,top+h*(.57-phase*.15)))
                path.cubicTo(cx+h*.04,top+h*.50,cx-h*.03,top+h*.47,cx+(i-1)*h*.075,top+h*(.49-phase*.15))
                p.drawPath(path)
        elif name=='hearts':
            for i in range(7):
                phase=(t*.42+i*.14)%1
                self.prop(p,'heart',cx+math.sin(i*2.8+t)*h*.32,top+h*(.7-phase*.7),h*(.09+phase*.04),math.sin(t+i)*15,1-phase)
        elif name=='celebrate':
            for i in range(16):
                phase=(t*.32+i*.061)%1
                a=i*2.4
                x=cx+math.cos(a)*h*(.12+phase*.37)
                y=top+h*.2+phase*h*.66
                p.save();p.translate(x,y);p.rotate(t*100+i*28)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(['#ffb0cb','#a0dfe9','#c4b6f2','#f8d77f'][i%4]))
                p.drawRoundedRect(QRectF(-2,-3,4,7),1,1);p.restore()
            self.prop(p,'star',cx,top+h*.03,h*.20,math.sin(t*3)*12)
        elif name=='sleep':
            self.prop(p,'moon',cx-h*.25,top+h*.12,h*.20)
            p.setPen(QColor('#7f8bb5'))
            for i in range(3):
                phase=(t*.20+i*.33)%1
                p.setOpacity(1-phase)
                p.setFont(QFont('Helvetica Neue',int(11+phase*9)))
                p.drawText(QPointF(cx+h*(.15+phase*.2),top+h*(.4-phase*.35)),'z')
            p.setOpacity(1)
        elif name=='dizzy':
            for i in range(4):
                a=t*4+i*math.pi/2
                self.prop(p,'star',cx+math.cos(a)*h*.30,top+h*.16+math.sin(a)*h*.065,h*.12,t*70)
        elif name=='fish':
            self.prop(p,'fish',cx+math.sin(t*2)*h*.28,top+h*.72+math.sin(t*4)*h*.05,h*.28,math.sin(t*2)*18)
            p.setPen(QPen(QColor('#8bcddd'),1.3))
            p.setBrush(QColor(170,222,238,30))
            for i in range(4):
                phase=(t*.28+i*.25)%1
                p.drawEllipse(QPointF(cx+math.cos(i*2)*h*.32,top+h*(.75-phase*.5)),3+phase*3,3+phase*3)
        elif name=='tea':
            self.prop(p,'cup',cx+h*.08,top+h*(.67-.08*max(0,math.sin(t*2))),h*.32,-10*math.sin(t*2))
        elif name=='coding':
            self.prop(p,'laptop',cx,top+h*.74,h*.46)
            p.setBrush(QColor('#ffe4d1'));p.setPen(Qt.PenStyle.NoPen)
            for side in (-1,1):
                p.drawEllipse(QPointF(cx+side*h*.13,top+h*.76+math.sin(t*17+side)*2),h*.025,h*.022)
        elif name=='think':
            self.prop(p,'bulb',cx+h*.25,top+h*.19,h*.21,math.sin(t*2)*5)
            for i in range(3):
                p.setBrush(QColor('#bad4ed'));p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(cx+h*(.12+i*.06),top+h*(.37-i*.06)),2+i,2+i)
        self.draw_caption(p,pet,now,name)
        p.end()

    def draw_caption(self,p,pet,now,name):
        # Bubble stays in its own coordinate layer; it never spins with the body.
        if pet.bubble_text and now<pet.bubble_until:
            p.setFont(QFont('PingFang SC',10))
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(249,252,255,240))
            p.drawRoundedRect(QRectF(4,4,pet.width()-8,43),11,11)
            p.setPen(QColor('#3c5777'))
            p.drawText(QRectF(10,7,pet.width()-20,37),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,pet.bubble_text)
        if name:
            p.setPen(QColor('#6585a4'))
            p.setFont(QFont('PingFang SC',8))
            p.drawText(QRectF(0,pet.height()-14,pet.width(),14),Qt.AlignmentFlag.AlignCenter,ACTIONS[name][0])
