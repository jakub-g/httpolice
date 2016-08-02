# -*- coding: utf-8; -*-

import os

import pytest

from httpolice.inputs import InputError
from httpolice.inputs.streams import (combined_input, tcpflow_input,
                                      tcpick_input)
from httpolice.known import h, m, st, upgrade
from httpolice.structure import Unavailable, Versioned, http11


def load_from_file(name):
    path = os.path.join(os.path.dirname(__file__), 'combined_data', name)
    return list(combined_input([path]))


def load_from_tcpflow(name):
    path = os.path.join(os.path.dirname(__file__), 'tcpflow_data', name)
    return list(tcpflow_input([path]))


def load_from_tcpick(name):
    path = os.path.join(os.path.dirname(__file__), 'tcpick_data', name)
    return list(tcpick_input([path]))


def test_complex_connection():
    [exch1, exch2, exch3, exch4, exch5, exch6] = \
        load_from_file('complex_connection')

    assert u'complex_connection' in exch1.request.remark
    assert exch1.request.method == m.POST
    assert exch1.request.target == u'/articles/'
    assert exch1.request.version == http11
    assert exch1.request.header_entries == [
        (h.host, b'example.com'),
        (h.user_agent, b'demo'),
        (h.content_type, b'text/plain'),
        (h.content_length, b'16'),
        (h.expect, b'100-continue'),
    ]
    assert repr(exch1.request.header_entries[0]) == '<HeaderEntry Host>'
    assert exch1.request.headers.content_length == 16
    assert repr(exch1.request.headers.content_length) == \
        '<SingleHeaderView Content-Length>'
    assert exch1.request.body == b'Hello world!\r\n\r\n'
    assert not exch1.request.trailer_entries
    assert repr(exch1.request) == '<Request POST>'

    assert len(exch1.responses) == 3
    assert u'complex_connection' in exch1.responses[0].remark
    assert exch1.responses[0].status == st.continue_
    assert repr(exch1.responses[0].status) == 'StatusCode(100)'
    assert exch1.responses[0].body == b''
    assert repr(exch1.responses[0]) == '<Response 100>'
    assert exch1.responses[1].status == 123
    assert exch1.responses[1].reason == u"Keep On Rollin' Baby"
    assert exch1.responses[1].headers.content_length == 1
    assert exch1.responses[1].body == b''
    assert exch1.responses[2].status == st.created
    assert exch1.responses[2].headers.content_length == 49
    assert exch1.responses[2].body == \
        b'Your article was posted under /articles/123/.\r\n\r\n'

    assert repr(exch1) == ('Exchange(<Request POST>, '
                           '[<Response 100>, <Response 123>, <Response 201>])')

    assert exch2.request.method == m.HEAD
    # According to my reading of the spec (which may be wrong),
    # every ``obs-fold`` becomes one space,
    # and these spaces are *not* stripped
    # from either end of the resulting ``field-value``.
    assert exch2.request.header_entries[2] == (u'Quux', b' demo  (demo) ')
    assert exch2.request.header_entries[3] == (u'Foo', b'  bar')
    assert exch2.request.header_entries[4] == (h.accept_encoding, b'')
    assert len(exch2.responses) == 1
    assert exch2.responses[0].status == st.ok
    assert exch2.responses[0].body == b''

    assert exch3.request.method == m.OPTIONS
    assert exch3.request.target == u'*'
    assert len(exch3.responses) == 1
    assert exch3.responses[0].status == st.ok
    assert exch3.responses[0].body == b''

    assert exch4.request.headers.upgrade.value == \
        [Versioned(upgrade.h2c, None)]
    assert len(exch4.responses) == 1
    assert exch4.responses[0].status == st.switching_protocols
    assert exch4.responses[0].body == b''

    # The last ones are just boxes for no. 1007 and 1010.
    assert exch5.request is None
    assert exch5.responses == []
    assert exch6.request is None
    assert exch6.responses == []


def test_unparseable():
    # Only notice boxes are produced from that file, no usable messages.
    for exch in load_from_file('unparseable'):
        assert exch.request is None
        assert exch.responses == []


def test_unparseable_body():
    [exch1, exch2] = load_from_file('1000_1')

    assert exch1.request.method == m.GET
    assert exch1.request.body == b''
    assert len(exch1.responses) == 1
    assert exch1.responses[0].status == st.ok
    assert not exch1.responses[0].headers.content_length.is_okay
    assert exch1.responses[0].headers.content_length.value is Unavailable
    assert exch1.responses[0].body is Unavailable

    # The other one is just a box for no. 1010.
    assert exch2.request is None
    assert exch2.responses == []


def test_chunked():
    [exch1] = load_from_file('chunked')
    assert exch1.request.body == b'foo bar foo bar foo bar baz xyzzy'
    assert exch1.request.trailer_entries == [(u'Some-Result', b'okay')]
    assert exch1.request.headers[u'Some-Result'].value == b'okay'


def test_chunked_empty():
    [exch1] = load_from_file('chunked_empty')
    assert exch1.request.body == b''


def test_implicit_response_framing():
    [exch1] = load_from_file('1025_2')
    assert exch1.responses[0].body == b'Hello world!\r\n'


def test_tcpflow():
    exchanges = load_from_tcpflow('httpbin')

    assert exchanges[0].request.method == m.GET
    assert exchanges[0].request.target == u'/get'
    assert exchanges[0].request.version == http11

    assert u'n → ∞' in exchanges[3].responses[0].unicode_body

    assert b'"gzipped": true' in exchanges[4].responses[0].decoded_body

    assert b'"deflated": true' in exchanges[5].responses[0].decoded_body

    assert exchanges[6].responses[0].status == st.no_content
    assert exchanges[6].responses[0].reason == u'NO CONTENT'

    assert exchanges[8].responses[0].body.count(b'{"url":') == 10

    assert len(exchanges[9].responses[0].body) == 1024


def test_tcpflow_multiple_connections():
    [exch1, exch2, exch3] = load_from_tcpflow('multiple_connections')
    assert exch1.request.target == u'/status/400'
    assert exch2.request.target == u'/status/401'
    assert exch3.request.target == u'/status/402'


def test_tcpflow_request_timeout():
    [box, exch1] = load_from_tcpflow('request_timeout')

    # The first exchange is only a box for no. 1278.
    assert box.request is None
    assert box.responses == []
    assert [complaint.id for complaint in box.complaints] == [1278]

    # The second exchange contains only the 408 response.
    assert exch1.request is None
    [resp] = exch1.responses
    assert resp.status == st.request_timeout
    assert resp.body == b'How long am I supposed to wait?\r\n'


def test_tcpflow_response_timeout():
    [box, exch1] = load_from_tcpflow('response_timeout')

    # The first exchange is only a box for no. 1278.
    assert box.request is None
    assert box.responses == []
    assert [complaint.id for complaint in box.complaints] == [1278]

    # The second exchange contains only the request.
    assert exch1.request.method == m.GET
    assert exch1.request.target == u'/delay/20'
    assert exch1.responses == []


def test_tcpflow_source_port_reused():
    with pytest.raises(InputError):
        load_from_tcpflow('source_port_reused')


def test_tcpflow_wrong_filenames():
    with pytest.raises(InputError):
        load_from_tcpflow('wrong_filenames')


def test_tcpflow_tls():
    [box] = load_from_tcpflow('tls')
    assert box.request is None
    assert box.responses == []
    assert [complaint.id for complaint in box.complaints] == [1279]


def test_tcpick():
    exchanges = load_from_tcpick('httpbin')

    assert exchanges[0].request.method == m.GET
    assert exchanges[0].request.target == u'/get'
    assert exchanges[0].request.version == http11

    assert u'n → ∞' in exchanges[3].responses[0].unicode_body

    assert b'"gzipped": true' in exchanges[4].responses[0].decoded_body

    assert b'"deflated": true' in exchanges[5].responses[0].decoded_body

    assert exchanges[6].responses[0].status == st.no_content
    assert exchanges[6].responses[0].reason == u'NO CONTENT'

    assert exchanges[8].responses[0].body.count(b'{"url":') == 10

    assert len(exchanges[9].responses[0].body) == 1024


def test_tcpick_multiple_connections():
    [exch1, exch2, exch3] = load_from_tcpick('multiple_connections')
    assert exch1.request.target == u'/status/400'
    assert exch2.request.target == u'/status/401'
    assert exch3.request.target == u'/status/402'


def test_tcpick_wrong_filenames():
    with pytest.raises(InputError):
        load_from_tcpick('wrong_filenames')
