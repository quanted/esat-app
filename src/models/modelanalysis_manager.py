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
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"Exception in worker thread: {e}\n{traceback.format_exc()}")
            result = None
        self.finished.emit(result)


class ModelAnalysisManager(QObject):
    aggregationReady = Signal(object, object)
    featureMetricsReady = Signal(object)
    modelStatsReady = Signal(object)
    residualHistogramReady = Signal(object, object)
    estimatedVsObservedReady = Signal(object)
    estimateTimeseriesReady = Signal(object)
    factorProfileReady = Signal(object, object)
    allfactorProfileReady = Signal(object)
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
        self.plots = {}

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
        import logging, traceback
        logger = logging.getLogger(__name__)
        # Keep references to prevent garbage collection
        if not hasattr(self, '_threads'):
            self._threads = []
        self._threads.append((thread, worker))
        # Wrap the signal emission to unpack tuple if needed
        def emit_result(result):
            import logging, traceback
            logger = logging.getLogger(__name__)
            logger.info(f"Emitting signal '{getattr(signal, 'signal', repr(signal))}' with result type: {type(result)}")
            try:
                if hasattr(signal, 'emit'):
                    if isinstance(result, tuple):
                        signal.emit(*result)
                    else:
                        signal.emit(result)
                    logger.info(f"Signal '{getattr(signal, 'signal', repr(signal))}' emitted")
                else:
                    signal(result)
                    logger.info(f"Signal '{getattr(signal, 'signal', repr(signal))}' emitted")
            except Exception as e:
                logger.error(f"Error emitting signal: {e}\n{traceback.format_exc()}")
        worker.finished.connect(emit_result)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def run_aggregation(self):
        import logging, traceback
        logger = logging.getLogger(__name__)
        try:
            self._start_thread(self.analysis.aggregate_factors_for_plotting, self.aggregationReady)
        except Exception as e:
            logger.error(f"Exception in aggregate_factors_for_plotting: {e}\n{traceback.format_exc()}")
            return

    def run_analysis(self):
        import logging, traceback
        logger = logging.getLogger(__name__)
        try:
            self._start_thread(self.analysis.features_metrics, self.featureMetricsReady)
        except Exception as e:
            logger.error(f"Exception in features_metrics: {e}\n{traceback.format_exc()}")
            return
        try:
            self._start_thread(self.analysis.calculate_statistics, self.modelStatsReady)
        except Exception as e:
            logger.error(f"Exception in calculate_statistics: {e}\n{traceback.format_exc()}")
            return

    def run_all(self):
        import logging, traceback
        logger = logging.getLogger(__name__)
        try:
            self.run()
        except Exception as e:
            logger.error(f"Exception in run(): {e}\n{traceback.format_exc()}")
            return
        # Connect aggregationReady to the next step before running aggregation
        self.aggregationReady.connect(self.on_aggregation_finished)
        try:
            self.run_aggregation()
        except Exception as e:
            logger.error(f"Exception in run_aggregation(): {e}\n{traceback.format_exc()}")
            return

    def on_aggregation_finished(self, *args, **kwargs):
        import logging, traceback
        logger = logging.getLogger(__name__)
        # Disconnect to avoid duplicate calls if run_all is called again
        try:
            self.aggregationReady.disconnect(self.on_aggregation_finished)
        except Exception:
            pass
        try:
            self.run_analysis()
        except Exception as e:
            logger.error(f"Exception in run_analysis(): {e}\n{traceback.format_exc()}")
            return
        try:
            self.run_residual_histogram()
        except Exception as e:
            logger.error(f"Exception in run_residual_histogram(): {e}\n{traceback.format_exc()}")
            return
        try:
            self.run_est_obs()
        except Exception as e:
            logger.error(f"Exception in run_est_obs(): {e}\n{traceback.format_exc()}")
            return
        try:
            self.run_est_ts()
        except Exception as e:
            logger.error(f"Exception in run_est_ts(): {e}\n{traceback.format_exc()}")
            return
        try:
            self.run_factor_profile()
        except Exception as e:
            logger.error(f"Exception in run_factor_profile(): {e}\n{traceback.format_exc()}")
            return
        try:
            self.run_all_factor_profile()
        except Exception as e:
            logger.error(f"Exception in run_all_factor_profile(): {e}\n{traceback.format_exc()}")
            return
        try:
            self.run_factors_3d()
        except Exception as e:
            logger.error(f"Exception in run_factors_3d(): {e}\n{traceback.format_exc()}")
            return
        try:
            self.run_factor_fingerprints()
        except Exception as e:
            logger.error(f"Exception in run_factor_fingerprints(): {e}\n{traceback.format_exc()}")
            return
        try:
            self.run_factor_contributions()
        except Exception as e:
            logger.error(f"Exception in run_factor_contributions(): {e}\n{traceback.format_exc()}")
            return
        try:
            self.run_g_space()
        except Exception as e:
            logger.error(f"Exception in run_g_space(): {e}\n{traceback.format_exc()}")
            return

    def run_residual_histogram(self, feature_idx: int = 0):
        def fn():
            return self.analysis.plot_residual_histogram(feature_idx=feature_idx, show=False)
        def handle_result(result):
            self.plots[f"residual_histogram_{feature_idx}"] = result
            self.residualHistogramReady.emit(*result)
        self._start_thread(fn, handle_result)

    def run_est_obs(self, feature_idx: int = 0):
        def fn():
            result = self.analysis.plot_estimated_observed(feature_idx=feature_idx, show=False)
            return result
        def handle_result(result):
            if result is None:
                logger.warning("plot_estimated_vs_observed returned None")
            self.plots[f"estimated_vs_observed_{feature_idx}"] = result
            self.estimatedVsObservedReady.emit(result)
        self._start_thread(fn, handle_result)

    def run_est_ts(self, feature_idx: int = 0):
        def fn():
            return self.analysis.plot_estimated_timeseries(feature_idx=feature_idx, show=False)
        def handle_result(result):
            self.plots[f"estimate_timeseries_{feature_idx}"] = result
            self.estimateTimeseriesReady.emit(result)
        self._start_thread(fn, handle_result)

    def run_factor_profile(self, factor_idx: int = 1):
        print(f"Running factor profile for factor index: {factor_idx}")
        def fn():
            return self.analysis.plot_factor_profile(factor_idx=factor_idx, show=False)
        def handle_result(result):
            self.plots[f"factor_profile_{factor_idx}"] = result
            self.factorProfileReady.emit(*(result if result is not None else (None, None)))
        self._start_thread(fn, handle_result)

    def run_all_factor_profile(self):
        print(f"Running all factor profile plot")
        def fn():
            return self.analysis.plot_all_factors(show=False)
        def handle_result(result):
            self.plots[f"all_factor_profiles"] = result
            self.allfactorProfileReady.emit(result)
        self._start_thread(fn, handle_result)

    def run_factors_3d(self):
        def fn():
            return self.analysis.plot_all_factors_3d(show=False)
        def handle_result(result):
            self.plots["factors_3d"] = result
            self.factors3dReady.emit(result)
        self._start_thread(fn, handle_result)

    def run_factor_fingerprints(self):
        def fn():
            return self.analysis.plot_factor_fingerprints(show=False)
        def handle_result(result):
            self.plots["factor_fingerprints"] = result
            self.factorFingerprintsReady.emit(result)
        self._start_thread(fn, handle_result)

    def run_factor_contributions(self, feature_idx: int = 0, contribution_threshold: float = 0.05):
        def fn():
            return self.analysis.plot_factor_contributions(feature_idx=feature_idx,
                                                           contribution_threshold=contribution_threshold,
                                                           show=False)
        def handle_result(result):
            self.plots[f"factor_contributions_{feature_idx}"] = result
            self.factorContributionsReady.emit(*result)
        self._start_thread(fn, handle_result)

    def run_g_space(self, factor_1_idx: int = 1, factor_2_idx: int = 2):
        factor_1_idx = factor_1_idx if factor_1_idx is not None else 1
        factor_2_idx = factor_2_idx if factor_2_idx is not None else 2
        def fn():
            return self.analysis.plot_g_space(factor_1=factor_1_idx, factor_2=factor_2_idx, show=False)
        def handle_result(result):
            self.plots[f"g_space_{factor_1_idx}_{factor_2_idx}"] = result
            self.gSpaceReady.emit(result)
        self._start_thread(fn, handle_result)
