#
# Slasti -- Templating engine and templates
#
# Copyright (C) 2012 Christian Aichinger
# See file COPYING for licensing information (expect GPL 2).
#

from __future__ import print_function
import string
import re
import six

from slasti import escapeHTML

class LaxTemplate(string.Template):
    """string.Template with less strict placeholder syntax

    Behaves just like string.Template but allows more general placeholders,
    e.g. ${class.member} or ${dictionary["key"]}
    """

    # This change of pattern allows for anything in braces, but
    # only identifiers outside of braces:
    pattern = r"""
    \$(?:
      (?P<escaped>\$)             |   # Escape sequence of two delimiters
      (?P<named>[_a-z][_a-z0-9]*) |   # delimiter and a Python identifier
      {(?P<braced>.*?)}           |   # delimiter and a braced identifier
      (?P<invalid>)                   # Other ill-formed delimiter exprs
    )
    """

    def substitute(self, d):
        s = super(LaxTemplate, self).substitute(d)
        return s.encode('utf-8')

class DictWrapper:
    """dict wrapper class for fancier variable expansion in templates

    Cf. http://blog.ianbicking.org/templating-via-dict-wrappers.html

    Supported syntax:
    ${a.b.c}            -> dict["a"]["b"]["c"]
    ${a:-default)       -> dict["a"]            if "a" in dict and not None
                           "default"            otherwise
    ${a.b.c:-xyz}       -> dict["a"]["b"]["c"]  if all keys found and not None
                           "xyz"                otherwise
    """
    def __init__(self, dict):
        self.dict = dict

    def _parse_default(self, item):
        lookup_str = item
        default = None
        m = re.match(r'^([^:]*):-([^:]*)$', item)
        if m:
            lookup_str = m.group(1)
            # if group is empty, default is None
            # We dont want that, force empty string instead
            default = m.group(2) or ""
        return (lookup_str, default)

    def _do_lookup(self, lookup_str):
        # allow dict access via d.member
        # example: ${member.submember} -> self.dict["member"]["submember"]
        items = lookup_str.split('.')
        res = self.dict[items[0]]
        for subitem in items[1:]:
            res = res[subitem]
        return res

    def _enforce_encoding(self, s):
        # handle HTML escaping stuff here
        # character encoding is done on the finished expanded template
        if isinstance(s, six.string_types):
            return escapeHTML(s)
        # We end here for every list, such as "$tags". The contents get
        # later escaped above too, as they get looked up one by one.
        return s

    def __getitem__(self, item):
        # Separate the query into the real lookup string and the default
        # Then do the lookup; if it blows up or the result is None, return the
        # default. Otherwise return the looked up value
        lookup_str, default = self._parse_default(item)
        default = self._enforce_encoding(default)
        try:
            lookup_result = self._do_lookup(lookup_str)
            if lookup_result is None:
                return default
            if lookup_str[0] == '_':
                return lookup_result
            return self._enforce_encoding(lookup_result)
        except (IndexError, KeyError) as e:
            # If we can't find a member/submember, return the default
            if default is not None:
                return default
            raise e

    def __setitem__(self, key, value):
        self.dict[key] = value


class TemplateNodeBase(object):
    """Base class for nodes in the template syntax tree"""
    def __init__(self):
        self.name = None
        self.children = []

    def substitute(self, d, children=None):
        output = []
        if children is None:
            children = self.children

        for child in children:
            if isinstance(child, TemplateNodeBase):
                output.append(child.substitute(d))
            else:
                # Should be some string, expand placeholders
                output.append(LaxTemplate(child).substitute(d))
        return b''.join(output)


class TemplateNodeRoot(TemplateNodeBase):
    """Root of the template syntax tree"""
    def __init__(self):
        super(TemplateNodeRoot, self).__init__()
        self.name = "root"

    # substitute() falls back to base class implementation


class TemplateNodeElem(TemplateNodeBase):
    def __init__(self, elem):
        super(TemplateNodeElem, self).__init__()
        self.elem = elem

    def substitute(self, d, children=None):
        # forward to template element
        if children:
            # never happens?
            print("Elem subst, children", self.name, len(children))
            return super(TemplateNodeElem, self).substitute(d, children)
        return self.elem.substitute_2(d)


class Template:
    def __init__(self, *args):
        self.template_list = args
        self._build_template_tree()

    def __str__(self):
        return ' '.join([str(arg) for arg in self.template_list])

    def _build_template_tree(self):
        self.template_tree = TemplateNodeRoot()
        stack = [self.template_tree]

        for elem in self.template_list:
            if isinstance(elem, six.string_types):
                stack[-1].children.append(elem)
            else:
                sub = TemplateNodeElem(elem)
                stack[-1].children.append(sub)

    def substitute_2(self, d):
        return self.template_tree.substitute(DictWrapper(d))

    def substitute(self, d):
        return self.template_tree.substitute(DictWrapper(d))

class TemplateElemLoop:
    def __init__(self, loopvar_name, list_name, loop_body):
        """
        loopvar_name: name of loopvar to be referred in loop_body
        list_name: name of list along which to iterate
        loop_body: an instance of Template to be looped
        """
        self.loopvar = loopvar_name
        self.listname = list_name
        self.body = loop_body

    def __str__(self):
        return "LOOP(%s,%s,%s)" % (self.loopvar, self.listname, str(self.body))

    # Forwarded by our TemplateNodeElem
    def substitute_2(self, d):
        output = []
        for n in d[self.listname]:
            new_d = {}
            new_d.update(d.dict)
            new_d[self.loopvar] = n
            if isinstance(self.body, str):
                o = LaxTemplate(self.body).substitute(DictWrapper(new_d))
                output.append(o)
            else:
                output.append(self.body.substitute_2(new_d))
        return b''.join(output)

    def substitute(self, d):
        # never happens?
        print("Legacy substitute of a loop")
        return self.substitute_2(d)

class TemplateElemCond:
    def __init__(self, condvar_name, if_body, else_body):
        self.condvar = condvar_name
        self.t_body = if_body
        self.f_body = else_body

    def __str__(self):
        return "COND(%s,%s,%s)" % (self.condvar,
                                   str(self.t_body), str(self.f_body))

    def substitute_2(self, d):
        try:
            val = d[self.condvar]
        except KeyError:
            val = None
        body = self.t_body if val else self.f_body
        if not body:
            return b""
        if isinstance(body, str):
            return LaxTemplate(body).substitute(d)
        return body.substitute_2(d)

    def substitute(self, d):
        return self.substitute_2(d)
