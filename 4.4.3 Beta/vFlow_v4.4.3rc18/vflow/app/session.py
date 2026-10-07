"""Single Tk-free owner for vFlow application/scientific session state."""

from __future__ import annotations

from dataclasses import dataclass, field

from .cache import AnalysisCache
from .dataset import DatasetState
from .state import AnalysisState
from vflow.nomenclature.session import ChannelAliasSession


@dataclass
class ApplicationSession:
    """Own the mutable analysis, dataset, and cache components for one FlowApp.

    The component classes and all legacy payloads remain unchanged.  This layer
    only centralizes lifetime/ownership so UI decomposition no longer needs to
    discover three unrelated state holders on the Tk object.
    """

    analysis: AnalysisState = field(default_factory=AnalysisState)
    dataset: DatasetState = field(default_factory=DatasetState)
    cache: AnalysisCache = field(default_factory=AnalysisCache)
    nomenclature: ChannelAliasSession = field(default_factory=ChannelAliasSession)
