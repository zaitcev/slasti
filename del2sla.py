#
# Import XML from Del.icio.us into Slasti
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#
# requires:
#  ElementTree as built into Python 2.7 (xml.etree)
#

import sys
import time
import os
import errno
import codecs
(utf8_encode, utf8_decode, utf8_reader, utf8_writer) = codecs.lookup("utf-8")
from xml.etree import ElementTree

TAG = "del2sla"

def Usage():
    print >>sys.stderr, "Usage: "+TAG+" target_dir bookmarks.xml"
    sys.exit(2)

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

class AppError(Exception):
    pass

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
        fix = 0
        while 1:
            stampkey = "%010d.%02d" % (timeint, fix)
            markname = stampkey
            # special-case full seconds to make directories a shade faster
            if fix == 0:
                markname = "%010d" % timeint
            try:
                f = open(self.markdir+"/"+markname, "w+")
            except IOError, e:
                fix = fix + 1
                # actually fix should always be zero for human-generated input
                if fix >= 100:
                    return
                continue
            break

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

def verify_tags(tagstr):
    if "/" in tagstr:
        return 0
    if "\n" in tagstr:
        return 0
    return 1

def verify_attr(attrstr):
    if "\n" in attrstr:
        return 0
    return 1

def do(dirname, xmlname):
    base = TagBase(dirname)

    base.open()

    try:
        # Verify XML has UTF-8 encoding perhaps?
        etree = ElementTree.parse(xmlname)
    except IOError, e:
        raise AppError(str(e))
    except ElementTree.ParseError, e:
        raise AppError(xmlname+": "+str(e))
    etroot = etree.getroot()
    if etroot == None:
        raise AppError(xmlname+": No root element")
    if etroot.tag != 'posts':
        raise AppError(xmlname+": root is not `posts'")

    for et in etroot:
        if et.tag != 'post':
            continue
        title = et.attrib.get('description')
        if title == None:
            continue
        url = et.attrib.get('href')
        if url == None:
            continue
        # 'tag' is a string of space-separated tags
        tagstr = et.attrib.get('tag')
        if tagstr == None:
            continue
        # not sure what to do with hash and meta
        # 'hash' is MD5 digest of URL
        #hash = et.attrib.get('hash')
        #meta = et.attrib.get('meta')
        note = et.attrib.get('extended')
        if note == None:
            note = ""

        if not verify_attr(title):
            raise AppError("Invalid title: `"+title+"'")
        if not verify_attr(url):
            raise AppError("Invalid URL: `"+url+"'")
        if not verify_attr(note):
            raise AppError("Invalid note: `"+note+"'")

        if not verify_tags(tagstr):
            raise AppError("Invalid tags: `"+tagstr+"'")
        tags = split_tags(tagstr)
        if tags == []:
            continue

        #time="2010-12-10T08:04:46Z"
        timestr = et.attrib.get('time')
        if timestr == None:
            # We could create fake dates, but that would be just wrong.
            continue

        try:
            timeval = time.strptime(timestr, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError, e:
            # We bug out on this because this case may be worth diagnosing.
            # The error message has both format and unparsed date string.
            raise AppError(str(e))
        if timeval == None:
            continue

        try:
            timeint = int(time.mktime(timeval))
        except (ValueError, OverflowError), e:
            # XXX A user supplied Year 1900 or something like that.
            print e
            continue

        base.add1(timeint, title, url, note, tags)

    base.close()

def main(args):
    argc = len(args)
    if argc == 2:
        dirname = args[0]
        xmlname = args[1]
    else:
        Usage()

    try:
        do(dirname, xmlname)
    #except EnvironmentError, e:
    #    die("OS problem: "+str(e))
    except AppError, e:
        print >>sys.stderr, TAG+":", e
        sys.exit(1)

# http://utcc.utoronto.ca/~cks/space/blog/python/ImportableMain
if __name__ == "__main__":
    main(sys.argv[1:])
