from PySide6.QtWidgets import QTableWidget, QAbstractItemView, QStyledItemDelegate
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QPainter, QPen


class HoverableTableWidget(QTableWidget):
    rowClicked = Signal(int)
    rowHovered = Signal(int)
    rowDoubleClicked = Signal(int)

    def __init__(self, *args, selection_color="#ADD8E6", completed_color="#43A047", **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)
        self._hovered_row = -1
        self._selected_row = -1
        self.completed_rows = set()  # Track completed rows
        self.hover_color = QColor("#2196F3")  # Light blue for hover
        self.selection_color = QColor(selection_color)
        self.completed_color = QColor(completed_color)  # Green for completed rows
        self.setSelectionMode(QAbstractItemView.NoSelection)  # Disable default selection behavior
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)

    def mark_row_completed(self, row):
        """Mark a row as completed."""
        self.completed_rows.add(row)
        self.viewport().update()

    def _on_cell_double_clicked(self, row, column):
        self.rowDoubleClicked.emit(row)

    def mouseMoveEvent(self, event):
        index = self.indexAt(event.pos())
        row = index.row()
        if row != self._hovered_row:
            self._hovered_row = row
            self.viewport().update()
            self.rowHovered.emit(row)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_row = -1
        self.viewport().update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        if index.isValid():
            if self._selected_row == index.row():
                self._selected_row = -1  # Deselect if already selected
            else:
                self._selected_row = index.row()
            self.viewport().update()
            self.rowClicked.emit(self._selected_row)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        for row in range(self.rowCount()):
            rect = self.visualItemRect(self.item(row, 0))
            rect.setLeft(0)
            rect.setRight(self.viewport().width())

            if row in self.completed_rows:
                painter.fillRect(rect, self.completed_color)  # Static color for completed rows
            elif row == self._selected_row:
                painter.fillRect(rect, self.selection_color)
            elif row == self._hovered_row:
                painter.fillRect(rect, self.hover_color)

        super().paintEvent(event)


class BestRowDelegate(QStyledItemDelegate):
    def __init__(self, best_row, table, border_color="#2196F3", parent=None):
        super().__init__(parent)
        self.best_row = best_row
        self.table = table
        self.border_color = border_color

    def paint(self, painter, option, index):
        # Draw the custom border for the best row
        if index.row() == self.best_row:
            pen = QPen(QColor(self.border_color), 2)
            painter.save()
            painter.setPen(pen)
            rect = option.rect
            painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
            if index.column() == 0:
                painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
            if index.column() == (index.model().columnCount() - 1):
                painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
            painter.restore()

        # Call the base class's paint method to render the cell content
        super().paint(painter, option, index)
