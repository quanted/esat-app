import os

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox
from PySide6.QtCore import QThread, Signal, QTimer

from src.views.main_view import MainView
from src.controllers import ProjectController, DataController, ModelController
from src.models import DatasetManager, BatchSAManager, BatchAnalysisManager, ModelAnalysisManager, Project, Dataset
from src.utils.esat_logger import init_logger, get_logger, set_log_file


class MainController(QMainWindow):
    batchsa_finished = Signal(str)
    batchsa_canceled = Signal()
    batchanalysis_finished = Signal(str)
    batchresiduals_finished = Signal(object)
    modelanalysis_finished = Signal(str)
    modelstats_finished = Signal(str)
    modelresiduals_finished = Signal(object, object)

    factor_profile_contrib_finished = Signal(object, object)
    factor_fingerprints_finished = Signal(object)
    factor_gplot_finished = Signal(object)

    factors_contributions_finished = Signal(object, object)

    def __init__(self, parent=None, webviews=None):
        super().__init__(parent)
        self.setWindowTitle("ESAT")
        init_logger()
        self.logger = get_logger()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.main_view = MainView(self)
        self.stack.addWidget(self.main_view)

        self.webviews = webviews if webviews is not None else []
        self.dataset_manager = DatasetManager(self)
        self.modelanalysis_manager = {}
        self.selected_modelanalysis_manager = None

        self.current_project = None

        self.project_controller = ProjectController(self)
        self.data_controller = DataController(self, webviews=self.webviews)
        self.model_controller = ModelController(self, webviews=self.webviews)
        self.current_view = self.main_view

        self.first_load = True

        self.completed_batches = {}
        self.batch_analysis_dict = {}
        self._factor_analysis_signal_trackers = {}
        self.show_main_view()

    def switch_to_view(self, new_view):
        # Remove current view widget from view_layout, not content_layout
        view_layout = self.main_view.view_layout
        # Remove all widgets from view_layout
        while view_layout.count():
            item = view_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setVisible(False)
        # If switching to main, leave view_layout empty and show permanent widgets
        if new_view == getattr(self, 'main_view', None):
            self.main_view.title_label.setVisible(True)
            self.main_view.logo_label.setVisible(True)
            self.main_view.desc_label.setVisible(True)
            self.main_view.links_browser.setVisible(True)
        else:
            # Hide permanent widgets
            self.main_view.title_label.setVisible(False)
            self.main_view.logo_label.setVisible(False)
            self.main_view.desc_label.setVisible(False)
            self.main_view.links_browser.setVisible(False)
            # Add new view widget to view_layout and show it
            view_layout.addWidget(new_view)
            new_view.setVisible(True)
        self.current_view = new_view

    @staticmethod
    def global_cleanup():
        """Perform global cleanup tasks."""
        logger = get_logger()
        logger.info("Performing global cleanup tasks.")
        # Remove project directory from environment
        os.environ.pop('ESAT_PROJECT_DIR', None)
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
        # Clean up model analysis manager
        if hasattr(MainController, "modelanalysis_manager"):
            logger.info("Cleaning up ModelAnalysisManager.")
            try:
                MainController.modelanalysis_manager.cleanup()
            except Exception:
                pass
        # Clean up Batch Analysis Manager
        if hasattr(MainController, "batch_analysis_dict"):
            logger.info("Cleaning up BatchAnalysisManager.")
            try:
                for batch_analysis in MainController.batch_analysis_dict.values():
                    batch_analysis.cleanup()
            except Exception:
                pass
        # Clean up BatchSAManager
        if hasattr(MainController, "completed_batches"):
            logger.info("Cleaning up BatchSAManager.")
            try:
                for batchsa_manager in MainController.completed_batches.values():
                    batchsa_manager.cleanup()
            except Exception:
                pass

    def show_main_view(self):
        """Switch to the main view without deleting other views."""
        # hide the current view
        central_layout = self.main_view.content_layout
        for i in reversed(range(central_layout.count())):
            widget = central_layout.itemAt(i).widget()
            if widget is not None:
                central_layout.removeWidget(widget)
                widget.setParent(None)
        self.main_view.load_main_content()

    def set_project(self, project: Project, dataset: Dataset):
        self.current_project = project
        if project is not None:
            os.makedirs(project.output_directory, exist_ok=True)
            set_log_file(project.output_directory)
        self.current_project.datasets.append(dataset)
        if project and project.output_directory:
            os.environ['ESAT_PROJECT_DIR'] = project.output_directory
        else:
            os.environ.pop('ESAT_PROJECT_DIR', None)

    def load_project(self, project_path: str):
        raise NotImplementedError("Project loading not implemented yet.")

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
        self.logger.error(f"Batch processing error: {exception}", exc_info=True)
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
        project_directory = self.current_project.output_directory if self.current_project else os.getcwd()
        if not os.path.exists(project_directory):
            os.mkdir(project_directory)
        batchsa_manager = self._batch_manager
        batch_directory = os.path.join(self.current_project.output_directory, batchsa_manager.dataset_name)

        os.makedirs(batch_directory, exist_ok=True)
        self.logger.info(f"Saving BatchSAManager results to {batch_directory}")
        batchsa_manager.batch_sa.save(
            batch_name=batchsa_manager.dataset_name,
            output_directory=batch_directory,
            pickle_model=False,
            pickle_batch=False,
            header=self.dataset_manager.loaded_datasets[batchsa_manager.dataset_name].features
        )
        batchsa_manager.batch_sa.save(
            batch_name=batchsa_manager.dataset_name,
            output_directory=batch_directory,
            pickle_model=True,
            pickle_batch=True,
            header=self.dataset_manager.loaded_datasets[batchsa_manager.dataset_name].features
        )
        self.completed_batches[batchsa_manager.dataset_name] = batchsa_manager
        self.logger.info(f"BatchSAManager {batchsa_manager.id} instance saved on finish. Dataset: {batchsa_manager.dataset_name}")
        self.batchsa_finished.emit(batchsa_manager.dataset_name)

        # --- Model analysis and plotting ---
        dataset_name = batchsa_manager.dataset_name
        batch_sa = batchsa_manager.batch_sa
        data_handler = batchsa_manager.data_handler if hasattr(batchsa_manager, 'data_handler') else None

        best_model = batch_sa.best_model
        model = batch_sa.results[batch_sa.best_model]
        if not model:
            self.logger.warning(f"No models found for batch: {dataset_name}")
            return
        if dataset_name not in self.modelanalysis_manager:
            self.modelanalysis_manager[dataset_name] = {}
        # Delay the model analysis call slightly to ensure readiness
        QTimer.singleShot(200, lambda: self.run_model_analysis(dataset_name, best_model))
        self.logger.info(f"Model analysis and plots started for batch: {dataset_name}")

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
        self.logger.info(f"BatchAnalysisManager instance saved on finish. Dataset: {batch_analysis_manager.name}")
        self.batchanalysis_finished.emit(batch_analysis_manager.name)

    def run_model_analysis(self, dataset_name, model_idx=0):
        """Run model analysis for the given dataset and model index."""
        if dataset_name not in self.dataset_manager.loaded_datasets:
            raise ValueError(f"Dataset '{dataset_name}' is not loaded.")
        data_handler = self.dataset_manager.loaded_datasets[dataset_name]

        try:
            if len(self.completed_batches) == 0:
                raise ValueError("No completed batches available. Please run a batch analysis first.")
            if dataset_name not in self.completed_batches:
                raise ValueError(f"No completed batch for dataset '{dataset_name}'.")
            batch = self.completed_batches[dataset_name]
            if not hasattr(batch, 'batch_sa') or not hasattr(batch.batch_sa, 'results'):
                raise ValueError(f"Batch analysis for '{dataset_name}' is missing results.")
            if model_idx >= len(batch.batch_sa.results):
                raise IndexError(f"Model index {model_idx} out of range for batch results.")
            sa = batch.batch_sa.results[model_idx]

            self.logger.info(f"Model analysis started for dataset: {dataset_name}, model index: {model_idx}")
            if dataset_name not in self.modelanalysis_manager:
                self.modelanalysis_manager[dataset_name] = {}
            if model_idx in self.modelanalysis_manager[dataset_name]:
                analysis_manager = self.modelanalysis_manager[dataset_name][model_idx]
                self.logger.info("Existing ModelAnalysisManager instance found.")
            else:
                self.logger.info(f"Creating ModelAnalysisManager for dataset: {dataset_name}, model_idx: {model_idx}")
                self.logger.info(f"sa type: {type(sa)}, sa repr: {repr(sa)}")
                self.logger.info(f"data_handler type: {type(data_handler)}, data_handler repr: {repr(data_handler)}")
                try:
                    analysis_manager = ModelAnalysisManager(sa, data_handler, model_idx=model_idx)
                except Exception as e:
                    self.logger.error(f"Error instantiating ModelAnalysisManager: {e}", exc_info=True)
                    raise
                self.modelanalysis_manager[dataset_name][model_idx] = analysis_manager
                analysis_manager.modelStatsReady.connect(self.modelstats_finished.emit)
                analysis_manager.residualHistogramReady.connect(self.modelresiduals_finished.emit)
                # # --- Factor analysis signals tracking ---
                analysis_manager.factorProfileReady.connect(self.factor_profile_contrib_finished)
                analysis_manager.factorFingerprintsReady.connect(self.factor_fingerprints_finished)
                analysis_manager.gSpaceReady.connect(self.factor_gplot_finished)
                # # ---
                analysis_manager.factorContributionsReady.connect(self.factors_contributions_finished)
                self.logger.info("Calling analysis_manager.run_all()...")
                try:
                    analysis_manager.run_all()
                except Exception as e:
                    self.logger.error(f"Error in analysis_manager.run_all(): {e}", exc_info=True)
                    raise
                self.logger.info("analysis_manager.run_all() completed.")
            self.selected_modelanalysis_manager = analysis_manager
            self.logger.info(f"Model analysis completed for dataset: {dataset_name}, model index: {model_idx}")
        except Exception as e:
            self.logger.error(f"Error in run_model_analysis: {e}", exc_info=True)
            # Optionally, show a dialog or propagate the error
        return None
