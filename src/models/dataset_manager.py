import uuid
import logging
from typing import List, Optional

from PySide6.QtCore import QObject, Signal, QThread

from esat.data.datahandler import DataHandler

from src.models.dataset import Dataset
from src.models.dataset_worker import DatasetLoaderWorker, PlotDataUncertaintyWorker, PlotFeatureTSWorker, \
    PlotFeatureDataWorker, PlotFeatureCorrelationHeatmapWorker, PlotSuperimposedHistogramsWorker, Plot2DHistogramWorker, \
    PlotRidgelineWorker


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

VERBOSE = True


class DatasetManager(QObject):
    datasets_changed = Signal()
    dataset_loaded = Signal(str)                    # Dataset name

    # Plot signals
    uncertainty_plot_ready = Signal(str, object)
    ts_plot_ready = Signal(str, object)
    plot_feature_data_ready = Signal(str, object)
    plot_correlation_heatmap_ready = Signal(str, object)
    plot_superimposed_histograms_ready = Signal(str, object)
    plot_2d_histogram_ready = Signal(str, object)
    plot_ridgeline_ready = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._instance_id = uuid.uuid4()
        if VERBOSE:
            logger.info(f"DatasetManager instance {self._instance_id} created")

        self.datasets: List[Dataset] = []

        self.loaded_datasets = {}
        self.dataset_feature_categories = {}  # Track feature categories for each dataset
        self.locations = {}

        self.threads = {}
        self.workers = {}
        self.loading_datasets = set()  # Track currently loading datasets

    def add_dataset(self,
            name: str,
            data_file_path: str,
            uncertainty_file_path: Optional[str],
            index_column: str,
            location_ids: Optional[List[str]],
            missing_value_label: str,
            latitude: Optional[float] = None,
            longitude: Optional[float] = None,
            location_label: Optional[str] = None
            ):
        if name in self.datasets:
            raise ValueError(f"Dataset with name {name} already exists")
        else:
            self.datasets.append(
                Dataset(
                    name=name,
                    data_file_path=data_file_path,
                    uncertainty_file_path=uncertainty_file_path,
                    index_column=index_column,
                    location_ids=location_ids,
                    missing_value_label=missing_value_label,
                    latitude=latitude,
                    longitude=longitude,
                    location_label=location_label
                )
            )
            if VERBOSE:
                logger.info(f"Added new dataset: {name}, data_file_path: {data_file_path}, "
                            f"uncertainty_file_path: {uncertainty_file_path}, index_column: {index_column}, "
                            f"location_ids: {location_ids}, missing_value_label: {missing_value_label}, "
                            f"latitude: {latitude}, longitude: {longitude}, location_label: {location_label}")
            self.load(name)  # Automatically load the dataset after adding
            self.datasets_changed.emit()

    def remove_dataset(self, name: str):
        for ds in self.datasets:
            if ds.name == name:
                self.datasets.remove(ds)
                self.datasets_changed.emit()
                if VERBOSE:
                    logger.info(f"Removed dataset {name}")
                return
        raise ValueError(f"Dataset with name {name} not found")

    def get_datasets(self) -> List[Dataset]:
        return self.datasets

    def get_dataset_by_name(self, name: str) -> Dataset:
        for ds in self.datasets:
            if ds.name == name:
                return ds
        raise ValueError(f"Dataset with name {name} not found")

    def get_names(self) -> List[str]:
        return [ds.name for ds in self.datasets]

    def _start_worker_thread(self, worker_cls, worker_args, finished_handler, error_handler, key):
        thread = QThread()
        worker = worker_cls(*worker_args)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(finished_handler)
        worker.error.connect(error_handler)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self.threads[key] = thread
        self.workers[key] = worker
        thread.start()

    def load(self, name: str):
        if name in self.loaded_datasets or name in self.loading_datasets:
            if VERBOSE:
                logger.info(f"Dataset {name} is already loaded or loading")
            if name in self.loaded_datasets:
                self.dataset_loaded.emit(name)
            return
        self.loading_datasets.add(name)
        dataset = self.get_dataset_by_name(name)
        self._start_worker_thread(
            worker_cls=DatasetLoaderWorker,
            worker_args=(dataset, DataHandler),
            finished_handler=self.on_load_finished,
            error_handler=self.on_load_error,
            key=name
        )

    def on_load_finished(self, name, dh):
        if VERBOSE:
            logger.info(f"on_load_finished for {name} in instance {self._instance_id}")
        self.loaded_datasets[name] = dh
        self.loading_datasets.discard(name)
        if VERBOSE:
            logger.info(f"Loaded dataset {name}")
        self.dataset_loaded.emit(name)

    def on_load_error(self, name, error):
        logger.error(f"on_load_error called for {name} in thread {QThread.currentThread()}: {error}")
        self.loading_datasets.discard(name)  # Remove from loading set

    def plot_data_uncertainty(self, dataset_name: str, feature_name: str):
        if dataset_name not in self.loaded_datasets:
            if VERBOSE:
                logger.warning(f"Dataset {dataset_name} not loaded")
            return
        dataset = self.loaded_datasets[dataset_name]
        self._start_worker_thread(
            worker_cls=PlotDataUncertaintyWorker,
            worker_args=(dataset, feature_name),
            finished_handler=self.on_plot_finished,
            error_handler=self.on_plot_error,
            key=f"plot_{feature_name}"
        )

    def on_plot_finished(self, name, fig):
        if VERBOSE:
            logger.info(f"Scatter plot ready for {name}")
        self.uncertainty_plot_ready.emit(name, fig)

    def on_plot_error(self, name, error):
        logger.error(f"Scatter plot error for {name}: {error}")

    def plot_feature_timeseries(self, dataset_name: str, feature_name: str):
        if dataset_name not in self.loaded_datasets:
            if VERBOSE:
                logger.warning(f"Dataset {dataset_name} not loaded")
            return
        dataset = self.loaded_datasets[dataset_name]
        self._start_worker_thread(
            worker_cls=PlotFeatureTSWorker,
            worker_args=(dataset, feature_name),
            finished_handler=self.on_ts_plot_finished,
            error_handler=self.on_ts_plot_error,
            key=f"ts_plot_{feature_name}"
        )

    def on_ts_plot_finished(self, name, fig):
        if VERBOSE:
            logger.info(f"Time series plot ready for {name}")
        self.ts_plot_ready.emit(name, fig)

    def on_ts_plot_error(self, name, error):
        logger.error(f"Time series plot error for {name}: {error}")

    def set_feature_category(self, dataset_name: str, feature_name :str, category: str):
        if dataset_name not in self.dataset_feature_categories:
            self.dataset_feature_categories[dataset_name] = {}
        self.dataset_feature_categories[dataset_name][feature_name] = category
        if VERBOSE:
            logger.info(f"Set Feature: {feature_name} category to: {category} for dataset: {dataset_name}")

    def plot_feature_data(self, dataset_name: str, x_feature: str, y_feature: str):
        if dataset_name not in self.loaded_datasets:
            if VERBOSE:
                logger.warning(f"Dataset {dataset_name} not loaded")
            return
        if VERBOSE:
            logger.info(f"Plotting feature data for {dataset_name} with x: {x_feature}, y: {y_feature}")
        dataset = self.loaded_datasets[dataset_name]
        if x_feature not in dataset.input_data.columns or y_feature not in dataset.input_data.columns:
            logger.error(f"Features {x_feature} or {y_feature} not found in dataset {dataset_name}")
            return
        x_idx = dataset.input_data.columns.get_loc(x_feature)
        y_idx = dataset.input_data.columns.get_loc(y_feature)
        self._start_worker_thread(
            worker_cls=PlotFeatureDataWorker,
            worker_args=(dataset, x_idx, y_idx),
            finished_handler=self.on_feature_data_finished,
            error_handler=self.on_feature_data_error,
            key=f"feature_data_{f"{x_feature}-{y_feature}"}"
        )

    def on_feature_data_finished(self, name, fig):
        if VERBOSE:
            logger.info(f"Feature data plot ready for {name}")
        self.plot_feature_data_ready.emit(name, fig)

    def on_feature_data_error(self, name, error):
        logger.error(f"Feature data plot error for {name}: {error}")

    def plot_correlation_heatmap(self, dataset_name: str, method: str):
        if dataset_name not in self.loaded_datasets:
            if VERBOSE:
                logger.warning(f"Dataset {dataset_name} not loaded")
            return
        dataset = self.loaded_datasets[dataset_name]
        self._start_worker_thread(
            worker_cls=PlotFeatureCorrelationHeatmapWorker,
            worker_args=(dataset, method),
            finished_handler=self.on_correlation_heatmap_finished,
            error_handler=self.on_correlation_heatmap_error,
            key=f"correlation_heatmap_{method}"
        )

    def on_correlation_heatmap_finished(self, name, fig):
        if VERBOSE:
            logger.info(f"Correlation heatmap ready for {name}")
        self.plot_correlation_heatmap_ready.emit(name, fig)

    def on_correlation_heatmap_error(self, name, error):
        logger.error(f"Correlation heatmap error for {name}: {error}")

    def plot_superimposed_histograms(self, dataset_name: str):
        if dataset_name not in self.loaded_datasets:
            if VERBOSE:
                logger.warning(f"Dataset {dataset_name} not loaded")
            return
        dataset = self.loaded_datasets[dataset_name]
        self._start_worker_thread(
            worker_cls=PlotSuperimposedHistogramsWorker,
            worker_args=(dataset,),
            finished_handler=self.on_superimposed_histograms_finished,
            error_handler=self.on_superimposed_histograms_error,
            key=f"superimposed_histograms"
        )

    def on_superimposed_histograms_finished(self, name, fig):
        if VERBOSE:
            logger.info(f"Superimposed histograms ready for {name}")
        self.plot_superimposed_histograms_ready.emit(name, fig)

    def on_superimposed_histograms_error(self, name, error):
        logger.error(f"Superimposed histograms error for {name}: {error}")

    def plot_2d_histogram(self, dataset_name: str, feature_x: str, feature_y: str):
        if dataset_name not in self.loaded_datasets:
            if VERBOSE:
                logger.warning(f"Dataset {dataset_name} not loaded")
            return
        dataset = self.loaded_datasets[dataset_name]
        if VERBOSE:
            logger.info(f"Plotting 2D histogram for {dataset_name} with x: {feature_x}, y: {feature_y}")
        self._start_worker_thread(
            worker_cls=Plot2DHistogramWorker,
            worker_args=(dataset, feature_x, feature_y),
            finished_handler=self.on_2d_histogram_finished,
            error_handler=self.on_2d_histogram_error,
            key=f"2d_histogram_{feature_x}-{feature_y}"
        )

    def on_2d_histogram_finished(self, name, fig):
        if VERBOSE:
            logger.info(f"2D histogram ready for {name}")
        self.plot_2d_histogram_ready.emit(name, fig)

    def on_2d_histogram_error(self, name, error):
        logger.error(f"2D histogram error for {name}: {error}")

    def plot_ridgeline(self, dataset_name: str):
        if dataset_name not in self.loaded_datasets:
            if VERBOSE:
                logger.warning(f"Dataset {dataset_name} not loaded")
            return
        dataset = self.loaded_datasets[dataset_name]
        self._start_worker_thread(
            worker_cls=PlotRidgelineWorker,
            worker_args=(dataset,),
            finished_handler=self.on_ridgeline_finished,
            error_handler=self.on_ridgeline_error,
            key=f"ridgeline"
        )

    def on_ridgeline_finished(self, name, fig):
        if VERBOSE:
            logger.info(f"Ridgeline plot ready for {name}")
        self.plot_ridgeline_ready.emit(name, fig)

    def on_ridgeline_error(self, name, error):
        logger.error(f"Ridgeline plot error for {name}: {error}")

    def preprocess_dataset(self, dataset_name: str):
        if dataset_name not in self.loaded_datasets:
            if VERBOSE:
                logger.warning(f"Dataset {dataset_name} not loaded")
            return None, None
        dataset = self.loaded_datasets[dataset_name]
        if VERBOSE:
            logger.info(f"Preprocessing dataset {dataset_name}")
        for feature, category in self.dataset_feature_categories.get(dataset_name, {}).items():
            dataset.set_category(feature, category)
        # Implement additional preprocessing steps here as needed
        if VERBOSE:
            logger.info(f"Preprocessing completed for dataset {dataset_name}")
        return dataset.get_data()