from dataclasses import dataclass
from typing import Optional, List

@dataclass
class Dataset:
    name: str
    data_file_path: str
    uncertainty_file_path: Optional[str]
    index_column: str
    location_ids: Optional[List[str]]
    missing_value_label: str
    latitude: Optional[float]
    longitude: Optional[float]
    location_label: Optional[str]