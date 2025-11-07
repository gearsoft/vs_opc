import threading
from typing import Dict, Any, List
from decimal import Decimal, ROUND_HALF_UP
from .models import Tag


class TagStore:
    """Thread-safe in-memory tag store.

    Stores tag metadata and current values. Provides simple hooks for
    other modules (OPC UA server, poller) to get/set tag values.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._tags: Dict[str, Tag] = {}
        self._values: Dict[str, Any] = {}

    def add_tag(self, tag: Tag, initial_value: Any = None):
        with self._lock:
            self._tags[tag.tag_id] = tag
            if initial_value is not None:
                self._values[tag.tag_id] = initial_value
            else:
                # default initial values based on type
                dt = tag.data_type.lower() if tag.data_type else ''
                if dt.startswith('bool'):
                    self._values[tag.tag_id] = False
                # treat any integer-like type (int32/int64/int16 etc.) as int
                elif 'int' in dt:
                    self._values[tag.tag_id] = 0
                else:
                    # default to float for other numeric types (Double/Float)
                    self._values[tag.tag_id] = 0.0

    def remove_tag(self, tag_id: str):
        with self._lock:
            self._tags.pop(tag_id, None)
            self._values.pop(tag_id, None)

    def get_value(self, tag_id: str):
        """Return the current value for tag_id.

        If the tag has scaling metadata (scale_mul/scale_add) and the value
        is numeric, apply the scaling before returning. Booleans are
        returned unchanged.
        """
        with self._lock:
            raw = self._values.get(tag_id)
            tag = self._tags.get(tag_id)
            if raw is None:
                return None
            # If no tag metadata or scaling is default, return raw value
            if not tag:
                return raw
            # Booleans should not be scaled
            try:
                if isinstance(raw, bool) or (hasattr(tag, 'data_type') and str(tag.data_type).lower().startswith('bool')):
                    return raw
            except Exception:
                pass
            # If scaling is default (1.0 / 0.0) return raw as-is
            try:
                mul = float(getattr(tag, 'scale_mul', 1.0))
            except Exception:
                mul = 1.0
            try:
                add = float(getattr(tag, 'scale_add', 0.0))
            except Exception:
                add = 0.0
            if mul == 1.0 and add == 0.0:
                # No scaling; convert numeric values to Decimal so internal
                # consumers always get Decimal for numeric types. If a
                # requested 'decimals' exists, quantize to preserve trailing
                # zeros.
                dec = getattr(tag, 'decimals', None)
                try:
                    d = Decimal(str(raw))
                    if dec is not None:
                        quant = Decimal(1).scaleb(-int(dec))
                        return d.quantize(quant, rounding=ROUND_HALF_UP)
                    return d
                except Exception:
                    # fall back to raw if conversion fails
                    return raw
            # Attempt numeric conversion and apply scaling
            try:
                # Use Decimal for arithmetic to retain exact decimal places
                num = Decimal(str(raw))
                dec_mul = Decimal(str(mul))
                dec_add = Decimal(str(add))
                scaled = (num * dec_mul) + dec_add
                dec = getattr(tag, 'decimals', None)
                if dec is not None:
                    try:
                        quant = Decimal(1).scaleb(-int(dec))
                        return scaled.quantize(quant, rounding=ROUND_HALF_UP)
                    except Exception:
                        return scaled
                # Return Decimal for consistency even when no explicit
                # decimals requested.
                return scaled
            except Exception:
                # If we can't convert to float, return raw value unchanged
                return raw

    def set_value(self, tag_id: str, value: Any):
        with self._lock:
            if tag_id in self._tags:
                self._values[tag_id] = value
            else:
                # allow setting unknown tags as a fallback
                self._values[tag_id] = value

    def list_tags(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    'tag_id': t.tag_id,
                    'name': t.name,
                    'plc_id': t.plc_id,
                    'address': t.address,
                    'data_type': t.data_type,
                    'group_id': t.group_id,
                    'project_id': t.project_id,
                    'scale_mul': t.scale_mul,
                    'scale_add': t.scale_add,
                    'decimals': getattr(t, 'decimals', None),
                    'writable': t.writable,
                    'description': t.description,
                    'enabled': t.enabled,
                    'client_visible': t.client_visible,
                }
                for t in self._tags.values()
            ]

    def snapshot(self):
        with self._lock:
            return { 'tags': {tid: self._values.get(tid) for tid in self._tags.keys()} }

    def get_raw_value(self, tag_id: str):
        """Return the raw stored value for tag_id (no scaling/conversion).

        This allows callers to decide how to serialize the value (e.g. preserve
        Decimal textual form when the source was a Decimal).
        """
        with self._lock:
            return self._values.get(tag_id)

    def get_tag(self, tag_id: str):
        """Return the Tag object for tag_id or None if missing."""
        with self._lock:
            return self._tags.get(tag_id)

    def update_tag(self, tag_id: str, **kwargs):
        """Update metadata fields of an existing Tag. Returns True if updated."""
        with self._lock:
            t = self._tags.get(tag_id)
            if not t:
                return False
            # Update only known attributes
            for k, v in kwargs.items():
                if hasattr(t, k):
                    setattr(t, k, v)
            return True

    def clear_tags(self):
        """Remove all tags and values from the store."""
        with self._lock:
            self._tags.clear()
            self._values.clear()
