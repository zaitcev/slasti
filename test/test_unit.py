import shutil
import tempfile
import unittest

import slasti

class TestUnit(unittest.TestCase):

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
            '<?xml version="1.0" encoding="UTF-8"?>\n' +\
            '<posts user="auser" tag="">\n' +\
            '  <post href="http://xxxx" description="moo" ' +\
                 'tag="a b c" time="2012-09-21T15:47:13Z" extended="" />\n' +\
            '  <post href="http://pant.su" description="\xd0\xbf\xd1\x80' +\
                 '\xd0\xbe\xd0\xb2\xd0\xb5\xd1\x80\xd0\xba\xd0\xb0" ' +\
                 'tag="pantsu" time="2012-09-21T15:47:11Z" extended="" />\n' +\
            '</posts>\n'
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

        export_str = ""
        for chunk in output:
            export_str += chunk
        self.assertEquals(export_str, export_master)

        shutil.rmtree(base_dir)