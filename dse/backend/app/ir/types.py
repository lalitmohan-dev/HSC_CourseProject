"""Shared types, enums, and constants for the DSE framework."""

from enum import Enum
from typing import Literal

class ResourceKind(str, Enum):
    PROCESSOR = "processor"
    HW_MODULE = "hw_module"
    BUS = "bus"

class TimeUnit(str, Enum):
    MS = "ms"
    US = "us"
    NS = "ns"
    TICKS = "ticks"
    CYCLES = "cycles"

class SearchStrategy(str, Enum):
    EXHAUSTIVE = "exhaustive"
    RANDOM = "random"
    GREEDY = "greedy"
    NSGA2 = "nsga2"

class PriorityPolicy(str, Enum):
    DEFAULT = "default"
    BOTTOM_LEVEL = "bottom_level"
    TOPOLOGICAL = "topological"
    EXPLICIT = "explicit"

class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
