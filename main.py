import warnings
import multiprocessing
from src.app import main


warnings.filterwarnings(
    "ignore",
    category=RuntimeWarning,
    message=r".*Failed to disconnect.*loadFinished\(bool\).*"
)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()