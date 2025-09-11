import os
import logging
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QMenu, QDialog, QVBoxLayout, QApplication, QInputDialog, QFileDialog, QFormLayout,
                               QLineEdit, QPushButton, QHBoxLayout, QFrame, QComboBox)
from PySide6.QtWebEngineWidgets import QWebEngineView

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class xWebEngineView(QWebEngineView):
    def __init__(self, parent=None, modaled=False):
        super().__init__(parent)
        self.modaled = modaled

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        # Add custom actions
        if not self.modaled:
            open_action = QAction("Expand", self)
            open_action.triggered.connect(self.open_in_modal)
            menu.addAction(open_action)

        reload_action = QAction("Reload", self)
        reload_action.triggered.connect(self.reload)
        menu.addAction(reload_action)

        save_action = QAction("Save As...", self)
        save_action.triggered.connect(self.save_page)
        menu.addAction(save_action)

        # Set custom styling for the menu
        menu.setStyleSheet("""
            QMenu {
                background-color: #2e2e2e; /* Replace with your primary background color */
                color: white;
            }
            QMenu::item:selected {
                background-color: #505050; /* Highlight color */
            }
        """)

        # Show the menu at the cursor position
        menu.exec(event.globalPos())

    def open_in_modal(self):
        # Create a non-blocking dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Data Plot")
        dialog.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        dialog.setModal(False)

        new_webview = xWebEngineView(dialog, modaled=True)

        # Center the dialog
        screen = QApplication.primaryScreen().geometry()
        width, height = 1200, 800
        x = (screen.width() - width) // 2
        y = (screen.height() - height) // 2
        dialog.setGeometry(x, y, width, height)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(new_webview)

        def set_html(html):
            new_webview.setHtml(html)

        self.page().toHtml(set_html)

        # Show the dialog
        dialog.show()

    def save_page(self):
        """Handle saving the current page as PNG."""
        # Get project directory as default save location
        project_dir = os.environ.get('ESAT_PROJECT_DIR', '.')
        plots_dir = os.path.join(project_dir, 'plots')
        os.makedirs(plots_dir, exist_ok=True)

        if self.modaled:
            # For modal dialogs, show customization options first

            # Create customization dialog
            options_dialog = QDialog(self)
            options_dialog.setWindowTitle("Plot Customization")
            options_dialog.setModal(True)
            options_dialog.resize(400, 300)

            # Apply dark styling to match the GUI
            options_dialog.setStyleSheet("""
                QDialog {
                    background-color: #2e2e2e;
                    color: white;
                }
                QLineEdit {
                    background-color: #3e3e3e;
                    color: white;
                    border: 1px solid #555555;
                    padding: 6px;
                    border-radius: 3px;
                    font-size: 12px;
                }
                QLineEdit:focus {
                    border: 1px solid #0078d4;
                }
                QPushButton {
                    background-color: #404040;
                    color: white;
                    border: 1px solid #555555;
                    padding: 8px 16px;
                    border-radius: 3px;
                    font-size: 12px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
                QPushButton:pressed {
                    background-color: #2e2e2e;
                }
                QLabel {
                    background-color: #2e2e2e;
                    color: white;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 2px;
                    border: none;
                }
                QComboBox {
                    background-color: #3e3e3e;
                    color: white;
                    border: 1px solid #555555;
                    padding: 6px;
                    border-radius: 3px;
                    font-size: 12px;
                }
                QComboBox:focus {
                    border: 1px solid #0078d4;
                }
                QComboBox::drop-down {
                    border: none;
                    background-color: #404040;
                }
                QComboBox::down-arrow {
                    border: none;
                    color: white;
                }
                QComboBox QAbstractItemView {
                    background-color: #3e3e3e;
                    color: white;
                    selection-background-color: #505050;
                    border: 1px solid #555555;
                }
                QComboBox QAbstractItemView::item {
                    padding: 6px;
                    color: white;
                }
                QComboBox QAbstractItemView::item:selected {
                    background-color: #505050;
                }
            """)

            layout = QFormLayout(options_dialog)

            # Input fields
            # Input fields with placeholders and default values

            x_min_input = QLineEdit()
            x_min_input.setPlaceholderText("Auto")
            x_min_input.setText("")  # Leave empty for auto-scaling

            x_max_input = QLineEdit()
            x_max_input.setPlaceholderText("Auto")
            x_max_input.setText("")  # Leave empty for auto-scaling

            y_min_input = QLineEdit()
            y_min_input.setPlaceholderText("Auto")
            y_min_input.setText("")  # Leave empty for auto-scaling

            y_max_input = QLineEdit()
            y_max_input.setPlaceholderText("Auto")
            y_max_input.setText("")  # Leave empty for auto-scaling

            width_input = QLineEdit()
            width_input.setPlaceholderText("1200")
            width_input.setText("1200")

            height_input = QLineEdit()
            height_input.setPlaceholderText("800")
            height_input.setText("800")

            scale_input = QComboBox()
            scale_input.addItems(["1", "2", "3", "4"])
            scale_input.setCurrentText("2")

            layout.addRow("X-Axis Min:", x_min_input)
            layout.addRow("X-Axis Max:", x_max_input)
            layout.addRow("Y-Axis Min:", y_min_input)
            layout.addRow("Y-Axis Max:", y_max_input)

            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            layout.addRow(separator)

            layout.addRow("Image Width (px):", width_input)
            layout.addRow("Image Height (px):", height_input)
            layout.addRow("Image Scale (DPI):", scale_input)

            # Buttons
            button_layout = QHBoxLayout()
            ok_button = QPushButton("Save Plot")
            cancel_button = QPushButton("Cancel")
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addRow(button_layout)

            cancel_button.clicked.connect(options_dialog.reject)

            def save_with_options():
                options_dialog.accept()

                # Get user inputs
                x_min = x_min_input.text().strip()
                x_max = x_max_input.text().strip()
                y_min = y_min_input.text().strip()
                y_max = y_max_input.text().strip()

                width = int(width_input.text().strip())
                height = int(height_input.text().strip())

                # Show file save dialog
                default_filename = os.path.join(plots_dir, "plot.png")
                filename, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save Plot As",
                    default_filename,
                    "PNG files (*.png)"
                )

                if filename:
                    # Apply customizations and save
                    scale = int(scale_input.currentText()) if scale_input.currentText() else 2

                    js_code = f"""
                    var plotlyDiv = document.querySelector('.plotly-graph-div');
                    if (plotlyDiv && window.Plotly) {{
                        var update = {{}};
                        var layout_update = {{}};

                        // Update axis ranges
                        if ('{x_min}' && '{x_max}') {{
                            layout_update.xaxis = layout_update.xaxis || {{}};
                            layout_update.xaxis.range = [{x_min or 'null'}, {x_max or 'null'}];
                        }}
                        if ('{y_min}' && '{y_max}') {{
                            layout_update.yaxis = layout_update.yaxis || {{}};
                            layout_update.yaxis.range = [{y_min or 'null'}, {y_max or 'null'}];
                        }}

                        // Apply updates if any
                        if (Object.keys(layout_update).length > 0) {{
                            Plotly.relayout(plotlyDiv, layout_update);
                        }}

                        // Wait a bit for the update to apply, then save
                        setTimeout(function() {{
                            Plotly.toImage(plotlyDiv, {{
                                format: 'png',
                                width: {width},
                                height: {height},
                                scale: {scale}
                            }}).then(function(dataUrl) {{
                                var base64Data = dataUrl.split(',')[1];
                                window.qtSaveImage = base64Data;
                                console.log('Image data ready for Qt save');
                            }}).catch(function(err) {{
                                console.error('Error creating image:', err);
                            }});
                        }}, 200);
                    }} else {{
                        console.log('Plotly plot not found');
                    }}
                    """

                    def save_image_data():
                        js_get_data = "window.qtSaveImage || null;"

                        def handle_image_data(data):
                            if data:
                                try:
                                    import base64
                                    image_data = base64.b64decode(data)
                                    with open(filename, 'wb') as f:
                                        f.write(image_data)
                                    logger.info(f"Plot saved to: {filename}")
                                except Exception as e:
                                    logger.error(f"Error saving file: {e}")

                        self.page().runJavaScript(js_get_data, handle_image_data)

                    self.page().runJavaScript(js_code)
                    QTimer.singleShot(1500, save_image_data)

            ok_button.clicked.connect(save_with_options)

            # Show the options dialog
            options_dialog.exec()

        else:
            # For non-modal, use Plotly's built-in download
            js_code = """
            var plotlyDiv = document.querySelector('.plotly-graph-div');
            if (plotlyDiv && window.Plotly) {
                Plotly.downloadImage(plotlyDiv, {
                    format: 'png',
                    width: 1200,
                    height: 800,
                    filename: 'plot'
                }).then(function(filename) {
                    console.log('Plot saved as: ' + filename);
                }).catch(function(err) {
                    console.error('Error saving plot:', err);
                });
            } else {
                console.log('Plotly plot not found');
            }
            """
            self.page().runJavaScript(js_code)
