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
import Cookie

from slasti import AppError, App400Error, App404Error, AppGetError

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
    tagt = cgi.escape(tag)
    return ' <a href="%s/%s/">%s</a>' % (path, tagu, tagt)

def spit_lead(output, ctx, left_lead):
    path = ctx.prefix+'/'+ctx.user['name']

    output.append('<table width="100%" style="background: #ebf7eb" ' +
                  'border=0 cellpadding=1 cellspacing=0><tr valign="top">\n')
    output.append('<td align="left">%s</td>\n' % left_lead)
    output.append('<td align="right">')
    if ctx.flogin == 0:
        output.append(' [<a href="%s/login">login</a>]' % path)
    output.append(' [<b><a href="%s/tags">tags</a></b>]' % path)
    output.append(' [<a href="%s/edit">new</a>]' % path)
    if ctx.flogin == 0:
        output.append(' [e]')
    else:
        output.append(' [<a href="%s/export.xml">e</a>]' % path)
    output.append('</td>\n')
    output.append('</tr></table>\n')

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
    output = ["<html><body>\n"]

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
    return page_any_html(start_response, ctx, mark)

def page_tag_html(start_response, ctx, tag, stamp0, stamp1):
    mark = ctx.base.taglookup(tag, stamp0, stamp1)
    if mark == None:
        raise App404Error("Tag page not found: "+tag+" / "+
                           str(stamp0)+"."+str(stamp1))
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

def one_mark_html(start_response, ctx, stamp0, stamp1):
    mark = ctx.base.lookup(stamp0, stamp1)
    if mark == None:
        raise App404Error("Mark not found: "+str(stamp0)+"."+str(stamp1))

    path = ctx.prefix+'/'+ctx.user['name']

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ["<html><body>\n"]

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

def root_mark_html(start_response, ctx):
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
    return page_any_html(start_response, ctx, mark)

# full_mark_html() would be a Netscape bookmarks file, perhaps.
def full_mark_xml(start_response, user, base):
    response_headers = [('Content-type', 'text/xml')]
    start_response("200 OK", response_headers)
    output = []
    output.append('<?xml version="1.0" encoding="UTF-8"?>')
    # <posts user="zaitcev" update="2010-12-16T20:17:55Z" tag="" total="860">
    # We omit total. Also, we noticed that Del.icio.us often miscalculates
    # the total, so obviously it's not used by any applications.
    # We omit the last update as well. Our data base does not keep it.
    output.append('<posts user="'+user['name']+'" tag="">\n')
    for mark in base:
        output.append(mark.xml())
    output.append("</posts>\n")
    return output

def full_tag_html(start_response, ctx):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ["<html><body>\n"]

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

def login_form(start_response, ctx):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    start_response("200 OK", [('Content-type', 'text/html')])

    output = ["<html><body>\n"]
    output.append('<form action="%s/login" method=POST>' % userpath)
    output.append(
        '  %s: <input name=password type=password size=32 maxlength=32 />' %
        username)
    output.append('  <input name=OK type=submit value="Enter" />\n')
    output.append('</form>\n')
    output.append("</body></html>\n")
    return output

def login_post(start_response, ctx):

    # XXX verify encoding application/x-www-form-urlencoded
    # pinput = "password=test&OK=Enter" and possibly a newline
    qdic = urlparse.parse_qs(ctx.pinput)
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
        raise AppError("User with no salt: "+ctx.user['name'])
    if not ctx.user.has_key('pass'):
        raise AppError("User with no password: "+ctx.user['name'])

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
    start_response("200 OK", response_headers)

    # XXX Replace with going the previous URL or root.
    output = ["<html><body>\n"]
    output.append("<p>OK</p>\n")
    output.append("</body></html>\n")
    return output

def login(start_response, ctx):
    if ctx.method == 'GET':
        return login_form(start_response, ctx)
    if ctx.method == 'POST':
        return login_post(start_response, ctx)
    start_response("405 Method Not Allowed",
                   [('Content-type', 'text/plain'),
                    ('Allow', 'GET, POST')])
    return ["405 Method %s not allowed\r\n" % ctx.method]

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
    if now < when:
        return 0
    if flags != '-':
        return 0

    coohash = hashlib.sha256()
    coohash.update(ctx.user['pass']+opdata)
    mdstr = coohash.hexdigest()

    if mdstr != xhash:
        return 0

    return 1

def edit_findmark(ctx, query):
    if query == None or query == "":
        return None

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

    mark = ctx.base.lookup(stamp0, stamp1)
    if mark == None:
        raise App400Error("not found: "+str(stamp0)+"."+str(stamp1))
    return mark

def edit_form_new(output, ctx):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a> / [%s]</h2>\n' % \
                (userpath, username, WHITESTAR)
    spit_lead(output, ctx, left_lead)

    output.append('<form action="%s/edit" method=POST>' % userpath)
    output.append('  title '+
                  '<input name=title type=text size=100 maxlength=1023 /><br>')
    output.append('  URL '+
                  '<input name=href type=text size=100 maxlength=1023 /><br />')
    output.append('  tags '+
                  '<input name=tags type=text size=100 maxlength=1023 /><br />')
    output.append('  extra '+
                  '<input name=extra type=text size=100 maxlength=1023 /><br>')
    output.append('  <input name=action type=submit value="OK" />\n')
    output.append('</form>\n')

def edit_form_mark(output, ctx, mark):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a> / %s</h2>\n' % \
                (userpath, username,
                 mark_anchor_html(mark, userpath, WHITESTAR))
    spit_lead(output, ctx, left_lead)

    (stamp0, stamp1) = mark.key()
    output.append('<form action="%s/mark.%d.%02d" method=POST>' %
                   (userpath, stamp0, stamp1))

    output.append('  title '+
                  '<input name=title type=text size=100 maxlength=1023'+
                  ' value="%s" /><br>' % mark.title)
    output.append('  URL '+
                  '<input name=href type=text size=100 maxlength=1023'+
                  ' value="%s" /><br>' % mark.url)
    tagstr = " ".join(mark.tags)
    # tagstr = cgi.escape(tagstr, 1)
    output.append('  tags '+
                  '<input name=tags type=text size=100 maxlength=1023'+
                  ' value="%s" /><br>' % tagstr)
    output.append('  extra '+
                  '<input name=extra type=text size=100 maxlength=1023'+
                  ' value="%s" /><br>' % mark.note)
    output.append('  <input name=action type=submit value="OK" />\n')
    output.append('</form>\n')

    ## Do we need a cancel? A link to old mark may be helpful....
    # output.append('<form action="%s/mark.%d.%02d" method=GET>' %
    #                (userpath, stamp0, stamp1))
    # output.append('  <input name=action type=submit value="Cancel" />\n')
    # output.append('</form>\n')

def edit_form(start_response, ctx):
    username = ctx.user['name']
    userpath = ctx.prefix+'/'+username

    mark = edit_findmark(ctx, ctx.query)

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ["<html><body>\n"]
    if mark == None:
        edit_form_new(output, ctx)
    else:
        edit_form_mark(output, ctx, mark)
    output.append("<hr />\n")
    output.append("</body></html>\n")
    return output

def edit_post(start_response, ctx):
    start_response("403 Not Permitted", [('Content-type', 'text/plain')])
    return ["Post mark does not work yet\r\n"]

def edit(start_response, ctx):
    if ctx.method == 'GET':
        return edit_form(start_response, ctx)
    if ctx.method == 'POST':
        return edit_post(start_response, ctx)
    start_response("405 Method Not Allowed",
                   [('Content-type', 'text/plain'),
                    ('Allow', 'GET, POST')])
    return ["405 Method %s not allowed\r\n" % ctx.method]

#
# Request paths:
#   ''                  -- default index (page.XXXX.XX)
#   page.1296951840.00  -- page off this down
#   mark.1296951840.00
#   export.xml          -- del-compatible XML
#   edit                -- PUT or POST here (XXX protect)
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
    if ctx.path == "edit":
        if ctx.flogin == 0:
            start_response("403 Not Permitted",
                           [('Content-type', 'text/plain')])
            return ["403 Not Logged In\r\n"]
        return edit(start_response, ctx)

    if ctx.method != 'GET':
        raise AppGetError(ctx.method)

    if ctx.path == "":
        return root_mark_html(start_response, ctx)
    if ctx.path == "export.xml":
        if ctx.flogin == 0:
            start_response("403 Not Permitted",
                           [('Content-type', 'text/plain')])
            return ["403 Not Logged In\r\n"]
        return full_mark_xml(start_response, ctx.user, ctx.base)
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
