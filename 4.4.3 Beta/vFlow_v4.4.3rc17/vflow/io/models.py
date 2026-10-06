"""Format-neutral acquisition contracts. No GUI dependencies."""
from dataclasses import dataclass, field
import pandas as pd

class UnsupportedFlowFormatError(ValueError):
    pass

class UnvalidatedFlowFormatError(UnsupportedFlowFormatError):
    pass

@dataclass
class ProbeResult:
    format_id: str
    signature: str
    validated: bool = True

@dataclass
class FlowSamplePayload:
    dataframe: pd.DataFrame
    logical_name: str
    source_path: str
    source_member_id: str | None = None
    source_format: str = ''
    metadata: dict = field(default_factory=dict)
    materialized_path: str | None = None

@dataclass
class FlowReadResult:
    samples: list[FlowSamplePayload]
    warnings: list[str] = field(default_factory=list)
