from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QGroupBox, QSizePolicy
from PySide6.QtCore import Qt, Signal
from pandas import Timestamp, DatetimeIndex, DataFrame
from src.utils.esat_logger import get_logger


class DatasetSelectionWidget(QWidget):
    dataset_selected = Signal(str)

    def __init__(self, dataset_manager=None, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.dataset_manager = dataset_manager
        self.selected_dataset = None
        self.dataset_details_labels = {}
        self.logger = get_logger()

        self._setup_ui()
        self._connect_signals()
        self.update_dataset_dropdown()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

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
        self.selection_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        selection_layout = QVBoxLayout(self.selection_group)
        selection_layout.setContentsMargins(8, 8, 8, 8)
        selection_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

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
        if self.dataset_manager:
            self.dataset_manager.datasets_changed.connect(self.update_dataset_dropdown)
            self.dataset_manager.selected_dataset_changed.connect(self._on_selected_dataset_changed)
            self.dataset_manager.dataset_loaded.connect(self._on_selected_dataset_changed)

    def update_dataset_dropdown(self):
        self.dataset_dropdown.blockSignals(True)
        self.dataset_dropdown.clear()
        if self.dataset_manager and hasattr(self.dataset_manager, "get_names"):
            names = self.dataset_manager.get_names()
            self.dataset_dropdown.addItems(names)
            if names:
                # Set dropdown to match manager's selected dataset
                idx = names.index(self.dataset_manager.selected_dataset) if self.dataset_manager.selected_dataset in names else 0
                self.dataset_dropdown.setCurrentIndex(idx)
        self.dataset_dropdown.blockSignals(False)
        if self.dataset_dropdown.count() > 0:
            self._on_dataset_changed(self.dataset_dropdown.currentIndex())

    def _on_dataset_changed(self, idx):
        name = self.dataset_dropdown.currentText()
        if self.dataset_manager and name != self.dataset_manager.selected_dataset:
            self.dataset_manager.selected_dataset = name
        self.selected_dataset = name
        self.dataset_selected.emit(name)
        self.logger.info(f"[DatasetSelectionWidget]: Dataset selected: {name}, index: {idx}")
        self._update_details(name)

    def _on_selected_dataset_changed(self, name):
        # Update dropdown selection if needed
        names = [self.dataset_dropdown.itemText(i) for i in range(self.dataset_dropdown.count())]
        if name in names:
            idx = names.index(name)
            if self.dataset_dropdown.currentIndex() != idx:
                self.dataset_dropdown.setCurrentIndex(idx)
        self.selected_dataset = name
        self._update_details(name)

    def _update_details(self, dataset_name):
        dataset_manager = self.dataset_manager
        self.logger.info(f"[DatasetSelectionWidget]: Updating details for dataset: {dataset_name}")
        self.logger.info(f"[DatasetSelectionWidget]: Available datasets: {list(dataset_manager.loaded_datasets.keys()) if dataset_manager else 'N/A'}")
        dataset = None
        if dataset_manager:
            if dataset_name in dataset_manager.loaded_datasets.keys():
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

        # Remove rows that are empty or all NaN
        if input_data is not None and isinstance(input_data, DataFrame):
            input_data = input_data.dropna(how='all')

        if input_data is not None and hasattr(input_data, "index"):
            idx = input_data.index
            if isinstance(idx, int) or isinstance(idx, Timestamp) or isinstance(idx, DatetimeIndex):
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
        self.show()

    # def on_dataset_loaded(self, dataset_name):
    #     if len(self.dataset_manager.loaded_datasets) > 0:
    #         self.update_dataset_details(dataset_name)
