from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget

from src.views.tabs.ma_featureanalysis_stab import FeatureAnalysisSubTab
from src.views.tabs.ma_residualanalysis_stab import ResidualAnalysisSubTab
from src.views.tabs.ma_factoranalysis_stab import FactorAnalysisSubTab
from src.views.tabs.ma_factorsummary_stab import FactorSummarySubTab


class ModelAnalysisTab(QWidget):
    def __init__(self, parent=None, controller=None, webviews=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller
        self.webviews = webviews or {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.subtabs = QTabWidget()
        self.subtabs.setTabPosition(QTabWidget.South)
        self.feature_analysis_tab = FeatureAnalysisSubTab(parent=self, controller=self.controller, webviews={
            'obs_pred_scatter': self.webviews["obs_pred_scatter"],
            'obs_pred_ts': self.webviews["obs_pred_ts"]
        })
        self.residual_analysis_tab = ResidualAnalysisSubTab(parent=self, controller=self.controller)
        self.factor_analysis_tab = FactorAnalysisSubTab(parent=self, controller=self.controller)
        self.factor_summary_tab = FactorSummarySubTab(parent=self, controller=self.controller)
        self.subtabs.addTab(self.feature_analysis_tab, "Feature Analysis")
        self.subtabs.addTab(self.residual_analysis_tab, "Residual Analysis")
        self.subtabs.addTab(self.factor_analysis_tab, "Factor Analysis")
        self.subtabs.addTab(self.factor_summary_tab, "Factor Summary")
        layout.addWidget(self.subtabs)

