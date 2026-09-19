#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GetMDList.py
带托盘图标 + 三边吸附悬浮窗的文本提取工具。

- 托盘右键：选择文件夹 / 隐藏窗口 / 退出
- 标题栏按钮：结构 / MD 切换
- 结构页：树 + 四态标注（NORMAL/RED/BLACK/MIX）
- MD 页：滑动窗口渲染（固定 500 行）
  · 滚轮到边缘继续滚 → 翻页
  · 拖动滚动条到顶/底 → 自动翻页
- 每次生成 md：销毁上一份临时文件，只保留当前
"""

import os
import sys
import tempfile
import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QWidget, QSystemTrayIcon, QMenu, QAction,
    QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStyle, QToolTip, QTextBrowser, QStackedWidget
)
from PyQt5.QtCore import Qt, QPoint, QTimer, QMimeData, QUrl, QEvent
from PyQt5.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QBrush, QCursor, QDrag
)


# ---------- 配置 ----------
TEXT_EXTENSIONS = {
    '.txt', '.md', '.markdown', '.text', '.log', '.err', '.out',
    '.py', '.pyw', '.pyx', '.pxd', '.pxi',
    '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs',
    '.html', '.htm', '.xhtml', '.xml', '.xsd', '.xsl', '.xslt',
    '.css', '.scss', '.sass', '.less', '.styl',
    '.json', '.jsonl', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
    '.csv', '.tsv', '.tab', '.psv',
    '.sh', '.bash', '.zsh', '.fish', '.ksh', '.csh',
    '.c', '.cpp', '.cxx', '.cc', '.h', '.hpp', '.hxx', '.hh',
    '.java', '.jsp', '.kt', '.kts',
    '.go', '.rb', '.php', '.pl', '.pm', '.pod', '.t',
    '.tex', '.latex', '.bib', '.bst', '.cls', '.sty',
    '.rst', '.org', '.wiki', '.dita', '.ditamap',
    '.properties', '.gitignore', '.gitattributes', '.dockerignore',
    '.editorconfig', '.env', '.example', '.sample',
    '.sql', '.ddl', '.dml', '.ps1', '.psm1', '.psd1',
    '.r', '.rmd', '.stan', '.julia', '.jl',
    '.lua', '.rkt', '.scm', '.el', '.lisp', '.cl',
    '.v', '.sv', '.vhdl', '.vhd', '.verilog',
    '.ml', '.mli', '.fs', '.fsi', '.fsx',
    '.scala', '.sbt', '.groovy', '.gvy', '.gy',
    '.nim', '.nims', '.cr', '.ex', '.exs',
    '.erl', '.hrl',
    '.mk', '.cmake', '.ninja', '.gradle',
    '.sip',
}
TEXT_FILENAMES = {'makefile', 'dockerfile', 'jenkinsfile', 'vagrantfile',
                  'rakefile', 'gemfile', 'procfile', 'brewfile'}

ROLE_PATH = Qt.UserRole + 1
ROLE_IS_DIR = Qt.UserRole + 2
ROLE_IS_TEXT = Qt.UserRole + 3
ROLE_STATE = Qt.UserRole + 4

STATE_NORMAL = 0
STATE_RED = 1
STATE_BLACK = 2
STATE_MIX = 3


def is_text_file(filepath: Path) -> bool:
    if filepath.suffix.lower() in TEXT_EXTENSIONS:
        return True
    return filepath.name.lower() in TEXT_FILENAMES


def read_text_content(filepath: Path, max_size=10 * 1024 * 1024):
    try:
        if filepath.stat().st_size > max_size:
            return '[文件过大，已跳过内容]'
    except OSError:
        return None
    for enc in ('utf-8', 'utf-8-sig', 'gbk', 'gb18030', 'big5', 'latin-1'):
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def get_attrs(p: Path):
    try:
        st = p.stat()
    except OSError:
        return {'size': 'N/A', 'mtime': 'N/A', 'mode': 'N/A'}
    return {
        'size': st.st_size if p.is_file() else 'N/A',
        'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        'mode': oct(st.st_mode)[-3:],
    }


# ---------- 缝隙条 ----------
class StripBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            p = self.parent()
            if hasattr(p, '_drag_hovering'):
                p._drag_hovering = True
            if hasattr(p, 'expand_from_edge') and getattr(p, '_collapsed', False):
                p.expand_from_edge()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        p = self.parent()
        if hasattr(p, '_drag_hovering'):
            p._drag_hovering = False
        e.accept()

    def dropEvent(self, e):
        self.parent().dropEvent(e)


# ---------- 可拖出的 MD 图标 ----------
class DraggableMdIcon(QLabel):
    """显示 md 图标，按住左键可拖出文件（file:// URL）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 64)
        self.setAlignment(Qt.AlignCenter)
        self.setToolTip('拖我到桌面 / 聊天窗口 / 任意位置')
        self.setCursor(Qt.OpenHandCursor)
        self._file_path: Path | None = None
        self._press_pos: QPoint | None = None
        self._build_icon()

    def _build_icon(self):
        pm = QPixmap(48, 48)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor('#ffffff')))
        p.setPen(QColor('#666666'))
        p.drawRoundedRect(4, 2, 32, 44, 4, 4)
        p.setPen(QColor('#3a7bd5'))
        p.drawLine(8, 34, 30, 34)
        p.drawLine(8, 38, 26, 38)
        p.setBrush(QBrush(QColor('#3a7bd5')))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(22, 22, 22, 22, 4, 4)
        p.setPen(QColor('#ffffff'))
        font = p.font()
        font.setBold(True)
        font.setPointSize(8)
        p.setFont(font)
        p.drawText(22, 22, 22, 22, Qt.AlignCenter, 'MD')
        p.end()
        self.setPixmap(pm)

    def set_file(self, path: Path | None):
        self._file_path = path
        if path is None:
            self.setEnabled(False)
            self.setCursor(Qt.ForbiddenCursor)
            self.setToolTip('先点「生成 MD」')
        else:
            self.setEnabled(True)
            self.setCursor(Qt.OpenHandCursor)
            self.setToolTip(f'拖我到桌面 / 聊天窗口 / 任意位置\n（源：{path}）')

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._file_path:
            self._press_pos = e.pos()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if (self._press_pos is not None and self._file_path
                and (e.pos() - self._press_pos).manhattanLength() >= 8):
            self._start_drag()
            self._press_pos = None
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._press_pos = None
        super().mouseReleaseEvent(e)

    def _start_drag(self):
        if not self._file_path or not self._file_path.exists():
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self._file_path))])

        drag = QDrag(self)
        drag.setMimeData(mime)
        if self.pixmap():
            drag.setPixmap(self.pixmap().scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        drag.setHotSpot(QPoint(24, 24))
        drag.exec_(Qt.CopyAction)


# ---------- 悬浮窗 ----------
class FloatingWindow(QWidget):
    SNAP_DISTANCE = 20
    STRIP_SIZE = 6

    EDGE_NONE = 0
    EDGE_LEFT = 1
    EDGE_RIGHT = 2
    EDGE_TOP = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setWindowTitle('文本提取悬浮窗')
        self.resize(520, 680)

        self._edge = self.EDGE_RIGHT
        self._collapsed = False
        self._drag_offset = None
        self._dragging = False
        self._drag_hovering = False
        self._root_dir: Path | None = None
        self._preview_file: Path | None = None   # 当前 md 内存副本的磁盘落地

        # ---- md 滑动窗口状态 ----
        self._md_lines: list[str] = []      # 已生成的 md 全文，按行存
        self._win_start = 0                 # 窗口起始行索引（0 基）
        self._win_size = 500                # 窗口固定行数
        self._win_step = 500                # 每次滑动步长
        self._win_loading = False           # 翻页/渲染中标记

        self._build_ui()

        self._strip_bar = StripBar(self)
        self._strip_bar.setStyleSheet(
            'background: qlineargradient(x1:0, y1:0, x2:0, y2:1,'
            ' stop:0 #3a7bd5, stop:1 #00d2ff);'
        )
        self._strip_bar.hide()

        self._state_timer = QTimer(self)
        self._state_timer.timeout.connect(self._check_auto_collapse)
        self._state_timer.start(400)

    # ---------- UI ----------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ----- 标题栏：两个切换按钮 -----
        self.title_bar = QWidget(self)
        self.title_bar.setFixedHeight(30)
        self.title_bar.setStyleSheet('background:#3a7bd5; border-radius:3px;')
        tb_layout = QHBoxLayout(self.title_bar)
        tb_layout.setContentsMargins(6, 2, 6, 2)
        tb_layout.setSpacing(4)

        btn_style = (
            'QPushButton { background: rgba(255,255,255,0.18); color:white;'
            ' border:none; padding:3px 16px; border-radius:3px; font-weight:bold; }'
            'QPushButton:hover { background: rgba(255,255,255,0.32); }'
            'QPushButton:checked { background: white; color:#3a7bd5; }'
        )

        self.btn_tab_tree = QPushButton('结构', self.title_bar)
        self.btn_tab_tree.setCheckable(True)
        self.btn_tab_tree.setChecked(True)
        self.btn_tab_tree.setStyleSheet(btn_style)
        self.btn_tab_tree.clicked.connect(lambda: self._switch_page(0))
        tb_layout.addWidget(self.btn_tab_tree)

        self.btn_tab_md = QPushButton('MD', self.title_bar)
        self.btn_tab_md.setCheckable(True)
        self.btn_tab_md.setStyleSheet(btn_style)
        self.btn_tab_md.clicked.connect(lambda: self._switch_page(1))
        tb_layout.addWidget(self.btn_tab_md)

        tb_layout.addStretch()
        layout.addWidget(self.title_bar)

        # ----- 主区域：QStackedWidget -----
        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack, 1)

        # 页 0：结构（树）
        self.page_tree = QWidget(self.stack)
        pt_layout = QVBoxLayout(self.page_tree)
        pt_layout.setContentsMargins(0, 0, 0, 0)
        pt_layout.setSpacing(4)

        self.tree = QTreeWidget(self.page_tree)
        self.tree.setHeaderLabels(['名称', '大小', '修改时间'])
        self.tree.setColumnWidth(0, 260)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 140)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.setMouseTracking(True)
        self.tree.itemEntered.connect(self._on_item_hovered)
        pt_layout.addWidget(self.tree, 1)

        self.stack.addWidget(self.page_tree)

        # 页 1：MD 预览
        self.page_md = QWidget(self.stack)
        pm_layout = QVBoxLayout(self.page_md)
        pm_layout.setContentsMargins(0, 0, 0, 0)
        pm_layout.setSpacing(4)

        # 顶部状态条：显示当前窗口行号区间
        self.md_more_label = QLabel('', self.page_md)
        self.md_more_label.setAlignment(Qt.AlignCenter)
        self.md_more_label.setStyleSheet('color:#3a7bd5; font-size:11px;')
        pm_layout.addWidget(self.md_more_label)

        self.md_view = QTextBrowser(self.page_md)
        self.md_view.setOpenExternalLinks(True)
        self.md_view.setStyleSheet(
            'QTextBrowser { background:#fafafa; border:1px solid #ddd;'
            ' border-radius:3px; padding:6px; }'
        )
        # ★ 滚轮在边缘继续滚 → 翻页
        self.md_view.viewport().installEventFilter(self)
        # ★ 拖动滚动条到顶/底 → 自动翻页
        self.md_view.verticalScrollBar().valueChanged.connect(self._on_scrollbar_changed)
        pm_layout.addWidget(self.md_view, 1)

        # MD 页底部：md 图标（拖出）
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(4, 4, 4, 4)
        self.md_icon = DraggableMdIcon(self.page_md)
        bottom_row.addWidget(self.md_icon)
        tip = QLabel('按住上面图标拖出去 → 复制到目标位置', self.page_md)
        tip.setStyleSheet('color:#888; font-size:11px;')
        bottom_row.addWidget(tip)
        bottom_row.addStretch()
        pm_layout.addLayout(bottom_row)

        self.stack.addWidget(self.page_md)

        # ----- 底部提示 + 按钮 -----
        self.hint = QLabel('把文件夹拖到这里，或点击下方按钮选择', self)
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet('color:#888;')
        layout.addWidget(self.hint)

        btn_row = QHBoxLayout()
        self.btn_open = QPushButton('选择文件夹', self)
        self.btn_open.clicked.connect(self._choose_folder)
        btn_row.addWidget(self.btn_open)

        self.btn_gen = QPushButton('生成 MD', self)
        self.btn_gen.clicked.connect(self._generate_md)
        btn_row.addWidget(self.btn_gen)

        self.btn_clear = QPushButton('清空', self)
        self.btn_clear.clicked.connect(self._clear_all)
        btn_row.addWidget(self.btn_clear)

        layout.addLayout(btn_row)

        self.setAcceptDrops(True)

    def _switch_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self.btn_tab_tree.setChecked(idx == 0)
        self.btn_tab_md.setChecked(idx == 1)

    # ---------- 显示 ----------
    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._check_auto_collapse)

    # ---------- 拖放（拖文件夹进来） ----------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            self._drag_hovering = True
            if self._collapsed:
                self.expand_from_edge()
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._drag_hovering = False
        e.accept()

    def dropEvent(self, e):
        self._drag_hovering = False
        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_dir():
                self.load_folder(p)
                break

    # ---------- 加载 ----------
    def _choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, '选择要扫描的文件夹')
        if d:
            self.load_folder(Path(d))

    def load_folder(self, folder: Path):
        self._root_dir = folder.resolve()
        self.tree.clear()
        root_item = QTreeWidgetItem(self.tree)
        root_item.setText(0, self._root_dir.name + '/')
        root_item.setData(0, ROLE_PATH, str(self._root_dir))
        root_item.setData(0, ROLE_IS_DIR, True)
        root_item.setData(0, ROLE_STATE, STATE_NORMAL)
        root_item.setExpanded(True)
        self._populate(root_item, self._root_dir, skip_hidden=True)
        self.hint.setText(f'已加载：{self._root_dir}')
        if self._collapsed:
            self.expand_from_edge()

    def _populate(self, parent_item: QTreeWidgetItem, folder: Path, skip_hidden=True):
        try:
            entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for entry in entries:
            if entry.is_symlink():
                continue
            name = entry.name
            is_dir = entry.is_dir()
            item = QTreeWidgetItem(parent_item)
            item.setText(0, name + ('/' if is_dir else ''))
            item.setData(0, ROLE_PATH, str(entry))
            item.setData(0, ROLE_IS_DIR, is_dir)
            item.setData(0, ROLE_IS_TEXT, (not is_dir) and is_text_file(entry))
            item.setData(0, ROLE_STATE, STATE_NORMAL)
            attrs = get_attrs(entry)
            item.setText(1, str(attrs['size']))
            item.setText(2, str(attrs['mtime']))
            if is_dir:
                if skip_hidden and name.startswith('.'):
                    item.setForeground(0, QBrush(QColor('#999999')))
                    item.setToolTip(0, '隐藏目录，内部不展开')
                else:
                    self._populate(item, entry, skip_hidden=skip_hidden)
        self._recalc(parent_item)

    # ---------- 点击 ----------
    def _on_item_clicked(self, item: QTreeWidgetItem, col: int):
        is_dir = item.data(0, ROLE_IS_DIR)
        cur = item.data(0, ROLE_STATE) or STATE_NORMAL
        if is_dir:
            if cur == STATE_MIX:
                new = STATE_NORMAL
            else:
                new = (cur + 1) % 3
            if new == STATE_NORMAL:
                self._set_folder_state(item, STATE_NORMAL)
            elif new == STATE_RED:
                self._set_folder_state(item, STATE_RED)
            else:
                self._set_folder_state(item, STATE_BLACK)
        else:
            new = (cur + 1) % 3
            self._set_state(item, new)
            parent = item.parent()
            while parent:
                self._recalc(parent)
                parent = parent.parent()

    def _on_item_hovered(self, item: QTreeWidgetItem, col: int):
        st = item.data(0, ROLE_STATE) or STATE_NORMAL
        is_dir = item.data(0, ROLE_IS_DIR)
        if st == STATE_RED:
            QToolTip.showText(QCursor.pos(), '该文件/文件夹不读取内容', self.tree)
        elif st == STATE_BLACK:
            if is_dir:
                QToolTip.showText(QCursor.pos(), '该文件夹标黑（内部全黑）', self.tree)
            else:
                QToolTip.showText(QCursor.pos(), '该文件标黑（隐身）', self.tree)
        elif st == STATE_MIX:
            QToolTip.showText(QCursor.pos(), '该文件夹内部状态混杂', self.tree)

    def _on_context_menu(self, pos: QPoint):
        item = self.tree.itemAt(pos)
        if not item:
            return
        is_dir = item.data(0, ROLE_IS_DIR)
        menu = QMenu(self)
        if is_dir:
            act_red = QAction('文件夹标红（内部全红）', self)
            act_red.triggered.connect(lambda: self._set_folder_state(item, STATE_RED))
            menu.addAction(act_red)

            act_black = QAction('文件夹标黑（内部全黑）', self)
            act_black.triggered.connect(lambda: self._set_folder_state(item, STATE_BLACK))
            menu.addAction(act_black)

            menu.addSeparator()

            act_reset = QAction('取消该文件夹所有标注', self)
            act_reset.triggered.connect(lambda: self._set_folder_state(item, STATE_NORMAL))
            menu.addAction(act_reset)
        else:
            act_red = QAction('标红（不读取内容）', self)
            act_red.triggered.connect(lambda: self._click_set_file(item, STATE_RED))
            menu.addAction(act_red)

            act_black = QAction('标黑（隐身）', self)
            act_black.triggered.connect(lambda: self._click_set_file(item, STATE_BLACK))
            menu.addAction(act_black)

            act_reset = QAction('复原', self)
            act_reset.triggered.connect(lambda: self._click_set_file(item, STATE_NORMAL))
            menu.addAction(act_reset)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _click_set_file(self, item: QTreeWidgetItem, state: int):
        self._set_state(item, state)
        parent = item.parent()
        while parent:
            self._recalc(parent)
            parent = parent.parent()

    def _set_folder_state(self, folder_item: QTreeWidgetItem, state: int):
        def set_leaves(it):
            for i in range(it.childCount()):
                child = it.child(i)
                if child.data(0, ROLE_IS_DIR):
                    set_leaves(child)
                else:
                    self._set_state(child, state)
        set_leaves(folder_item)
        self._recalc_subtree_bottom_up(folder_item)
        parent = folder_item.parent()
        while parent:
            self._recalc(parent)
            parent = parent.parent()

    def _recalc_subtree_bottom_up(self, folder_item: QTreeWidgetItem):
        for i in range(folder_item.childCount()):
            child = folder_item.child(i)
            if child.data(0, ROLE_IS_DIR):
                self._recalc_subtree_bottom_up(child)
        self._recalc(folder_item)

    def _set_state(self, item: QTreeWidgetItem, state: int):
        item.setData(0, ROLE_STATE, state)
        self._apply_item_style(item)

    def _apply_item_style(self, item: QTreeWidgetItem):
        state = item.data(0, ROLE_STATE) or STATE_NORMAL
        is_dir = item.data(0, ROLE_IS_DIR)
        if state == STATE_RED:
            item.setForeground(0, QBrush(QColor('#d32f2f')))
            item.setIcon(0, self._red_dot_icon())
            item.setToolTip(0, '该文件/文件夹不读取内容')
        elif state == STATE_BLACK:
            item.setForeground(0, QBrush(QColor('#000000')))
            item.setIcon(0, self._black_dot_icon())
            item.setToolTip(0, '该文件夹标黑（内部全黑）' if is_dir else '该文件标黑（隐身）')
        elif state == STATE_MIX:
            item.setForeground(0, QBrush(QColor('#f9a825')))
            item.setIcon(0, self._mix_dot_icon())
            item.setToolTip(0, '该文件夹内部状态混杂')
        else:
            item.setForeground(0, QBrush(QColor('#1565c0' if is_dir else '#000000')))
            item.setIcon(0, QIcon())
            item.setToolTip(0, '')

    @staticmethod
    def _red_dot_icon() -> QIcon:
        pm = QPixmap(12, 12)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor('#e53935')))
        p.setPen(Qt.NoPen)
        p.drawEllipse(2, 2, 8, 8)
        p.end()
        return QIcon(pm)

    @staticmethod
    def _black_dot_icon() -> QIcon:
        pm = QPixmap(12, 12)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor('#212121')))
        p.setPen(Qt.NoPen)
        p.drawEllipse(2, 2, 8, 8)
        p.end()
        return QIcon(pm)

    @staticmethod
    def _mix_dot_icon() -> QIcon:
        pm = QPixmap(12, 12)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor('#f9a825')))
        p.setPen(Qt.NoPen)
        p.drawEllipse(2, 2, 8, 8)
        p.end()
        return QIcon(pm)

    def _recalc(self, folder_item: QTreeWidgetItem):
        if not folder_item.data(0, ROLE_IS_DIR):
            return
        children = [folder_item.child(i) for i in range(folder_item.childCount())]
        if not children:
            new_state = STATE_NORMAL
        else:
            states = set(c.data(0, ROLE_STATE) or STATE_NORMAL for c in children)
            if states == {STATE_NORMAL}:
                new_state = STATE_NORMAL
            elif states == {STATE_BLACK}:
                new_state = STATE_BLACK
            elif states == {STATE_RED}:
                new_state = STATE_RED
            else:
                new_state = STATE_MIX
        if (folder_item.data(0, ROLE_STATE) or STATE_NORMAL) != new_state:
            folder_item.setData(0, ROLE_STATE, new_state)
            self._apply_item_style(folder_item)

    # ---------- 生成 MD（内存） ----------
    def _generate_md(self):
        if not self._root_dir:
            QMessageBox.warning(self, '提示', '请先拖入一个文件夹。')
            return

        md_text = self._build_md_text()

        # ★ 销毁上一份临时文件
        if self._preview_file and self._preview_file.exists():
            try:
                self._preview_file.unlink()
            except OSError:
                pass
            self._preview_file = None

        # 写入新的临时文件
        tmp_dir = Path(tempfile.gettempdir())
        base = self._root_dir.name or 'text_extract'
        safe = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in base)
        tmp_path = tmp_dir / f'{safe}_report.md'
        n = 1
        while tmp_path.exists():
            tmp_path = tmp_dir / f'{safe}_report_{n}.md'
            n += 1

        try:
            tmp_path.write_text(md_text, encoding='utf-8')
        except OSError as e:
            QMessageBox.critical(self, '出错', f'无法写入临时文件：{e}')
            return

        self._preview_file = tmp_path

        # ★ 按行存，窗口复位到顶部，渲染首屏
        self._md_lines = md_text.splitlines()
        self._win_start = 0
        self.md_view.clear()
        self._render_window(scroll_to='top')

        # 让拖拽图标生效（拖出的是完整文件）
        self.md_icon.set_file(tmp_path)
        # 自动切到 MD 页
        self._switch_page(1)

    # ---------- md 滑动窗口 ----------
    def _render_window(self, scroll_to='top'):
        """渲染当前窗口 [start, start+size) 的 500 行。
        scroll_to: 'top' 渲染后停在顶部；'bottom' 渲染后停在底部。
        """
        total = len(self._md_lines)
        if total == 0:
            self.md_view.clear()
            self.md_more_label.setText('（空）')
            return

        start = max(0, min(self._win_start, max(0, total - self._win_size)))
        end = min(start + self._win_size, total)
        self._win_start = start

        chunk = '\n'.join(self._md_lines[start:end])

        self._win_loading = True
        try:
            self.md_view.setMarkdown(chunk)
            bar = self.md_view.verticalScrollBar()
            if scroll_to == 'bottom':
                bar.setValue(bar.maximum())
                QTimer.singleShot(0, self._scroll_bottom_guarded)
            else:
                bar.setValue(0)
        finally:
            self._win_loading = False

        self.md_more_label.setText(
            f'当前显示：第 {start + 1} – {end} 行 / 共 {total} 行'
        )

    def _scroll_bottom_guarded(self):
        """异步把滚动条放到最底部，期间屏蔽翻页判断。"""
        if not self._md_lines:
            return
        self._win_loading = True
        try:
            bar = self.md_view.verticalScrollBar()
            bar.setValue(bar.maximum())
        finally:
            self._win_loading = False

    def _on_scrollbar_changed(self, value):
        """拖动滚动条到顶/底时自动翻页。"""
        if self._win_loading:
            return
        total = len(self._md_lines)
        if total == 0:
            return

        bar = self.md_view.verticalScrollBar()
        if bar.maximum() <= 0:
            return  # 内容不足一屏

        at_top = value <= 0
        at_bottom = value >= bar.maximum()

        if at_bottom:
            # 到底 → 下一页
            if self._win_start + self._win_size < total:
                new_start = min(
                    self._win_start + self._win_step,
                    max(0, total - self._win_size)
                )
                if new_start != self._win_start:
                    self._win_start = new_start
                    self._render_window(scroll_to='top')
        elif at_top:
            # 到顶 → 上一页
            if self._win_start > 0:
                self._win_start = max(0, self._win_start - self._win_step)
                self._render_window(scroll_to='bottom')

    def eventFilter(self, obj, event):
        """拦截 md_view 视口的滚轮事件：在边缘继续滚时翻页。"""
        if obj is self.md_view.viewport() and event.type() == QEvent.Wheel:
            if self._win_loading:
                return True
            total = len(self._md_lines)
            if total == 0:
                return super().eventFilter(obj, event)

            bar = self.md_view.verticalScrollBar()
            delta = event.angleDelta().y()
            at_top = bar.value() <= 0
            at_bottom = bar.value() >= bar.maximum()

            # 已在顶部还继续往上滚 → 上一页
            if delta > 0 and at_top:
                if self._win_start > 0:
                    self._win_start = max(0, self._win_start - self._win_step)
                    self._render_window(scroll_to='bottom')
                return True

            # 已在底部还继续往下滚 → 下一页
            if delta < 0 and at_bottom:
                if self._win_start + self._win_size < total:
                    self._win_start = min(
                        self._win_start + self._win_step,
                        max(0, total - self._win_size)
                    )
                    self._render_window(scroll_to='top')
                return True

        return super().eventFilter(obj, event)

    def _build_md_text(self) -> str:
        """按当前树状态构建 md 文本，返回字符串（不落盘）。"""
        root_item = self.tree.topLevelItem(0)
        if not root_item:
            return '# （无数据）\n'

        tree_lines = [self._root_dir.name + '/']
        self._render_tree(root_item, tree_lines, 1)
        tree_text = '\n'.join(tree_lines)

        contents = []

        def walk(item, rel, ancestor_blocked):
            is_dir = item.data(0, ROLE_IS_DIR)
            state = item.data(0, ROLE_STATE) or STATE_NORMAL
            blocked = ancestor_blocked or (state in (STATE_RED, STATE_BLACK))
            abs_path = Path(item.data(0, ROLE_PATH))

            if is_dir:
                for i in range(item.childCount()):
                    child = item.child(i)
                    walk(child, rel / child.text(0).rstrip('/'), blocked)
            else:
                if state != STATE_NORMAL or ancestor_blocked:
                    return
                if item.data(0, ROLE_IS_TEXT):
                    attrs = get_attrs(abs_path)
                    content = read_text_content(abs_path) if attrs['size'] else None
                    contents.append((rel, attrs, content))

        for i in range(root_item.childCount()):
            child = root_item.child(i)
            walk(child, Path(child.text(0).rstrip('/')), False)

        lines = []
        lines.append('# 纯文本文件提取报告\n')
        lines.append(f'扫描目录：`{self._root_dir}`\n')
        lines.append('## 项目结构\n')
        lines.append('> **颜色说明**\n')
        lines.append('>\n')
        lines.append('> 🔴 标红：该文件/文件夹不读取内容\n')
        lines.append('> ⬛ 标黑：文件夹内部全黑；文件隐身（不出现于下方内容区）\n')
        lines.append('> 🟡 混杂：文件夹内部状态混杂（部分子项被标注）\n')
        lines.append('>\n')
        lines.append('> 以上颜色仅为用户在提取器里的手动标注，用于控制是否读取内容，\n')
        lines.append('> 与文件中代码/文本的实际内容无关。\n')
        lines.append('```')
        lines.append(tree_text)
        lines.append('```\n')
        lines.append(f'共输出 {len(contents)} 个文件的内容。\n')
        lines.append('---\n')
        if contents:
            lines.append('## 文件内容\n')
            for rel, attrs, content in contents:
                attr_str = f"大小: {attrs['size']} | 修改时间: {attrs['mtime']} | 权限: {attrs['mode']}"
                lines.append(f'### {rel} ({attr_str})\n')
                if content is None:
                    lines.append('null\n')
                else:
                    fence = '```'
                    while fence in content:
                        fence += '`'
                    lines.append(f'{fence}\n{content}\n{fence}\n')
        else:
            lines.append('## 文件内容\n')
            lines.append('（无可输出的文件内容）\n')

        return '\n'.join(lines)

    def _render_tree(self, item: QTreeWidgetItem, lines: list, indent: int):
        for i in range(item.childCount()):
            child = item.child(i)
            prefix = '    ' * indent
            name = child.text(0)
            state = child.data(0, ROLE_STATE) or STATE_NORMAL
            is_dir = child.data(0, ROLE_IS_DIR)

            if state == STATE_BLACK:
                if is_dir:
                    lines.append(prefix + name + ' ⬛')
                    self._render_tree(child, lines, indent + 1)
            elif state == STATE_RED:
                lines.append(prefix + name + ' 🔴')
                if is_dir:
                    self._render_tree(child, lines, indent + 1)
            elif state == STATE_MIX:
                lines.append(prefix + name + ' 🟡')
                if is_dir:
                    self._render_tree(child, lines, indent + 1)
            else:
                lines.append(prefix + name)
                if is_dir:
                    self._render_tree(child, lines, indent + 1)

    def _clear_all(self):
        self.tree.clear()
        self._root_dir = None
        self.hint.setText('把文件夹拖到这里，或点击下方按钮选择')
        self.md_view.clear()
        self._md_lines = []
        self._win_start = 0
        self.md_more_label.setText('')
        self.md_icon.set_file(None)
        # 销毁临时文件
        if self._preview_file and self._preview_file.exists():
            try:
                self._preview_file.unlink()
            except OSError:
                pass
            self._preview_file = None

    # ---------- 吸附核心 ----------
    def _screen_geometry(self):
        return QApplication.primaryScreen().availableGeometry()

    def _check_auto_collapse(self):
        if self._dragging or not self.isVisible():
            return
        if self._drag_hovering:
            return
        if self._root_dir is not None:
            if self._collapsed:
                self.expand_from_edge()
        else:
            if not self._collapsed:
                self.collapse_to_edge()

    def _place_on_edge(self, edge: int, slide_pos: int):
        g = self._screen_geometry()
        geo = self.geometry()
        w, h = geo.width(), geo.height()
        s = self.STRIP_SIZE

        if edge == self.EDGE_LEFT:
            x = g.left() - w + s if self._collapsed else g.left()
            y = max(g.top(), min(slide_pos, g.bottom() - h + 1))
        elif edge == self.EDGE_RIGHT:
            x = g.right() - s + 1 if self._collapsed else g.right() - w + 1
            y = max(g.top(), min(slide_pos, g.bottom() - h + 1))
        elif edge == self.EDGE_TOP:
            x = max(g.left(), min(slide_pos, g.right() - w + 1))
            y = g.top() - h + s if self._collapsed else g.top()
        else:
            return

        self._edge = edge
        self.move(x, y)

    def collapse_to_edge(self):
        if self._edge == self.EDGE_NONE:
            self._edge = self.EDGE_RIGHT
        geo = self.geometry()
        if self._edge == self.EDGE_TOP:
            slide = geo.left()
        else:
            slide = geo.top()
        self._collapsed = True
        self._place_on_edge(self._edge, slide)
        self._strip_bar.setGeometry(0, 0, self.width(), self.height())
        self._strip_bar.show()
        self._strip_bar.raise_()

    def expand_from_edge(self):
        if self._edge == self.EDGE_NONE:
            self._edge = self.EDGE_RIGHT
        geo = self.geometry()
        if self._edge == self.EDGE_TOP:
            slide = geo.left()
        else:
            slide = geo.top()
        self._collapsed = False
        self._place_on_edge(self._edge, slide)
        self._strip_bar.hide()

    # ---------- 鼠标事件 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self._collapsed or self.title_bar.geometry().contains(e.pos()):
                self._dragging = True
                self._drag_offset = e.globalPos() - self.frameGeometry().topLeft()
                e.accept()
                return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._dragging and self._drag_offset is not None:
            self._drag_follow(e.globalPos())
            e.accept()
            return
        super().mouseMoveEvent(e)

    def _drag_follow(self, global_pos: QPoint):
        g = self._screen_geometry()
        mx, my = global_pos.x(), global_pos.y()

        d_left = mx - g.left()
        d_right = g.right() - mx
        d_top = my - g.top()

        bonus = 30
        dists = {
            self.EDGE_LEFT: d_left - (bonus if self._edge == self.EDGE_LEFT else 0),
            self.EDGE_RIGHT: d_right - (bonus if self._edge == self.EDGE_RIGHT else 0),
            self.EDGE_TOP: d_top - (bonus if self._edge == self.EDGE_TOP else 0),
        }
        new_edge = min(dists.items(), key=lambda kv: kv[1])[0]

        if new_edge == self.EDGE_TOP:
            slide = mx - self._drag_offset.x()
        else:
            slide = my - self._drag_offset.y()

        self._place_on_edge(new_edge, slide)

    def mouseReleaseEvent(self, e):
        if self._dragging:
            self._dragging = False
            self._drag_offset = None
            if self._collapsed:
                self.collapse_to_edge()
            else:
                self.expand_from_edge()
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if self._collapsed:
            self.expand_from_edge()
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._collapsed:
            self._strip_bar.setGeometry(0, 0, self.width(), self.height())

    def closeEvent(self, e):
        # 退出时销毁临时文件
        if self._preview_file and self._preview_file.exists():
            try:
                self._preview_file.unlink()
            except OSError:
                pass
            self._preview_file = None
        super().closeEvent(e)


# ---------- 托盘 ----------
class TrayApp:
    def __init__(self, app: QApplication):
        self.app = app
        self.window = FloatingWindow()

        icon = app.style().standardIcon(QStyle.SP_FileDialogContentsView)
        self.tray = QSystemTrayIcon(icon, app)
        self.tray.setToolTip('文本提取器')

        menu = QMenu()

        # 托盘里加「选择文件夹」
        self.act_choose = QAction('选择文件夹', menu)
        self.act_choose.triggered.connect(self._choose_folder_from_tray)
        menu.addAction(self.act_choose)

        menu.addSeparator()

        self.act_toggle = QAction('隐藏窗口', menu)
        self.act_toggle.triggered.connect(self._toggle_window)
        menu.addAction(self.act_toggle)

        menu.addSeparator()

        act_quit = QAction('退出', menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        menu.aboutToShow.connect(self._update_menu_text)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        g = QApplication.primaryScreen().availableGeometry()
        w = self.window.width()
        h = self.window.height()
        self.window.move(g.right() - w, g.top() + (g.height() - h) // 2)
        self.window.show()

    def _choose_folder_from_tray(self):
        """托盘菜单点「选择文件夹」：唤起窗口并弹选择框。"""
        if not self.window.isVisible():
            self.window.show()
        self.window.raise_()
        self.window.activateWindow()
        self.window._choose_folder()

    def _update_menu_text(self):
        self.act_toggle.setText('隐藏窗口' if self.window.isVisible() else '显示窗口')

    def _toggle_window(self):
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._toggle_window()

    def _quit(self):
        # 退出前清掉临时文件
        if self.window._preview_file and self.window._preview_file.exists():
            try:
                self.window._preview_file.unlink()
            except OSError:
                pass
            self.window._preview_file = None
        self.tray.hide()
        self.app.quit()


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _ = TrayApp(app)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()