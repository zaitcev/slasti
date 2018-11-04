import shutil
import tempfile
import unittest

import slasti

import six

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
            'GET', 'http', "localhost:8080", b"/testuser/login",
            b"savedref=\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e",
            None, None)
        result_ = slasti.main.login_form(fake_start_response, ctx)

        self.assertTrue(status_[0].startswith("200 "))
        for chunk in result_:
            self.assertTrue(isinstance(chunk, six.binary_type))
        body = b''.join(result_)
        # Strictly speaking, we should be parsing the HTML, but it takes
        # too much work and adds dependencies.
        self.assertIn(
            b'<input name=savedref type=hidden '
            b'value="\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e" />',
            body)

        status_[0] = None
        headers_[0] = None

        ctx = slasti.Context(
            "", user_entry, None,
            'GET', 'http', "localhost:8080", b"/testuser/login",
            u"savedref=\u65e5\u672c\u8a9e",
            None, None)
        result_ = slasti.main.login_form(fake_start_response, ctx)

        self.assertTrue(status_[0].startswith("200 "))
        for chunk in result_:
            self.assertTrue(isinstance(chunk, six.binary_type))
        body = b''.join(result_)
        self.assertIn(
            b'<input name=savedref type=hidden '
            b'value="\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e" />',
            body)

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
            'POST', 'http', "localhost:8080", b"/testuser/login", "",
            u'password=X&OK=Enter&savedref=test', None)
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
            'POST', 'http', "localhost:8080", b"/testuser/login", "",
            u'password=PassWord&OK=Enter&savedref=\u30c6\u30b9\u30c8', None)
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
