#
# Slasti -- Main Application
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#

import string
import time
import urllib
import cgi

from slasti import AppError, App404Error, AppGetError

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

def tag_anchor_html(tag, path):
    if tag == None:
        return ' -'
    tagu = urllib.quote_plus(tag)
    tagt = cgi.escape(tag)
    return ' <a href="%s/%s/">%s</a>' % (path, tagu, tagt)

def spit_lead(output, path, left_lead):
    output.append('<table width="100%" style="background: #ebf7eb" ' +
                  'border=0 cellpadding=1 cellspacing=0><tr valign="top">\n')
    output.append('<td align="left">%s</td>\n' % left_lead)
    output.append('<td align="right">')
    output.append(' [<a href="%s/tags">tags</a>]' % path)
    output.append(' [<a href="%s/newmark">n</a>]' % path)
    output.append(' [<a href="%s/export.xml">e</a>]' % path)
    output.append('</td>\n')
    output.append('</tr></table>')

def page_any_html(start_response, pfx, user, base, mark_top):
    username = user['name']
    userpath = pfx+'/'+username

    what = mark_top.tag()
    if what == None:
        path = pfx+'/'+username
        what = BLACKSTAR
    else:
        path = pfx+'/'+username+'/'+what
        what = what+'/'

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ["<html><body>\n"]

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a> / %s</h2>\n' % \
             (userpath, username, what)
    spit_lead(output, userpath, left_lead)

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

def page_mark_html(start_response, pfx, user, base, stamp0, stamp1):
    mark = base.lookup(stamp0, stamp1)
    if mark == None:
        # We have to have at least one mark to display a page
        raise App404Error("Page not found: "+str(stamp0)+"."+str(stamp1))
    return page_any_html(start_response, pfx, user, base, mark)

def page_tag_html(start_response, pfx, user, base, tag, stamp0, stamp1):
    mark = base.taglookup(tag, stamp0, stamp1)
    if mark == None:
        raise App404Error("Tag page not found: "+tag+" / "+\
                           str(stamp0)+"."+str(stamp1))
    return page_any_html(start_response, pfx, user, base, mark)

def page_empty_html(start_response, pfx, user, base):
    path = pfx+'/'+user['name']

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ["<html><body>\n"]

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a> / [-]</h2>\n' % \
                (path, user['name'])
    spit_lead(output, path, left_lead)

    output.append("<hr />\n")
    output.append('[-] [-] [-]')
    output.append("<br />\n")

    output.append("</body></html>\n")
    return output

def one_mark_html(start_response, pfx, user, base, stamp0, stamp1):
    mark = base.lookup(stamp0, stamp1)
    if mark == None:
        raise App404Error("Mark not found: "+str(stamp0)+"."+str(stamp1))

    path = pfx+'/'+user['name']

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ["<html><body>\n"]

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a></h2>\n' % \
                (path, user['name'])
    spit_lead(output, path, left_lead)

    output.append("<p>")
    datestr = time.strftime("%Y-%m-%d", time.gmtime(stamp0))
    output.append(datestr)
    output.append("<br>\n")
    output.append(mark.html())
    output.append("<br>\n")
    for tag in mark.tags:
        output.append(tag_anchor_html(tag, path))
    output.append("</p>\n")

    output.append("<hr />\n")
    output.append(mark_anchor_html(mark.pred(), path, "&laquo;"))
    output.append(mark_anchor_html(mark,        path, WHITESTAR))
    output.append(mark_anchor_html(mark.succ(), path, "&raquo;"))
    output.append("<br />\n")

    output.append("</body></html>\n")
    return output

def root_mark_html(start_response, pfx, user, base):
    mark = base.first()
    if mark == None:
        return page_empty_html(start_response, pfx, user, base)
    return page_any_html(start_response, pfx, user, base, mark)
    ## The non-paginated version
    #
    # response_headers = [('Content-type', 'text/html')]
    # start_response("200 OK", response_headers)
    # output = ["<html><body>\n"]
    #
    # left_lead = '  <h2 style="margin-bottom:0">'+\
    #             '<a href="%s/">%s</a></h2>\n' % \
    #             (path, user['name']))
    # spit_lead(output, path, left_lead)
    #
    # for mark in base:
    #     (stamp0, stamp1) = mark.key()
    #     datestr = time.strftime("%Y-%m-%d", time.gmtime(stamp0))
    #
    #     output.append("<p>%s %s " % \
    #                   (datestr, mark_anchor_html(mark, path, WHITESTAR)))
    #     output.append(mark.html())
    #     output.append("</p>\n")
    #
    # output.append("</body></html>\n")
    # return output

def root_tag_html(start_response, pfx, user, base, tag):
    mark = base.tagfirst(tag)
    if mark == None:
        # Not sure if this may happen legitimately, so 404 for now.
        raise App404Error("Tag page not found: "+tag)
    return page_any_html(start_response, pfx, user, base, mark)

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

def full_tag_html(start_response, pfx, user, base):
    username = user['name']
    userpath = pfx+'/'+username

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ["<html><body>\n"]

    left_lead = '  <h2 style="margin-bottom:0">'+\
                '<a href="%s/">%s</a> / tags</h2>\n' % \
                (userpath, username)
    spit_lead(output, userpath, left_lead)

    output.append("<p>")
    for tag in base.tagcurs():
        ref = tag.key()
        output.append('<a href="%s/%s/">%s</a> %d<br />\n' %
                      (userpath, ref, ref, tag.num()))
    output.append("</p>")

    output.append("<hr />\n")

    output.append("</body></html>\n")
    return output

def login_form(start_response, pfx, user, base):
    username = user['name']
    userpath = pfx+'/'+username

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

def login_post(start_response, pfx, user, base, pinput):

    # XXX verify encoding application/x-www-form-urlencoded or whatever

    # pinput = "password=test&OK=Enter" and possibly a newline

    response_headers = [('Content-type', 'text/html')]
    # Set an RFC 2901 cookie (not RFC 2965).
    response_headers.append(('Set-Cookie', 'moo=a'))
    start_response("200 OK", response_headers)

    # XXX Replace with going the previous URL or root.
    output = ["<html><body>\n"]
    output.append("<p>OK</p>\n")
    output.append("</body></html>\n")
    return output

def login(start_response, pfx, user, base, method, pinput):
    if method == 'GET':
        return login_form(start_response, pfx, user, base)
    if method == 'POST':
        return login_post(start_response, pfx, user, base, pinput)
    start_response("405 Method Not Allowed",
                   [('Content-type', 'text/plain'),
                    ('Allow', 'GET, POST')])
    return ["Method %s not allowed\r\n" % method]

#
# Request paths:
#   ''                  -- default index (page.XXXX.XX)
#   page.1296951840.00  -- page off this down
#   mark.1296951840.00
#   export.xml          -- del-compatible XML
#   newmark             -- PUT or POST here (XXX protect)
#   login               -- GET or POST to obtain a cookie (not snoop-proof)
#   anime/              -- tag (must have slash)
#   anime/page.1293667202.11  -- tag page off this down
#   moo.xml/            -- tricky tag
#   page.1293667202.11/ -- even trickier tag
#
def app(start_response, pfx, user, base, method, pinput, reqpath):
    if reqpath == "login":
        return login(start_response, pfx, user, base, method, pinput)

    if method != 'GET':
        raise AppGetError(method)

    if reqpath == "":
        return root_mark_html(start_response, pfx, user, base)
    if reqpath == "export.xml":
        return full_mark_xml(start_response, user, base)
    if reqpath == "newmark":
        start_response("403 Not Permitted", [('Content-type', 'text/plain')])
        return ["New mark does not work yet\r\n"]
    if reqpath == "tags":
        return full_tag_html(start_response, pfx, user, base)
    if "/" in reqpath:
        # Trick: by splitting with limit 2 we prevent users from poisoning
        # the tag with slashes. Not that it matters all that much, but still.
        p = string.split(reqpath, "/", 2)
        tag = p[0]
        page = p[1]
        if page == "":
            return root_tag_html(start_response, pfx, user, base, tag)
        p = string.split(page, ".")
        if len(p) != 3:
            raise App404Error("Not found: "+reqpath)
        try:
            stamp0 = int(p[1])
            stamp1 = int(p[2])
        except ValueError:
            raise App404Error("Not found: "+reqpath)
        if p[0] == "page":
            return page_tag_html(start_response, pfx, user, base, tag,
                                 stamp0, stamp1)
        raise App404Error("Not found: "+reqpath)
    else:
        p = string.split(reqpath, ".")
        if len(p) != 3:
            raise App404Error("Not found: "+reqpath)
        try:
            stamp0 = int(p[1])
            stamp1 = int(p[2])
        except ValueError:
            raise App404Error("Not found: "+reqpath)
        if p[0] == "mark":
            return one_mark_html(start_response, pfx, user, base,
                                 stamp0, stamp1)
        if p[0] == "page":
            return page_mark_html(start_response, pfx, user, base,
                                  stamp0, stamp1)
        raise App404Error("Not found: "+reqpath)
