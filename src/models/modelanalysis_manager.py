import logging
from PySide6.QtCore import QObject, Signal, Slot, QThread

from esat.data.analysis import ModelAnalysis


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Worker(QObject):
    finished = Signal(object)
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        result = self.fn(*self.args, **self.kwargs)
        self.finished.emit(result)


class ModelAnalysisManager(QObject):
    aggregationReady = Signal(object, object)
    featureMetricsReady = Signal(object)
    modelStatsReady = Signal(object)
    residualHistogramReady = Signal(object, object)
    estimatedVsObservedReady = Signal(object)
    estimateTimeseriesReady = Signal(object)
    factorProfileReady = Signal(object, object)
    factors3dReady = Signal(object)
    factorFingerprintsReady = Signal(object)
    factorContributionsReady = Signal(object, object)
    gSpaceReady = Signal(object)

    def __init__(self, sa, data_handler, model_idx: int = -1, parent=None):
        super().__init__(parent)
        self.sa = sa
        self.data_handler = data_handler
        self.model_idx = model_idx
        self.analysis = None

    def cleanup(self):
        """Cleanup method to release resources."""
        self.sa = None
        self.data_handler = None
        self.analysis = None
        logger.info("ModelAnalysisManager cleaned up.")

    def run(self):
        self.analysis = ModelAnalysis(datahandler=self.data_handler,
                                     model=self.sa,
                                     selected_model=self.model_idx)

    def _start_thread(self, fn, signal, *args, **kwargs):
        thread = QThread()
        worker = Worker(fn, *args, **kwargs)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(signal)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def run_analysis(self):
        self._start_thread(self.analysis.aggregate_factors_for_plotting, self.aggregationReady)
        self._start_thread(self.analysis.features_metrics, self.featureMetricsReady)
        self._start_thread(self.analysis.calculate_statistics, self.modelStatsReady)

    def run_residual_histogram(self, feature_idx: int = 0):
        def fn():
            return self.analysis.plot_residual_histogram(feature_idx=feature_idx, show=False)
        self._start_thread(fn, lambda result: self.residualHistogramReady.emit(*result))

    def run_est_obs(self, feature_idx: int = 0):
        def fn():
            return self.analysis.plot_estimated_observed(feature_idx=feature_idx, show=False)
        self._start_thread(fn, self.estimatedVsObservedReady)

    def run_est_ts(self, feature_idx: int = 0):
        def fn():
            return self.analysis.plot_estimated_timeseries(feature_idx=feature_idx, show=False)
        self._start_thread(fn, self.estimateTimeseriesReady)

    def run_factor_profile(self, factor_idx: int = 0):
        def fn():
            return self.analysis.plot_factor_profile(factor_idx=factor_idx, show=False)
        self._start_thread(fn, lambda result: self.factorProfileReady.emit(*result))

    def run_factors_3d(self):
        def fn():
            return self.analysis.plot_all_factors_3d(show=False)
        self._start_thread(fn, self.factors3dReady)

    def run_factor_fingerprints(self):
        def fn():
            return self.analysis.plot_factor_fingerprints(show=False)
        self._start_thread(fn, self.factorFingerprintsReady)

    def run_factor_contributions(self, feature_idx: int = 0, contribution_threshold: float = 0.1):
        def fn():
            return self.analysis.plot_factor_contributions(feature_idx=feature_idx,
                                                           contribution_threshold=contribution_threshold,
                                                           show=False)
        self._start_thread(fn, lambda result: self.factorContributionsReady.emit(*result))

    def run_g_space(self, factor_1_idx: int = 0, factor_2_idx: int = 1):
        def fn():
            return self.analysis.plot_g_space(factor_1_idx=factor_1_idx, factor_2_idx=factor_2_idx, show=False)
        self._start_thread(fn, self.gSpaceReady)