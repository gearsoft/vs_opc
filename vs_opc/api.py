from flask import Blueprint, jsonify, request, Response
import json as _json
from decimal import Decimal
from .tag_store import TagStore
from .models import Tag

bp = Blueprint('tags_api', __name__)

# We'll import/create the TagStore lazily so importing this module doesn't
# force initialization order in the main server. The main server will set
# bp.tag_store before registering the blueprint.
bp.tag_store: TagStore = None  # type: ignore


@bp.route('/api/v1/tags', methods=['GET'])
def list_tags():
    ts: TagStore = bp.tag_store
    if ts is None:
        return _json_response({'tags': []})
    return _json_response({'tags': ts.list_tags()})


@bp.route('/api/v1/tags', methods=['POST'])
def add_tag():
    ts: TagStore = bp.tag_store
    if ts is None:
        return _json_response({'error': 'TagStore not initialized'}, status=500)
    payload = request.get_json() or {}
    # support single tag or batch
    if 'tags' in payload:
        tags = payload['tags']
    else:
        tags = [payload]

    created = []
    for t in tags:
        try:
            tag_obj = Tag(
                tag_id=t.get('tag_id') or t.get('name'),
                name=t.get('name', t.get('tag_id')),
                plc_id=t.get('plc_id', 'plc_1'),
                address=t.get('address', ''),
                data_type=t.get('data_type', 'Double'),
                group_id=t.get('group_id', 'default'),
                description=t.get('description'),
                project_id=t.get('project_id'),
                scale_mul=float(t.get('scale_mul', 1.0)),
                scale_add=float(t.get('scale_add', 0.0)),
                writable=bool(t.get('writable', False)),
                enabled=bool(t.get('enabled', True)),
                client_visible=t.get('client_visible', []),
            )
            ts.add_tag(tag_obj, initial_value=t.get('initial_value'))
            # Attempt to create an OPC UA node for the new tag if the
            # OPC UA server is running. This is best-effort; scheduling may
            # be a no-op in unit tests where the OPC UA loop is not active.
            try:
                # import here to avoid a hard dependency from this module
                from .plc_gateway_server import _schedule_on_opc_loop, _create_opcua_node_async
                _schedule_on_opc_loop(_create_opcua_node_async, {
                    'tag_id': tag_obj.tag_id,
                    'data_type': tag_obj.data_type,
                    'name': tag_obj.name,
                    'description': tag_obj.description,
                    'writable': tag_obj.writable,
                })
            except Exception:
                pass
            created.append(tag_obj.tag_id)
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    return _json_response({'created': created}, status=201)


def _validate_tag_payload(d: dict):
    if not isinstance(d, dict):
        return False, 'tag must be an object'
    tag_id = d.get('tag_id') or d.get('name')
    if not tag_id or not isinstance(tag_id, str):
        return False, 'tag_id or name is required and must be a string'
    # Basic datatype check
    dt = d.get('data_type') or 'Double'
    if not isinstance(dt, str):
        return False, 'data_type must be a string'
    return True, ''


@bp.route('/api/v1/tags/<tag_id>', methods=['GET'])
def get_tag(tag_id: str):
    ts: TagStore = bp.tag_store
    if ts is None:
        return _json_response({'error': 'TagStore not initialized'}, status=500)
    tag = ts.get_tag(tag_id)
    if not tag:
        return _json_response({'error': 'not found'}, status=404)
    # Retrieve both the converted value and the raw stored value so we can
    # decide how to present it to clients. If the raw stored value is a
    # Decimal (e.g. when the tag was added with an explicit Decimal that
    # preserves trailing zeros) return the string form to preserve that
    # representation. If the raw value was a numeric type provided by a
    # client (int/float) we return a numeric JSON value.
    val = ts.get_value(tag.tag_id)
    raw = None
    try:
        raw = ts.get_raw_value(tag.tag_id)
    except Exception:
        raw = None

    out_val = val
    # Preserve textual Decimal when the raw stored value was a Decimal
    from decimal import Decimal as _D
    if isinstance(raw, _D) and isinstance(val, _D):
        out_val = str(val)

    return _json_response({'tag': {
        'tag_id': tag.tag_id,
        'name': tag.name,
        'plc_id': tag.plc_id,
        'address': tag.address,
        'data_type': tag.data_type,
        'group_id': tag.group_id,
        'description': tag.description,
        'enabled': tag.enabled,
        'project_id': tag.project_id,
        'scale_mul': tag.scale_mul,
        'scale_add': tag.scale_add,
        'writable': tag.writable,
        'client_visible': tag.client_visible,
        'value': out_val
    }})


@bp.route('/api/v1/tags/<tag_id>', methods=['PATCH'])
def patch_tag(tag_id: str):
    ts: TagStore = bp.tag_store
    if ts is None:
        return _json_response({'error': 'TagStore not initialized'}, status=500)
    payload = request.get_json() or {}
    if not payload:
        return _json_response({'error': 'empty payload'}, status=400)
    # Only allow specific fields to be updated
    allowed = {'name', 'plc_id', 'address', 'data_type', 'group_id', 'description', 'enabled', 'project_id', 'scale_mul', 'scale_add', 'writable', 'client_visible'}
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates and 'value' not in payload:
        return jsonify({'error': 'no updatable fields provided'}), 400

    tag = ts.get_tag(tag_id)
    if not tag:
        return _json_response({'error': 'not found'}, status=404)

    # Update metadata
    if updates:
        ts.update_tag(tag_id, **updates)

    # Optionally update current value
    if 'value' in payload:
        try:
            ts.set_value(tag_id, payload['value'])
            # reflect value change into OPC UA node if present
            try:
                from .plc_gateway_server import _schedule_on_opc_loop, _update_opcua_value_async
                _schedule_on_opc_loop(_update_opcua_value_async, tag_id, payload['value'])
            except Exception:
                pass
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    return jsonify({'updated': tag_id})


@bp.route('/api/v1/tags/<tag_id>', methods=['DELETE'])
def delete_tag(tag_id: str):
    ts: TagStore = bp.tag_store
    if ts is None:
        return _json_response({'error': 'TagStore not initialized'}, status=500)
    tag = ts.get_tag(tag_id)
    if not tag:
        return _json_response({'error': 'not found'}, status=404)
    ts.remove_tag(tag_id)
    # attempt to remove OPC UA node as well
    try:
        from .plc_gateway_server import _schedule_on_opc_loop, _delete_opcua_node_async
        _schedule_on_opc_loop(_delete_opcua_node_async, tag_id)
    except Exception:
        pass
    return _json_response({'deleted': tag_id})


@bp.route('/api/v1/tags/import', methods=['PUT'])
def import_tags():
    """Import tags (JSON body). Accepts {'tags': [ ... ]}. If query param
    replace_all=true is provided the existing tags will be removed first.
    """
    ts: TagStore = bp.tag_store
    if ts is None:
        return _json_response({'error': 'TagStore not initialized'}, status=500)
    replace_all = request.args.get('replace_all', 'false').lower() in ('1', 'true', 'yes')
    payload = request.get_json() or {}
    tags = payload.get('tags')
    if not isinstance(tags, list):
        return _json_response({'error': 'tags must be a list'}, status=400)
    # optional replace
    if replace_all:
        ts.clear_tags()

    created = []
    for t in tags:
        ok, msg = _validate_tag_payload(t)
        if not ok:
            return jsonify({'error': msg}), 400
        tag_obj = Tag(
            tag_id=t.get('tag_id') or t.get('name'),
            name=t.get('name', t.get('tag_id')),
            plc_id=t.get('plc_id', 'plc_1'),
            address=t.get('address', ''),
            data_type=t.get('data_type', 'Double'),
            group_id=t.get('group_id', 'default'),
            description=t.get('description'),
            project_id=t.get('project_id'),
            scale_mul=float(t.get('scale_mul', 1.0)),
            scale_add=float(t.get('scale_add', 0.0)),
            writable=bool(t.get('writable', False)),
            enabled=bool(t.get('enabled', True)),
            client_visible=t.get('client_visible', []),
        )
        ts.add_tag(tag_obj, initial_value=t.get('initial_value'))
        # schedule OPC UA node creation for imported tag
        try:
            from .plc_gateway_server import _schedule_on_opc_loop, _create_opcua_node_async
            _schedule_on_opc_loop(_create_opcua_node_async, {
                'tag_id': tag_obj.tag_id,
                'data_type': tag_obj.data_type
            })
        except Exception:
            pass
        created.append(tag_obj.tag_id)

    return _json_response({'imported': created}, status=200)


def _json_response(obj, status=200):
    """Serialize a Python object to JSON, converting Decimal objects to
    numeric JSON values when appropriate (ints for whole-values, floats
    for fractional). This preserves Decimal internally but presents numbers
    as JSON numbers for clients and tests that expect numeric types.
    """
    def _convert(o):
        # Convert Decimal instances to int if integral, else float.
        if isinstance(o, Decimal):
            # Use quantize-free check for integral value
            try:
                if o == o.to_integral_value():
                    return int(o)
            except Exception:
                pass
            try:
                return float(o)
            except Exception:
                return str(o)
        # Convert mappings/lists recursively
        if isinstance(o, dict):
            return {k: _convert(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_convert(v) for v in o]
        if isinstance(o, tuple):
            return tuple(_convert(v) for v in o)
        return o

    safe_obj = _convert(obj)
    return Response(_json.dumps(safe_obj, default=str), mimetype='application/json', status=status)

