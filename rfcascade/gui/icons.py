"""Crisp vector toolbar icons drawn with QPainter (no external image files)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from . import theme

_S = 40  # source pixmap size (rendered down for crispness)


def _canvas(color: str):
    pm = QPixmap(_S, _S)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(2.6)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    return pm, p


def _icon(name: str, color: str) -> QIcon:
    pm, p = _canvas(color)
    c = QColor(color)

    if name == "new":
        p.drawRoundedRect(QRectF(11, 7, 18, 26), 3, 3)
        p.drawLine(20, 14, 20, 26)
        p.drawLine(14, 20, 26, 20)
    elif name == "open":
        path = QPainterPath()
        path.moveTo(7, 14); path.lineTo(16, 14); path.lineTo(19, 17); path.lineTo(33, 17)
        path.lineTo(33, 31); path.lineTo(7, 31); path.closeSubpath()
        p.drawPath(path)
    elif name == "save":
        p.drawRoundedRect(QRectF(8, 8, 24, 24), 3, 3)
        p.drawRect(QRectF(14, 8, 12, 8))
        p.drawRect(QRectF(13, 22, 14, 10))
    elif name == "add":
        p.drawEllipse(QRectF(8, 8, 24, 24))
        p.drawLine(20, 14, 20, 26)
        p.drawLine(14, 20, 26, 20)
    elif name == "delete":
        p.drawLine(11, 13, 29, 13)
        p.drawLine(16, 13, 17, 9); p.drawLine(24, 13, 23, 9); p.drawLine(17, 9, 23, 9)
        path = QPainterPath()
        path.moveTo(13, 13); path.lineTo(15, 31); path.lineTo(25, 31); path.lineTo(27, 13)
        p.drawPath(path)
        p.drawLine(20, 17, 20, 27)
    elif name == "duplicate":
        p.drawRoundedRect(QRectF(9, 13, 17, 20), 3, 3)
        p.drawRoundedRect(QRectF(15, 7, 17, 20), 3, 3)
    elif name == "up":
        poly = QPolygonF([QPointF(20, 9), QPointF(29, 21), QPointF(11, 21)])
        p.drawPolyline(poly)
        p.drawLine(20, 13, 20, 31)
    elif name == "down":
        poly = QPolygonF([QPointF(11, 19), QPointF(20, 31), QPointF(29, 19)])
        p.drawPolyline(poly)
        p.drawLine(20, 9, 20, 27)
    elif name == "edit":
        p.drawLine(10, 30, 14, 30)
        path = QPainterPath()
        path.moveTo(13, 27); path.lineTo(27, 13); path.lineTo(31, 17); path.lineTo(17, 31); path.closeSubpath()
        p.drawPath(path)
    elif name == "sweep":
        path = QPainterPath()
        path.moveTo(8, 28)
        path.cubicTo(16, 28, 16, 12, 22, 12)
        path.cubicTo(28, 12, 28, 28, 33, 22)
        p.drawPath(path)
        p.drawLine(8, 31, 33, 31)
    elif name == "montecarlo":
        p.drawRoundedRect(QRectF(10, 10, 20, 20), 4, 4)
        p.setBrush(c)
        for (x, y) in [(15, 15), (25, 15), (20, 20), (15, 25), (25, 25)]:
            p.drawEllipse(QPointF(x, y), 1.7, 1.7)
    elif name == "export":
        p.drawLine(20, 8, 20, 24)
        poly = QPolygonF([QPointF(14, 16), QPointF(20, 8), QPointF(26, 16)])
        p.drawPolyline(poly)
        path = QPainterPath()
        path.moveTo(11, 22); path.lineTo(11, 32); path.lineTo(29, 32); path.lineTo(29, 22)
        p.drawPath(path)
    elif name == "library":
        p.drawLine(11, 9, 11, 31); p.drawLine(15, 9, 15, 31)
        p.drawRect(QRectF(19, 9, 6, 22))
        p.save(); p.translate(30, 10); p.rotate(15)
        p.drawRect(QRectF(0, 0, 5, 22)); p.restore()
    elif name == "theme":
        p.drawEllipse(QRectF(10, 10, 20, 20))
        path = QPainterPath()
        path.moveTo(20, 10)
        path.arcTo(QRectF(10, 10, 20, 20), 90, -180)
        p.setBrush(c); p.drawPath(path)
    elif name == "run":
        poly = QPolygonF([QPointF(14, 10), QPointF(31, 20), QPointF(14, 30)])
        p.setBrush(c); p.drawPolygon(poly)
    elif name == "circuit":
        # a little series/shunt ladder schematic
        p.drawLine(7, 14, 14, 14)
        p.drawRoundedRect(QRectF(14, 11, 9, 6), 1.5, 1.5)
        p.drawLine(23, 14, 33, 14)
        p.drawLine(28, 14, 28, 21)        # shunt branch
        p.drawLine(23, 21, 33, 21)        # cap plate
        p.drawLine(25, 24, 31, 24)        # cap plate
        p.drawLine(26, 28, 30, 28)        # ground
    elif name == "freq":
        # a filter response curve (band-pass hump)
        path = QPainterPath()
        path.moveTo(8, 29)
        path.lineTo(16, 29)
        path.cubicTo(20, 29, 20, 12, 24, 12)
        path.cubicTo(28, 12, 28, 29, 32, 29)
        p.drawPath(path)
        p.drawLine(7, 31, 33, 31)
    elif name == "import":
        p.drawLine(20, 8, 20, 22)
        poly = QPolygonF([QPointF(14, 15), QPointF(20, 23), QPointF(26, 15)])
        p.drawPolyline(poly)
        path = QPainterPath()
        path.moveTo(11, 24); path.lineTo(11, 32); path.lineTo(29, 32); path.lineTo(29, 24)
        p.drawPath(path)

    p.end()
    return QIcon(pm.scaled(int(_S * 0.7), int(_S * 0.7), Qt.KeepAspectRatio, Qt.SmoothTransformation))


def icon(name: str, color: str | None = None) -> QIcon:
    return _icon(name, color or theme.current_palette().text)
