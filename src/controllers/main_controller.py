import logging

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox
from PySide6.QtCore import QThread, Signal

from src.views.main_view import MainView
from src.controllers import ProjectController, DataController, ModelController
from src.models import DatasetManager, BatchSAManager, BatchAnalysisManager, ModelAnalysisManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class MainController(QMainWindow):
    batchsa_finished = Signal(str)
    batchsa_canceled = Signal()
    batchanalysis_finished = Signal(str)

    def __init__(self, parent=None, webviews=None):
        super().__init__(parent)
        self.setWindowTitle("ESAT")
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.main_view = MainView(self)
        self.stack.addWidget(self.main_view)

        self.webviews = webviews if webviews is not None else []
        self.dataset_manager = DatasetManager(self)
        self.modelanalysis_manager = None

        self.project_controller = ProjectController(self)
        self.data_controller = DataController(self, webviews=self.webviews)
        self.model_controller = ModelController(self, webviews=self.webviews)

        self.completed_batches = {}
        self.batch_analysis_dict = {}

    @staticmethod
    def global_cleanup():
        """Perform global cleanup tasks."""
        logger.info("Performing global cleanup tasks.")
        # Clean up batch thread
        if hasattr(MainController, "_batch_thread"):
            thread = MainController._batch_thread
            if thread and thread.isRunning():
                logger.info("Stopping batch thread.")
                thread.quit()
                thread.wait()
        # Clean up batch analysis thread
        if hasattr(MainController, "_batch_analysis_thread"):
            thread = MainController._batch_analysis_thread
            if thread and thread.isRunning():
                logger.info("Stopping batch analysis thread.")
                thread.quit()
                thread.wait()

        # Clean up controllers
        for ctrl_attr in ["project_controller", "data_controller", "model_controller"]:
            ctrl = getattr(MainController, ctrl_attr, None)
            if ctrl and hasattr(ctrl, "cleanup"):
                logger.info(f"Cleaning up {ctrl_attr}.")
                ctrl.cleanup()
        # Clean up dataset manager
        if hasattr(MainController, "dataset_manager"):
            logger.info("Cleaning up DatasetManager.")
            MainController.dataset_manager.cleanup()

    def run_batch(self, dataset, factors, models, method, max_iter, seed, init_method, init_norm, converge_delta, converge_n, progress_callback):
        """Run batch analysis with the given parameters."""
        V, U = self.dataset_manager.preprocess_dataset(dataset)
        if V is None or U is None:
            raise ValueError("Invalid dataset provided. Ensure the dataset is loaded correctly.")
        # Create a new BatchSAManager and QThread
        batchsa_manager = BatchSAManager(dataset)
        batchsa_manager.setup(V, U, factors, models, method, seed, max_iter,
                              init_method, init_norm, converge_delta, converge_n, progress_callback)
        thread = QThread(self)
        batchsa_manager.moveToThread(thread)

        # Connect signals/slots
        thread.started.connect(batchsa_manager.start_batch_sa_in_thread)
        batchsa_manager.finished.connect(thread.quit)
        batchsa_manager.finished.connect(batchsa_manager.deleteLater)
        thread.finished.connect(thread.deleteLater)
        batchsa_manager.finished.connect(self.on_batchsa_finished)

        # Start the thread
        thread.start()

        # Store references to prevent garbage collection
        self._batch_thread = thread
        self._batch_manager = batchsa_manager
        return batchsa_manager

    def handle_batch_error(self, exception):
        logger.error(f"Batch processing error: {exception}", exc_info=True)
        QMessageBox.critical(self, "Batch Error", f"An error occurred during batch processing:\n{exception}")

    def cancel_batch(self):
        """Request cancellation of the running batch process."""
        if hasattr(self, "_batch_manager") and self._batch_manager is not None:
            self._batch_manager.cancel()  # Set cancel flag in worker
        if hasattr(self, "_batch_thread") and self._batch_thread is not None:
            self._batch_thread.quit()  # Ask thread to exit event loop
            self._batch_thread.wait()  # Optionally wait for thread to finish
        self.batchsa_canceled.emit()  # Emit cancellation signal

    def on_batchsa_finished(self):
        batchsa_manager = self._batch_manager
        self.completed_batches[batchsa_manager.dataset_name] = batchsa_manager
        logger.info(f"BatchSAManager {batchsa_manager.id} instance saved on finish. Dataset: {batchsa_manager.dataset_name}")
        self.batchsa_finished.emit(batchsa_manager.dataset_name)

    def run_batch_analysis(self, dataset_name):
        """Run batch analysis for the given dataset."""
        if dataset_name not in self.completed_batches:
            raise ValueError(f"No completed batch found for dataset: {dataset_name}. Available datasets: {list(self.completed_batches.keys())}")
        batchsa = self.completed_batches[dataset_name].batch_sa

        if dataset_name not in self.dataset_manager.loaded_datasets:
            raise ValueError(f"Dataset '{dataset_name}' is not loaded.")
        data_handler = self.dataset_manager.loaded_datasets[dataset_name]

        batch_analysis_manager = BatchAnalysisManager(
            dataset_name=dataset_name,
            batch_sa=batchsa,
            data_handler=data_handler
        )
        thread = QThread(self)
        batch_analysis_manager.moveToThread(thread)

        # Connect signals/slots
        thread.started.connect(batch_analysis_manager.run_analysis)
        batch_analysis_manager.finished.connect(thread.quit)
        batch_analysis_manager.finished.connect(batch_analysis_manager.deleteLater)
        thread.finished.connect(thread.deleteLater)
        batch_analysis_manager.finished.connect(self.on_batchanalysis_finished)

        # Start the thread
        thread.start()

        # Store references to prevent garbage collection
        self._batch_analysis_thread = thread
        self._batch_analysis = batch_analysis_manager
        return batch_analysis_manager

    def on_batchanalysis_finished(self):
        batch_analysis_manager = self._batch_analysis
        self.batch_analysis_dict[batch_analysis_manager.name] = batch_analysis_manager
        logger.info(f"BatchAnalysisManager instance saved on finish. Dataset: {batch_analysis_manager.name}")
        self.batchanalysis_finished.emit(batch_analysis_manager.name)

    def start_model_analysis(self, dataset_name, model_idx=0):
        """Run model analysis for the given dataset and model index."""
        if dataset_name not in self.dataset_manager.loaded_datasets:
            raise ValueError(f"Dataset '{dataset_name}' is not loaded.")
        data_handler = self.dataset_manager.loaded_datasets[dataset_name]

        if len(self.completed_batches) == 0:
            raise ValueError("No completed batches available. Please run a batch analysis first.")
        sa = self.completed_batches[dataset_name].results[model_idx]
        self.modelanalysis_manager = ModelAnalysisManager(
            sa=sa,
            data_handler=data_handler,
            model_idx=model_idx,
            parent=self
        )
        return self.modelanalysis_manager