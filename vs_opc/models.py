from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class PLC:
    id: str
    name: str
    ip: str
    driver: str = 'logix'
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Tag:
    tag_id: str
    name: str
    plc_id: str
    address: str
    data_type: str = 'Double'
    group_id: str = 'default'
    project_id: Optional[str] = None
    scale_mul: float = 1.0
    scale_add: float = 0.0
    # number of decimal places to round returned (scaled) values to.
    # short name 'decimals' keeps naming consistent with other short fields
    decimals: Optional[int] = None
    writable: bool = False
    description: Optional[str] = None
    enabled: bool = True
    client_visible: List[str] = field(default_factory=list)
