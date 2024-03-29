#
# Slasti -- Main Application
#
# Copyright (C) 2011 Pete Zaitcev
#           (C) 2012 Christian Aichinger
# See file COPYING for licensing information (expect GPL 2).
#

import base64
import bs4
import hashlib
import os
import time

from jinja2 import Environment, DictLoader, select_autoescape

from six.moves import http_client
from six.moves.urllib.parse import quote, urlsplit

from slasti import (
   AppError, App400Error, AppLoginError, App404Error, AppGetError,
   AppGetHeadError, AppGetHeadPostError, AppGetPostError)
import slasti

PAGESZ = 25

BLACKSTAR = u"\u2605"     # "&#9733;"
WHITESTAR = u"\u2606"     # "&#9734;"

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

def page_anchor_href(mark, path):
    if mark == None:
        return None
    (stamp0, stamp1) = mark.key()
    return '%s/page.%d.%02d' % (path, stamp0, stamp1)

def mark_anchor_href(mark, path):
    if mark == None:
        return None
    (stamp0, stamp1) = mark.key()
    return '%s/mark.%d.%02d' % (path, stamp0, stamp1)

def find_post_args(ctx):
    rdic = {}
    for key in ['title', 'href', 'tags', 'extra']:
        rdic[key] = ctx.get_pinput_arg(key) or ""

    if not rdic["href"] or not rdic["tags"]:
        raise App400Error("The URL and tags are mandatory")

    return rdic

def findmark(mark_str):
    if not mark_str:
        raise App400Error("no mark tag")
    p = mark_str.split(".")
    try:
        stamp0 = int(p[0])
        stamp1 = int(p[1])
    except (ValueError, IndexError):
        raise App400Error("bad mark format")
    return (stamp0, stamp1)

def page_any_html(start_response, ctx, mark_top, headonly=False):
    userpath = ctx.prefix+'/'+ctx.user['name']

    jsondict = ctx.create_jsondict()

    what = mark_top.tag()
    if what:
        path = userpath + '/' + slasti.escapeURL(what)
        jsondict['main_text_ext'] = what+'/'
    else:
        path = userpath
        jsondict['main_text_ext'] = BLACKSTAR

    jsondict["marks"] = []

    mark = mark_top
    mark_next = None
    n = 0
    for n in range(PAGESZ):
        jsondict["marks"].append(mark.to_jsondict(userpath))

        mark_next = mark.succ()
        if mark_next == None:
            break
        mark = mark_next

    jsondict.update({
        "page_prev_href": page_anchor_href(page_back(mark_top), path),
        "page_this_href": page_anchor_href(mark_top,            path),
        "page_this_text": BLACKSTAR,
        "page_next_href": page_anchor_href(mark_next,           path)
    })

    start_response("200 OK", [('Content-type', 'text/html; charset=utf-8')])
    if headonly:
        return [b'']
    template = ctx.j2env.get_template('page.html')
    result = template.render(**jsondict)
    return [result.encode('utf-8')]

def page_mark_html(start_response, ctx, stamp0, stamp1):
    mark = ctx.base.lookup(stamp0, stamp1)
    if mark == None:
        # We have to have at least one mark to display a page
        raise App404Error("Page not found: "+str(stamp0)+"."+str(stamp1))
    if ctx.method == 'GET':
        return page_any_html(start_response, ctx, mark)
    if ctx.method == 'HEAD':
        return page_any_html(start_response, ctx, mark, headonly=True)
    raise AppGetHeadError(ctx.method)

def page_tag_html(start_response, ctx, tag, stamp0, stamp1):
    mark = ctx.base.taglookup(tag, stamp0, stamp1)
    if mark == None:
        raise App404Error("Tag page not found: "+tag+" / "+
                           str(stamp0)+"."+str(stamp1))
    if ctx.method == 'GET':
        return page_any_html(start_response, ctx, mark)
    if ctx.method == 'HEAD':
        return page_any_html(start_response, ctx, mark, headonly=True)
    raise AppGetHeadError(ctx.method)

def page_empty_html(start_response, ctx, headonly=False):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    jsondict = ctx.create_jsondict()
    jsondict['main_text_ext'] = '[-]'

    start_response("200 OK", [('Content-type', 'text/html; charset=utf-8')])
    if headonly:
        return [b'']
    template = ctx.j2env.get_template('empty.html')
    result = template.render(**jsondict)
    return [result.encode('utf-8')]

def delete_post(start_response, ctx):
    userpath = ctx.prefix+'/'+ctx.user['name']

    (stamp0, stamp1) = findmark(ctx.get_pinput_arg("mark"))

    mark = ctx.base.lookup(stamp0, stamp1)
    if not mark:
        raise App400Error("not found: "+str(stamp0)+"."+str(stamp1))
    tags = mark.tags

    ctx.base.delete(stamp0, stamp1);

    jsondict = ctx.create_jsondict()

    jsondict["tags"] = []
    for ref in tags:
        tag = ctx.base.keylookup(ref)
        if tag is None:
            continue
        jsondict["tags"].append(
            {"href_tag": '%s/%s/' % (userpath, slasti.escapeURLComponent(ref)),
             "name_tag": ref,
             "num_tagged": tag.num(),
            })

    start_response("200 OK", [('Content-type', 'text/html; charset=utf-8')])
    template = ctx.j2env.get_template('delete.html')
    result = template.render(**jsondict)
    return [result.encode('utf-8')]

def fetch_parse(chunk):
    # BeautifulSoup prints a warning about "using the best available HTML
    # parser for this system" if defaults are used, so we must specify "lxml".
    soup = bs4.BeautifulSoup(chunk, "lxml")
    titlestr = soup.head.title.get_text()
    return titlestr

# XXX This may need switching to urllib yet, if 301 redirects become a problem.
def fetch_body(url):
    # XXX Seriously, sanitize url before parsing

    scheme, host, path, u_query, u_frag = urlsplit(url)
    if scheme != 'http' and scheme != 'https':
        raise App400Error("bad url scheme")

    headers = {}
    # XXX Forward the Referer: that we received from the client, if any.

    if scheme == 'http':
        conn = http_client.HTTPConnection(host, timeout=25)
    else:
        conn = http_client.HTTPSConnection(host, timeout=25)

    # Unfortunately, passing a scheme of None blows up in py3 when coercing
    # the arguments of urlunsplit(): None is mistaken for bytes (not an str).
    # fullpath = urlunsplit((None, None, path, u_query, None))
    fullpath = path + '?' + u_query if u_query else path

    conn.request("GET", fullpath, None, headers)
    response = conn.getresponse()
    # XXX A different return code for 201 and 204?
    if response.status != 200:
        raise App400Error("target error %d" % response.status)

    typeval = response.getheader("Content-Type")
    if typeval == None:
        raise App400Error("target no type")
    typestr = typeval.split(";")
    if len(typestr) == 0:
        raise App400Error("target type none")
    if typestr[0] != 'text/html':
        raise App400Error("target type %s" % typestr[0])

    body = response.read(10000)
    return body

#
# The server-side indirection requires extreme care to prevent abuse.
# User may hit us with URLs that point to generated pages, slow servers, etc.
# Also, security. As the first defense, we require user to be logged in.
# As the last resort, we never work as a generic proxy: only return the title.
#
def fetch_get(start_response, ctx):
    url = ctx.get_query_arg("url")
    if not url:
        raise App400Error("no query")
    body = fetch_body(url)
    title = fetch_parse(body)

    output = [b'%s\r\n' % slasti.safestr(title)]
    start_response("200 OK", [('Content-type', 'text/plain')])
    return output

def mark_post(start_response, ctx, mark):
    argd = find_post_args(ctx)

    tags = slasti.tagbase.split_marks(argd['tags'])
    (stamp0, stamp1) = mark.key()
    ctx.base.edit1(stamp0, stamp1,
                   argd['title'], argd['href'], argd['extra'], tags)

    # Since the URL stays the same, we eschew 303 here.
    # Just re-read the base entry with a lookup and pretend this was a GET.
    mark = ctx.base.lookup(stamp0, stamp1)
    if mark == None:
        raise App404Error("Mark not found: "+str(stamp0)+"."+str(stamp1))
    return mark_get(start_response, ctx, mark)

def mark_get(start_response, ctx, mark, headonly=False):
    path = ctx.prefix+'/'+ctx.user['name']

    if ctx.ims_ts and mark.mtime and mark.mtime <= ctx.ims_ts:
        (stamp0, stamp1) = mark.key()
        redihref = slasti.to_str('%s/mark.%d.%02d' % (path, stamp0, stamp1))
        response_headers = [('Content-type', 'text/html; charset=utf-8')]
        response_headers.append(('Content-Location', redihref))
        start_response("304 Not Modified", response_headers)
        return [b'']

    jsondict = ctx.create_jsondict()
    jsondict.update({
        "page_prev_href": mark_anchor_href(mark.pred(), path),
        "page_this_href": mark_anchor_href(mark,        path),
        "page_this_text": WHITESTAR,
        "page_next_href": mark_anchor_href(mark.succ(), path)
    })
    jsondict.update({"mark": mark.to_jsondict(path)})

    start_response("200 OK", [('Content-type', 'text/html; charset=utf-8')])
    if headonly:
        return [b'']
    template = ctx.j2env.get_template('mark.html')
    result = template.render(**jsondict)
    return [result.encode('utf-8')]

def one_mark_html(start_response, ctx, stamp0, stamp1):
    mark = ctx.base.lookup(stamp0, stamp1)
    if mark == None:
        raise App404Error("Mark not found: "+str(stamp0)+"."+str(stamp1))
    if ctx.method == 'GET':
        return mark_get(start_response, ctx, mark)
    if ctx.method == 'HEAD':
        return mark_get(start_response, ctx, mark, headonly=True)
    if ctx.method == 'POST':
        if ctx.flogin == 0:
            raise AppLoginError()
        return mark_post(start_response, ctx, mark)
    raise AppGetHeadPostError(ctx.method)

def root_mark_html(start_response, ctx):
    if ctx.method == 'GET':
        mark = ctx.base.first()
        if mark == None:
            return page_empty_html(start_response, ctx)
        return page_any_html(start_response, ctx, mark)
    if ctx.method == 'HEAD':
        mark = ctx.base.first()
        if mark == None:
            return page_empty_html(start_response, ctx, headonly=True)
        return page_any_html(start_response, ctx, mark, headonly=True)
    raise AppGetHeadError(ctx.method)

def root_tag_html(start_response, ctx, tag):
    mark = ctx.base.tagfirst(tag)
    if mark == None:
        # Not sure if this may happen legitimately, so 404 for now.
        raise App404Error("Tag page not found: "+tag)
    if ctx.method == 'GET':
        return page_any_html(start_response, ctx, mark)
    if ctx.method == 'HEAD':
        return page_any_html(start_response, ctx, mark, headonly=True)
    raise AppGetHeadError(ctx.method)

class MarkDumper(object):
    def __init__(self, base, user):
        self.username = user['name']
        self.base = slasti.tagbase.TagBase(base.dirname)
    # <posts user="zaitcev" update="2010-12-16T20:17:55Z" tag="" total="860">
    # We omit total. Also, we noticed that Del.icio.us often miscalculates
    # the total, so obviously it's not used by any applications.
    # We omit the last update as well. Our data base does not keep it.
    def __iter__(self):
        self.base.open()
        try:
            yield b'<?xml version="1.0" encoding="UTF-8"?>\n'
            yield b'<posts user="'+slasti.safestr(self.username)+b'" tag="">\n'
            for mark in self.base:
                yield slasti.safestr(mark.xml())
            yield b'</posts>\n'
        finally:
            self.base.close()

# full_mark_html() would be a Netscape bookmarks file, perhaps.
def full_mark_xml(start_response, ctx):
    if ctx.method != 'GET':
        raise AppGetError(ctx.method)
    response_headers = [('Content-type', 'text/xml; charset=utf-8')]
    start_response("200 OK", response_headers)
    return MarkDumper(ctx.base, ctx.user)

def full_tag_html(start_response, ctx):
    if ctx.method == 'HEAD':
        start_response("200 OK",
                       [('Content-type', 'text/html; charset=utf-8')])
        return [b'']

    if ctx.method != 'GET':
        raise AppGetHeadError(ctx.method)

    userpath = ctx.prefix + '/' + ctx.user['name']
    start_response("200 OK", [('Content-type', 'text/html; charset=utf-8')])
    jsondict = ctx.create_jsondict()
    jsondict['main_text_ext'] = 'tags'
    jsondict["tags"] = []
    for tag in ctx.base.tagcurs():
        ref = tag.key()
        jsondict["tags"].append(
            {"href_tag": '%s/%s/' % (userpath, slasti.escapeURLComponent(ref)),
             "name_tag": ref,
             "num_tagged": tag.num(),
            })
    template = ctx.j2env.get_template('tags.html')
    result = template.render(**jsondict)
    return [result.encode('utf-8')]

def login_form(start_response, ctx):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username
    savedref = ctx.get_query_arg("savedref")

    start_response("200 OK", [('Content-type', 'text/html; charset=utf-8')])
    jsondict = ctx.create_jsondict()
    jsondict.update({
            "username": username,
            "action_login": "%s/login" % userpath,
            "savedref": savedref,
            })
    template = ctx.j2env.get_template('login.html')
    result = template.render(**jsondict)
    return [result.encode('utf-8')]

def login_post(start_response, ctx):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    # pinput = "password=test&OK=Enter" and possibly a newline
    savedref = ctx.get_pinput_arg("savedref")
    if savedref:
        redihref = "%s/%s" % (userpath,
                              quote(slasti.safestr(savedref)))
    else:
        redihref = "%s/" % userpath;
    redihref = slasti.to_str(redihref)

    password = ctx.get_pinput_arg("password")
    if not password:
        raise App400Error("bad password tag")

    # We do not require every user to have a password, in order to have
    # archive users or other pseudo-users. They cannot login, even if they
    # fake the login cookies.
    if 'salt' not in ctx.user:
        raise AppError("User with no salt: "+username)
    if 'pass' not in ctx.user:
        raise AppError("User with no password: "+username)

    pwhash = hashlib.md5()
    pwhash.update((ctx.user['salt']+password).encode('utf-8'))
    pwstr = pwhash.hexdigest()

    # We operate on a hex of the salted password's digest, to avoid parsing.
    if pwstr != ctx.user['pass']:
        start_response("403 Not Permitted",
                      [('Content-type', 'text/plain; charset=utf-8')])
        template = ctx.j2env.get_template('simple.txt')
        result = template.render(output="403 Not Permitted: Bad Password\r\n")
        return [result.encode('utf-8')]

    csalt = slasti.to_str(base64.b64encode(os.urandom(6)))
    flags = "-"
    nowstr = "%d" % int(time.time())
    opdata = csalt+","+flags+","+nowstr

    coohash = hashlib.sha256()
    coohash.update((ctx.user['pass']+opdata).encode('utf-8'))
    # We use hex instead of base64 because it's easy to test in shell.
    mdstr = coohash.hexdigest()

    response_headers = [('Content-type', 'text/plain')]
    # Set an RFC 2901 cookie (not RFC 2965).
    response_headers.append(('Set-Cookie', "login=%s:%s" % (opdata, mdstr)))
    response_headers.append(('Location', redihref))
    start_response("303 See Other", response_headers)

    jsondict = { "href_redir": redihref }
    template = ctx.j2env.get_template('redirect.html')
    result = template.render(**jsondict)
    return [result.encode('utf-8')]

def login(start_response, ctx):
    if ctx.method == 'GET':
        return login_form(start_response, ctx)
    if ctx.method == 'POST':
        return login_post(start_response, ctx)
    raise AppGetPostError(ctx.method)

def login_verify(ctx):
    if 'pass' not in ctx.user:
        return 0
    if ctx.cookies == None:
        return 0
    if 'login' not in ctx.cookies:
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
    coohash.update((ctx.user['pass']+opdata).encode('utf-8'))
    mdstr = coohash.hexdigest()

    if mdstr != xhash:
        return 0

    return 1

def new_form(start_response, ctx):
    userpath = ctx.prefix + '/' + ctx.user['name']
    title = ctx.get_query_arg('title')
    href = ctx.get_query_arg('href')

    jsondict = ctx.create_jsondict()
    jsondict['main_text_ext'] = '['+WHITESTAR+']'
    jsondict.update({
            "id_title": "title1",
            "id_button": "button1",
            "href_editjs": ctx.prefix + '/edit.js',
            "href_fetch": userpath + '/fetchtitle',
            "mark": None,
            "action_edit": userpath + '/edit',
            "val_title": title or "",
            "val_href": href or "",
        })

    start_response("200 OK", [('Content-type', 'text/html; charset=utf-8')])
    template = ctx.j2env.get_template('editform.html')
    result = template.render(**jsondict)
    return [result.encode('utf-8')]

def edit_form(start_response, ctx):
    userpath = ctx.prefix + '/' + ctx.user['name']

    (stamp0, stamp1) = findmark(ctx.get_query_arg("mark"))
    mark = ctx.base.lookup(stamp0, stamp1)
    if not mark:
        raise App400Error("not found: "+str(stamp0)+"."+str(stamp1))

    jsondict = ctx.create_jsondict()
    jsondict['main_path_ext'] = mark_anchor_href(mark, userpath)
    jsondict['main_text_ext'] = WHITESTAR
    jsondict.update({
        "id_title": "title1",
        "id_button": "button1",
        "href_editjs": ctx.prefix + '/edit.js',
        "href_fetch": userpath + '/fetchtitle',
        "mark": mark.to_jsondict(userpath),
        "action_edit": "%s/mark.%d.%02d" % (userpath, stamp0, stamp1),
        "action_delete": userpath + '/delete',
        "val_title": mark.title,
        "val_href": mark.url,
        "val_tags": ' '.join(mark.tags),
        "val_note": mark.note,
        })

    start_response("200 OK", [('Content-type', 'text/html; charset=utf-8')])
    template = ctx.j2env.get_template('editform.html')
    result = template.render(**jsondict)
    return [result.encode('utf-8')]

# The name edit_post() is a bit misleading, because POST to /edit is used
# to create new marks, not to edit existing ones (see mark_post() for that).
def edit_post(start_response, ctx):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    argd = find_post_args(ctx)
    tags = slasti.tagbase.split_marks(argd['tags'])

    stamp0 = int(time.time())
    stamp1 = ctx.base.add1(stamp0,
                           argd['title'], argd['href'], argd['extra'], tags)
    if stamp1 < 0:
        raise App404Error("Out of fix: %d" % stamp0)

    redihref = slasti.to_str('%s/mark.%d.%02d' % (userpath, stamp0, stamp1))

    response_headers = [('Content-type', 'text/html; charset=utf-8')]
    response_headers.append(('Location', redihref))
    start_response("303 See Other", response_headers)

    jsondict = { "href_redir": redihref }
    template = ctx.j2env.get_template('redirect.html')
    result = template.render(**jsondict)
    return [result.encode('utf-8')]

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

def redirect_to_login(start_response, ctx):
    userpath = ctx.prefix + '/' + ctx.user['name']
    thisref = ctx.path
    login_loc = slasti.to_str(
        userpath + '/login?savedref=' + quote(slasti.safestr(thisref)))
    response_headers = [('Content-type', 'text/html; charset=utf-8')]
    response_headers.append(('Location', login_loc))
    start_response("303 See Other", response_headers)

    jsondict = { "href_redir": login_loc }
    template = ctx.j2env.get_template('redirect.html')
    result = template.render(**jsondict)
    return [result.encode('utf-8')]

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
    ctx.j2env = Environment(loader=DictLoader(templates),
        autoescape=select_autoescape(['html', 'xml']))

    if ctx.path == "login":
        return login(start_response, ctx)
    if ctx.path == "new":
        if ctx.flogin == 0:
            return redirect_to_login(start_response, ctx)
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
        p = ctx.path.split("/", 2)
        tag = p[0]
        page = p[1]
        if page == "":
            return root_tag_html(start_response, ctx, tag)
        p = page.split(".")
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
        p = ctx.path.split(".")
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

template_header = \
"""
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
</head>
<style type="text/css">
  body {
    background-color: white;
  }
</style>
<body>
"""

# The &href should be escaped in inline script (although Firefox eats it fine)

template_body_top = \
"""
<table width="100%" style="background: #ebf7eb"
 border=0 cellpadding=1 cellspacing=0>
<tr valign="top">
    <td align="left">
        <h2 style="margin-bottom:0">
          <a href="{{ main_path }}/">{{ main_text }}</a>
          {% if main_text_ext %}
            /
            {% if main_path_ext %}
              <a href="{{ main_path_ext }}">{{ main_text_ext }}</a>
            {% else %}
              {{ main_text_ext }}
            {% endif %}
          {% endif %}
        </h2>

    </td>
    <td align="right">
        {% if flogin %}
          [<a href="{{ href_new }}">new</a>]
          [<a href="javascript:
 var F=document;
 ref = '';
 ref += '{{ hrefa_new }}';
 ref += '?title=' + F.title;
 ref += '&href=' + location.href;
 F.location = ref" title="Drag This To Toolbar">bm</a>]
          [<a href="{{ href_export }}">e</a>]
        {% else %}
          [<a href="{{ href_login }}">login</a>]
        {% endif %}
        [<b><a href="{{ href_tags }}">tags</a></b>]
    </td>
</tr></table>
"""

template_body_bottom = \
"""
<hr />
{% if page_prev_href %}
    [<a href="{{ page_prev_href }}">&laquo;</a>]
{% else %}
    [-]
{% endif %}
{% if page_this_href %}
    [<a href="{{ page_this_href }}">{{ page_this_text }}</a>]
{% else %}
    [{{ page_this_text }}]
{% endif %}
{% if page_next_href %}
    [<a href="{{ page_next_href }}">&raquo;</a>]
{% else %}
    [-]
{% endif %}
</body></html>
"""

template_page = \
"""
    {% include 'header.html' %}
    {% include 'body_top.html' %}
    {% for mark in marks %}
      <p>{{ mark.date }} [<a href="{{ mark.href_mark }}">&#9734;</a>]
       {% if flogin %}
         [<a href="{{ mark.href_edit }}">&#128393;</a>]
       {% endif %}
       <a href="{{ mark.href_mark_url }}">{{ mark.title }}</a>
       {% if mark.note %}
         <br />{{ mark.note }}
       {% endif %}
       <br />
       {% for tag in mark.tags %}
         <a href="{{ tag.href_tag }}">{{ tag.name_tag }}</a>
       {% endfor %}
      </p>
    {% endfor %}
    {% include 'body_bottom.html' %}
"""

template_empty = \
"""
    {% include 'header.html' %}
    {% include 'body_top.html' %}
    {% include 'body_bottom.html' %}
"""

template_mark = \
"""
    {% include 'header.html' %}
    {% include 'body_top.html' %}
    <p>{{ mark.date }}<br />
       {% if flogin %}
         [<a href="{{ mark.href_edit }}">&#128393;</a>]<br />
       {% endif %}
       <a href="{{ mark.href_mark_url }}">{{ mark.title }}</a> <br />
       {% if mark.note %}
         {{ mark.note }}<br />
       {% endif %}
       {% for tag in mark.tags %}
         <a href="{{ tag.href_tag }}">{{ tag.name_tag }}</a>
       {% endfor %}
    </p>
    {% include 'body_bottom.html' %}
"""

template_tags = \
"""
{% include 'header.html' %}
{% include 'body_top.html' %}
<p>
    {% for tag in tags %}
       <a href="{{ tag.href_tag }}">{{ tag.name_tag }}</a>
         {{ tag.num_tagged }}<br />
    {% endfor %}
</p>
<hr />
</body></html>
"""

template_delete = \
"""
{% include 'header.html' %}
{% include 'body_top.html' %}
  <p>Deleted.</p>
  <p>
    {% for tag in tags %}
       <a href="{{ tag.href_tag }}">{{ tag.name_tag }}</a>
         {{ tag.num_tagged }}<br />
    {% endfor %}
  </p>
</body></html>
"""

template_login = \
"""
{% include 'header.html' %}
{% include 'body_top.html' %}
  <div align="center">
    <form action="{{ action_login }}" method="POST">
      Password:
      <input name=password type=password size=32 maxlength=32 />
      <input name=OK type=submit value="Enter" />
      {% if savedref %}
          <input name=savedref type=hidden value="{{ savedref }}" />
      {% endif %}
    </form>
  </div>
</body>
</html>
"""

template_redirect = \
"""
    {% include 'header.html' %}
    <p><a href="{{ href_redir }}">See Other</a></p>
    </body></html>
"""

template_editform = \
"""
{% include 'header.html' %}
{% include 'body_top.html' %}
    <script src="{{ href_editjs }}"></script>
    <form action="{{ action_edit }}" method="POST" name="editform">
     <table>
     <tr>
      <td>Title
      <td>
        <input name="title" type="text" size=80 maxlength=1023
               id="{{ id_title }}" value="{{ val_title }}" />
        {% if mark is none %}
          <input name="preload" value="Preload" type="button"
                 id="{{ id_button }}"
                 onclick="preload_title(
                     '{{href_fetch}}','{{id_title}}','{{id_button}}');" />
        {% endif %}
     </tr><tr>
      <td>URL
      <td><input name="href" type="text" size=95 maxlength=1023
                 value="{{ val_href }}" />
     </tr><tr>
      <td>tags
      <td><input name="tags" type="text" size=95 maxlength=1023
                 value="{{ val_tags }}" />
     </tr><tr>
      <td>Extra
      <td><input name="extra" type="text" size=95 maxlength=1023
                 value="{{ val_note }}" />
     </tr><tr>
      <td colspan=2><input name=action type=submit value="Save" />
     </tr></table>
    </form>

    {% if action_delete %}
    <p>or</p>
    <form action="{{ action_delete }}" method="POST">
      <input name=mark type=hidden value="{{ mark.key }}" />
      <input name=action type=submit value="Delete" />
      (There is no undo.)
    </form>
    {% endif %}
    <hr />
    </body></html>
"""

template_simple_output = """{{ output }}"""

templates = {
    'body_bottom.html': template_body_bottom,
    'body_top.html': template_body_top,
    'delete.html': template_delete,
    'editform.html': template_editform,
    'empty.html': template_empty,
    'header.html': template_header,
    'login.html': template_login,
    'mark.html': template_mark,
    'page.html': template_page,
    'redirect.html': template_redirect,
    'simple.txt': template_simple_output,
    'tags.html': template_tags
}
