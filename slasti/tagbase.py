#
# Slasti -- Mark/Tag database
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#
# requires:
#  codecs
#

import codecs
utf8_writer = codecs.getwriter("utf-8")
import os
import errno
import math
import time
import base64
import six

from xml.sax.saxutils import quoteattr

from slasti import AppError
import slasti

# A WSGI module running on Fedora 15 gets no LANG, so Python decides
# that filesystem encoding is "ascii". This cannot be changed.
# Then, an attempt to call open(basedir+"/"+tag) blows up with
# "UnicodeDecodeError: 'ascii' codec can't decode byte 0xe3 in posi...".
# Manual encoding does not work, it still blows up even if argument is str.
# The only way is to avoid UTF-8 filenames entirely.

def fs_encode(tag):
    return base64.b64encode(slasti.safestr(tag), b"+_").decode('ascii')

def fs_decode(tag):
    # XXX try TypeError -- and then what?
    s = base64.b64decode(tag, b"+_")
    # XXX try UnicodeDecodeError -- and then what?
    u = s.decode('utf-8')
    return u

def fs_decode_list(names):
    ret = []
    for s in names:
        # Encoding with ascii? Why, yes. In F15, listdir returns unicode
        # strings, but b64decode blows up on them (deep in .translate()
        # not having the right table). Force back into str. They are base64
        # encoded, so 'ascii' is appropriate.
        if isinstance(s, six.string_types):
            s = s.encode('ascii')
        ret.append(fs_decode(s))
    return ret

#

def split_marks(tagstr):
    tags = []
    for t in tagstr.split(' '):
        if t != '':
            tags.append(t)
    return tags

def load_tag(tagdir, tag):
    try:
        f = open(tagdir+"/"+fs_encode(tag), "r")
    except IOError as e:
        f = None
    if f != None:
        # This can be a long read - tens of thousands of mark keys
        tagbuf = f.read()
        f.close()
    else:
        tagbuf = ''
    return tagbuf

def read_tags(markdir, markname):
    try:
        f = codecs.open(markdir+"/"+markname, "r",
                        encoding="utf-8", errors="replace")
    except IOError:
        return []

    # self-id: stamp1.stamp2
    s = f.readline()
    if s == None or len(s) == 0:
        f.close()
        return []

    # title (???)
    s = f.readline()
    if s == None or len(s) == 0:
        f.close()
        return []

    # url
    s = f.readline()
    if s == None or len(s) == 0:
        f.close()
        return []

    # note
    s = f.readline()
    if s == None or len(s) == 0:
        f.close()
        return []

    s = f.readline()
    if s == None or len(s) == 0:
        f.close()
        return []
    tags = split_marks(s.rstrip("\r\n"))

    f.close()
    return tags

# def difftags is not just what diff does, but a diff of two sorted lists.

# We just throw it all into a colored list and let the result fall out.
# The cleanest approach would be to merge reds and blues with the same key,
# but we do not know a nice way to do it. So we join and then recolor.

def difftags(old, new):

    # No amount of tinkering with strxfrm, strcoll, and locale settings helps.
    # The sort still blows up with UnicodeDecodeError, codec 'ascii'.
    # So, just safestr the sort keys.

    joint = []
    for s in old:
        joint.append([slasti.safestr(s),s,'-'])
    for s in new:
        joint.append([slasti.safestr(s),s,'+'])

    joint.sort(key = lambda t: t[0])

    prev = None
    for s in joint:
        if prev != None and prev[0] == s[0]:
            prev[2] = ' ';
            s[2] = ' ';
        prev = s

    minus = []
    plus = []
    for s in joint:
        if s[2] == '-':
            minus.append(s[1])
        if s[2] == '+':
            plus.append(s[1])

    return (minus, plus)

#
# TagMark is one bookmark when we manipulate it (extracted from TagBase).
#
class TagMark:
    def __init__(self, base, fromtag, marklist, markindex):
        markname = marklist[markindex]

        self.base = base
        self.ourtag = fromtag
        self.ourlist = marklist
        self.ourindex = markindex

        self.stamp0 = 0
        self.stamp1 = 0
        self.mtime = 0.0
        self.title = "-"
        self.url = "-"
        self.note = ""
        self.tags = []

        try:
            f = codecs.open(base.markdir+"/"+markname, "r",
                            encoding="utf-8", errors="replace")
        except IOError:
            # Set a red tag to tell us where we crashed.
            self.stamp1 = 1
            return

        s = f.readline()
        if s == None or len(s) == 0:
            self.stamp1 = 2
            f.close()
            return

        s_words = s.split()

        mtime = None
        if len(s_words) > 1:
            # The tag was written by mtime-aware code
            try:
                mtime = float(s_words[1])
            except ValueError:
                pass
        if mtime is None:
            # Old-style mark or whatever
            try:
                mtime = math.floor(float(os.fstat(f.fileno()).st_mtime))
            except (OSError, ValueError, OverflowError):
                mtime = 0.0
            self.mtime = mtime

        # Format is defined as two integers over a dot, which unfortunately
        # looks like a decimal fraction. Should've used a space. Oh well.
        slist = s_words[0].rstrip("\r\n").split(".")
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
        self.title = s.rstrip("\r\n")

        s = f.readline()
        if s == None or len(s) == 0:
            f.close()
            return
        self.url = s.rstrip("\r\n")

        s = f.readline()
        if s == None or len(s) == 0:
            f.close()
            return
        self.note = s.rstrip("\r\n")

        s = f.readline()
        if s == None or len(s) == 0:
            f.close()
            return

        s = s.rstrip("\r\n")
        # Stripping spaces prevents emply tags coming out of split().
        s = s.strip(" ")
        self.tags = s.split(" ")

        f.close()

    def __str__(self):
        # There do not seem to be any exceptions raised with weird inputs.
        datestr = time.strftime("%Y-%m-%d", time.gmtime(self.stamp0))
        return self.ourlist[self.ourindex]+'|'+datestr+'|'+\
               self.title+'|'+self.url+'|'+self.note+'|'+self.tags

    def key(self):
        return (self.stamp0, self.stamp1)

    def tag(self):
        return self.ourtag

    def xml(self):
        datestr = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.stamp0))
        datestr = '"%s"' % datestr

        title = quoteattr(self.title)
        url = quoteattr(self.url);
        tagstr = quoteattr(" ".join(self.tags))
        note = quoteattr(self.note)

        # Del.icio.us also export hash="" (MD5 of URL in href) and meta=""
        # (MD5 of unknown content). We don't know if this is needed for anyone.
        fmt = '  <post href=%s description=%s tag=%s time=%s extended=%s />\n'
        return fmt % (url, title, tagstr, datestr, note)

    # We return mark's jsondict here, not a full-page jsondict, of course.
    def to_jsondict(self, path_prefix):
        title = self.title
        if not title:
            title = self.url

        mark_url = '%s/mark.%d.%02d' % (path_prefix, self.stamp0, self.stamp1)
        edit_url = '%s/edit?mark=%d.%02d' % (
                                        path_prefix, self.stamp0, self.stamp1)
        ts = time.gmtime(self.stamp0)
        jsondict = {
            "date": time.strftime("%Y-%m-%d", ts),
            "href_mark": mark_url,
            "href_mark_url": slasti.escapeURL(self.url),
            "href_edit": edit_url,
            "title": title,
            "note": self.note,
            "tags": [],
            "key": "%d.%02d" % (self.stamp0, self.stamp1),
        }

        for tag in self.tags:
            jsondict["tags"].append(
                {"href_tag": '%s/%s/' % (path_prefix,
                                         slasti.escapeURLComponent(tag)),
                 "name_tag": tag,
                })

        jsondict['_main_path'] = u"MOO"

        return jsondict

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
# TagMarkCursor is an iterator class.
#
class TagMarkCursor:
    def __init__(self, base):
        self.base = base
        # Apparently Python does not provide opendir() and friends, so our
        # cursor actually loads whole list in memory.
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

    # py3
    __next__ = next

class TagTag:
    def __init__(self, base, tagname):
        self.ourname = tagname

        self.nmark = len(split_marks(load_tag(base.tagdir, tagname)))

    def __str__(self):
        return self.ourname

    def key(self):
        return self.ourname

    def num(self):
        return self.nmark

class TagTagCursor:
    def __init__(self, base):
        self.base = base
        self.dlist = fs_decode_list(os.listdir(base.tagdir))
        self.dlist.sort()
        self.index = 0
        self.length = len(self.dlist)

    def __iter__(self):
        return self

    def next(self):
        if self.index >= self.length:
            raise StopIteration
        tag = TagTag(self.base, self.dlist[self.index])
        self.index += 1
        return tag

    # py3
    __next__ = next

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
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise AppError(str(e))
        try:
            os.mkdir(self.markdir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise AppError(str(e))

    def close(self):
        pass

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

    #
    # XXX Add locking for consistency of concurrent updates

    # Store the mark body
    def store(self, markname, stampkey, title, url, note, tags):
        try:
            f = open(self.markdir+"/"+markname, "wb+")
        except IOError as e:
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

    # Add tag links for a new mark (still, don't double-add)
    def links_add(self, markname, tags):
        for t in tags:
            # 1. Read
            tagbuf = load_tag(self.tagdir, t)
            # 2. Modify
            # It would be more efficient to scan by hand instead of splitting,
            # but premature optimization is the root etc.
            if markname in split_marks(tagbuf):
                continue
            tagbuf = tagbuf+" "+markname
            # 3. Write
            try:
                f = open(self.tagdir+"/"+fs_encode(t), "w")
            except IOError:
                continue
            f.write(tagbuf)
            f.close()

    def links_del(self, markname, tags):
        for t in tags:
            # 1. Read
            tagbuf = load_tag(self.tagdir, t)
            # 2. Modify
            mark_list = split_marks(tagbuf)
            if not markname in mark_list:
                continue
            mark_list.remove(markname)
            # 3. Write
            if len(mark_list) != 0:
                tagbuf = " ".join(mark_list)
                try:
                    f = open(self.tagdir+"/"+fs_encode(t), "w")
                except IOError:
                    continue
                f.write(tagbuf)
                f.close()
            else:
                os.remove(self.tagdir+"/"+fs_encode(t))

    def links_edit(self, markname, old_tags, new_tags):
        tags_drop, tags_add = difftags(old_tags, new_tags)
        # f = open("/tmp/slasti.run","w")
        # print >>f, str(old_tags)
        # print >>f, str(new_tags)
        # print >>f, str(tags_drop)
        # print >>f, str(tags_add)
        # f.close()
        self.links_del(markname, tags_drop)
        self.links_add(markname, tags_add)

    # The add1 constructs key from UNIX seconds.
    def add1(self, timeint, title, url, note, tags):

        # for normal website-entered content fix is usually zero
        fix = 0
        while 1:
            stampkey = "%010d.%02d" % (timeint, fix)
            # special-case full seconds to make directories a shade faster
            if fix == 0:
                markname = "%010d" % timeint
            else:
                markname = stampkey
            if not os.path.exists(self.markdir+"/"+markname):
                break
            fix += 1
            if fix >= 100:
                return -1

        self.store(markname, stampkey, title, url, note, tags)
        self.links_add(markname, tags)
        return fix

    # Edit a presumably existing tag.
    def edit1(self, timeint, fix, title, url, note, new_tags):
        stampkey = "%010d.%02d" % (timeint, fix)
        if fix == 0:
            markname = "%010d" % timeint
        else:
            markname = stampkey
        old_tags = read_tags(self.markdir, markname)
        self.store(markname, stampkey, title, url, note, new_tags)
        self.links_edit(markname, old_tags, new_tags)

    def delete(self, timeint, fix):
        stampkey = "%010d.%02d" % (timeint, fix)
        if fix == 0:
            markname = "%010d" % timeint
        else:
            markname = stampkey
        old_tags = read_tags(self.markdir, markname)
        self.links_del(markname, old_tags)
        try:
            os.unlink(self.markdir+"/"+markname)
        except IOError as e:
            raise AppError(str(e))

    def __iter__(self):
        return TagMarkCursor(self)

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

        dlist = split_marks(load_tag(self.tagdir, tag))
        dlist.sort()
        dlist.reverse()
        if len(dlist) == 0:
            return None

        return self.lookup_name(tag, dlist, matchname)

    def tagfirst(self, tag):
        dlist = split_marks(load_tag(self.tagdir, tag))
        dlist.sort()
        dlist.reverse()
        if len(dlist) == 0:
            return None
        return TagMark(self, tag, dlist, 0)

    def tagcurs(self):
        return TagTagCursor(self)

    def keylookup(self, tagname):
        tag = TagTag(self, tagname)
        if tag.nmark == 0:
            return None
        return tag
