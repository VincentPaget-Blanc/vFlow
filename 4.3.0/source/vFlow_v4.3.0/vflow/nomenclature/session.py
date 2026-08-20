"""Session-scoped, Tk-free axis/channel alias state."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChannelAliasSession:
    """Own confirmed label aliases and resolver prompt de-duplication state."""

    aliases: dict = field(default_factory=dict)
    prompt_signature: object = None

    def clear(self) -> None:
        self.aliases.clear()
        self.prompt_signature = None

    def resolve_target(self, name):
        """Resolve an alias chain defensively; cycles stop at the last stable name."""
        cur = name
        seen = set()
        while cur in self.aliases and cur not in seen:
            seen.add(cur)
            nxt = self.aliases.get(cur, cur)
            if nxt == cur:
                break
            cur = nxt
        return cur

    def apply_to_dataframe(self, df):
        """Apply confirmed label aliases without changing numeric data or row order."""
        if df is None or not self.aliases:
            return df, {'renamed': {}, 'ambiguous': []}

        present = list(df.columns)
        present_set = set(present)
        by_target = {}
        for col in present:
            target = self.resolve_target(col)
            if target != col:
                by_target.setdefault(target, []).append(col)

        rename_map = {}
        ambiguous = []
        for target, sources in by_target.items():
            if target in present_set:
                ambiguous.append(
                    f"{', '.join(repr(x) for x in sources)} map to {target!r}, "
                    "which already exists in this file")
                continue
            if len(sources) == 1:
                rename_map[sources[0]] = target
            else:
                ambiguous.append(
                    f"{', '.join(repr(x) for x in sources)} all map to {target!r}")

        if rename_map:
            df = df.rename(columns=rename_map)
        return df, {'renamed': rename_map, 'ambiguous': ambiguous}
