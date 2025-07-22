import uuid
import sys
import re
import logging
import numpy as np
import multiprocessing as mp
import threading
from functools import partial
from typing import List, Optional

from PySide6.QtCore import QObject, Signal, QThread

from esat.model.batch_sa import BatchSA


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def wrapped_progress_callback(progress_queue, model_i, i, max_iter, qtrue, qrobust, mse, completed):
    progress_queue.put({
        "model_i": model_i,
        "i": i,
        "max_iter": max_iter,
        "qtrue": qtrue,
        "qrobust": qrobust,
        "mse": mse,
        "completed": completed
    })

# In the main thread:
def listen_for_progress(progress_queue, progress_signal):
    while True:
        progress_data = progress_queue.get()
        if progress_data is None:
            break
        progress_signal.emit(progress_data)


class BatchSAManager(QObject):
    finished = Signal(str, object)
    error = Signal(str, Exception)
    progress = Signal(dict)  # New signal for progress

    def __init__(self, dataset_name, parent=None):
        super().__init__(parent)
        self.id = str(uuid.uuid4())
        self.V = None
        self.U = None
        self.factors = None
        self.models = None
        self.method = None
        self.seed = None
        self.max_iter = None
        self.init_method = None
        self.init_norm = None
        self.converge_delta = None
        self.converge_n = None

        self.user_progress_callback = None
        self.manager = mp.Manager()  # Create a Manager instance
        self.progress_queue = self.manager.Queue()  # Use Manager's Queue
        self.listener_thread = None
        self.dataset_name = dataset_name
        self.batch_sa = None


    def setup(self, V: np.ndarray, U: np.ndarray, factors: int, models: int, method: str, seed: int, max_iter: int,
              init_method: str, init_norm: bool, converge_delta: float, converge_n: int,
              progress_callback: callable
              ):
        self.V = V
        self.U = U
        self.factors = factors
        self.models = models
        self.method = method
        self.max_iter = max_iter
        self.init_method = init_method
        self.init_norm = init_norm
        self.converge_delta = converge_delta
        self.converge_n = converge_n
        self.seed = seed

        self.user_progress_callback = progress_callback
        logger.info(f"BatchSAManager setup complete - ID: {self.id}")

    def start_batch_sa_in_thread(self):
        self.listener_thread = threading.Thread(
            target=listen_for_progress,
            args=(self.progress_queue, self.progress),
            daemon=True
        )
        self.listener_thread.start()
        # Create a new thread
        self.batch_sa_thread = QThread()
        # Move the manager to the thread
        self.moveToThread(self.batch_sa_thread)
        # Connect signals
        self.batch_sa_thread.started.connect(self.run)
        self.finished.connect(self.batch_sa_thread.quit)
        self.finished.connect(self.deleteLater)
        self.batch_sa_thread.finished.connect(self.batch_sa_thread.deleteLater)
        # Start the thread
        self.batch_sa_thread.start()

    def run(self):
        try:
            logger.info(f"Starting BatchSA {self.id}")
            progress_cb = partial(
                wrapped_progress_callback,
                self.progress_queue
            )
            batch_sa = BatchSA(
                V=self.V, U=self.U, factors=self.factors, models=self.models, seed=self.seed,
                method=self.method, max_iter=self.max_iter, init_method=self.init_method,
                init_norm=self.init_norm, converge_delta=self.converge_delta,
                converge_n=self.converge_n, verbose=False, progress_callback=progress_cb
            )
            _ = batch_sa.train()
            logger.info(f"BatchSA {self.id} completed successfully.")
            self.batch_sa = batch_sa
            self.finished.emit("BatchSA", batch_sa)
            self.progress_queue.put(None)
        except Exception as e:
            self.error.emit("BatchSA", e)
            self.progress_queue.put(None)

