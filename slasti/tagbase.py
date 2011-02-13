#
# Slasti -- Mark/Tag database
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#
# requires:
#  codecs
#
import os
import errno
import codecs
(utf8_encode, utf8_decode, utf8_reader, utf8_writer) = codecs.lookup("utf-8")
import string

from slasti import AppError

# We are not aware of any specification, so it is unclear if tags are split
# by space or whitespace. We assume space, to be locale-independent.
# But this means that we include tabs and foreign whitespace into tags.
def split_tags(tagstr):
    tags = []
    for t in tagstr.split(' '):
        t = t.strip(' ')
        if t != '':
            tags.append(t)
    return tags

#
# TagMark is one bookmark when we manipulate it (extracted from TagBase).
#
class TagMark:
    def __init__(self, base, markname):
        self.name = markname
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
        return self.name+'|'+str(self.stamp0)+'.'+str(self.stamp1)+'|'+\
               self.title+'|'+self.url+'|'+self.note+"|"+str(self.tags)

    def html(self):
        return "<p>"+str(self)+"</p>\n"

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
        self.dlist.sort()
        self.index = 0
        self.length = len(self.dlist)

    def next(self):
        if self.index >= self.length:
            raise StopIteration
        mark = TagMark(self.base, self.dlist[self.index])
        self.index = self.index + 1
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
            fix = fix + 1
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
            try:
                f = open(self.tagdir+"/"+t, "r")
            except IOError, e:
                f = None
            if f != None:
                # This can be a long read - tens of thousands of mark keys
                tagbuf = f.read()
                f.close()
            else:
                tagbuf = ''
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
