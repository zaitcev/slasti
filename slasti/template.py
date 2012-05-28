#
# Slasti -- Templating engine and templates
#
# Copyright (C) 2012 Christian Aichinger
# See file COPYING for licensing information (expect GPL 2).
#

import string
import re


html_escape_table = {
    ">": "&gt;",
    "<": "&lt;",
    "&": "&amp;",
    '"': "&quot;",
    "'": "&apos;",
    "\\": "&#92;",
    }

def escapeHTML(text):
    """Escape strings to be safe for use anywhere in HTML

    Should be used for escaping any user-supplied strings values before
    outputting them in HTML. The output is safe to use HTML running text and
    within HTML attributes (e.g. value="%s").

    Escaped chars:
      < and >   HTML tags
      &         HTML entities
      " and '   Allow use within HTML tag attributes
      \\        Shouldn't actually be necessary, but better safe than sorry
    """
    # performance idea: compare with cgi.escape-like implementation
    return "".join(html_escape_table.get(c,c) for c in text)


class TemplateError(ValueError):
    def __init__(self, m, message):
        self.m = m
        self.message = message

        # m is the match object where the error occurred
        # m.string is always the complete template_str, see comment below
        i = m.start()
        lines = m.string[:i].splitlines(True)
        if not lines:
            colno = 1
            lineno = 1
        else:
            colno = i - len(''.join(lines[:-1]))
            lineno = len(lines)
        ValueError.__init__(self, 'Template error at line %d, col %d\n%s' %
                                  (lineno, colno, message))


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
        if isinstance(s, unicode):
            return escapeHTML(s)
        if isinstance(s, str):
            print ("str found:", s)
            return s
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
            return self._enforce_encoding(lookup_result)
        except (IndexError, KeyError) as e:
            # If we can't find a member/submember, return the default
            if default is not None:
                return default
            raise e

    def __setitem__(self, key, value):
        self.dict[key] = value

    def _clone(self):
        d = {}
        d.update(self.dict)
        return DictWrapper(d)


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
        return ''.join(output)


class TemplateNodeRoot(TemplateNodeBase):
    """Root of the template syntax tree"""
    def __init__(self):
        super(TemplateNodeRoot, self).__init__()
        self.name = "root"

    # substitute() falls back to base class implementation


class TemplateNode(TemplateNodeBase):
    def __init__(self, start_match):
        super(TemplateNode, self).__init__()
        self.m_start = start_match
        self.m_end = None
        self.dict = start_match.groupdict()
        self.name = self.dict["name"]

    def set_end(self, end_match):
        self.m_end = end_match

    @staticmethod
    def _varname_generator():
        "Helper for _eval_template_code to generate unique variable names"
        i = 0
        while True:
            yield "tmplvar%d" % i
            i += 1

    def _eval_template_code(self, code, d):
        """Eval an expression containing template placeholders"""
        # Strategy:
        # * Substitute each placeholder string with a unique variable name
        #   (tmplvar0, tmplvar1, ...)
        # * Place the variable name in a dict together with the lookup value
        #   for the placeholder: { "tmplvar0": lookup_value, ... }
        # * eval() the substituted string, using the varname/lookup_value dict
        #   as globals argument for eval.
        globals = {}
        var_names = self._varname_generator()
        def repl_fun(m):
            expr = m.group("named") or m.group("braced")
            varname = next(var_names)
            globals[varname] = d[expr]
            return varname

        code = LaxTemplate.pattern.sub(repl_fun, code)
        return eval(code, globals)

    def substitute(self, d, children=None):
        if children is None:
            children = self.children

        if self.name == "for":
            output = []
            forlist = self._eval_template_code(self.dict["forlist"], d)
            for loopvalue in forlist:
                new_d = d._clone()
                new_d[self.dict["loopvar"]] = loopvalue
                output.append(super(TemplateNode, self).substitute(new_d))
            return ''.join(output)

        elif self.name == "if":
            # Split the children into if/else clauses (if else is present)
            else_marker = [x for x in children
                             if isinstance(x, TemplateNodeBase) and
                                x.name == "else"]
            if_clause = else_clause = []
            if not else_marker:
                if_clause = children
            else:
                else_index = children.index(else_marker[0])
                if_clause = children[:else_index]
                else_clause = children[else_index+1:]

            # Transform the if code into a boolean: if_result: True/False
            condition = self.dict["condition"]
            if_result = self._eval_template_code(condition, d)

            # Substitute the correct template
            if if_result:
                return super(TemplateNode, self).substitute(d, if_clause)
            else:
                return super(TemplateNode, self).substitute(d, else_clause)

        # Some control construct not handled properly
        raise NotImplementedError("Control directive handler missing")


class Template:
    def __init__(self, *args):
        self.template_str = ' '.join([str(arg) for arg in args])
        self._build_template_tree()

    def __str__(self):
        return self.template_str

    def _build_template_tree(self):
        def mk_re(s):
            # re.MULTILINE so that $ matches EOL, not only end-of-string
            return re.compile(s, re.VERBOSE | re.MULTILINE)

        re_directive = mk_re(r"\r?\n\s*(?P<directive>\#.+)$")
        directives = {
            "if":   mk_re(r"""\#(?P<name>if)\s+(?P<condition>.+?)\s*$"""),
            "else": mk_re(r"""\#(?P<name>else)\s*$"""),
            "end":  mk_re(r"""\#(?P<name>end)\s+(?P<endof>if|for)\s*$"""),
            "for":  mk_re(r"""\#(?P<name>for)\s+
                              \$(?P<loopvar>\w+) \s+in\s+
                              (?P<forlist>.+?)$"""),
        }

        cursor = 0
        self.template_tree = TemplateNodeRoot()
        stack = [self.template_tree]
        for m_line in re_directive.finditer(self.template_str):
            stack[-1].children.append(self.template_str[cursor:m_line.start()])
            cursor = m_line.end()

            cseq = m_line.group("directive")
            cmd = [key for key in directives if cseq.startswith('#'+key)]
            if not cmd:
                raise TemplateError(m_line, "Unknown syntax: " + cseq)

            cmd = cmd[0]

            # Match template_str here, with a start_position argument
            # This keeps the whole template string alive in m_cmd.string
            # Important for showing line/column numbers on syntax errors
            # DO NOT optimize to directives[cmd].match(cseq)!
            m_cmd = directives[cmd].match(self.template_str,
                                          pos=m_line.start("directive"))
            if not m_cmd:
                raise TemplateError(m_line,
                                    "Invalid %s clause: %s" % (cmd, cseq))

            if cmd == "if":
                sub = TemplateNode(m_cmd)
                stack[-1].children.append(sub)
                stack.append(sub)
            elif cmd == "for":
                sub = TemplateNode(m_cmd)
                stack[-1].children.append(sub)
                stack.append(sub)
            elif cmd == "else":
                if stack[-1].name != "if":
                    raise TemplateError(m_line, "Else not within if: " + cseq)
                stack[-1].children.append(TemplateNode(m_cmd))
            elif cmd == "end":
                endof = m_cmd.group("endof")
                if endof not in set(["for", "if"]):
                    raise TemplateError(m_line, "Unknown end tag: " + cseq)
                if endof != stack[-1].name:
                    raise TemplateError(m_line, "End tag not matched: " + cseq)
                subtemplate = stack.pop()
                subtemplate.set_end(m_cmd)
            else:
                # A syntax regex was added above but is not actually handled
                raise NotImplementedError("Syntax handler missing")

        if cursor < len(self.template_str):
            stack[-1].children.append(self.template_str[cursor:])
            cursor = len(self.template_str)

        if len(stack) != 1:
            m = re.search('$', self.template_str)
            raise TemplateError(m,
                    "Open %s clause at end of file" % stack[-1].name)

    def _check_encoding(self, d):
        if isinstance(d, dict):
            for key in d:
                self._check_encoding(d[key])
            return
        if isinstance(d, list):
            for item in d:
                self._check_encoding(item)
            return
        if d is None:
            return
        if isinstance(d, unicode) or isinstance(d, int):
            return
        print "->", type(d), repr(d)

    def substitute(self, d):
        self._check_encoding(d)
        return self.template_tree.substitute(DictWrapper(d)).encode("utf-8")
