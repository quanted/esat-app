from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QGroupBox, QSizePolicy
from PySide6.QtCore import Qt, Signal
import pandas as pd


class DatasetSelectionWidget(QWidget):
    dataset_selected = Signal(str)

    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.selected_dataset = None
        self.dataset_details_labels = {}

        self._setup_ui()
        self._connect_signals()
        self.update_dataset_dropdown()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)

        # Single group box for dataset selection and details
        self.selection_group = QGroupBox("Dataset Selection")
        self.selection_group.setStyleSheet("""
            QGroupBox {
                font-size: 12px;
            }
            QLabel, QComboBox {
                font-size: 12px;
            }
        """)
        self.selection_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        selection_layout = QVBoxLayout(self.selection_group)
        selection_layout.setContentsMargins(8, 8, 8, 8)
        selection_layout.setAlignment(Qt.AlignTop)

        # Add dropdown without label
        self.dataset_dropdown = QComboBox()
        selection_layout.addWidget(self.dataset_dropdown)

        # Add dataset details below dropdown
        for key in ["Samples", "Features", "Date/Index Range", "Location"]:
            label = QLabel(f"{key}:")
            font = label.font()
            font.setBold(True)
            font.setPointSize(10)
            label.setFont(font)
            value = QLabel("-")
            value.setWordWrap(True)
            selection_layout.addWidget(label)
            selection_layout.addWidget(value)
            self.dataset_details_labels[key] = value

        layout.addWidget(self.selection_group)

    def _connect_signals(self):
        self.dataset_dropdown.currentIndexChanged.connect(self._on_dataset_changed)
        dataset_manager = self._get_dataset_manager()
        if dataset_manager:
            dataset_manager.datasets_changed.connect(self.update_dataset_dropdown)
            dataset_manager.dataset_loaded.connect(self.on_dataset_loaded)

    def _get_dataset_manager(self):
        if self.controller and hasattr(self.controller, "main_controller"):
            return getattr(self.controller.main_controller, "dataset_manager", None)
        return None

    def update_dataset_dropdown(self):
        self.dataset_dropdown.blockSignals(True)
        self.dataset_dropdown.clear()
        dataset_manager = self._get_dataset_manager()
        if dataset_manager and hasattr(dataset_manager, "get_names"):
            names = dataset_manager.get_names()
            self.dataset_dropdown.addItems(names)
            if names:
                self.dataset_dropdown.setCurrentIndex(0)
        self.dataset_dropdown.blockSignals(False)
        if self.dataset_dropdown.count() > 0:
            self._on_dataset_changed(0)

    def _on_dataset_changed(self, idx):
        name = self.dataset_dropdown.currentText()
        self.selected_dataset = name
        self.update_dataset_details(name)
        self.dataset_selected.emit(name)

    def update_dataset_details(self, dataset_name):
        dataset_manager = self._get_dataset_manager()
        dataset = None
        if dataset_manager:
            dataset = dataset_manager.loaded_datasets.get(dataset_name)
        if not dataset:
            for v in self.dataset_details_labels.values():
                v.setText("-")
            return

        files = [getattr(dataset, "input_path", "N/A"), getattr(dataset, "uncertainty_path", "N/A")]
        n_samples = getattr(dataset, "input_data", None)
        n_samples = n_samples.shape[0] if n_samples is not None else "N/A"
        n_features = getattr(dataset, "input_data", None)
        n_features = n_features.shape[1] if n_features is not None else "N/A"
        input_data = getattr(dataset, "input_data", None)
        if input_data is not None and hasattr(input_data, "index"):
            idx = input_data.index
            if isinstance(idx, int) or isinstance(idx, pd.Timestamp) or isinstance(idx, pd.DatetimeIndex):
                if hasattr(idx, "min") and hasattr(idx, "max"):
                    date_range = f"{idx.min()} - {idx.max()}"
                else:
                    date_range = "N/A"
            else:
                date_range = f"{idx[0]} - {idx[-1]}"
        else:
            date_range = "N/A"
        location = getattr(dataset, "loc_cols", [])
        location = location if location else "N/A"

        # self.dataset_details_labels["Files"].setText("\n".join(map(str, files)))
        self.dataset_details_labels["Samples"].setText(str(n_samples))
        self.dataset_details_labels["Features"].setText(str(n_features))
        self.dataset_details_labels["Date/Index Range"].setText(str(date_range))
        self.dataset_details_labels["Location"].setText(str(location))

    def on_dataset_loaded(self, dataset_name):
        if dataset_name == self.dataset_dropdown.currentText():
            self.update_dataset_details(dataset_name)