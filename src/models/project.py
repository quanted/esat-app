from dataclasses import dataclass
from typing import Optional, List
from src.models.dataset import Dataset

@dataclass
class Project:
    name: str
    description: Optional[str]
    datasets: List[Dataset]
    output_directory: str
