<div align="center">
  <img src="src/resources/icons/esat-logo.png" alt="ESAT Logo" width="200">
</div>

# ESAT Application — Developer Options & Roadmap

## Overview
The ESAT application is a cross-platform Python GUI for source apportionment modeling, designed to modernize and extend the EPA's PMF5 tool. It is built with PySide6, scikit-learn, Plotly, and PyMC, and features a modular architecture for extensibility and maintainability.

---

## Implemented Features

### Data Analysis & Preprocessing
- Enhanced interactive data visualization (Plotly in Qt WebEngine)
- Data cleaning and preprocessing tools:
  - Interpolation of missing data (SimpleImputer, KNNImputer, IterativeImputer via scikit-learn)
- Multi-location data analysis and visualization:
  - Support for single/multiple files and locations
  - Separate or joint analysis per location

### Batch & Model Analysis
- Batch model analysis and factor cataloging (batchanalysis_manager, batchsa_manager)
- Factor clustering and cataloging by correlation
- Factor count analysis:
  - Multi-criteria evaluation (BIC, AIC, error metrics, stability)
- Project and dataset management (project_controller, dataset_manager)

### GUI & Usability
- Modern PySide6 interface with custom widgets and views
- Error handling and logging (error_controller, esat_logger)
- Resource management (icons, styles, content)
- Modular MVC-like code structure for extensibility

---

## Planned / Future Features

### Advanced Uncertainty Evaluation
- Monte Carlo perturbation simulations for uncertainty quantification
- Deeper integration of uncertainty into model results and reporting

### Bayesian Source Apportionment
- Full-featured Bayesian matrix factorization workflows (PyMC)
- Hybrid modeling: batch model initialization for Bayesian models
- Enhanced uncertainty quantification and prior knowledge integration

### Dynamic Source Profiling
- Rolling window batch modeling for time-varying source profiles
- Automated detection of emerging/disappearing sources

### Factor Profile Search & Database Integration
- Integration with EPA SPECIATE and other factor profile databases
- Vectorized embeddings for rapid similarity search and clustering
- User-defined factor profile database support

### Live Data Integration & Automation
- Automated workflows for live data (e.g., EPA AirNow)
- Real-time factor count analysis, cataloging, and BNMF modeling
- Dashboard for live visualization and analysis

---

## Developer Notes
- The main entry point is `src/app.py`.
- Controllers, models, views, and widgets are organized in their respective subfolders under `src/`.
- For building and packaging instructions, see the main `README.md`.
- Contributions and suggestions for new workflows are welcome!
