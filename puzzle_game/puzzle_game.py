import sys
import os
import random
import zipfile
import tempfile
import shutil
import math

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel,
    QMessageBox, QGridLayout
)
from PySide6.QtGui import (
    QPixmap, QImage, QImageReader, QDragEnterEvent, QDropEvent,
    QPainter, QColor, QPen, QBrush, QRadialGradient, QPainterPath,
    QRegion, QIcon
)
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF


IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tiff', '.ico'}
MIN_PUZZLE_SIZE = 400
MAX_SCREEN_RATIO = 0.75


def resource_path(relative_path):
    """兼容 PyInstaller 打包后的资源路径"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def is_image_by_content(file_path):
    try:
        reader = QImageReader(file_path)
        reader.setDecideFormatFromContent(True)
        return reader.canRead()
    except Exception:
        return False


def is_image_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return True
    return is_image_by_content(file_path)


def find_images_in_folder(folder_path):
    images = []
    for root, dirs, files in os.walk(folder_path):
        for f in files:
            full_path = os.path.join(root, f)
            if is_image_file(full_path):
                images.append(full_path)
    return images


def extract_images_from_zip(zip_path):
    temp_dir = tempfile.mkdtemp(prefix="puzzle_zip_")
    images = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.namelist():
                _, ext = os.path.splitext(member.lower())
                if ext in IMAGE_EXTENSIONS or not ext:
                    try:
                        data = zf.read(member)
                        img = QImage.fromData(data)
                        if not img.isNull():
                            safe_name = member.replace('/', '_').replace('\\', '_')
                            out_path = os.path.join(temp_dir, safe_name)
                            img.save(out_path, "PNG")
                            images.append(out_path)
                    except Exception:
                        continue
    except zipfile.BadZipFile:
        pass
    return temp_dir, images


# ============ 像素数字绘制 ============
class PixelNumber(QLabel):
    DIGITS = {
        '0': ["111", "101", "101", "101", "111"],
        '1': ["010", "110", "010", "010", "111"],
        '2': ["111", "001", "111", "100", "111"],
        '3': ["111", "001", "111", "001", "111"],
        '4': ["101", "101", "111", "001", "001"],
        '5': ["111", "100", "111", "001", "111"],
        '6': ["111", "100", "111", "101", "111"],
        '7': ["111", "001", "010", "010", "010"],
        '8': ["111", "101", "111", "101", "111"],
        '9': ["111", "101", "111", "001", "111"],
    }

    def __init__(self, size=4, digits=2, parent=None):
        super().__init__(parent)
        self.size = size
        self.digits = digits
        self.value = 0
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._update_size()

    def set_value(self, v):
        self.value = v
        self._update_size()
        self.update()

    def set_score(self, v):
        self.set_value(v)

    def _text(self):
        return f"{self.value:0{self.digits}d}" if self.value < 10 ** self.digits else str(self.value)

    def _update_size(self):
        t = self._text()
        gap = self.size
        w = len(t) * 3 * self.size + (len(t) - 1) * gap
        h = 5 * self.size
        self.setFixedSize(w + 4, h + 4)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 245))
        t = self._text()
        gap = self.size
        x = 2
        y = 2
        for ch in t:
            rows = self.DIGITS.get(ch, [])
            for ry, row in enumerate(rows):
                for cx, c in enumerate(row):
                    if c == '1':
                        p.drawRect(x + cx * self.size, y + ry * self.size, self.size, self.size)
            x += 3 * self.size + gap


# ============ 透明三角箭头按钮 ============
class ArrowButton(QPushButton):
    def __init__(self, direction, size=16, parent=None):
        super().__init__(parent)
        self.direction = direction  # up/down/left/right
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(255, 255, 255, 200) if not self._hover else QColor(120, 200, 255, 255)
        s = min(self.width(), self.height()) * 0.35
        cx, cy = self.width() / 2, self.height() / 2
        path = QPainterPath()
        if self.direction == "up":
            path.moveTo(cx, cy - s)
            path.lineTo(cx + s, cy + s)
            path.lineTo(cx - s, cy + s)
        elif self.direction == "down":
            path.moveTo(cx, cy + s)
            path.lineTo(cx + s, cy - s)
            path.lineTo(cx - s, cy - s)
        elif self.direction == "right":
            path.moveTo(cx + s, cy)
            path.lineTo(cx - s, cy - s)
            path.lineTo(cx - s, cy + s)
        elif self.direction == "left":
            path.moveTo(cx - s, cy)
            path.lineTo(cx + s, cy - s)
            path.lineTo(cx + s, cy + s)
        path.closeSubpath()
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawPath(path)


# ============ 透明图标按钮 ============
class IconButton(QPushButton):
    def __init__(self, glyph, size=28, parent=None):
        super().__init__(parent)
        self.glyph = glyph
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(255, 255, 255, 220) if not self._hover else QColor(120, 200, 255, 255)
        if self._hover:
            p.setBrush(QColor(255, 255, 255, 30))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 6, 6)
        self._draw_glyph(p, col)

    def _draw_glyph(self, p, col):
        cx, cy = self.width() / 2, self.height() / 2
        s = min(self.width(), self.height()) * 0.28
        p.setPen(QPen(col, 1.8, Qt.SolidLine, Qt.RoundCap))
        if self.glyph == "close":
            p.drawLine(QPointF(cx - s, cy - s), QPointF(cx + s, cy + s))
            p.drawLine(QPointF(cx + s, cy - s), QPointF(cx - s, cy + s))
        elif self.glyph == "reload":
            p.drawArc(QRectF(cx - s, cy - s, 2 * s, 2 * s), 30 * 16, 270 * 16)
            p.setBrush(col)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx + s, cy), 2.2, 2.2)
        elif self.glyph == "shuffle":
            p.drawLine(QPointF(cx - s, cy - s * 0.4), QPointF(cx + s * 0.4, cy - s * 0.4))
            p.drawLine(QPointF(cx - s, cy + s * 0.4), QPointF(cx + s * 0.4, cy + s * 0.4))
            p.drawLine(QPointF(cx + s * 0.4, cy - s * 0.4), QPointF(cx + s * 0.7, cy - s * 0.7))
            p.drawLine(QPointF(cx + s * 0.4, cy + s * 0.4), QPointF(cx + s * 0.7, cy + s * 0.7))
        elif self.glyph == "check":
            path = QPainterPath()
            path.moveTo(cx - s, cy)
            path.lineTo(cx - s * 0.2, cy + s * 0.7)
            path.lineTo(cx + s, cy - s * 0.6)
            p.drawPath(path)
        elif self.glyph == "next":
            p.setBrush(col)
            p.setPen(Qt.NoPen)
            tri = QPainterPath()
            tri.moveTo(cx - s * 0.6, cy - s)
            tri.lineTo(cx + s * 0.9, cy)
            tri.lineTo(cx - s * 0.6, cy + s)
            tri.closeSubpath()
            p.drawPath(tri)
        elif self.glyph == "drag":
            for i in range(3):
                yy = cy - s + i * s
                p.setPen(QPen(col, 1.8, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(cx - s, yy), QPointF(cx + s, yy))


# ============ 白雾特效 ============
class FogEffect(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.phase = 0.0
        self.active = False
        self.intensity = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(40)
        self.hide()

    def activate(self):
        self.active = True
        self.phase = 0.0
        self.intensity = 1.0
        self.show()
        self.raise_()

    def tick(self):
        if not self.active:
            return
        self.phase += 0.06
        self.intensity = max(0.0, 1.0 - self.phase / 4.0)
        if self.intensity <= 0.0:
            self.active = False
            self.hide()
        self.update()

    def paintEvent(self, e):
        if not self.active:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        grad = QRadialGradient(cx, cy, max(w, h) * 0.72)
        base = int(160 * self.intensity)
        grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        grad.setColorAt(0.62, QColor(255, 255, 255, 0))
        grad.setColorAt(0.86, QColor(255, 255, 255, int(base * 0.5)))
        grad.setColorAt(1.0, QColor(255, 255, 255, base))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRect(self.rect())
        for i in range(4):
            t = (self.phase + i * 0.7) % 3.0
            alpha = max(0, int(180 * (1 - t / 3.0) * self.intensity))
            expand = t * 26
            ring = QRectF(-expand, -expand, w + 2 * expand, h + 2 * expand)
            pen = QPen(QColor(255, 255, 255, alpha))
            pen.setWidthF(10)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(ring, 14, 14)


# ============ 拼图块 ============
class PuzzlePiece(QWidget):
    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.original_index = index
        self.pixmap = None
        self.selected = False
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.PointingHandCursor)

    def set_pixmap(self, pm):
        self.pixmap = pm
        self.setFixedSize(pm.size())
        self.update()

    def paintEvent(self, e):
        if not self.pixmap:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawPixmap(0, 0, self.width(), self.height(), self.pixmap)
        if self.selected:
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QColor(80, 170, 255, 70))
            p.setPen(QPen(QColor(120, 200, 255, 230), 2))
            p.drawRect(self.rect().adjusted(0, 0, -1, -1))


# ============ 拼图棋盘 ============
class PuzzleBoard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)

        self.pieces = []
        self.rows = 3
        self.cols = 3
        self.image_path = None
        self.original_pixmap = None
        self.selected_piece = None
        self.on_files_dropped = None
        self.solved_flag = False
        self._laying_out = False

        self.container = QWidget(self)
        self.container.setAttribute(Qt.WA_TranslucentBackground)
        self.grid = None

        self.fog = FogEffect(self.container)

        self.welcome = QLabel("拖拽图片 / 文件夹 / ZIP 到此处", self)
        self.welcome.setAlignment(Qt.AlignCenter)
        self.welcome.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,170);
                font-size: 14px;
                padding: 40px;
                border: 2px dashed rgba(255,255,255,80);
                border-radius: 12px;
                background: rgba(40,40,60,60);
            }
        """)
        self.welcome.setFixedSize(360, 360)

        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 0)
        self.outer.setSpacing(0)
        self.outer.addWidget(self.container, alignment=Qt.AlignCenter)
        self.outer.addWidget(self.welcome, alignment=Qt.AlignCenter)
        self.container.hide()

    def set_on_files_dropped(self, cb):
        self.on_files_dropped = cb

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        files = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if files and self.on_files_dropped:
            self.on_files_dropped(files)
            event.acceptProposedAction()

    def set_grid(self, rows, cols):
        self.rows = rows
        self.cols = cols

    def load_image(self, image_path):
        self.image_path = image_path
        reader = QImageReader(image_path)
        reader.setDecideFormatFromContent(True)
        img = reader.read()
        if img.isNull():
            self.original_pixmap = QPixmap(image_path)
        else:
            self.original_pixmap = QPixmap.fromImage(img)
        if self.original_pixmap.isNull():
            return False
        self.solved_flag = False
        self.selected_piece = None
        self.layout_pieces()
        return True

    def _compute_size(self):
        src_w = self.original_pixmap.width()
        src_h = self.original_pixmap.height()
        # 获取屏幕可用尺寸，设置上限
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            max_side = int(min(avail.width(), avail.height()) * MAX_SCREEN_RATIO)
        else:
            max_side = 800
        max_side = max(max_side, MIN_PUZZLE_SIZE)
        # 按比例缩放到区间内
        ratio = min(max_side / max(src_w, 1), max_side / max(src_h, 1))
        # 如果图片太小则放大
        min_side = MIN_PUZZLE_SIZE
        min_ratio = max(min_side / max(src_w, 1), min_side / max(src_h, 1))
        if ratio < 1 and min_ratio > 1:
            ratio = min_ratio
        elif ratio > 1 and min_ratio > ratio:
            ratio = min_ratio
        bw = max(min_side // 2, int(src_w * ratio))
        bh = max(min_side // 2, int(src_h * ratio))
        pw = max(24, bw // self.cols)
        ph = max(24, bh // self.rows)
        bw = pw * self.cols
        bh = ph * self.rows
        return pw, ph, bw, bh

    def layout_pieces(self):
        if not self.original_pixmap or self.original_pixmap.isNull():
            return
        if self._laying_out:
            return
        self._laying_out = True
        self.setUpdatesEnabled(False)
        try:
            self.container.hide()
            self.clear_pieces()
            pw, ph, bw, bh = self._compute_size()
            if self.container.size().width() != bw or self.container.size().height() != bh:
                self.container.setFixedSize(bw, bh)
            # 一次缩放到目标大小，使用 SmoothTransformation 保证高清
            scaled = self.original_pixmap.scaled(
                bw, bh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            )
            # 用 QPainter 保证高质量切片
            for r in range(self.rows):
                for c in range(self.cols):
                    idx = r * self.cols + c
                    x = c * pw
                    y = r * ph
                    cropped = scaled.copy(x, y, pw, ph)
                    piece = PuzzlePiece(idx, self.container)
                    piece.set_pixmap(cropped)
                    # 向右向下各重叠1px消除间隙
                    piece.setGeometry(x, y, pw + 1, ph + 1)
                    piece.mousePressEvent = lambda e, p=piece: self.on_piece_clicked(p)
                    piece.show()
                    self.pieces.append(piece)

            self.fog.setGeometry(0, 0, bw, bh)
            self.fog.raise_()
            self.fog.hide()
            self.welcome.hide()
            for _ in range(10):
                random.shuffle(self.pieces)
                if not self.is_solved():
                    break
            self.refresh_grid()
            self.container.show()
        finally:
            self._laying_out = False
            self.setUpdatesEnabled(True)
            self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pieces and self.image_path and not self._laying_out:
            self.layout_pieces()

    def clear_pieces(self):
        for piece in self.pieces:
            piece.setParent(None)
            piece.setGeometry(-9999, -9999, 0, 0)
            piece.hide()
            piece.deleteLater()
        self.pieces = []
        self.selected_piece = None

    def on_piece_clicked(self, piece):
        if self.solved_flag:
            return
        if self.selected_piece is None:
            self.selected_piece = piece
            piece.selected = True
            piece.update()
        elif self.selected_piece is piece:
            piece.selected = False
            piece.update()
            self.selected_piece = None
        else:
            self.selected_piece.selected = False
            self.selected_piece.update()
            self.swap_pieces(self.selected_piece, piece)
            self.selected_piece = None
            if self.is_solved() and not self.solved_flag:
                self.solved_flag = True
                self.fog.activate()
                if self.on_solved:
                    self.on_solved()

    on_solved = None

    def swap_pieces(self, a, b):
        ia = self.pieces.index(a)
        ib = self.pieces.index(b)
        self.pieces[ia], self.pieces[ib] = self.pieces[ib], self.pieces[ia]
        self.refresh_grid()

    def refresh_grid(self):
        if not self.pieces:
            return
        pw = self.pieces[0].width() - 1 if self.pieces else 0
        ph = self.pieces[0].height() - 1 if self.pieces else 0
        for i, piece in enumerate(self.pieces):
            r = i // self.cols
            c = i % self.cols
            piece.setGeometry(c * pw, r * ph, piece.width(), piece.height())

    def shuffle(self):
        if not self.pieces:
            return
        random.shuffle(self.pieces)
        self.refresh_grid()

    def is_solved(self):
        for i, piece in enumerate(self.pieces):
            if piece.original_index != i:
                return False
        return True

    def reset_view(self):
        self.clear_pieces()
        self.image_path = None
        self.original_pixmap = None
        self.solved_flag = False
        self.container.setMask(QRegion())
        self.welcome.show()
        self.container.hide()


# ============ 主窗口 ============
class PuzzleGame(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("拼图")
        self.setWindowIcon(QIcon(resource_path("puzzle_icon.ico")))
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(140, 90, 780, 780)
        self.setMinimumSize(560, 560)

        self.image_list = []
        self.current_image_index = 0
        self.temp_dirs = []
        self.score = 0

        self._drag_pos = None
        self._build_ui()

    def _build_ui(self):
        self.bg = QWidget()
        self.bg.setAttribute(Qt.WA_TranslucentBackground)
        self.setCentralWidget(self.bg)

        outer = QVBoxLayout(self.bg)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(2)
        outer.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # 顶部：行数控制 ← 03 →
        top_row = QHBoxLayout()
        top_row.setSpacing(2)
        top_row.addStretch()
        self.btn_row_left = ArrowButton("left", 16)
        self.btn_row_left.clicked.connect(lambda: self.change_rows(-1))
        self.lbl_rows = PixelNumber(size=5, digits=2)
        self.lbl_rows.set_value(3)
        self.btn_row_right = ArrowButton("right", 16)
        self.btn_row_right.clicked.connect(lambda: self.change_rows(1))
        top_row.addWidget(self.btn_row_left)
        top_row.addWidget(self.lbl_rows)
        top_row.addWidget(self.btn_row_right)
        top_row.addStretch()
        outer.addLayout(top_row)

        # 中间：列数控制 + 拼图 + 右侧按钮
        mid_row = QHBoxLayout()
        mid_row.setSpacing(4)
        mid_row.setAlignment(Qt.AlignCenter)

        # 列数控制 ↑ 03 ↓（竖着排，紧贴拼图左边缘）
        col_box = QVBoxLayout()
        col_box.setSpacing(0)
        col_box.setAlignment(Qt.AlignCenter)
        self.btn_col_up = ArrowButton("up", 16)
        self.btn_col_up.clicked.connect(lambda: self.change_cols(1))
        self.lbl_cols = PixelNumber(size=5, digits=2)
        self.lbl_cols.set_value(3)
        self.btn_col_down = ArrowButton("down", 16)
        self.btn_col_down.clicked.connect(lambda: self.change_cols(-1))
        col_box.addWidget(self.btn_col_up, alignment=Qt.AlignHCenter)
        col_box.addWidget(self.lbl_cols, alignment=Qt.AlignHCenter)
        col_box.addWidget(self.btn_col_down, alignment=Qt.AlignHCenter)
        mid_row.addLayout(col_box)

        # 拼图
        self.board = PuzzleBoard()
        self.board.set_on_files_dropped(self.process_paths)
        self.board.on_solved = self.on_puzzle_solved
        self.board.setMinimumSize(360, 360)
        mid_row.addWidget(self.board)

        # 右侧按钮列（紧贴拼图右边缘）
        right_btns = QVBoxLayout()
        right_btns.setSpacing(4)
        right_btns.setAlignment(Qt.AlignVCenter)
        self.btn_drag = IconButton("drag", 28)
        self.btn_drag.setCursor(Qt.OpenHandCursor)
        self.btn_drag.mousePressEvent = self._on_drag_press
        self.btn_drag.mouseMoveEvent = self._on_drag_move
        self.btn_drag.mouseReleaseEvent = self._on_drag_release
        self.btn_shuffle = IconButton("shuffle", 28)
        self.btn_shuffle.clicked.connect(self.shuffle_pieces)
        self.btn_check = IconButton("check", 28)
        self.btn_check.clicked.connect(self.check_win)
        self.btn_reload = IconButton("reload", 28)
        self.btn_reload.clicked.connect(self.reload_image)
        self.btn_close = IconButton("close", 28)
        self.btn_close.clicked.connect(self.close)
        for b in (self.btn_drag, self.btn_shuffle, self.btn_check, self.btn_reload, self.btn_close):
            right_btns.addWidget(b, alignment=Qt.AlignHCenter)
        mid_row.addLayout(right_btns)

        outer.addLayout(mid_row)

        # 底部：分数 + 下一图箭头（多图时显示）
        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        bottom.addStretch()
        self.score_widget = PixelNumber(size=5, digits=2)
        bottom.addWidget(self.score_widget)
        self.btn_next = IconButton("next", 26)
        self.btn_next.clicked.connect(self.next_image)
        self.btn_next.hide()
        bottom.addWidget(self.btn_next)
        bottom.addStretch()
        outer.addLayout(bottom)

    def _on_drag_press(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.btn_drag.setCursor(Qt.ClosedHandCursor)

    def _on_drag_move(self, e):
        if self._drag_pos is not None and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def _on_drag_release(self, e):
        self._drag_pos = None
        self.btn_drag.setCursor(Qt.OpenHandCursor)

    def change_rows(self, delta):
        v = self.lbl_rows.value + delta
        if 2 <= v <= 20:
            self.lbl_rows.set_value(v)
            self.apply_grid()

    def change_cols(self, delta):
        v = self.lbl_cols.value + delta
        if 2 <= v <= 20:
            self.lbl_cols.set_value(v)
            self.apply_grid()

    # ----- 数据处理 -----
    def cleanup_temp(self):
        for d in self.temp_dirs:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        self.temp_dirs = []

    def closeEvent(self, event):
        self.cleanup_temp()
        super().closeEvent(event)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()

    def process_paths(self, paths):
        self.cleanup_temp()
        found = []
        for p in paths:
            if os.path.isdir(p):
                found.extend(find_images_in_folder(p))
            elif os.path.isfile(p):
                ext = os.path.splitext(p)[1].lower()
                if ext == '.zip':
                    temp_dir, imgs = extract_images_from_zip(p)
                    if temp_dir:
                        self.temp_dirs.append(temp_dir)
                    found.extend(imgs)
                elif is_image_file(p):
                    found.append(p)
        if not found:
            QMessageBox.warning(self, "提示", "未找到图片")
            return
        self.image_list = sorted(found)
        self.current_image_index = 0
        self.btn_next.setVisible(len(self.image_list) > 1)
        self.load_current_image()

    def load_current_image(self):
        if not self.image_list:
            return
        path = self.image_list[self.current_image_index]
        self.board.set_grid(self.lbl_rows.value, self.lbl_cols.value)
        self.board.load_image(path)

    def apply_grid(self):
        if not self.image_list:
            return
        self.load_current_image()

    def next_image(self):
        if len(self.image_list) <= 1:
            return
        self.current_image_index = (self.current_image_index + 1) % len(self.image_list)
        self.load_current_image()

    def shuffle_pieces(self):
        if not self.board.pieces:
            return
        self.board.shuffle()
        self.board.solved_flag = False

    def check_win(self):
        if not self.board.pieces:
            return
        if self.board.is_solved():
            if not self.board.solved_flag:
                self.board.solved_flag = True
                self.board.fog.activate()
                self.on_puzzle_solved()
        else:
            QMessageBox.information(self, "提示", "还差一点哦～")

    def on_puzzle_solved(self):
        self.score += 1
        self.score_widget.set_score(self.score)

    def reload_image(self):
        self.board.reset_view()
        self.image_list = []
        self.current_image_index = 0
        self.image_path = None
        self.btn_next.hide()
        self.cleanup_temp()


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    window = PuzzleGame()
    window.show()
    sys.exit(app.exec())
