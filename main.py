from warnings import filterwarnings
from multiprocessing import freeze_support
from src.app import main


filterwarnings(
    "ignore",
    category=RuntimeWarning,
    message=r".*Failed to disconnect.*loadFinished\(bool\).*"
)


if __name__ == "__main__":
    freeze_support()
    main()