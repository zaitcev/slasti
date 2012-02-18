#
# Slasti -- Main Application
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#

import string
import time
import urllib
import urlparse
import cgi
import base64
import os
import hashlib
import httplib
# XXX sgmllib was removed in Python 3.0
import sgmllib

from slasti import AppError, App400Error, AppLoginError, App404Error
from slasti import AppGetError, AppGetPostError
import slasti
import tagbase

PAGESZ = 25

BLACKSTAR = "&#9733;"
WHITESTAR = "&#9734;"

def page_back(mark):
    mark = mark.pred()
    if mark == None:
        return None
    # In all other cases, we'll return something, even if 1 entry back.
    n = 1
    while n < PAGESZ:
        m = mark.pred()
        if m == None:
            return mark
        mark = m
        n += 1
    return mark

def page_anchor_html(mark, path, text):
    if mark == None:
        return '[-]'
    (stamp0, stamp1) = mark.key()
    return '[<a href="%s/page.%d.%02d">%s</a>]' % (path, stamp0, stamp1, text)

def mark_anchor_html(mark, path, text):
    if mark == None:
        return '[-]'
    (stamp0, stamp1) = mark.key()
    return '[<a href="%s/mark.%d.%02d">%s</a>]' % (path, stamp0, stamp1, text)

def edit_anchor_html(mark, path, text):
    if mark == None:
        return '[-]'
    (stamp0, stamp1) = mark.key()
    return '[<a href="%s/edit?mark=%d.%02d">%s</a>]' % \
           (path, stamp0, stamp1, text)

def tag_anchor_html(tag, path):
    if tag == None:
        return ' -'
    tagu = urllib.quote_plus(tag)
    tagt = unicode(cgi.escape(slasti.safestr(tag)),'utf-8')
    return ' <a href="%s/%s/">%s</a>' % (path, tagu, tagt)

def spit_lead(output, ctx, left_lead):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    output.append('<table width="100%" style="background: #ebf7eb" ' +
                  'border=0 cellpadding=1 cellspacing=0><tr valign="top">\n')
    output.append('<td align="left">%s</td>\n' % left_lead)
    output.append('<td align="right">')
    if ctx.flogin == 0:
        if ctx.path == "" or ctx.path == "login" or ctx.path == "edit":
            output.append(' [<a href="%s/login">login</a>]' % userpath)
        else:
            output.append(' [<a href="%s/login?savedref=%s">login</a>]' %
                          (userpath, ctx.path))
    output.append(' [<b><a href="%s/tags">tags</a></b>]' % userpath)
    output.append(' [<a href="%s/new">new</a>]' % userpath)
    if ctx.flogin == 0:
        output.append(' [e]')
    else:
        output.append(' [<a href="%s/export.xml">e</a>]' % userpath)
    output.append('</td>\n')
    output.append('</tr></table>\n')

# qdic = urlparse.parse_qs(ctx.pinput)
def fix_post_args(qdic):

    # 'href' & 'tags' must be non-empty, other keys are optional
    for arg in ['href', 'tags']:
        if not qdic.has_key(arg):
            raise App400Error("no tag %s" % arg)

    argd = { }
    for arg in ['title', 'href', 'tags', 'extra']:
        # Empty actually ends here (browser may not send a key if empty).
        if not qdic.has_key(arg):
            argd[arg] = ""
            continue
        arglist = qdic[arg]
        # This does not seem to happen even for empties, but be safe.
        if len(arglist) < 1:
            raise App400Error("bad tag %s" % arg)
        # Convert into Unicode, else tagbase.store() blows up when writing.
        argd[arg] = arglist[0].decode("utf-8", 'replace')

    return argd

def findmark(ctx, query):
    qdic = urlparse.parse_qs(query)
    if not qdic.has_key('mark'):
        raise App400Error("no mark tag")
    mlist = qdic['mark']
    if len(mlist) < 1:
        raise App400Error("bad mark tag")
    p = string.split(mlist[0], ".")
    if len(p) != 2:
        raise App400Error("bad mark format")
    try:
        stamp0 = int(p[0])
        stamp1 = int(p[1])
    except ValueError:
        raise App400Error("bad mark format")
    return (stamp0, stamp1)

def findpar(ctx, query, keys):
    qdic = urlparse.parse_qs(query)

    ret = {}
    for key in keys:
        try:
            ret[key] = qdic[key][0]
        except (KeyError, IndexError):
            ret[key] = None

    return ret

def page_any_html(start_response, ctx, mark_top):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    what = mark_top.tag()
    if what == None:
        path = ctx.prefix+'/'+username
        what = BLACKSTAR
    else:
        path = ctx.prefix+'/'+username+'/'+what
        what = what+'/'

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ['<html>\n']
    output.append('<head><meta http-equiv="Content-Type"'+
                  ' content="text/html; charset=UTF-8"></head>\n')
    output.append('<body>\n')

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a> / %s</h2>\n' % \
                (userpath, username, what)
    spit_lead(output, ctx, left_lead)

    mark = mark_top
    mark_next = None
    n = 0
    while n < PAGESZ:
        (stamp0, stamp1) = mark.key()
        datestr = time.strftime("%Y-%m-%d", time.gmtime(stamp0))

        output.append("<p>%s %s " %
                      (datestr, mark_anchor_html(mark, userpath, WHITESTAR)))
        output.append(mark.html())
        output.append("<br>\n")
        for tag in mark.tags:
            output.append(tag_anchor_html(tag, userpath))
        output.append("</p>\n")

        mark_next = mark.succ()
        if mark_next == None:
            break
        mark = mark_next
        n += 1

    output.append("<hr />\n")
    output.append(page_anchor_html(page_back(mark_top), path, "&laquo;"))
    output.append(page_anchor_html(mark_top,            path, BLACKSTAR))
    output.append(page_anchor_html(mark_next,           path, "&raquo;"))
    output.append("<br />\n")

    output.append("</body></html>\n")
    return output

def page_mark_html(start_response, ctx, stamp0, stamp1):
    mark = ctx.base.lookup(stamp0, stamp1)
    if mark == None:
        # We have to have at least one mark to display a page
        raise App404Error("Page not found: "+str(stamp0)+"."+str(stamp1))
    if ctx.method != 'GET':
        raise AppGetError(ctx.method)
    return page_any_html(start_response, ctx, mark)

def page_tag_html(start_response, ctx, tag, stamp0, stamp1):
    mark = ctx.base.taglookup(tag, stamp0, stamp1)
    if mark == None:
        raise App404Error("Tag page not found: "+tag+" / "+
                           str(stamp0)+"."+str(stamp1))
    if ctx.method != 'GET':
        raise AppGetError(ctx.method)
    return page_any_html(start_response, ctx, mark)

def page_empty_html(start_response, ctx):
    start_response("200 OK", [('Content-type', 'text/html')])
    output = ["<html><body>\n"]

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a> / [-]</h2>\n' % \
                (path, ctx.user['name'])
    spit_lead(output, ctx, left_lead)

    output.append("<hr />\n")
    output.append('[-] [-] [-]')
    output.append("<br />\n")

    output.append("</body></html>\n")
    return output

def delete_post(start_response, ctx):
    path = ctx.prefix+'/'+ctx.user['name']

    query = ctx.pinput
    if not query:
        raise App400Error("no mark to delete")
    (stamp0, stamp1) = findmark(ctx, query)
    ctx.base.delete(stamp0, stamp1);

    start_response("200 OK", [('Content-type', 'text/html')])

    output = ['<html>\n']
    output.append('<head><meta http-equiv="Content-Type"'+
                  ' content="text/html; charset=UTF-8"></head>\n')
    output.append('<body>\n')

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a></h2>\n' % \
                (path, ctx.user['name'])
    spit_lead(output, ctx, left_lead)

    output.append('<p>Deleted.</p>\n')
    output.append("</body></html>\n")
    return output

def fetch_url(query):
    if not query:
        raise App400Error("no query")
    qdic = urlparse.parse_qs(query)
    if not qdic.has_key('url'):
        raise App400Error("no url tag")
    urlist = qdic['url']
    if len(urlist) < 1:
        raise App400Error("bad url tag")
    return urlist[0]

class FetchParser(sgmllib.SGMLParser):
    def __init__(self, verbose=0):
        sgmllib.SGMLParser.__init__(self, verbose)
        self.in_title = False
        self.titlestr = None
    def start_title(self, attributes):
        self.in_title = True
    def end_title(self):
        self.in_title = False
    def handle_data(self, data):
        if self.in_title:
            self.titlestr = data

def fetch_parse(chunk):
    parser = FetchParser()
    parser.feed(chunk)
    parser.close()
    if parser.titlestr == None:
        return "(none)"
    return parser.titlestr

# XXX This may need switching to urllib yet, if 301 redirects become a problem.
def fetch_body(url):
    # XXX Seriously, sanitize url before parsing

    scheme, host, path, u_par, u_query, u_frag = urlparse.urlparse(url)
    if scheme != 'http' and scheme != 'https':
        raise App400Error("bad url scheme")

    headers = {}
    # XXX Forward the Referer: that we received from the client, if any.

    if scheme == 'http':
        conn = httplib.HTTPConnection(host, timeout=25)
    else:
        conn = httplib.HTTPSConnection(host, timeout=25)

    conn.request("GET", path, None, headers)
    response = conn.getresponse()
    # XXX A different return code for 201 and 204?
    if response.status != 200:
        raise App400Error("target error %d" % response.status)

    typeval = response.getheader("Content-Type")
    if typeval == None:
        raise App400Error("target no type")
    typestr = string.split(typeval, ";")
    if len(typestr) == 0:
        raise App400Error("target type none")
    if typestr[0] != 'text/html':
        raise App400Error("target type %s" % typestr[0])

    body = response.read(10000)
    return body

#
# The server-side indirection requires extreme care to prevent abuse.
# User may hit us with URLs that point to generated pages, slow servers, etc.
# As the last resort, we never work as a generic proxy.
#
def fetch_get(start_response, ctx):
    url = fetch_url(ctx.query)
    body = fetch_body(url)
    title = fetch_parse(body)

    output = ['%s\r\n' % title]
    start_response("200 OK", [('Content-type', 'text/plain')])
    return output

def mark_post(start_response, ctx, mark):
    argd = fix_post_args(urlparse.parse_qs(ctx.pinput))

    tags = tagbase.split_marks(argd['tags'])
    (stamp0, stamp1) = mark.key()
    ctx.base.edit1(stamp0, stamp1,
                   argd['title'], argd['href'], argd['extra'], tags)

    # Since the URL stays the same, we eschew 303 here.
    # Just re-read the base entry with a lookup and pretend this was a GET.
    mark = ctx.base.lookup(stamp0, stamp1)
    if mark == None:
        raise App404Error("Mark not found: "+str(stamp0)+"."+str(stamp1))
    return mark_get(start_response, ctx, mark, stamp0)

def mark_get(start_response, ctx, mark, stamp0):
    path = ctx.prefix+'/'+ctx.user['name']

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ['<html>\n']
    output.append('<head><meta http-equiv="Content-Type"'+
                  ' content="text/html; charset=UTF-8"></head>\n')
    output.append('<body>\n')

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a></h2>\n' % \
                (path, ctx.user['name'])
    spit_lead(output, ctx, left_lead)

    output.append("<p>")
    datestr = time.strftime("%Y-%m-%d", time.gmtime(stamp0))
    output.append(datestr)
    output.append("<br>\n")
    output.append(mark.html())
    output.append("<br>\n")
    for tag in mark.tags:
        output.append(tag_anchor_html(tag, path))
    output.append("</p>\n")

    # This looks ugly in browser.
    if ctx.flogin != 0:
       output.append("<p>")
       output.append(edit_anchor_html(mark, path, "edit"))
       output.append("</p>\n")

    output.append("<hr />\n")
    output.append(mark_anchor_html(mark.pred(), path, "&laquo;"))
    output.append(mark_anchor_html(mark,        path, WHITESTAR))
    output.append(mark_anchor_html(mark.succ(), path, "&raquo;"))
    output.append("<br />\n")

    output.append("</body></html>\n")
    return output

def one_mark_html(start_response, ctx, stamp0, stamp1):
    mark = ctx.base.lookup(stamp0, stamp1)
    if mark == None:
        raise App404Error("Mark not found: "+str(stamp0)+"."+str(stamp1))
    if ctx.method == 'GET':
        return mark_get(start_response, ctx, mark, stamp0)
    if ctx.method == 'POST':
        if ctx.flogin == 0:
            raise AppLoginError()
        return mark_post(start_response, ctx, mark)
    raise AppGetPostError(ctx.method)

def root_mark_html(start_response, ctx):
    if ctx.method != 'GET':
        raise AppGetError(ctx.method)
    mark = ctx.base.first()
    if mark == None:
        return page_empty_html(start_response, ctx)
    return page_any_html(start_response, ctx, mark)
    ## The non-paginated version
    #
    # response_headers = [('Content-type', 'text/html')]
    # start_response("200 OK", response_headers)
    # output = ["<html><body>\n"]
    #
    # left_lead = '  <h2 style="margin-bottom:0">'+\
    #             '<a href="%s/">%s</a></h2>\n' % \
    #             (ctx.path, ctx.user['name']))
    # spit_lead(output, ctx, left_lead)
    #
    # for mark in base:
    #     (stamp0, stamp1) = mark.key()
    #     datestr = time.strftime("%Y-%m-%d", time.gmtime(stamp0))
    #
    #     output.append("<p>%s %s " % \
    #                   (datestr, mark_anchor_html(mark, ctx.path, WHITESTAR)))
    #     output.append(mark.html())
    #     output.append("</p>\n")
    #
    # output.append("</body></html>\n")
    # return output

def root_tag_html(start_response, ctx, tag):
    mark = ctx.base.tagfirst(tag)
    if mark == None:
        # Not sure if this may happen legitimately, so 404 for now.
        raise App404Error("Tag page not found: "+tag)
    if ctx.method != 'GET':
        raise AppGetError(ctx.method)
    return page_any_html(start_response, ctx, mark)

# full_mark_html() would be a Netscape bookmarks file, perhaps.
def full_mark_xml(start_response, ctx):
    if ctx.method != 'GET':
        raise AppGetError(ctx.method)
    response_headers = [('Content-type', 'text/xml')]
    start_response("200 OK", response_headers)
    output = []
    output.append('<?xml version="1.0" encoding="UTF-8"?>\n')
    # <posts user="zaitcev" update="2010-12-16T20:17:55Z" tag="" total="860">
    # We omit total. Also, we noticed that Del.icio.us often miscalculates
    # the total, so obviously it's not used by any applications.
    # We omit the last update as well. Our data base does not keep it.
    output.append('<posts user="'+ctx.user['name']+'" tag="">\n')
    for mark in ctx.base:
        output.append(mark.xml())
    output.append("</posts>\n")
    return output

def full_tag_html(start_response, ctx):
    if ctx.method != 'GET':
        raise AppGetError(ctx.method)
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ['<html>\n']
    output.append('<head><meta http-equiv="Content-Type"'+
                  ' content="text/html; charset=UTF-8"></head>\n')
    output.append('<body>\n')

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a> / tags</h2>\n' % \
                (userpath, username)
    spit_lead(output, ctx, left_lead)

    output.append("<p>")
    for tag in ctx.base.tagcurs():
        ref = tag.key()
        output.append('<a href="%s/%s/">%s</a> %d<br />\n' %
                      (userpath, ref, ref, tag.num()))
    output.append("</p>")

    output.append("<hr />\n")

    output.append("</body></html>\n")
    return output

def login_findref(qdic):
    if not qdic.has_key('savedref'):
        return None
    qlist = qdic['savedref']
    if len(qlist) < 1:
        return None
    return qlist[0]

def login_form(start_response, ctx):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    if ctx.query == None:
        savedref = None
    else:
        qdic = urlparse.parse_qs(ctx.query)
        savedref = login_findref(qdic)

    start_response("200 OK", [('Content-type', 'text/html')])

    output = ['<html>\n']
    output.append('<head><meta http-equiv="Content-Type"'+
                  ' content="text/html; charset=UTF-8"></head>\n')
    output.append('<body>\n')
    output.append('<form action="%s/login" method="POST">\n' % userpath)
    output.append(
        '  %s: <input name=password type=password size=32 maxlength=32 />\n' %
        username)
    output.append('  <input name=OK type=submit value="Enter" />\n')
    if savedref:
        output.append('  <input name=savedref type=hidden value="%s" />\n' %
                      savedref)
    output.append('</form>\n')
    output.append("</body></html>\n")
    return output

def login_post(start_response, ctx):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    # pinput = "password=test&OK=Enter" and possibly a newline
    qdic = urlparse.parse_qs(ctx.pinput)

    savedref = login_findref(qdic)
    if savedref:
        savedref = savedref.decode("utf-8", 'replace')
        redihref = "%s/%s" % (userpath, savedref)
    else:
        redihref = "%s/" % userpath;

    if not qdic.has_key('password'):
        raise App400Error("no password tag")
    plist = qdic['password']
    if len(plist) < 1:
        raise App400Error("bad password tag")
    password = plist[0]
    if len(password) < 1:
        raise App400Error("empty password")

    # We do not require every user to have a password, in order to have
    # archive users or other pseudo-users. They cannot login, even if they
    # fake the login cookies.
    if not ctx.user.has_key('salt'):
        raise AppError("User with no salt: "+username)
    if not ctx.user.has_key('pass'):
        raise AppError("User with no password: "+username)

    pwhash = hashlib.md5()
    pwhash.update(ctx.user['salt']+password)
    pwstr = pwhash.hexdigest()

    # We operate on a hex of the salted password's digest, to avoid parsing.
    if pwstr != ctx.user['pass']:
        start_response("403 Not Permitted", [('Content-type', 'text/plain')])
        return ["403 Not Permitted: Bad Password\r\n"]

    csalt = base64.b64encode(os.urandom(6))
    flags = "-"
    nowstr = "%d" % int(time.time())
    opdata = csalt+","+flags+","+nowstr

    coohash = hashlib.sha256()
    coohash.update(ctx.user['pass']+opdata)
    # We use hex instead of base64 because it's easy to test in shell.
    mdstr = coohash.hexdigest()

    response_headers = [('Content-type', 'text/html')]
    # Set an RFC 2901 cookie (not RFC 2965).
    response_headers.append(('Set-Cookie', "login=%s:%s" % (opdata, mdstr)))
    response_headers.append(('Location', slasti.safestr(redihref)))
    start_response("303 See Other", response_headers)

    output = ['<html>\n']
    output.append('<head><meta http-equiv="Content-Type"'+
                  ' content="text/html; charset=UTF-8"></head>\n')
    output.append('<body>\n')
    output.append('<p><a href="%s">See Other</a></p>\n' % redihref)
    output.append('</body></html>\n')
    return output

def login(start_response, ctx):
    if ctx.method == 'GET':
        return login_form(start_response, ctx)
    if ctx.method == 'POST':
        return login_post(start_response, ctx)
    raise AppGetPostError(ctx.method)

def login_verify(ctx):
    if not ctx.user.has_key('pass'):
        return 0
    if ctx.cookies == None:
        return 0
    if not ctx.cookies.has_key('login'):
        return 0

    cval = ctx.cookies['login'].value
    (opdata, xhash) = cval.split(':')
    (csalt,flags,whenstr) = opdata.split(',')
    try:
        when = int(whenstr)
    except ValueError:
        return 0
    now = int(time.time())
    if now < when or now >= when + 1209600:
        return 0
    if flags != '-':
        return 0

    coohash = hashlib.sha256()
    coohash.update(ctx.user['pass']+opdata)
    mdstr = coohash.hexdigest()

    if mdstr != xhash:
        return 0

    return 1

def new_form(start_response, ctx):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username
    editpath = ctx.prefix+'/edit.js'
    fetchpath = userpath+'/fetchtitle'

    query = ctx.query
    if not query:
        title = None
        href = None
    else:
        rdic = findpar(ctx, query, ['title', 'href'])
        # not sure if the quote is necessary but let's be safe w/ user input
        title = urllib.quote_plus(rdic['title'])
        href = urllib.quote_plus(rdic['href'])

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ['<html>\n']
    output.append('<head><meta http-equiv="Content-Type"'+
                  ' content="text/html; charset=UTF-8"></head>\n')
    output.append('<body>\n')

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a> / [%s]</h2>\n' % \
                (userpath, username, WHITESTAR)
    spit_lead(output, ctx, left_lead)

    title_id = "title1"
    button_id = "button1"
    output.append('<script src="%s"></script>\n' % editpath)
    # The "editform" has to be a paramter to preload_title() too. Maybe later.
    output.append('<form action="%s/edit" method="POST" name="editform">' %
                   userpath)
    output.append(' <table>\n<tr>\n')
    output.append('  <td>Title\n'+
                  '  <td><input name="title" type="text"'+
                  ' size=80 maxlength=1023 id="%s"' % title_id)
    if title:
        output.append(' value="%s"' % title)
    output.append(' />\n');
    output.append('      <input name="preload" value="Preload" type="button"')
    strfmt = "&quot;%s&quot;"
    hanfmt = ' onclick="preload_title(%s,%s,%s);"' % (strfmt,strfmt,strfmt)
    output.append(hanfmt % (fetchpath, title_id, button_id))
    output.append(' id="%s">\n' % button_id)

    output.append(' </tr><tr>\n')
    output.append('  <td>URL '+
                  '  <td><input name="href" type="text"'+
                  ' size=95 maxlength=1023')
    if href:
        output.append(' value="%s"' % href)
    output.append(' />\n')
    output.append(' </tr><tr>\n')
    output.append('  <td>tags '+
                  '  <td><input name="tags" type="text"'+
                  ' size=95 maxlength=1023 />\n')
    output.append(' </tr><tr>\n')
    output.append('  <td>Extra '+
                  '  <td><input name="extra" type="text"'+
                  ' size=95 maxlength=1023 />\n')
    output.append(' </tr><tr>\n')
    output.append('  <td colspan=2>'+
                  ' <input name=action type=submit value="Save" />\n')
    output.append(' </tr></table>')
    output.append('</form>\n')

    output.append("<hr />\n")
    output.append("</body></html>\n")
    return output

def edit_form(start_response, ctx):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    query = ctx.query
    if not query:
        raise App400Error("not mark parameter")

    (stamp0, stamp1) = findmark(ctx, query)
    mark = ctx.base.lookup(stamp0, stamp1)
    if mark == None:
        raise App400Error("not found: "+str(stamp0)+"."+str(stamp1))

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ['<html>\n']
    output.append('<head><meta http-equiv="Content-Type"'+
                  ' content="text/html; charset=UTF-8"></head>\n')
    output.append('<body>\n')

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a> / %s</h2>\n' % \
                (userpath, username,
                 mark_anchor_html(mark, userpath, WHITESTAR))
    spit_lead(output, ctx, left_lead)

    output.append('<form action="%s/mark.%d.%02d" method="POST">\n' %
                   (userpath, stamp0, stamp1))
    output.append(' <table>\n<tr>\n')

    output.append('  <td>Title\n'+
                  '  <td><input name="title" type="text"'+
                  ' size=80 maxlength=1023'+
                  ' value="%s" />\n' % cgi.escape(mark.title, 1))
    output.append(' </tr><tr>\n')
    output.append('  <td>URL '+
                  '  <td><input name="href" type="text"'+
                  ' size=95 maxlength=1023'+
                  ' value="%s" />\n' % cgi.escape(mark.url, 1))
    output.append(' </tr><tr>\n')
    tagstr = " ".join(mark.tags)
    # tagstr = cgi.escape(tagstr, 1)
    output.append('  <td>tags '+
                  '  <td><input name="tags" type="text"'+
                  ' size=95 maxlength=1023'+
                  ' value="%s" />\n' % tagstr)
    output.append(' </tr><tr>\n')
    # notestr = cgi.escape(slasti.safestr(mark.note), 1)
    notestr = cgi.escape(mark.note, 1)
    output.append('  <td>Extra '+
                  '  <td><input name="extra" type="text"'+
                  ' size=95 maxlength=1023'+
                  ' value="%s" />\n' % notestr)
    output.append(' </tr><tr>\n')
    output.append('  <td colspan=2>\n')
    output.append('   <input name=action type=submit value="Save" />\n')
    output.append(' </tr></table>\n')
    output.append('</form>\n')

    output.append('<p>or</p>\n')
    output.append('<form action="%s/delete" method="POST">\n' % (userpath))
    output.append('  <input name=mark type=hidden value="%d.%02d" />\n' %
                   (stamp0, stamp1))
    output.append('  <input name=action type=submit value="Delete" />\n')
    output.append('  (There is no undo.)\n')
    output.append('</form>\n')

    output.append("<hr />\n")
    output.append("</body></html>\n")
    return output

# The name edit_post() is a bit misleading, because POST to /edit is used
# to create new marks, not to edit existing ones (see mark_post() for that).
def edit_post(start_response, ctx):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    argd = fix_post_args(urlparse.parse_qs(ctx.pinput))
    tags = tagbase.split_marks(argd['tags'])

    stamp0 = int(time.time())
    stamp1 = ctx.base.add1(stamp0,
                           argd['title'], argd['href'], argd['extra'], tags)
    if stamp1 < 0:
        raise App404Error("Out of fix: %d" % stamp0)

    redihref = '%s/mark.%d.%02d' % (userpath, stamp0, stamp1)

    response_headers = [('Content-type', 'text/html')]
    response_headers.append(('Location', slasti.safestr(redihref)))
    start_response("303 See Other", response_headers)

    output = ['<html>\n']
    output.append('<head><meta http-equiv="Content-Type"'+
                  ' content="text/html; charset=UTF-8"></head>\n')
    output.append('<body>\n')
    output.append('<p><a href="%s">See Other</a></p>\n' % redihref)
    output.append('</body></html>\n')
    return output

def new(start_response, ctx):
    if ctx.method == 'GET':
        return new_form(start_response, ctx)
    raise AppGetError(ctx.method)

def edit(start_response, ctx):
    if ctx.method == 'GET':
        return edit_form(start_response, ctx)
    if ctx.method == 'POST':
        return edit_post(start_response, ctx)
    raise AppGetPostError(ctx.method)

def delete(start_response, ctx):
    if ctx.method == 'POST':
        return delete_post(start_response, ctx)
    raise AppPostError(ctx.method)

def fetch_title(start_response, ctx):
    if ctx.method == 'GET':
        return fetch_get(start_response, ctx)
    raise AppGetError(ctx.method)

#
# Request paths:
#   ''                  -- default index (page.XXXX.XX)
#   page.1296951840.00  -- page off this down
#   mark.1296951840.00
#   export.xml          -- del-compatible XML
#   new                 -- GET for the form
#   edit                -- PUT or POST here, GET may have ?query
#   delete              -- POST
#   fetchtitle          -- GET with ?query
#   login               -- GET or POST to obtain a cookie (not snoop-proof)
#   anime/              -- tag (must have slash)
#   anime/page.1293667202.11  -- tag page off this down
#   moo.xml/            -- tricky tag
#   page.1293667202.11/ -- even trickier tag
#
def app(start_response, ctx):
    ctx.flogin = login_verify(ctx)

    if ctx.path == "login":
        return login(start_response, ctx)
    if ctx.path == "new":
        if ctx.flogin == 0:
            raise AppLoginError()
        return new(start_response, ctx)
    if ctx.path == "edit":
        if ctx.flogin == 0:
            raise AppLoginError()
        return edit(start_response, ctx)
    if ctx.path == "delete":
        if ctx.flogin == 0:
            raise AppLoginError()
        return delete(start_response, ctx)
    if ctx.path == "fetchtitle":
        if ctx.flogin == 0:
            raise AppLoginError()
        return fetch_title(start_response, ctx)
    if ctx.path == "":
        return root_mark_html(start_response, ctx)
    if ctx.path == "export.xml":
        if ctx.flogin == 0:
            raise AppLoginError()
        return full_mark_xml(start_response, ctx)
    if ctx.path == "tags":
        return full_tag_html(start_response, ctx)
    if "/" in ctx.path:
        # Trick: by splitting with limit 2 we prevent users from poisoning
        # the tag with slashes. Not that it matters all that much, but still.
        p = string.split(ctx.path, "/", 2)
        tag = p[0]
        page = p[1]
        if page == "":
            return root_tag_html(start_response, ctx, tag)
        p = string.split(page, ".")
        if len(p) != 3:
            raise App404Error("Not found: "+ctx.path)
        try:
            stamp0 = int(p[1])
            stamp1 = int(p[2])
        except ValueError:
            raise App404Error("Not found: "+ctx.path)
        if p[0] == "page":
            return page_tag_html(start_response, ctx, tag, stamp0, stamp1)
        raise App404Error("Not found: "+ctx.path)
    else:
        p = string.split(ctx.path, ".")
        if len(p) != 3:
            raise App404Error("Not found: "+ctx.path)
        try:
            stamp0 = int(p[1])
            stamp1 = int(p[2])
        except ValueError:
            raise App404Error("Not found: "+ctx.path)
        if p[0] == "mark":
            return one_mark_html(start_response, ctx, stamp0, stamp1)
        if p[0] == "page":
            return page_mark_html(start_response, ctx, stamp0, stamp1)
        raise App404Error("Not found: "+ctx.path)
