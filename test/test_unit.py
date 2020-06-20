import bs4
import shutil
import tempfile
import time
import unittest

from jinja2 import Environment, DictLoader

import six

import slasti


class FakeMark(object):

    def __init__(self, stamp0, ourtag):
        self._stamp0 = stamp0
        self._ourtag = ourtag

    def key(self):
        return (self._stamp0, 0)

    def tag(self):
        return self._ourtag

    def to_jsondict(self, path):
        tag1 = self._ourtag or "test_tag"

        tags = [
            {"href_tag": '%s/%s/' % (path, slasti.escapeURLComponent(tag1)),
             "name_tag": tag1}
        ]

        jsondict = {
            "date": time.strftime("%Y-%m-%d", time.gmtime(self._stamp0)),
            "href_mark": '%s/mark.%d.%02d' % (path, self._stamp0, 0),
            "href_mark_url": slasti.escapeURL("http://www.ibm.com/"),
            "href_edit": '%s/edit?mark=0.0' % (path,),
            "title": "Test_title",
            "note": "",
            "tags": tags,
            "key": "%d.%02d" % (self._stamp0, 0),
        }
        return jsondict

    def succ(self):
        return None

    def pred(self):
        return None


class FakeBase(object):

    def __init__(self, time0=None, tag=None):
        self._time0 = time0
        self._tag = tag or "test"

    def lookup(self, timeint, fix):
        if fix != 0:
            return None
        if timeint != self._time0:
            return None
        return FakeMark(timeint, None)

    def taglookup(self, tag, timeint, fix):
        if fix != 0:
            return None
        if tag != self._tag:
            return None
        return FakeMark(timeint, tag)


class TestUnit(unittest.TestCase):

    def test_difftags(self):
        old = ["tmp", "test"]
        new = ["tmp", "test", "new"]
        res = slasti.tagbase.difftags(old, new)
        self.assertEqual(res[0], [])
        self.assertEqual(res[1], ["new"])

        old = ["tmp", "test"]
        new = ["test"]
        res = slasti.tagbase.difftags(old, new)
        self.assertEqual(res[0], ["tmp"])
        self.assertEqual(res[1], [])

    def test_export(self):

        capt_status = None
        capt_headers = None

        def start_resp(status, headers):
            capt_status = status
            capt_headers = headers

        #c = Cookie.SimpleCookie()
        #c.load(environ['HTTP_COOKIE'])
        c = None

        base_dir = tempfile.mkdtemp()
        user = { 'name':"auser", 'type':"fs", 'root': base_dir }
        base = slasti.tagbase.TagBase(base_dir)
        ctx = slasti.Context("", user, base, 'GET', 'http', 'localhost',
                             'export.xml', None, None, c)
        ctx.j2env = Environment(loader=DictLoader(slasti.main.templates))

        # Ordering is by the timestamp, newest first, not list order.
        # '\xd0\xbf\xd1\x80\xd0\xbe\xd0\xb2\xd0\xb5\xd1\x80\xd0\xba\xd0\xb0'
        # u'\u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430'
        base_sample = [
          {'stamp':  1348242433, 'title':"moo",
           'href':"http://xxxx", 'extra': "", 'tags': "a b c"},
          {'stamp':  1348242431,
           'title': u'\u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430',
           'href':"http://pant.su", 'extra': "", 'tags': "pantsu"}
        ]
        # In theory, two XMLs are equivalent if attributes match, but
        # in practice people run diff on exported files, so we compare
        # outputs literally byte by byte and flag if mismatch.
        # BTW, we use
        export_master = \
            b'<?xml version="1.0" encoding="UTF-8"?>\n' +\
            b'<posts user="auser" tag="">\n' +\
            b'  <post href="http://xxxx" description="moo" ' +\
                b'tag="a b c" time="2012-09-21T15:47:13Z" extended="" />\n' +\
            b'  <post href="http://pant.su" description="\xd0\xbf\xd1\x80' +\
                b'\xd0\xbe\xd0\xb2\xd0\xb5\xd1\x80\xd0\xba\xd0\xb0" ' +\
                b'tag="pantsu" time="2012-09-21T15:47:11Z" extended="" />\n' +\
            b'</posts>\n'
        # Use base itself to populate it.
        base.open()
        for ms in base_sample:
            tags = slasti.tagbase.split_marks(ms['tags'])
            base.add1(ms['stamp'], ms['title'], ms['href'], ms['extra'], tags)

        # Calling app is a more complete way to invoke the application.
        # But it requires cookies to be fully functional for login_verify().
        # So for now we invoke the full_mark_xml directly.
        #app = slasti.main.app
        #output = app(start_resp, ctx)
        #  =>  ctx.flogin = login_verify(ctx)
        output = slasti.main.full_mark_xml(start_resp, ctx)

        export_str = b""
        for chunk in output:
            export_str += chunk
        self.assertEqual(export_str, export_master)

        shutil.rmtree(base_dir)

    def test_fetch_parse(self):

        html1 = """
            <html>
                <title>Simple Test</title>
                <body><p>moo</p></body>
            </html>
        """
        title1 = slasti.main.fetch_parse(html1)
        self.assertEquals('Simple Test', title1)

        html2 = """
            <html>
                <title>The Online Comic &copy;1999-2010 Greg Dean</title>
                <body><p>moo</p></body>
            </html>
        """
        title2 = slasti.main.fetch_parse(html2)
        self.assertEquals(u'The Online Comic \xa91999-2010 Greg Dean', title2)

    def test_ctx_parse_args(self):

        ctx = slasti.Context(
            None, None, None, 'GET', 'http', None, None, None, None, None)

        qd = ctx._parse_args(b"savedref=\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e*")
        self.assertEqual(qd['savedref'], u'\u65e5\u672c\u8a9e*')

        qd = ctx._parse_args(u"savedref=\u65e5\u672c\u8a9e*")
        self.assertEqual(qd['savedref'], u'\u65e5\u672c\u8a9e*')

        qd = ctx._parse_args(b"savedref=%E6%97%A5%E6%9C%AC%E8%AA%9E")
        self.assertEqual(qd['savedref'], u'\u65e5\u672c\u8a9e')

        qd = ctx._parse_args(u"savedref=%E6%97%A5%E6%9C%AC%E8%AA%9E")
        self.assertEqual(qd['savedref'], u'\u65e5\u672c\u8a9e')

    def test_login_form(self):

        # user_password = "PassWord"
        user_entry = {
            "name": "testuser",
            "type": "fs", "root": "/missing",
            "salt": "abcdef",
            "pass": "8bb4b4f91dcfafbfea438ae0132bbd20" }

        status_ = [None]
        headers_ = [None]

        def fake_start_response(status, headers):
            status_[0] = status
            headers_[0] = headers

        ctx = slasti.Context(
            "", user_entry, None,
            'GET', 'http', "localhost:8080", u"/testuser/login",
            b"savedref=\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e",
            None, None)
        ctx.j2env = Environment(loader=DictLoader(slasti.main.templates))
        result_ = slasti.main.login_form(fake_start_response, ctx)

        self.assertTrue(status_[0].startswith("200 "))
        for chunk in result_:
            self.assertTrue(isinstance(chunk, six.binary_type))
        body = b''.join(result_)
        soup = bs4.BeautifulSoup(body, "lxml")
        soup_savedref = None
        for inp in soup.body.form.select('input'):
            if inp['name'] == 'savedref':
                soup_savedref = inp
        self.assertIsNotNone(soup_savedref)
        self.assertEqual(soup_savedref['type'], 'hidden')
        # The actual value is b"\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e", but
        # bs4 auto-converts what it parses to Unicode, using UTF-8 magically.
        # Well, we do have UTF-8 marker in <head> meta.
        self.assertEqual(soup_savedref['value'], u'\u65e5\u672c\u8a9e')

        status_[0] = None
        headers_[0] = None

        ctx = slasti.Context(
            "", user_entry, None,
            'GET', 'http', "localhost:8080", u"/testuser/login",
            u"savedref=\u65e5\u672c\u8a9e",
            None, None)
        ctx.j2env = Environment(loader=DictLoader(slasti.main.templates))
        result_ = slasti.main.login_form(fake_start_response, ctx)

        self.assertTrue(status_[0].startswith("200 "))
        for chunk in result_:
            self.assertTrue(isinstance(chunk, six.binary_type))
        body = b''.join(result_)
        soup = bs4.BeautifulSoup(body, "lxml")
        soup_savedref = None
        for inp in soup.body.form.select('input'):
            if inp['name'] == 'savedref':
                soup_savedref = inp
        self.assertIsNotNone(soup_savedref)
        self.assertEqual(soup_savedref['type'], 'hidden')
        self.assertEqual(soup_savedref['value'], u'\u65e5\u672c\u8a9e')

    def test_login_post(self):

        # user_password = "PassWord"
        user_entry = {
            "name": "testuser",
            "type": "fs", "root": "/missing",
            "salt": "abcdef",
            "pass": "8bb4b4f91dcfafbfea438ae0132bbd20" }

        status_ = [None]
        headers_ = [None]

        def fake_start_response(status, headers):
            status_[0] = status
            headers_[0] = headers

        # First attempt is a bad password.
        # Note that the empty password throws a 400.

        ctx = slasti.Context(
            "", user_entry, None,
            'POST', 'http', "localhost:8080", u"/testuser/login", "",
            u'password=X&OK=Enter&savedref=test', None)
        ctx.j2env = Environment(loader=DictLoader(slasti.main.templates))
        result_ = slasti.main.login_post(fake_start_response, ctx)

        self.assertTrue(status_[0].startswith("403 "))

        headers = dict()
        for t in headers_[0]:
            headers[t[0]] = t[1]
        self.assertTrue(isinstance(headers['Content-type'], str))
        self.assertEquals(headers['Content-type'],
                          'text/plain; charset=utf-8')

        for chunk in result_:
            self.assertTrue(isinstance(chunk, six.binary_type))
        body = b''.join(result_)
        self.assertEqual(
            b'403 Not Permitted: Bad Password\r\n',
            body)

        # Let's try to log in now.

        status_ = [None]
        headers_ = [None]

        ctx = slasti.Context(
            "", user_entry, None,
            'POST', 'http', "localhost:8080", u"/testuser/login", "",
            u'password=PassWord&OK=Enter&savedref=\u30c6\u30b9\u30c8', None)
        ctx.j2env = Environment(loader=DictLoader(slasti.main.templates))
        result_ = slasti.main.login_post(fake_start_response, ctx)

        self.assertTrue(status_[0].startswith("303 "))

        headers = dict()
        for t in headers_[0]:
            headers[t[0]] = t[1]
        self.assertTrue(isinstance(headers['Set-Cookie'], str))
        self.assertIn('login=', headers['Set-Cookie'])
        # Look for "b'str'" in order to catch a stray str(b'str') on py3.
        self.assertNotIn("b'", headers['Set-Cookie'])
        self.assertTrue(isinstance(headers['Location'], str))
        self.assertEquals(headers['Location'],
                          '/testuser/%E3%83%86%E3%82%B9%E3%83%88')

        for chunk in result_:
            self.assertTrue(isinstance(chunk, six.binary_type))

        # Exactly same as the above, only with unicode injected, for py2.

        status_[0] = None
        headers_[0] = None

        ctx = slasti.Context(
            u"", user_entry, None,
            'POST', 'http', "localhost:8080", u"/testuser/login", "",
            u'password=PassWord&OK=Enter&savedref=\u30c6\u30b9\u30c8', None)
        ctx.j2env = Environment(loader=DictLoader(slasti.main.templates))
        result_ = slasti.main.login_post(fake_start_response, ctx)

        self.assertTrue(status_[0].startswith("303 "))

        headers = dict()
        for t in headers_[0]:
            headers[t[0]] = t[1]
        self.assertTrue(isinstance(headers['Set-Cookie'], str))
        self.assertIn('login=', headers['Set-Cookie'])
        # Look for "b'str'" in order to catch a stray str(b'str') on py3.
        self.assertNotIn("b'", headers['Set-Cookie'])
        self.assertTrue(isinstance(headers['Location'], str))
        self.assertEquals(headers['Location'],
                          '/testuser/%E3%83%86%E3%82%B9%E3%83%88')

        for chunk in result_:
            self.assertTrue(isinstance(chunk, six.binary_type))

    def test_get_mark(self):

        stamp0 = 1524461179

        # user_password = "PassWord"
        user_entry = {
            "name": "testuser",
            "type": "fs", "root": "/missing",
            "salt": "abcdef",
            "pass": "8bb4b4f91dcfafbfea438ae0132bbd20" }

        base = FakeBase(time0=stamp0)

        status_ = [None]
        headers_ = [None]

        def fake_start_response(status, headers):
            status_[0] = status
            headers_[0] = headers

        ctx = slasti.Context(
            "", user_entry, base,
            'GET', 'http', "localhost:8080",
            u"/testuser/mark.%d.00" % (stamp0,),
            None, None, None)
        ctx.j2env = Environment(loader=DictLoader(slasti.main.templates))
        result_ = slasti.main.one_mark_html(
            fake_start_response, ctx, stamp0, 0)

        self.assertTrue(status_[0].startswith("200 "))
        for chunk in result_:
            self.assertTrue(isinstance(chunk, six.binary_type))
        body = b''.join(result_)
        soup = bs4.BeautifulSoup(body, "lxml")

        # The body of the mark is just a naked list of <a> tags in a single
        # bulk <p>. So, all we can do is test if expected <a> are present.
        a_result = dict((a['href'], a.string) for a in soup.select('a'))

        # {'/testuser/edit?mark=%d.00': u'\u1F589'} -- only when logged in
        a_pattern = {
            '/testuser/login?savedref=/testuser/mark.%d.00' % stamp0: 'login',
            '/testuser/tags': 'tags',
            '/testuser/test_tag/': 'test_tag',
            '/testuser/mark.%d.00' % stamp0: u'\u2606'}

        for k in a_pattern:
            self.assertIn(k, a_result)
            self.assertEqual(a_result[k], a_pattern[k])

    def test_get_page(self):

        # Our test page contains only one mark, this.
        stamp0 = 1524461179

        # user_password = "PassWord"
        user_entry = {
            "name": "testuser",
            "type": "fs", "root": "/missing",
            "salt": "abcdef",
            "pass": "8bb4b4f91dcfafbfea438ae0132bbd20" }

        base = FakeBase(time0=stamp0)

        status_ = [None]
        headers_ = [None]

        def fake_start_response(status, headers):
            status_[0] = status
            headers_[0] = headers

        ctx = slasti.Context(
            "", user_entry, base,
            'GET', 'http', "localhost:8080",
            u"/testuser/mark.%d.00" % (stamp0,),
            None, None, None)
        ctx.j2env = Environment(loader=DictLoader(slasti.main.templates))
        result_ = slasti.main.page_mark_html(
            fake_start_response, ctx, stamp0, 0)

        self.assertTrue(status_[0].startswith("200 "))
        for chunk in result_:
            self.assertTrue(isinstance(chunk, six.binary_type))
        body = b''.join(result_)
        soup = bs4.BeautifulSoup(body, "lxml")

        p_mark = None
        t_pattern = time.strftime("%Y-%m-%d", time.gmtime(stamp0))
        for p in soup.select('p'):
            t = p.get_text()
            if t and t.startswith(t_pattern):
                p_mark = p
        self.assertIsNotNone(p_mark)

        # We only look at <a> inside the <p> for our mark. This test flags
        # both missing and extra <a> per the mark listed.
        a_result = dict((a['href'], a.string) for a in p_mark.select('a'))
        a_pattern = {
            '/testuser/test_tag/': 'test_tag',
            '/testuser/mark.%d.00' % stamp0: u'\u2606'}
        for k in a_pattern:
            self.assertIn(k, a_result)
            self.assertEqual(a_result[k], a_pattern[k])
