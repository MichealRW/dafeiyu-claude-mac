"""macOS adaptation of 1190fasheqi/dafeiyu-pet, with a local Claude usage HUD."""
import os
import sys
import json
import html
import random
import threading
import plistlib
import time
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QObject, Signal, QLockFile
from PySide6.QtGui import QFont, QIcon, QAction, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QApplication, QWidget, QFrame, QLabel, QVBoxLayout,
    QHBoxLayout, QPushButton, QLineEdit, QTextBrowser, QMenu, QSystemTrayIcon,
    QDialog, QMessageBox, QGridLayout, QRadioButton, QCheckBox)
import upstream_pet as base
from monitor import DATA, CST, UsageReader, BalanceLedger, request_api, chat, write_private, api_key
from effects import Motion, ACTIONS
from mac_window import keep_on_top

APP_BUNDLE = Path.home() / 'Applications/大肥鱼桌宠.app'
AUTOSTART = Path.home() / 'Library/LaunchAgents/local.dafeiyu.claude.plist'
DATA.mkdir(parents=True, exist_ok=True)
base.CONFIG_PATH = str(DATA / 'config.json')
base.BUBBLE_H = 104  # Keep complete raised-arm / jumping poses below the bubble.
base.LINES = ['我在旁边帮你数 token～', '努力干活，记得喝水。', '白饭可以吃，预算也要看好！', '有我陪着，写代码不孤单。']
base.INNER_LINES = ['今天又学到了新知识。', '什么时候开饭呀？', '主人在认真工作，我小声一点。']
base.REACT_LINES = ['收到摸摸头！', '嘿嘿，被你戳到啦。', '今天也陪你一起写代码。']
if not Path(base.CONFIG_PATH).exists():
    write_private(base.CONFIG_PATH, {'mode':'still','size':0.55,'topmost':True,'passthrough':False,
        'autostart':False,'x':None,'y':None,'hud':True})


def compact(n):
    return f'{n/1000000:.2f}M' if n >= 1000000 else f'{n/1000:.1f}k' if n >= 1000 else str(n)


STYLE = '''
QWidget { font-family: "PingFang SC", "Helvetica Neue"; font-size: 12px; color: #203653; }
QFrame#card { background: #f5faff; border: 1px solid #bfd8ef; border-radius: 18px; }
QLabel { background: transparent; border: none; }
QPushButton { background: #e1effb; border: none; border-radius: 8px; padding: 6px 10px; }
QPushButton:hover { background: #c8e4fa; }
QPushButton:disabled { color: #8d9eb1; }
QLineEdit { background: white; border: 1px solid #c6d8eb; border-radius: 9px; padding: 9px; }
QTextBrowser { background: white; border: 1px solid #d8e7f3; border-radius: 10px; padding: 6px; }
'''


class Bus(QObject):
    usage = Signal(object)
    balance = Signal(object)
    balance_error = Signal(str)
    answer = Signal(str, object)
    chat_error = Signal(str)


class UsagePanel(QWidget):
    def __init__(self, pet):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.pet = pet
        self.setWindowTitle('大肥鱼 · Claude 用量')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setFixedWidth(332)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        card = QFrame()
        card.setObjectName('card')
        root.addWidget(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18,14,18,14)
        layout.setSpacing(9)
        title = QHBoxLayout()
        name = QLabel('🐋 大肥鱼 · Claude 用量')
        name.setStyleSheet('font-size:14px; font-weight:600;')
        title.addWidget(name)
        title.addStretch()
        hide = QPushButton('－')
        hide.setAccessibleName('收起用量面板')
        hide.setFixedWidth(28)
        hide.clicked.connect(pet.toggle_hud)
        title.addWidget(hide)
        layout.addLayout(title)
        self.total = QLabel('正在读取本机 Claude 日志…')
        self.total.setStyleSheet('font-size:21px; font-weight:600; color:#195b94;')
        layout.addWidget(self.total)
        self.detail = QLabel('今日输入 / 输出 · 请求数')
        layout.addWidget(self.detail)
        self.last = QLabel('最近请求：等待数据')
        self.last.setWordWrap(True)
        self.last.setStyleSheet('color:#60758e; font-size:11px;')
        layout.addWidget(self.last)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet('background:#d7e6f4; border:none;')
        layout.addWidget(line)
        self.money = QLabel('账户余额：正在查询…')
        self.money.setStyleSheet('font-size:16px; font-weight:600;')
        layout.addWidget(self.money)
        self.spent = QLabel('监测后账户扣款：建立基准中')
        layout.addWidget(self.spent)
        self.fresh = QLabel('余额每 30 秒刷新 · 用量每 3 秒刷新')
        self.fresh.setStyleSheet('color:#60758e; font-size:10px;')
        layout.addWidget(self.fresh)
        info = QLabel('Claude 用量来自本机日志；账户扣款含同账户其他应用。\n每日统计按北京时间，扣款从本桌宠开始监测时累计。')
        info.setWordWrap(True)
        info.setStyleSheet('font-size:10px; color:#60758e;')
        layout.addWidget(info)
        actions = QHBoxLayout()
        refresh = QPushButton('刷新余额')
        refresh.clicked.connect(pet.refresh_balance)
        actions.addWidget(QLabel('右键大肥鱼：聊天 · 投喂 · 动作'))
        actions.addWidget(refresh)
        layout.addLayout(actions)
        self.adjustSize()

    def update_usage(self, d):
        n = d['input'] + d['output']
        self.total.setText(f'今日 {compact(n)} tokens')
        self.detail.setText(f'输入 {compact(d["input"])}  ·  输出 {compact(d["output"])}  ·  {d["calls"]} 次请求')
        self.detail.setToolTip(f'缓存读取 {d["cache"]:,} tokens；已按消息 ID 去除流式重复块。')
        r = d.get('last')
        if r:
            stamp = datetime.fromisoformat(r['timestamp'].replace('Z','+00:00')).astimezone(CST).strftime('%m-%d %H:%M')
            total = sum(r[k] for k in ('input','output','cache','creation'))
            self.last.setText(f'最近请求 {stamp} · {compact(total)} tokens\n{r["model"]} · {r["project"]}')
        else:
            self.last.setText('尚未发现 Claude Code 请求记录')
        self.adjustSize()

    def update_balance(self, rows):
        symbols = {'CNY':'¥', 'USD':'$'}
        self.money.setText('账户余额  ' + ' / '.join(symbols.get(r['currency'],r['currency']) + r['balance'] for r in rows))
        self.spent.setText('今日监测后账户扣款  ' + ' / '.join(symbols.get(r['currency'],r['currency']) + r['spent'] for r in rows))
        self.fresh.setText('余额更新 ' + datetime.now(CST).strftime('%H:%M:%S') + ' · 30 秒自动刷新')
        self.adjustSize()

    def mousePressEvent(self, e):
        self._drag = e.globalPosition().toPoint() - self.pos()

    def contextMenuEvent(self,e):
        self.pet.show_context_menu(e.globalPos())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton and hasattr(self, '_drag'):
            self.move(e.globalPosition().toPoint() - self._drag)


class Conversation(QDialog):
    def __init__(self, pet):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.pet = pet
        self.setWindowTitle('大肥鱼 · 对话')
        self.resize(430,410)
        self.setStyleSheet(STYLE)
        lay = QVBoxLayout(self)
        title = QLabel('和大肥鱼聊聊')
        title.setStyleSheet('font-size:19px; font-weight:600;')
        lay.addWidget(title)
        self.note = QLabel('DeepSeek Flash · 非思考 · 对话消耗同一 API 账户余额')
        self.note.setStyleSheet('font-size:11px; color:#60758e;')
        lay.addWidget(self.note)
        self.history = QTextBrowser()
        self.history.setAccessibleName('大肥鱼聊天记录')
        self.history.setOpenExternalLinks(False)
        lay.addWidget(self.history)
        self.history.append('<b>🐋 大肥鱼</b><br>我来陪你写代码，也帮你看着 token！右键点我，可以聊天、投喂和选动作。')
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText('给大肥鱼发一句话…')
        self.input.setAccessibleName('给大肥鱼的消息')
        self.input.returnPressed.connect(self.submit)
        self.send = QPushButton('发送')
        self.send.clicked.connect(self.submit)
        row.addWidget(self.input)
        row.addWidget(self.send)
        lay.addLayout(row)

    def submit(self):
        text = self.input.text().strip()
        if text and not self.pet.ds_busy:
            self.input.clear()
            self.history.append('<br><b>你</b><br>' + html.escape(text))
            self.send.setEnabled(False)
            self.send.setText('回复中…')
            self.pet._call_ds(text)

    def received(self, reply, error=False):
        self.history.append('<br><b>' + ('连接提示' if error else '🐋 大肥鱼') + '</b><br>' + html.escape(reply))
        self.history.verticalScrollBar().setValue(self.history.verticalScrollBar().maximum())
        self.send.setEnabled(True)
        self.send.setText('发送')
        self.input.setFocus()

    def closeEvent(self, e):
        self.pet.chat_paused = False
        super().closeEvent(e)
        if self.pet.hud_visible:
            self.pet.hud.show()
            self.pet.hud.raise_()
            self.pet.hud.activateWindow()


class ActionPalette(QDialog):
    def __init__(self,pet):
        super().__init__(None,Qt.WindowType.Window|Qt.WindowType.WindowStaysOnTopHint)
        self.pet=pet
        self.setWindowTitle('大肥鱼 · 互动动作')
        self.setFixedWidth(430)
        self.setStyleSheet(STYLE)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(20,18,20,18)
        title=QLabel('今天和大肥鱼玩什么？')
        title.setStyleSheet('font-size:19px;font-weight:600;')
        layout.addWidget(title)
        layout.addWidget(QLabel(f'{len(ACTIONS)} 种动作与表情 · 动作结束后安静陪伴'))
        grid=QGridLayout()
        for i,(key,(label,seconds,line)) in enumerate(ACTIONS.items()):
            b=QPushButton(label)
            b.setMinimumHeight(42)
            b.clicked.connect(lambda checked=False,k=key:self.choose(k))
            grid.addWidget(b,i//3,i%3)
        layout.addLayout(grid)
        layout.addWidget(QLabel('舞蹈节奏'))
        options=QHBoxLayout()
        for label,value in [('轻轻摇',.6),('正常',1.0),('活力满满',1.4)]:
            radio=QRadioButton(label)
            radio.setChecked(pet.cfg.get('dance_intensity',1.0)==value)
            radio.toggled.connect(lambda on,v=value:pet.set_dance(v) if on else None)
            options.addWidget(radio)
        layout.addLayout(options)
        auto=QCheckBox('空闲时偶尔做小动作')
        auto.setChecked(pet.cfg.get('idle_actions',True))
        auto.toggled.connect(pet.set_idle_actions)
        layout.addWidget(auto)
        quiet=QPushButton('回到安静陪伴')
        quiet.clicked.connect(lambda:(pet.stop_action(),self.hide()))
        layout.addWidget(quiet)

    def choose(self,key):
        self.pet.start_action(key)
        self.hide()
        if self.pet.hud_visible:
            self.pet.hud.activateWindow()


class Pet(base.PetWindow):
    @property
    def sprite_bottom(self):
        return base.BUBBLE_H+base.MARGIN+self.cur_h

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True)
        self.cfg['topmost']=True
        self.show()
        self.food_panel.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.motion = Motion()
        self.next_idle = time.monotonic()+60
        self.win_w += 58
        self.setFixedWidth(self.win_w)
        self.snap_into_screen()
        self.setWindowTitle('大肥鱼桌宠')
        self.bus = Bus()
        self.bus.usage.connect(self.on_usage)
        self.bus.balance.connect(self.on_balance)
        self.bus.balance_error.connect(self.on_balance_error)
        self.bus.answer.connect(self.on_answer)
        self.bus.chat_error.connect(self.on_chat_error)
        self.reader = UsageReader()
        self.ledger = BalanceLedger()
        self.usage_busy = False
        self.balance_busy = False
        self.usage_snapshot = {}
        self.balance_snapshot = []
        self.balance_bubble_pending = False
        self._balance_bubble_hold = 0
        self._click_count = 0
        self.click_interval_ms = QApplication.doubleClickInterval()
        self._click_timer.timeout.disconnect()
        self._click_timer.timeout.connect(self._finish_click_sequence)
        self.last_request = None
        self.conversation = Conversation(self)
        self.palette = ActionPalette(self)
        self.hud = UsagePanel(self)
        self.hud_visible = self.cfg.get('hud', True)
        if self.hud_visible:
            self.place_hud()
            self.hud.show()
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.refresh_usage)
        self.poll.start(3000)
        self.balance_timer = QTimer(self)
        self.balance_timer.timeout.connect(self.refresh_balance)
        self.balance_timer.start(30000)
        self.bubble_font = QFont('PingFang SC', 11)
        self.refresh_usage()
        self.refresh_balance()
        self.say('单击摸摸头，三击看余额～')
        self.menu_open = False
        self.last_reaction = None

    def paintEvent(self, event):
        if hasattr(self,'motion'):
            self.motion.render(self)
        else:
            super().paintEvent(event)

    def action_menu(self):
        menu = QMenu(self)
        for key, (label, duration, line) in ACTIONS.items():
            menu.addAction(label, lambda checked=False, k=key: self.start_action(k))
        menu.addSeparator()
        menu.addAction('回到安静陪伴', self.stop_action)
        dance = menu.addMenu('舞蹈节奏')
        for label,value in [('轻轻摇',0.6),('正常',1.0),('活力满满',1.4)]:
            a=dance.addAction(label)
            a.setCheckable(True)
            a.setChecked(self.cfg.get('dance_intensity',1.0)==value)
            a.triggered.connect(lambda checked, v=value: self.set_dance(v))
        idle = menu.addAction('空闲时偶尔做小动作')
        idle.setCheckable(True)
        idle.setChecked(self.cfg.get('idle_actions',True))
        idle.triggered.connect(self.set_idle_actions)
        return menu

    def show_actions(self):
        self.palette.show()
        self.palette.raise_()
        self.palette.activateWindow()

    def set_dance(self, value):
        self.cfg['dance_intensity']=value
        if self.motion.active()=='dance':
            self.motion.intensity=value
        self.save_config()

    def set_idle_actions(self, value):
        self.cfg['idle_actions']=bool(value)
        self.save_config()

    def start_action(self, key, speak=True):
        if not hasattr(self,'motion'):
            return
        self.target = None
        self._set_dir('down',1)
        self.motion.start(key,self.cfg.get('dance_intensity',1.0))
        self.rest_until = self.t*base.TICK+int((self.motion.duration+2)*1000)
        self.next_idle=time.monotonic()+random.randint(50,90)
        if speak:
            self.say(ACTIONS[key][2])
        write_private(DATA/'motion-state.json', {'action':key,'at':datetime.now(CST).isoformat()})
        self.update()

    def stop_action(self):
        self.motion.name=None
        self.chat_paused=False
        self.next_idle=time.monotonic()+60
        self.say('好，我安静陪着你～')

    def _maybe_idle_action(self):
        if not hasattr(self,'motion') or self.motion.active():
            return
        if self.cfg.get('idle_actions',True) and time.monotonic()>self.next_idle:
            self.start_action(random.choice(['look','wave','stretch','fish','rice']))

    def _build_menu(self):
        menu = QMenu(self)
        menu.addAction('🐋 和大肥鱼聊天', self._show_chat_dialog)
        menu.addAction('📊 显示 / 收起 Claude 用量', self.toggle_hud)
        menu.addAction('💰 刷新 DeepSeek 余额', self.refresh_balance)
        menu.addAction('🐟 投喂', lambda: self.food_panel.popup_at(self.x()+self.width()/2,self.y()+base.BUBBLE_H))
        menu.addAction('✨ 动作与表情…', self.show_actions)
        menu.addSeparator()
        modes = menu.addMenu('活动模式')
        for label, key in [('原地陪伴','still'),('自由散步','wander'),('跟随鼠标','follow')]:
            a = modes.addAction(label)
            a.setCheckable(True)
            a.setChecked(self.mode == key)
            a.triggered.connect(lambda checked, k=key: self.set_mode(k))
        sizes = menu.addMenu('大小')
        for label, mult in base.SIZE_LEVELS.items():
            sizes.addAction(label, lambda checked=False, m=mult: self.set_size(m))
        menu.addAction('回到屏幕内', self.snap_into_screen)
        menu.addAction('显示 / 隐藏桌宠', self.toggle_visible)
        a = menu.addAction('鼠标穿透（菜单栏可关闭）')
        a.setCheckable(True)
        a.setChecked(self.cfg.get('passthrough',False))
        a.triggered.connect(self.set_passthrough)
        a = menu.addAction('登录时启动')
        a.setCheckable(True)
        a.setChecked(AUTOSTART.exists())
        a.triggered.connect(self.set_autostart)
        menu.addSeparator()
        menu.addAction('关于和统计说明', self.about)
        menu.addAction('退出大肥鱼', self.quit_app)
        return menu

    def show_context_menu(self, position):
        if self.menu_open:
            return
        self.last_context_menu = datetime.now(CST).isoformat()
        self._click_timer.stop()
        self._click_count = 0
        self.menu_open = True
        self._context_menu = self._build_menu()
        def closed():
            self.menu_open = False
        self._context_menu.aboutToHide.connect(closed)
        self._context_menu.aboutToHide.connect(self._context_menu.deleteLater)
        self._context_menu.popup(position)

    def contextMenuEvent(self,e):
        # Mouse menus are opened explicitly in mousePressEvent: Cocoa can
        # suppress a context event on an inactive frameless Tool window.
        if e.reason() != e.Reason.Mouse:
            self.show_context_menu(e.globalPos())
        e.accept()

    def mousePressEvent(self, e):
        self.last_pointer = {'button':str(e.button()),'at':datetime.now(CST).isoformat()}
        if e.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(e.globalPosition().toPoint())
            e.accept()
            return
        super().mousePressEvent(e)

    def check_system_status(self):
        pass  # No system or screen monitoring is necessary for this companion.

    def _apply_passthrough(self, on):
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, bool(on))
        self.show()

    def set_autostart(self, on):
        if on:
            AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
            d = {'Label':'local.dafeiyu.claude', 'ProgramArguments':['/usr/bin/open','-a',str(APP_BUNDLE)],
                 'RunAtLoad':True, 'LimitLoadToSessionType':'Aqua'}
            AUTOSTART.write_bytes(plistlib.dumps(d))
        else:
            AUTOSTART.unlink(missing_ok=True)
        self.cfg['autostart'] = bool(on)
        self.save_config()
        self.say('已设置登录启动～' if on else '已取消登录启动～')

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show()
            self.raise_()
            if hasattr(self,'hud'):
                self.hud_visible = True
                self.hud.show()
                self.place_hud()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            self.tray.setContextMenu(self._build_menu())

    def _on_single_click(self):
        self.chat_paused = False
        self.jump_t = 0.8
        self.say(random.choice(base.REACT_LINES))
        options=[k for k in ['hearts','happy','shy','angry','wave'] if k!=self.last_reaction]
        self.last_reaction=random.choice(options)
        self.start_action(self.last_reaction,speak=False)

    def _finish_click_sequence(self):
        count = self._click_count
        self._click_count = 0
        if count:
            self._on_single_click()

    def mouseDoubleClickEvent(self, e):
        # Qt replaces the second press with a double-click event. Count every
        # release once, so a physical triple click is three releases on macOS.
        if e.button() == Qt.MouseButton.LeftButton:
            super().mousePressEvent(e)
            e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and not self.dragging:
            self.chat_paused = False
            self.drag_start_pos = None
            self.last_press_pos = None
            self._click_count += 1
            if self._click_count == 3:
                self._click_count = 0
                self._click_timer.stop()
                self.show_balance_bubble()
            else:
                self._click_timer.start(self.click_interval_ms)
            e.accept()
            self.save_config()
            return
        if self.dragging:
            self._click_count = 0
            self._click_timer.stop()
        super().mouseReleaseEvent(e)
        self.save_config()

    def say(self, text, inner=False):
        if time.monotonic() < getattr(self,'_balance_bubble_hold',0):
            return
        super().say(text,inner)

    def _show_balance_text(self, text):
        super().say(text)
        self.bubble_until = self.t * base.TICK / 1000.0 + 5
        self._balance_bubble_hold = time.monotonic() + 5
        self.update()

    def _balance_text(self):
        symbols = {'CNY':'¥','USD':'$'}
        return '余额 ' + ' / '.join(
            symbols.get(row['currency'],row['currency']+' ') + row['balance']
            for row in self.balance_snapshot)

    def show_balance_bubble(self):
        self.balance_bubble_pending = True
        self._show_balance_text(self._balance_text() if self.balance_snapshot else '正在查余额…')
        self.refresh_balance()

    def on_food(self, food):
        super().on_food(food)
        self.chat_paused = False
        self.start_action('rice',speak=False)

    def _show_chat_dialog(self):
        if not hasattr(self, 'conversation'):
            return
        self.chat_paused = True
        self.conversation.show()
        self.conversation.raise_()
        self.conversation.activateWindow()
        self.conversation.input.setFocus()

    def _call_ds(self, text):
        if self.ds_busy:
            return
        self.ds_busy = True
        messages = [{'role':'system', 'content':'你是桌面宠物大肥鱼，一只俏皮温暖的小鲸鱼。用中文简短自然地回答，通常一到三句话。你陪主人使用 Claude Code；不要声称能读取屏幕或执行操作。'}]
        messages += self.chat_history[-20:]
        messages.append({'role':'user','content':text})
        self.pending_user = text
        self.say('让我想一句好听的～')
        self.start_action('think',speak=False)
        def run():
            try:
                answer, usage = chat(messages)
                self.bus.answer.emit(answer, usage)
            except Exception as e:
                self.bus.chat_error.emit(str(e))
        threading.Thread(target=run,daemon=True).start()

    def on_answer(self, answer, usage):
        self.ds_busy = False
        self.chat_history += [{'role':'user','content':self.pending_user},{'role':'assistant','content':answer}]
        self.chat_history = self.chat_history[-20:]
        self.conversation.received(answer)
        self.start_action('talk',speak=False)
        self.say(answer[:42] + ('…' if len(answer)>42 else ''))
        write_private(DATA/'last-chat-usage.json', {'at':datetime.now(CST).isoformat(),'model':'deepseek-flash','usage':usage,'ok':True})
        QTimer.singleShot(2000, self.refresh_balance)

    def on_chat_error(self, message):
        self.ds_busy = False
        self.conversation.received(message,True)
        self.say(message)

    def refresh_usage(self):
        if not hasattr(self,'usage_busy') or self.usage_busy:
            return
        self.usage_busy = True
        def run():
            try:
                self.bus.usage.emit(self.reader.read())
            except Exception:
                self.bus.usage.emit({'error':True})
        threading.Thread(target=run,daemon=True).start()

    def on_usage(self, d):
        self.usage_busy = False
        if d.get('error'):
            return
        self.usage_snapshot = d
        self.hud.update_usage(d)
        event = d.get('latest_event',['',''])
        if event[1]=='user' and event[0]:
            try:
                age=(datetime.now(CST)-datetime.fromisoformat(event[0].replace('Z','+00:00'))).total_seconds()
                if age<90 and not self.chat_paused and not self.motion.active():
                    self.start_action('coding',speak=False)
            except ValueError:
                pass
        r = d.get('last')
        ident = r['id'] if r else None
        if self.last_request and ident != self.last_request:
            total = sum(r[k] for k in ('input','output','cache','creation'))
            self.say(f'Claude 又完成一次请求：{compact(total)} tokens')
            if not self.chat_paused:
                self.start_action('celebrate',speak=False)
            QTimer.singleShot(2000, self.refresh_balance)
        self.last_request = ident
        self.save_snapshot()

    def refresh_balance(self):
        if not hasattr(self,'balance_busy') or self.balance_busy:
            return
        self.balance_busy = True
        def run():
            try:
                result = request_api('user/balance')
                self.bus.balance.emit(self.ledger.update(result))
            except Exception as e:
                self.bus.balance_error.emit(str(e))
        threading.Thread(target=run,daemon=True).start()

    def on_balance(self, rows):
        self.balance_busy = False
        self.balance_snapshot = rows
        self.hud.update_balance(rows)
        if self.balance_bubble_pending:
            self.balance_bubble_pending = False
            self._show_balance_text(self._balance_text())
        self.save_snapshot()

    def on_balance_error(self, message):
        self.balance_busy = False
        if self.balance_bubble_pending:
            self.balance_bubble_pending = False
            self._show_balance_text((self._balance_text()+'（暂未刷新）') if self.balance_snapshot
                else '余额暂时查不到，稍后再试～')
        self.hud.fresh.setText(message + ' · 30 秒后重试')
        write_private(DATA/'balance-error.json', {'at':datetime.now(CST).isoformat(),'error':message})

    def save_snapshot(self):
        write_private(DATA/'status.json', {'version':'1.2.0','updated':datetime.now(CST).isoformat(),
            'claude':self.usage_snapshot,'balance':self.balance_snapshot,
            'windows':{'pet_visible':self.isVisible(),'panel_visible':self.hud.isVisible(),
                'pet_topmost':bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint),
                'pet_visible_when_inactive':self.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow),
                'panel_visible_when_inactive':self.hud.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow),
                'app_state':str(QApplication.applicationState()),
                'native_pet':keep_on_top(self),'native_panel':keep_on_top(self.hud)},
            'interaction':{'left_click':'reaction_only','double_click':'reaction_only',
                'triple_click':'balance_bubble','extras':'context_menu',
                'last_pointer':getattr(self,'last_pointer',None),
                'last_context_menu':getattr(self,'last_context_menu',None),'menu_open':self.menu_open},
            'animation':{'pose':self.motion.clips.last_name,'frame_cache':len(self.motion.clips.cache),
                'complete_clips':len(self.motion.clips.manifest)}})

    def save_config(self):
        self.cfg.pop('ds_api_key',None)
        self.cfg['x'], self.cfg['y'] = self.x(), self.y()
        self.cfg['hud'] = getattr(self,'hud_visible',True)
        write_private(base.CONFIG_PATH,self.cfg)

    def place_hud(self):
        if not hasattr(self,'hud'):
            return
        geo = self.screen().availableGeometry()
        x = self.x() - self.hud.width() - 12
        if x < geo.left():
            x = self.x()+self.width()+12
        x = min(max(geo.left()+8,x),geo.right()-self.hud.width()-8)
        y = min(max(geo.top()+8,self.y()+60),geo.bottom()-self.hud.height()-8)
        self.hud.move(x,y)

    def moveEvent(self, e):
        super().moveEvent(e)
        self.place_hud()

    def toggle_hud(self):
        if not hasattr(self,'hud'):
            return
        self.hud_visible = not self.hud_visible
        self.hud.setVisible(self.hud_visible)
        if self.hud_visible:
            self.place_hud()
        self.save_config()

    def set_mode(self, mode):
        super().set_mode(mode)
        self.chat_paused = False
        self.save_config()

    def set_size(self, mult):
        super().set_size(mult)
        self.win_w += 58
        self.setFixedWidth(self.win_w)
        self.snap_into_screen()
        self.save_config()

    def about(self):
        QMessageBox.information(self, '关于大肥鱼桌宠',
            '大肥鱼桌宠 · Claude 用量伴侣（macOS）\n\n'
            '单击和双击：人物反馈；拖动：移动；右键：聊天、投喂、动作菜单。\n'
            '快速连续三击：头顶显示余额气泡，并刷新官方余额。\n'
            f'动作与表情面板：干饭、跳舞、眨眼、害羞、生气等 {len(ACTIONS)} 种动作。\n'
            'Claude tokens 来自 ~/.claude/projects，本地读取并去除流式重复。\n'
            '余额来自 DeepSeek 官方接口，账户扣款包含其他客户端。\n'
            '每天从监测开始累计，充值只更新余额，不作为负消耗。\n'
            '聊天只发送你在桌宠输入的消息，不上传 Claude 的会话内容。\n'
            'API Key 复用本机 Claude 配置，不额外保存。\n\n'
            '桌宠底座：1190fasheqi/dafeiyu-pet（MIT）。\n'
            '完整角色动画原作：https://github.com/PC2005-cloud/dsh-pet\n'
            '素材取自 Refining-colors/pet-with-you 的授权副本。\n'
            '动画及角色素材允许开源非商用使用，保留原作者署名。')

    def quit_app(self):
        self.save_config()
        self.tray.hide()
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('大肥鱼桌宠')
    app.setOrganizationName('Dafeiyu')
    app.setWindowIcon(QIcon(str(Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'assets/app-icon.png')))
    app.setQuitOnLastWindowClosed(False)
    lock = QLockFile(str(DATA/'instance.lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        return 0
    pet = Pet()
    app.aboutToQuit.connect(pet.save_config)
    return app.exec()


if __name__ == '__main__':
    if '--check-network' in sys.argv:
        try:
            result = {'ok':True,'balance':request_api('user/balance')}
        except Exception as exc:
            result = {'ok':False,'type':type(exc).__name__,'error':str(exc).replace(api_key(),'<redacted>')}
        write_private(DATA/'packaged-network-check.json',result)
    else:
        sys.exit(main())
