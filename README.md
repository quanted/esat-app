<div align="center">
  <img src="src/resources/icons/esat-logo.png" alt="ESAT Logo" width="200">
</div>

# ESAT GUI Application

## Overview
The ESAT application is a cross-platform graphical user interface (GUI) for source apportionment modeling, built with Python and [PySide6](https://doc.qt.io/qtforpython/). The GUI provides an interactive environment for data analysis, model creation, and visualization, aiming to modernize and extend the functionality of the EPA's PMF5 tool.

The source code for the ESAT GUI is located in the `src/` directory.

## Features
- Interactive data visualization using Plotly
- Data cleaning and preprocessing tools (with scikit-learn)
- Batch model analysis and factor cataloging
- Multi-location and dynamic source profiling workflows
- Bayesian matrix factorization (using PyMC)
- Factor profile search and integration with external databases
- Modern, user-friendly interface with advanced plotting and reporting

## Installation
1. **Clone the repository:**
   ```sh
   git clone <repo-url>
   cd esat_app
   ```
2. **Install dependencies:**
   It is recommended to use a virtual environment.
   ```sh
   pip install -r requirements.txt
   ```
   Ensure you have Python 3.9+ installed.

## Running the Application
To launch the ESAT GUI:
```sh
python main.py
```
This will start the PySide6-based GUI. All main application logic and interface code is in the `src/` directory.

## Current Features
- Multiple data file types supported (CSV, Excel)
- Data analysis and preprocessing tools
- Batch model running (with parallel processing progress feedback)
- Batch model analysis
- Model, factor and feature analysis and visualizations
- Results saving and exporting (CSV, images)
- Interactive visualizations with Plotly
- Modular architecture for extensibility

## PMF5 Features Remaining to be Implemented
- Error estimation and uncertainty analysis (BS, DISP, BS-DISP)
- Custom constraints

## New Features Planned
Some of these features are ready to be integrated into the ESAT package and GUI, while others will require testing 
prior to integration or are not yet complete.
- Data
  - Missing data interpolation (esat/esat/data/impute.py)
  - Outlier detection and handling (autoencoders, isolation forests)
  - Simulated data generation for testing and validation (esat/eval/simulator.py)
- Models
  - Batch factor clustering and cataloging (esat/exp/factor_catalog.py)
- Workflows
  - Uncertainty perturbation workflow (esat/notebooks/uncertainty-perturbation-workflow.ipynb)
  - Bayesian NMF workflow (esat/exp/bayes_nmf.py)
  - Multi-location factor catalog workflow: comparing two or more factor catalogs to determine common or changing factors.
  - Dynamic source profiling workflow: rolling window batch modeling to capture time-varying source profiles.
- Enhancements
  - GPU acceleration for matrix factorization in the rust backend (esat/rust/)
  - Integration with EPA SPECIATE database for factor profile search and matching.

## Directory Structure
- `src/` — Main source code for the ESAT GUI application
- `data/` — Example datasets
- `requirements.txt` — Python dependencies
- `DEVOPTIONS.md` — Advanced developer and workflow documentation

## Documentation & Advanced Usage
For detailed workflow descriptions, developer options, and advanced features, see [DEVOPTIONS.md](DEVOPTIONS.md).

## License
See [LICENSE](LICENSE) for license information.

## Building the Executable (Windows)

You can build a standalone Windows executable for the ESAT GUI using [PyInstaller](https://pyinstaller.org/).

### 1. Install PyInstaller
```sh
pip install pyinstaller
```

### 2. Build the Executable
Run the following command from the project root:
```sh
pyinstaller --clean esat.spec
```

This command uses the `esat.spec` file, which is a PyInstaller specification script tailored for the ESAT application. The `esat.spec` file:
- Sets the entry point to `src/app.py` (the main GUI application).
- Includes all necessary source code from the `src/` directory and example datasets from `data/`.
- Adds required resources (such as icons and styles) to the build, ensuring the GUI displays correctly.
- Sets the application icon (located in `src/resources/icons/esat-logo.ico`).
- Configures PyInstaller to build a single-folder distribution in `dist`.
- Applies any additional PyInstaller options needed for ESAT to run as a standalone Windows executable.
- To build for other platforms (Linux, macOS), you will need to run PyInstaller on those respective systems.

You can customize the build by editing `esat.spec` to add or remove data files, change the entry script, or adjust PyInstaller options as needed. For more details, see the comments inside `esat.spec` and the [PyInstaller documentation](https://pyinstaller.org/en/stable/spec-files.html).

### 3. Locate the Executable
The built executable will be in the `dist/` directory.

### 4. Notes
- You may need to adjust `--add-data` paths for your environment (use `;` as a separator on Windows).
- If you use additional data files or resources, add them with more `--add-data` options.
- For advanced options or troubleshooting, see the [PyInstaller documentation](https://pyinstaller.org/en/stable/).
