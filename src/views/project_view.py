import os
import pandas as pd
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton,
    QFileDialog, QGroupBox, QFormLayout, QScrollArea, QComboBox, QMessageBox,
    QListWidget, QToolButton, QMenu, QSizePolicy, QFrame, QStackedWidget, QDialog,
    QApplication
)
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt


class LoadingDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Please Wait")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.setFixedSize(220, 70)


class ProjectView(QWidget):
    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller

        self.setup_ui()
        self.setup_default_project() # For testing purposes, set default paths

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)

        # Project Setup Section
        setup_group = QGroupBox("Project Setup")
        setup_layout = QFormLayout()
        self.project_name_edit = QLineEdit()
        self.project_dir_edit = QLineEdit()
        self.project_dir_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_project_dir)
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.project_dir_edit)
        dir_layout.addWidget(browse_btn)
        setup_layout.addRow("Project Name:", self.project_name_edit)
        setup_layout.addRow("Project Directory:", dir_layout)
        setup_group.setLayout(setup_layout)
        main_layout.addWidget(setup_group)

        # Datasets Section
        datasets_group = QGroupBox("Datasets")
        datasets_layout = QVBoxLayout()
        datasets_group.setLayout(datasets_layout)
        main_layout.addWidget(datasets_group)

        # Add a scroll area for datasets
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        datasets_container = QWidget()
        self.datasets_area = QVBoxLayout(datasets_container)
        self.datasets_area.setAlignment(Qt.AlignTop)
        scroll.setWidget(datasets_container)
        datasets_layout.addWidget(scroll)

        # Add first dataset row by default
        self.dataset_rows = []
        self.add_dataset_row()
        self.data_path_edit = None
        self.unc_path_edit = None

    def setup_default_project(self):
        # Set default paths (ensure these variables are defined in your module)
        testing_project = os.path.join("D:\\", "git", "esat_app", "data", "test_project")
        testing_data = os.path.join("D:\\", "git", "esat_app", "data", "Dataset-BatonRouge-con.csv")
        testing_uncertainty = os.path.join("D:\\", "git", "esat_app", "data", "Dataset-BatonRouge-unc.csv")
        self.set_default_dataset_paths(testing_data, testing_uncertainty)
        self.project_dir_edit.setText(testing_project)

    def browse_project_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if dir_path:
            self.project_dir_edit.setText(dir_path)
        #TODO: Add logic to handle loading an existing project if the directory is not empty

    def add_dataset_row(self):
        group_box = QGroupBox()
        group_layout = QHBoxLayout(group_box)
        group_layout.setContentsMargins(8, 8, 8, 8)

        fields_widget = QWidget()
        fields_layout = QVBoxLayout(fields_widget)
        fields_layout.setContentsMargins(0, 0, 0, 0)

        # First row: Data
        top_row = QHBoxLayout()
        data_path_edit = QLineEdit()
        data_browse_btn = QPushButton("Browse")
        data_browse_btn.clicked.connect(lambda: self.browse_file(data_path_edit))

        # Second row: Uncertainty
        middle_row = QHBoxLayout()
        unc_path_edit = QLineEdit()
        unc_browse_btn = QPushButton("Browse")
        unc_browse_btn.clicked.connect(lambda: self.browse_file(unc_path_edit))

        self.data_path_edit = data_path_edit
        self.unc_path_edit = unc_path_edit

        top_row.addWidget(QLabel("Data:"))
        top_row.addSpacing(46)
        top_row.addWidget(data_path_edit)
        top_row.addWidget(data_browse_btn)
        middle_row.addWidget(QLabel("Uncertainty:"))
        middle_row.addSpacing(8)
        middle_row.addWidget(unc_path_edit)
        middle_row.addWidget(unc_browse_btn)

        # Third row: name and location ID
        name_edit = QLineEdit()
        name_edit.setFixedHeight(24)
        name_edit.setMinimumWidth(160)
        bottom_row_a = QHBoxLayout()
        bottom_row_a.addWidget(QLabel("Name:"))
        bottom_row_a.addSpacing(38)
        bottom_row_a.addWidget(name_edit, 1)

        # 1. Mode selection
        loc_id_mode_combo = QComboBox()
        loc_id_mode_combo.setFixedHeight(24)
        loc_id_mode_combo.addItems(["Select Columns", "Manual Lat/Lon", "Label"])

        # 2. Stacked widget for input modes
        loc_id_stack = QStackedWidget()
        loc_id_stack.setFixedHeight(24)

        # --- Option 1: Select Columns ---
        columns_widget = QWidget()
        columns_layout = QHBoxLayout(columns_widget)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setAlignment(Qt.AlignVCenter)

        loc_id_btn = QToolButton()
        loc_id_btn.setText("Select Column(s)")
        loc_id_btn.setMinimumWidth(120)  # Adjust width as needed
        loc_id_btn.setMinimumHeight(20)  # Optional: match other input heights
        loc_id_btn.setPopupMode(QToolButton.InstantPopup)
        loc_id_menu = QMenu(loc_id_btn)
        loc_id_btn.setMenu(loc_id_menu)
        columns_layout.addWidget(loc_id_btn)
        loc_id_stack.addWidget(columns_widget)

        # --- Option 2: Manual Lat/Lon ---
        latlon_widget = QWidget()
        latlon_layout = QHBoxLayout(latlon_widget)
        latlon_layout.setContentsMargins(0, 0, 0, 0)
        latlon_layout.setAlignment(Qt.AlignVCenter)

        lat_edit = QLineEdit()
        lat_edit.setPlaceholderText("Latitude")
        lat_edit.setFixedHeight(24)
        lon_edit = QLineEdit()
        lon_edit.setPlaceholderText("Longitude")
        lon_edit.setFixedHeight(24)
        latlon_layout.addWidget(QLabel("Lat:"))
        latlon_layout.addWidget(lat_edit)
        latlon_layout.addWidget(QLabel("Lon:"))
        latlon_layout.addWidget(lon_edit)
        loc_id_stack.addWidget(latlon_widget)

        # --- Option 3: Label ---
        label_widget = QWidget()
        label_layout = QHBoxLayout(label_widget)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setAlignment(Qt.AlignVCenter)

        label_edit = QLineEdit()
        label_edit.setPlaceholderText("Location Label")
        label_edit.setFixedHeight(24)
        label_layout.addWidget(label_edit)
        loc_id_stack.addWidget(label_widget)

        # 3. Connect mode selection to stacked widget
        loc_id_mode_combo.currentIndexChanged.connect(loc_id_stack.setCurrentIndex)

        loc_id_stack.setMaximumHeight(32)
        loc_id_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        columns_widget.setMaximumHeight(32)
        latlon_widget.setMaximumHeight(32)
        label_widget.setMaximumHeight(32)

        # 4. Add to your layout
        bottom_row_a.addSpacing(32)
        bottom_row_a.addWidget(QLabel("Location:"))
        bottom_row_a.addWidget(loc_id_mode_combo)
        bottom_row_a.addWidget(loc_id_stack)

        # Set vertical alignment for the layout
        bottom_row_a.setAlignment(Qt.AlignVCenter)

        # Fourth row: Index column and missing value
        index_col_combo = QComboBox()
        index_col_combo.setEditable(True)
        index_col_combo.addItem("Date")
        bottom_row_b = QHBoxLayout()
        bottom_row_b.addWidget(QLabel("Index Col:"))
        bottom_row_b.addSpacing(20)
        bottom_row_b.addWidget(index_col_combo, 1)

        missing_val_edit = QLineEdit("-999")
        missing_val_edit.setFixedWidth(100)
        bottom_row_b.addSpacing(32)
        bottom_row_b.addWidget(QLabel("Missing:"))
        bottom_row_b.addWidget(missing_val_edit)

        fields_layout.addLayout(top_row)
        fields_layout.addLayout(middle_row)
        fields_layout.addSpacing(8)  # Add space between middle and bottom row
        fields_layout.addLayout(bottom_row_a)
        fields_layout.addLayout(bottom_row_b)

        # Add/remove button
        add_btn = QPushButton()
        add_btn.setIcon(QIcon(os.path.join("src", "resources", "icons", "plus-white.svg")))
        add_btn.setToolTip("Add dataset")
        add_btn.setFixedSize(32, 32)
        add_btn.setEnabled(False)  # Disabled by default

        group_layout.addWidget(fields_widget)
        group_layout.addWidget(add_btn, alignment=Qt.AlignVCenter)

        def update_loc_id_menu(columns):
            loc_id_menu.clear()
            for col in columns:
                action = QAction(col, loc_id_menu)
                action.setCheckable(True)
                loc_id_menu.addAction(action)
            update_loc_id_btn_text()

        def update_loc_id_btn_text():
            selected = [a.text() for a in loc_id_menu.actions() if a.isChecked()]
            if selected:
                loc_id_btn.setText(", ".join(selected))
            else:
                loc_id_btn.setText("Select")

        loc_id_menu.triggered.connect(update_loc_id_btn_text)

        def update_index_col_options():
            path = data_path_edit.text()
            if os.path.isfile(path):
                try:
                    ext = os.path.splitext(path)[1].lower()
                    if ext in [".csv", ".txt"]:
                        df = pd.read_csv(path, nrows=0, sep=None, engine="python")
                    elif ext in [".xls", ".xlsx"]:
                        df = pd.read_excel(path, nrows=0)
                    else:
                        QMessageBox.critical(
                            self,
                            "Unsupported File Type",
                            "Only CSV, TXT, XLS, and XLSX files are supported."
                        )
                        index_col_combo.clear()
                        index_col_combo.addItem("Date")
                        return
                    index_col_combo.clear()
                    index_col_combo.addItems(df.columns)
                    if index_col_combo.count() > 0:
                        index_col_combo.setCurrentIndex(0)
                    update_loc_id_menu(df.columns)
                except Exception:
                    index_col_combo.clear()
                    index_col_combo.addItem("Date")
            else:
                index_col_combo.clear()
                index_col_combo.addItem("Date")

        def update_name():
            if not name_edit.text() and data_path_edit.text():
                name_edit.setText(os.path.basename(data_path_edit.text().split('.')[0]))

        data_path_edit.textChanged.connect(update_name)
        data_path_edit.textChanged.connect(update_index_col_options)
        update_index_col_options()  # Initial call

        # Enable add button only if Data field is not empty
        def check_data_field():
            add_btn.setEnabled(bool(data_path_edit.text()))

        data_path_edit.textChanged.connect(check_data_field)
        check_data_field()  # Initial check

        self.datasets_area.addWidget(group_box)

        def add_dataset():
            "Add a new dataset to the DataManager"
            self.add_dataset(
                name=name_edit.text().strip(),
                data_file_path=data_path_edit.text().strip(),
                uncertainty_file_path=unc_path_edit.text().strip() or None,
                index_column=index_col_combo.currentText().strip(),
                location_ids=[a.text() for a in loc_id_menu.actions() if a.isChecked()],
                missing_value_label=missing_val_edit.text().strip()
            )

            add_btn.setIcon(QIcon(os.path.join("src", "resources", "icons", "minus-white.svg")))
            add_btn.setToolTip("Remove dataset")
            add_btn.clicked.disconnect()
            add_btn.clicked.connect(remove_dataset)
            self.add_dataset_row()

        def remove_dataset():
            "Remove the current dataset row"
            self.remove_dataset(name=name_edit.text().strip())
            group_box.setParent(None)
            group_box.deleteLater()

        add_btn.clicked.connect(add_dataset)

        self.dataset_rows.append({
            "data_path_edit": data_path_edit,
            "unc_path_edit": unc_path_edit,
            "update_index_col_options": update_index_col_options,
            "update_name": update_name
        })

    def browse_file(self, line_edit):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if file_path:
            line_edit.setText(file_path)

    def set_default_dataset_paths(self, data_path, unc_path):
        if self.dataset_rows:
            row = self.dataset_rows[-1]  # Set defaults for the most recent row
            row["data_path_edit"].setText(data_path)
            row["unc_path_edit"].setText(unc_path)
            row["update_index_col_options"]()
            row["update_name"]()

    def add_dataset(self,
                    name: str,
                    data_file_path: str,
                    uncertainty_file_path: Optional[str],
                    index_column: str,
                    location_ids: Optional[List[str]],
                    missing_value_label: str
                    ):
        """Add a new dataset to the DataManager"""
        loading_dialog = LoadingDialog("Loading dataset...", self)
        loading_dialog.show()
        QApplication.processEvents()  # Ensure dialog appears
        try:
            self.controller.main_controller.dataset_manager.add_dataset(
                name=name,
                data_file_path=data_file_path,
                uncertainty_file_path=uncertainty_file_path,
                index_column=index_column,
                location_ids=location_ids,
                missing_value_label=missing_value_label
            )
            self.parent.statusBar().showMessage(f"Dataset '{name}' added successfully.", 3000)
        except ValueError:
            QMessageBox.critical(self, "Error", f"Dataset with name '{name}' already exists.")
            return
        finally:
            loading_dialog.close()

    def remove_dataset(self, name: str):
        """Remove a dataset from the DataManager"""
        loading_dialog = LoadingDialog("Removing dataset...", self)
        loading_dialog.show()
        QApplication.processEvents()  # Ensure dialog appears
        try:
            self.controller.main_controller.dataset_manager.remove_dataset(name)
            self.parent.statusBar().showMessage(f"Dataset '{name}' removed.", 3000)
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        finally:
            loading_dialog.close()