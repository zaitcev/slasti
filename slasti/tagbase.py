#
# Slasti -- Mark/Tag database
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#
# requires:
#  codecs
#
import string
import codecs
(utf8_encode, utf8_decode, utf8_reader, utf8_writer) = codecs.lookup("utf-8")
import os
import errno
import time
# import urllib
import cgi

from slasti import AppError

# We are not aware of any specification, so it is unclear if tags are split
# by space or whitespace. We assume space, to be locale-independent.
# But this means that we include tabs and foreign whitespace into tags.
def split_tags(tagstr):
    tags = []
    for t in tagstr.split(' '):
        if t != '':
            tags.append(t)
    return tags

#
# TagMark is one bookmark when we manipulate it (extracted from TagBase).
#
class TagMark:
    def __init__(self, base, tagname, marklist, markindex):
        markname = marklist[markindex]

        self.base = base
        self.ourtag = tagname
        self.ourlist = marklist
        self.ourindex = markindex

        self.stamp0 = 0
        self.stamp1 = 0
        self.title = "-"
        self.url = "-"
        self.note = ""
        self.tags = []

        try:
            f = open(base.markdir+"/"+markname, "r")
        except IOError:
            # Set a red tag to tell us where we crashed.
            self.stamp1 = 1
            return

        s = f.readline()
        if s == None or len(s) == 0:
            self.stamp1 = 2
            f.close()
            return
        # Format is defined as two integers over a dot, which unfortunately
        # looks like a decimal fraction. Should've used a space. Oh well.
        slist = string.split(string.rstrip(s, "\r\n"), ".")
        if len(slist) != 2:
            self.stamp1 = 3
            f.close()
            return

        try:
            self.stamp0 = int(slist[0])
            self.stamp1 = int(slist[1])
        except ValueError:
            self.stamp1 = 4
            f.close()
            return

        s = f.readline()
        if s == None or len(s) == 0:
            f.close()
            return
        self.title = string.rstrip(s, "\r\n");

        s = f.readline()
        if s == None or len(s) == 0:
            f.close()
            return
        self.url = string.rstrip(s, "\r\n");

        s = f.readline()
        if s == None or len(s) == 0:
            f.close()
            return
        self.note = string.rstrip(s, "\r\n");

        s = f.readline()
        if s == None or len(s) == 0:
            f.close()
            return

        self.tags = string.split(string.rstrip(s, "\r\n"))

        f.close()

    def __str__(self):
        # There do not seem to be any exceptions raised with weird inputs.
        datestr = time.strftime("%Y-%m-%d", time.gmtime(self.stamp0))
        return self.ourlist[self.ourindex]+'|'+datestr+'|'+\
               self.title+'|'+self.url+'|'+self.note+"|"+str(self.tags)

    def key(self):
        return (self.stamp0, self.stamp1)

    def tag(self):
        return self.ourtag;

    def html(self):
        title = self.title
        if len(title) == 0:
            title = self.url
        title = cgi.escape(title, 1)

        # The urllib.quote_plus does not work as expected: it escapes ':' and
        # such too, so "http://host" turns into "http%3A//host", and this
        # corrupts the link. So, hand-roll quotes and XML escapes for now.
        ## url = urllib.quote_plus(self.url)
        url = self.url
        url = url.replace('"', '%22')
        url = url.replace('&', '%26')
        url = url.replace('<', '%3C')
        url = url.replace('>', '%3E')

        tagstr = cgi.escape(" ".join(self.tags), 1)

        anchor = '<a href="'+url+'">'+title+'</a>'

        note = self.note
        if len(note) == 0:
            return anchor

        note = cgi.escape(note)
        return anchor+"<br />"+note

    def xml(self):
        datestr = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.stamp0))

        title = self.title
        title = cgi.escape(title, 1)

        url = self.url;
        url = cgi.escape(url, 1)

        tagstr = " ".join(self.tags)
        tagstr = cgi.escape(tagstr, 1)

        note = self.note
        note = cgi.escape(note, 1)

        # Del.icio.us also export hash="" (MD5 of URL in href) and meta=""
        # (MD5 of unknown content). We don't know if this is needed for anyone.
        fmt = '  <post href="%s" description="%s" tag="%s" time="%s"'+\
              ' extended="%s" />\n'
        return fmt % (url, title, tagstr, datestr, note)

    def succ(self):
        if self.ourindex+1 >= len(self.ourlist):
            return None
        # maybe check here that TagMark returned with nonzero stamp0
        return TagMark(self.base, self.ourtag, self.ourlist, self.ourindex+1)

    def pred(self):
        if self.ourindex == 0:
            return None
        # maybe check here that TagMark returned with nonzero stamp0
        return TagMark(self.base, self.ourtag, self.ourlist, self.ourindex-1)

#
# TagCursor is an iterator class.
#
class TagCursor:
    def __init__(self, base):
        self.base = base
        # Apparently Python does not provide opendir() and friends, so our
        # cursor actually loads whole list in memory. As long as the whole
        # HTML output is in memory too, there is no special concern.
        # If we cared enough, we'd convert filenames to stamps right away,
        # then sorted an array of integers. But we don't.
        # Most likely we'll switch to a database back-end anyway.
        self.dlist = os.listdir(base.markdir)
        # Miraclously this sort() works as expected in presence of dot-fix.
        self.dlist.sort()
        self.dlist.reverse()
        self.index = 0
        self.length = len(self.dlist)

    def next(self):
        if self.index >= self.length:
            raise StopIteration
        mark = TagMark(self.base, None, self.dlist, self.index)
        self.index += 1
        return mark

    # def __del__(self):
    #     ......

#
# The open database (any back-end in theory, hardcoded to files for now)
# XXX files are very inefficient: 870 bookmarks from a 280 KB XML take 6 MB.
#
class TagBase:
    def __init__(self, dirname0):
        # An excessively clever way to do the same thing exists, see:
        # http://zaitcev.livejournal.com/206050.html?thread=418530#t418530
        # self.dirname = dirname0[:1] + dirname0[1:].rstrip('/')
        d = dirname0
        if len(d) > 1 and d[-1] == '/':
            d = dirname0[:-1]
        self.dirname = d

        if not os.path.exists(self.dirname):
            raise AppError("Does not exist: "+self.dirname)
        if not os.path.isdir(self.dirname):
            raise AppError("Not a directory: "+self.dirname)

        self.tagdir = self.dirname+"/tags"
        self.markdir = self.dirname+"/marks"

    def open(self):
        try:
            os.mkdir(self.tagdir)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise AppError(str(e))
        try:
            os.mkdir(self.markdir)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise AppError(str(e))

    def close(self):
        pass

    def load_tag(self, tag):
        try:
            f = open(self.tagdir+"/"+tag, "r")
        except IOError, e:
            f = None
        if f != None:
            # This can be a long read - tens of thousands of mark keys
            tagbuf = f.read()
            f.close()
        else:
            tagbuf = ''
        return tagbuf

    def lookup_name(self, tag, dlist, matchname):
        ## The antipythonic roll-my-own way:
        # matchindex = 0
        # while matchindex < len(dlist):
        #     if dlist[matchindex] == matchname:
        #         break
        #     matchindex += 1
        # if matchindex == len(dlist):
        #     return None
        ## A more pytonic way:
        try:
            matchindex = dlist.index(matchname)
        except ValueError:
            return None
        return TagMark(self, tag, dlist, matchindex)

    # The add1 constructs key from UNIX seconds.
    def add1(self, timeint, title, url, note, tags):

        # for normal website-entered content fix is usually zero
        fix = 0
        while 1:
            stampkey = "%010d.%02d" % (timeint, fix)
            markname = stampkey
            # special-case full seconds to make directories a shade faster
            if fix == 0:
                markname = "%010d" % timeint
            if not os.path.exists(self.markdir+"/"+markname):
                break
            fix += 1
            if fix >= 100:
                return

        try:
            f = open(self.markdir+"/"+markname, "w+")
        except IOError, e:
            raise AppError(str(e))

        # This is done because ElementTree throws Unicode strings at us.
        # When we try to write these strings, UnicodeEncodeError happens.
        f = utf8_writer(f)

        # We write the key into the file in case we ever decide to batch marks.
        f.write(stampkey)
        f.write("\n")

        f.write(title)
        f.write("\n")
        f.write(url)
        f.write("\n")
        f.write(note)
        f.write("\n")

        for t in tags:
            f.write(" ")
            f.write(t)
        f.write("\n")

        f.close()

        for t in tags:
            # 1. Read
            tagbuf = self.load_tag(t)
            # 2. Modify
            # It would be more efficient to scan by hand instead of splitting,
            # but premature optimization is the root etc.
            if markname in split_tags(tagbuf):
                continue
            tagbuf = tagbuf+" "+markname
            # 3. Write
            try:
                f = open(self.tagdir+"/"+t, "w")
            except IOError, e:
                continue
            f.write(tagbuf)
            f.close()

    def __iter__(self):
        return TagCursor(self)

    def lookup(self, timeint, fix):
        if fix == 0:
                matchname = "%010d" % timeint
        else:
                matchname = "%010d.%02d" % (timeint, fix)

        # Would be nice to cache the directory in TagBase somewhere.
        # Should we catch OSError here, incase of lookup on un-opened base?
        dlist = os.listdir(self.markdir)
        dlist.sort()
        dlist.reverse()

        return self.lookup_name(None, dlist, matchname)

    def first(self):
        dlist = os.listdir(self.markdir)
        dlist.sort()
        dlist.reverse()
        if len(dlist) == 0:
            return None
        return TagMark(self, None, dlist, 0)

    def taglookup(self, tag, timeint, fix):
        if fix == 0:
                matchname = "%010d" % timeint
        else:
                matchname = "%010d.%02d" % (timeint, fix)

        dlist = split_tags(self.load_tag(tag))
        dlist.sort()
        dlist.reverse()
        if len(dlist) == 0:
            return None

        return self.lookup_name(tag, dlist, matchname)

    def tagfirst(self, tag):
        dlist = split_tags(self.load_tag(tag))
        dlist.sort()
        dlist.reverse()
        if len(dlist) == 0:
            return None
        return TagMark(self, tag, dlist, 0)
