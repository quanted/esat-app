# ESAT Application
## Overview
The ESAT application is a python based cross-platform application that allows users to create and analyze source 
apportionment models. The application is designed to replace the EPA's PMF5 application, fully recreating the 
functionality of PMF5 while adding new features and modern workflows. The application is built using the esat python 
package, which provides the core functionality for source apportionment modeling, pyside6 for the GUI, scikit-learn for 
machine learning, and pymc for Bayesian modeling.

## Features
### Data Analysis
The first step in the ESAT, and PMF5, workflow is to analyze and prepare the data. The ESAT application provides
additional features for data analysis, including:
* Enhanced interactive data visualization (plotly)
* Data cleaning and preprocessing tools. 
  * Interpolation of missing data using sklearn: 
    * SimpleImputer (mean, median, most frequent)
    * KNNImputer (k-nearest neighbors)
    * IterativeImputer (iterative regressor).
* Multi-location data analysis and visualization.
  * Allow for single file containing location data
  * Allow for multiple files for different locations
  * Each location can be analyzed separately or together.

## Workflows
In addition to the core functionality found in PMF5, the ESAT application provides several new enhanced workflows.

### Uncertainty Evaluation
Evaluation of the input uncertainty is a critical step in source apportionment modeling. ESAT will provide a workflow to
quantify the impact the uncertainty has on the model results. This will include:
* Uncertainty evaluation using monte carlo perturbation simulations.

### Batch Analysis
In addition to the model analysis that is available in PMF5, the ESAT application will provide batch analysis to
evaluate the factors and their contributions across multiple models. This will allow users to determine common factors,
calculate their occurrence and variability across models, and identify trends in the data.
* Factor Catalog
  * A catalog of factors that can be used to compare and analyze factors across models, where factors are clustered by correlation.
  * Allows users to identify common factors across models and evaluate their contributions.

### Factor Count Analysis
A critical step in source apportionment modeling is determining the number of factors to extract from the data. Often 
this is done by trial and error, but the ESAT application will provide a more systematic approach to factor count analysis.
* Multi-criteria evalution of the number of factors to use by combining information theory, cross-validation and stability metrics.
* Evaluate batch model error, the Bayesian Information Criterion (BIC), Akaike Information Criterion (AIC), and of the cataloged clusters.

### Multi-Location Analysis
Multi-location analysis allows users to analyze data from multiple locations simultaneously, providing a more 
comprehensive understanding of source apportionment across different locations.
* Develop batches of models for each location all with their own catalog of factors.
  * Allows users to analyze data from multiple locations simultaneously.
* Compare the catalog of factors across locations.
  * Allows users to identify common factors across locations and evaluate how the change.

### Dynamic Source Profiling
In matrix factorization, the source profiles are assumed to be static. However, in reality, the source profiles can 
change over time. Source profiles can change in time, new sources can emerge, and existing sources can disappear. 
Capturing this dynamic nature of sources is critical for accurate source apportionment modeling.
* Rolling window batch modelling
  * A fixed window of data is used to create a batch, then the window is shifted forward in time and a new batch is created. These models can then be evaluated for source changes.
  * A possible approach: An initial batch is created, in the next window 3 new independent batches are created for k factors +/- 1. Each of these batches are evaluated to determine the best fit for the new data.

### Bayesian Source Apportionment
Bayesian matrix factorization (BNMF) is a powerful approach to source apportionment modeling that allows for uncertainty to be 
integrated directly into the model. While more complex than traditional matrix factorization approaches, a hybrid modeling
approach can be used to combine the strengths of both algorithms. Running a batch of models then using the results to 
initialize a Bayesian model we can provide efficient and accuracy BNMF model. Benefits of BNMF:
* Uncertainty quantification and probabilistic modeling.
* Incorporation of prior knowledge, easily customized for model/source constraints.
* Use of prior distributions to inform the model, allowing for continuous learning, and adaptation to new data.

### Factor Profile Search
Evaluating the outputs of a source apportionment model can be challenging, especially when trying to identify specific sources. 
To assist with this, the ESAT application will provide a factor profile search feature that allows users to compare factor
profiles to those in a database of known sources, such as the EPA SPECIATE database.
* Integration of SPECIATE database for factor profile comparison/search/labeling.
* Enhance the database by converting the SPECIATE database to use vectorized embeddings, allowing for rapid similarity search and clustering.
* Allow for users to develop their own factor profile databases.

### Live Data Integration
By combining several of these new features, the ESAT application would be capable of providing live data integration 
functionality. Automating the factor count analysis (which will have to include a decision criteria), factor cataloging, 
profile search, and BNMF modeling would allow for real-time source apportionment modeling.
* Develop automated workflow for the EPA's AirNow data.
* Develop dashboard for visualization and analysis of source apportionment results for the live-data.