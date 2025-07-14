import logging

from PySide6.QtWidgets import QMainWindow, QStackedWidget
from PySide6.QtCore import QThread

from src.views.main_view import MainView
from src.controllers import ProjectController, DataController, ModelController
from src.models.dataset_manager import DatasetManager
from src.models.batchsa_manager import BatchSAManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class MainController(QMainWindow):
    def __init__(self, parent=None, webviews=None):
        super().__init__(parent)
        self.setWindowTitle("ESAT")
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.main_view = MainView(self)
        self.stack.addWidget(self.main_view)

        self.webviews = webviews if webviews is not None else []
        self.dataset_manager = DatasetManager(self)

        self.project_controller = ProjectController(self)
        self.data_controller = DataController(self, webviews=self.webviews)
        self.model_controller = ModelController(self, webviews=self.webviews)

        self.completed_batches = {}

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
        self._batchsa_thread = thread
        self._batchsa_manager = batchsa_manager
        return batchsa_manager

    def on_batchsa_finished(self):
        # Save the BatchSAManager instance (self._batchsa_manager)
        # Example: store to a file, database, or keep in memory
        # For demonstration, just print or assign to an attribute
        self.completed_batches[self._batchsa_manager.dataset_name] = self._batchsa_manager
        logger.info(f"BatchSAManager {self._batchsa_manager.id} instance saved on finish. Dataset: {self._batchsa_manager.dataset_name}")
