import logging
import traceback
from PySide6.QtCore import QObject, Signal, Slot

from esat.model.sa import SA
from esat.data.analysis import BatchAnalysis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BatchAnalysisManager(QObject):
    finished = Signal(object)  # Emitted with results when done
    error = Signal(Exception)  # Emitted with exception on error

    def __init__(self, dataset_name, batch_sa, data_handler, parent=None):
        super().__init__(parent)
        self.name = dataset_name
        self.batch_sa = batch_sa
        self.data_handler = data_handler
        self.analysis = None  # Will hold the esat.data.BatchAnalysis instance
        self.loss_plot = None
        self.loss_distribution_plot = None
        self.temporal_residual_plot = None

    @Slot()
    def run_analysis(self):
        logger.info(f"BatchAnalysisManager for {self.name} instance started.")
        try:
            self.analysis = BatchAnalysis(self.batch_sa, self.data_handler)
            self.loss_plot = self.analysis.plot_loss(show=False)
            self.loss_distribution_plot = self.analysis.plot_loss_distribution(show=False)
            self.temporal_residual_plot = self.analysis.plot_temporal_residuals(feature_idx=0, show=False)
            self.finished.emit(self.analysis)
        except Exception as e:
            logger.error(traceback.format_exc())
            self.error.emit(e)