import math
import re

from numbers import Integral, Real

# system constant syntax:
char_coded = 'i'
char_phys = 'p'

# value tag
values_tag = ['VF', 'V', 'VT']

# regular expression used to convert constant expression
#_REGEX_
re_remove_tail = re.compile(r"[\t\n]*")
re_find_value_tag = re.compile(r'<.?(V*).>')
re_find_cond_tag = re.compile(r'<(.+?)>(.+?)<\/\1>')
re_find_whitespace = re.compile(r'\s+?')
re_find_comment = re.compile(r'(/\*.*?\*/)')

re_find_sc = re.compile(r'<([\w\-]+)>([\w\s\_]+)<\/\1>')
re_find_sc_decoded = re.compile(r'[pP|iI]\((\w+)\)')
re_find_operators = re.compile(r'&([a-z]+)\;')
re_find_defined = re.compile(r'defined(\s*\([\s\(]*([%s%s]?\(|))(\w+)\)' % (char_coded, char_phys), flags=re.IGNORECASE)
re_find_not = re.compile(r'\!([^=])')
re_find_digit_u = re.compile(r'\b(\d+)[u]\b')
re_find_false = re.compile(r'\bFALSE\b', flags=re.IGNORECASE)
re_find_true = re.compile(r'\bTRUE\b', flags=re.IGNORECASE)
re_val_long = re.compile(r'^[lL][\d]+')

re_val_oct_check = re.compile(r'^(0)([1-7]*[0-7])$')
re_name_error_check = re.compile(r"name\s+\'(\w+)\'")

char_html_dict = {
        'quot':'"' ,
        'amp' :'&' ,
        'lt'  :'<' ,
        'gt'  :'>' ,
    }

def old_div(a, b):
    if isinstance(a, Integral) and isinstance(b, Integral):
        return a // b
    else:
        return a / b


def damos_iceil(val):
    return int(math.ceil(val))


def damos_uceil(val):
    return int(math.ceil(val))


def damos_ifloor(val):
    return int(math.floor(val))


def damos_ufloor(val):
    return int(math.floor(val))


def damos_ln(val):
    return math.log(val)


def damos_round(val):
    return round(val)


def damos_max(val1, val2):
    return max(val1, val2)


def damos_min(val1, val2):
    return min(val1, val2)


def damos_div(x, y):
    return old_div(x, y)


def damos_define(val):
    if val >= 1:
        return True
    elif val < 0:
        return False
    else:
        return val


damos = {
    'divide': damos_div,
    'ICEIL': damos_iceil,
    'iceil': damos_iceil,
    'UCEIL': damos_uceil,
    'uceil': damos_uceil,
    'LN': damos_ln,
    'ln': damos_ln,
    'IFLOOR': damos_ifloor,
    'ifloor': damos_ifloor,
    'ufloor': damos_ufloor,
    'UFLOOR': damos_ufloor,
    'IROUND': damos_round,
    'iround': damos_round,
    'UROUND': damos_round,
    'uround': damos_round,
    'MAX': damos_max,
    'max': damos_max,
    'MIN': damos_min,
    'min': damos_min,
    'DEFINED': damos_define,
    'defined': damos_define
}

def eval_nested(eval_str, use_dict={}, nested_cnt=0):
    """DOC
    In some cases more then maximum count of braces is used in damos expressions.\\
    This function calls eval for each nested expression beginning from inside.\\
    """
    this_str = ''
    other_str = ''
    brace_cnt = 0
    for idx, chr in enumerate(eval_str):
        if chr == ')':
            brace_cnt -= 1
            if brace_cnt == 0:
                this_str += eval_nested(other_str, use_dict=use_dict, nested_cnt=nested_cnt + 1)
                other_str = ''
                continue
            elif brace_cnt < 0:
                # error 'should not happen
                raise SyntaxError('invalid syntax')
        elif chr == '(':
            brace_cnt += 1
            if brace_cnt == 1:
                continue

        if brace_cnt > 0:
            other_str += chr
        else:
            this_str += chr
    else:
        if brace_cnt != 0:
            raise SyntaxError('unexpected EOF while parsing')
        if nested_cnt:
            return '(' + str(eval(this_str, use_dict)) + ')'
        else:
            return eval(this_str, use_dict)


def evaluate(value_str, original_values, type, post_eval=True):
    """
    Evaluate the value objects.
    1. remove tail tag or un-relative tag
    2. check if value is int or float and return accordingly
    3. if post_value is False start to resolve ref tags
    ---OPT
    value_str:str value string

    """
    check_type = type
    # 1. remove comments
    replaced = re_find_comment.sub('', value_str)

    # 2. remove un-related tag name
    if check_type == 'system_const':
        replaced = re_find_value_tag.sub("", replaced)
    elif check_type == 'syscond':
        replaced = re_find_cond_tag.sub(r"\g<2>", replaced)

    replaced = re_find_whitespace.sub("", replaced)

    # 3. start resolve ref tag inside the value tag
    if len(re_find_sc.findall(replaced)) > 0:
        match = re_find_sc.sub(
            lambda x: str(original_values[x.group(2)]),
            replaced).strip()
        replaced = str(evaluate(match, original_values, check_type, post_eval=False))

    if len(re_find_sc_decoded.findall(replaced)) > 0:
        match = re_find_sc_decoded.sub(lambda x: str(original_values[x.group(1)]),
                                       replaced).strip()
        replaced = str(evaluate(match, original_values, check_type, post_eval=False))

    if replaced.isdigit():
        if post_eval:
            return int(replaced)
        else:
            return replaced

    if replaced.count('.') ==1:
        if replaced.replace('.', '').isdigit():
            if post_eval:
                return float(replaced)
            else:
                return replaced

    # 4. replace negations ! with not
    replaced = re_find_not.sub(' not \g<1>', replaced)

    # 5. replace digit+'u', ie '1u'
    replaced = re_find_digit_u.sub('\g<1>', replaced)

    # 6. replace special operation : && with and -- || with or
    replaced = re_find_operators.sub(lambda x: char_html_dict[x.group(1)],
                                           replaced).strip()
    replaced = replaced.replace('||', ' or ').replace('&&', ' and ')

    # 7. replace defined()
    replaced = re_find_defined.sub(lambda x: original_values[x.group(3)],
                                        replaced).strip()

    # 8. replace false|true
    replaced = re_find_false.sub('False', replaced)
    replaced = re_find_true.sub('True', replaced)

    # 9. replace numeric problems:
    replaced = re_val_oct_check.sub(lambda x: x.group(1) + 'o' + x.group(2), replaced)

    replaced = eval_nested(replaced, damos)
    if isinstance(replaced, Real) or isinstance(replaced, Integral):
        return replaced
    else:
        new_content = evaluate(replaced, original_values, check_type, post_eval=False)
        return new_content
