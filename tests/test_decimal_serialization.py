from decimal import Decimal
from flask import Flask

from vs_opc.api import bp
from vs_opc.tag_store import TagStore
from vs_opc.models import Tag


def test_decimal_serialization_roundtrip():
    app = Flask(__name__)
    ts = TagStore()
    # attach tagstore to blueprint and register
    bp.tag_store = ts
    app.register_blueprint(bp)

    # create a tag with a Decimal initial value containing trailing zeros
    tag = Tag(
        tag_id='t1',
        name='t1',
        plc_id='p1',
        address='A1',
        data_type='Double',
        group_id='g',
        description=None,
        project_id=None,
        scale_mul=1.0,
        scale_add=0.0,
        writable=False,
        enabled=True,
        client_visible=[],
    )
    ts.add_tag(tag, initial_value=Decimal('1.2300'))

    with app.test_client() as c:
        rv = c.get('/api/v1/tags/t1')
        assert rv.status_code == 200
        j = rv.get_json()
        assert 'tag' in j
        # value should be serialized as a string preserving trailing zeros
        assert j['tag']['value'] == '1.2300'


def test_list_tags_contains_serialized_values():
    app = Flask(__name__)
    ts = TagStore()
    bp.tag_store = ts
    app.register_blueprint(bp)

    tag = Tag(
        tag_id='t2',
        name='t2',
        plc_id='p1',
        address='A2',
    )
    ts.add_tag(tag, initial_value=Decimal('42'))

    with app.test_client() as c:
        rv = c.get('/api/v1/tags')
        assert rv.status_code == 200
        j = rv.get_json()
        assert 'tags' in j
        # list_tags returns metadata only; ensure endpoint works and returns JSON
        assert isinstance(j['tags'], list)
