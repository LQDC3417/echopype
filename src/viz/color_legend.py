"""Echogram 独立色标栏，不接受声图缩放和选区操作。"""

from matplotlib import colormaps
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QMenu, QWidget

from src.gui.i18n import T
from src.gui.theme import CHROME_COLORS


class ColorLegend(QWidget):
    def __init__(self, renderer):
        super().__init__(renderer)
        self.renderer = renderer
        self.setAccessibleName(T("legend_title"))
        self.setToolTip(T("legend_hint"))

    def preferred_width(self):
        labels = ("Sv (dB)", T("legend_no_data"), f"{self.renderer._vmin:.0f}", f"{self.renderer._vmax:.0f}")
        return max(90, 48 + max(self.fontMetrics().horizontalAdvance(s) for s in labels))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(CHROME_COLORS["panel"]))
        painter.setPen(QColor(CHROME_COLORS["border"]))
        painter.drawLine(0, 0, 0, self.height())
        if self.renderer.get_data() is None:
            return
        top, bottom = 30, max(31, self.height() - 40)
        height = bottom - top
        cmap = colormaps[self.renderer._cmap_name]
        for y in range(height):
            r, g, b, _ = cmap(1 - y / max(height - 1, 1))
            painter.setPen(QColor.fromRgbF(r, g, b))
            painter.drawLine(10, top + y, 28, top + y)
        painter.setPen(QColor(CHROME_COLORS["text"]))
        painter.drawText(10, 20, "Sv (dB)")
        ticks = max(2, min(10, height // 70 + 1))
        for i in range(ticks):
            t = i / (ticks - 1)
            value = self.renderer._vmax + t * (self.renderer._vmin - self.renderer._vmax)
            y = round(top + t * height)
            painter.drawLine(29, y, 33, y)
            painter.drawText(37, y + 4, f"{value:.0f}")
        painter.fillRect(10, self.height() - 23, 12, 12, QColor("#707780"))
        painter.drawText(28, self.height() - 12, T("legend_no_data"))

    def wheelEvent(self, event):
        event.accept()

    def mousePressEvent(self, event):
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction(T("panel_display_settings"), self.renderer.display_settings_requested.emit)
        menu.exec(event.globalPos())
