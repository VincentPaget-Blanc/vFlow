"""Channel/axis nomenclature helpers and session state."""

from .channel_names import (
    axis_name_compact,
    axis_name_similarity,
    channel_relation,
    discover_channel_schema,
    extract_channel_from_template,
    replace_channel_in_template,
    summarise_names,
)
from .session import ChannelAliasSession

__all__ = [
    "ChannelAliasSession",
    "axis_name_compact",
    "axis_name_similarity",
    "channel_relation",
    "discover_channel_schema",
    "extract_channel_from_template",
    "replace_channel_in_template",
    "summarise_names",
]
