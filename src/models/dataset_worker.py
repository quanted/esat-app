import logging

from PySide6.QtCore import QObject, Signal, Slot, QThread

logger = logging.getLogger(__name__)


class DatasetLoaderWorker(QObject):
    finished = Signal(str, object)
    error = Signal(str, Exception)

    def __init__(self, dataset, datahandler_cls):
        super().__init__()
        self.dataset = dataset
        self.datahandler_cls = datahandler_cls

    @Slot()
    def run(self):
        logger.info(f"Worker started for dataset {self.dataset.name} in thread {QThread.currentThread()}")
        try:
            dh = self.datahandler_cls(
                input_path=self.dataset.data_file_path,
                uncertainty_path=self.dataset.uncertainty_file_path,
                index_col=self.dataset.index_column,
                loc_cols=self.dataset.location_ids,
            )
            self.finished.emit(self.dataset.name, dh)
        except Exception as e:
            self.error.emit(self.dataset.name, e)


class PlotDataUncertaintyWorker(QObject):
    finished = Signal(str, object)  # Feature name, plotly figure
    error = Signal(str, Exception)

    def __init__(self, datahandler, feature_name):
        super().__init__()
        self.datahandler = datahandler
        self.feature_name = feature_name

    @Slot()
    def run(self):
        try:
            dh = self.datahandler
            feature_idx = dh.input_data.columns.get_loc(self.feature_name)
            fig = dh.plot_data_uncertainty(show=False, feature_idx=feature_idx, include_menu=False)
            self.finished.emit(self.feature_name, fig)
        except Exception as e:
            self.error.emit(self.feature_name, e)


class PlotFeatureTSWorker(QObject):
    finished = Signal(str, object)  # Feature name, plotly figure
    error = Signal(str, Exception)

    def __init__(self, datahandler, feature_name):
        super().__init__()
        self.datahandler = datahandler
        self.feature_name = feature_name

    @Slot()
    def run(self):
        try:
            dh = self.datahandler
            fig = dh.plot_feature_timeseries(show=False, feature_selection=self.feature_name)
            self.finished.emit(self.feature_name, fig)
        except Exception as e:
            self.error.emit(self.feature_name, e)


class PlotFeatureDataWorker(QObject):
    finished = Signal(str, object)  # Feature name, plotly figure
    error = Signal(str, Exception)

    def __init__(self, datahandler, x_feature, y_feature):
        super().__init__()
        self.datahandler = datahandler
        self.x_feature = x_feature
        self.y_feature = y_feature

    @Slot()
    def run(self):
        try:
            fig = self.datahandler.plot_feature_data(show=False, x_idx=self.x_feature, y_idx=self.y_feature)
            self.finished.emit(f"{self.x_feature}-{self.y_feature}", fig)
        except Exception as e:
            self.error.emit(f"{self.x_feature}-{self.y_feature}", e)


class PlotFeatureCorrelationHeatmapWorker(QObject):
    finished = Signal(str, object)  # plotly figure
    error = Signal(str, Exception)

    def __init__(self, datahandler, method):
        super().__init__()
        self.datahandler = datahandler
        self.method = method

    @Slot()
    def run(self):
        try:
            fig = self.datahandler.plot_feature_correlation_heatmap(show=False, method=self.method)
            self.finished.emit(f"CorHeatmap {self.method}", fig)
        except Exception as e:
            self.error.emit(f"CorHeatmap {self.method}", e)

class PlotSuperimposedHistogramsWorker(QObject):
    finished = Signal(str, object)  # Feature name, plotly figure
    error = Signal(str, Exception)

    def __init__(self, datahandler):
        super().__init__()
        self.datahandler = datahandler

    @Slot()
    def run(self):
        try:
            fig = self.datahandler.plot_superimposed_histograms(show=False)
            self.finished.emit("SuperHistogram", fig)
        except Exception as e:
            self.error.emit("SuperHistogram", e)


class Plot2DHistogramWorker(QObject):
    finished = Signal(str, object)
    error = Signal(str, Exception)

    def __init__(self, datahandler, feature_x, feature_y):
        super().__init__()
        self.datahandler = datahandler
        self.feature_x = feature_x
        self.feature_y = feature_y

    @Slot()
    def run(self):
        try:
            fig = self.datahandler.plot_2d_histogram(show=False, x_col=self.feature_x, y_col=self.feature_y)
            self.finished.emit(f"{self.feature_x}-{self.feature_y}", fig)
        except Exception as e:
            self.error.emit(f"{self.feature_x}-{self.feature_y}", e)


class PlotRidgelineWorker(QObject):
    finished = Signal(str, object)  # Feature name, plotly figure
    error = Signal(str, Exception)

    def __init__(self, datahandler):
        super().__init__()
        self.datahandler = datahandler

    @Slot()
    def run(self):
        try:
            fig = self.datahandler.plot_ridgeline(show=False)
            self.finished.emit("Ridgeline", fig)
        except Exception as e:
            self.error.emit("Ridgeline", e)