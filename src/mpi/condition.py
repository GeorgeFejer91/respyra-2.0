from respyra.core.target_generator import SegmentDef
from dataclasses import dataclass, field


@dataclass
class ConditionDef:
    """A named experimental condition composed of one or more segments.

    Parameters
    ----------
    name : str
        Human-readable label used in data files (e.g. ``'slow_steady'``).
    segments : list[SegmentDef]
        Ordered list of segments that form the repeating pattern.
    feedback_gain : float
        Multiplicative gain applied to the visual trace around the
        participant's breathing center.  ``1.0`` = veridical feedback.
        Values > 1 amplify displayed deviations; < 1 attenuate them.
    """

    name: str
    segments: list[SegmentDef] = field(default_factory=list)
    feedback_gain: float = 1.0
    feedback: bool = True

    @property
    def total_duration(self) -> float:
        """Total duration of one pass through all segments (seconds)."""
        return sum(seg.duration for seg in self.segments)
