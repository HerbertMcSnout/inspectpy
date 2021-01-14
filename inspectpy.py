import os
import platform
import sys

_is_ipython = 'ipykernel' in sys.modules
if _is_ipython:
    import IPython
    import ipywidgets

################

def _eat_word(text, i):
    '''
    text: str — string to get next word from
    i: int — index to begin at
    returns: (str, int) — next word in text, index of end of word
    '''
    i_o = i
    i_f = len(text)
    while i < i_f and text[i] not in ['(', '[', '.']:
        i += 1
    return text[i_o:i].strip(), i

def _eat_group(text, i):
    '''
    text: str — string to get next word from (assumes opening paren at text[i-1])
    i: int — index to begin at
    returns: (str, int) — string inside parens, index of closing paren
    '''
    i_o = i
    groups = 1
    while groups:
        if text[i] in [')', '[']:
            groups -= 1
        elif text[i] in ['(', '[']:
            groups += 1
        i += 1
    return text[i_o:i - 1], i

def _parse_apps(text, apps=None):
    '''
    Parses something like '.to_list(arg1, arg2)[i]' into a list of _InspectApply objects:
    [_InspectApply_getattr('to_list'),
     _InspectApply_call((arg1, arg2)),
     _InspectApply_index(i)]
    '''
    apps = apps or []
    text = text.strip()
    i = 0
    max_i = len(text)
    while i < max_i:
        if text[i] == '.':
            attr, i = _eat_word(text, i + 1)
            apps.append(_InspectApply_getattr(attr))
        elif text[i] == '(':
            args, i = _eat_group(text, i + 1)
            apps.append(_InspectApply_call(args))
        elif text[i] == '[':
            index, i = _eat_group(text, i + 1)
            apps.append(_InspectApply_index(index))
        elif text[i].isspace():
            i += 1
        else:
            raise SyntaxError(text)
    return apps

################

class _InspectApply:

    def __init__(self):
        pass

    def __call__(self, obj):
        raise NotImplementedError(f'{self.__class__}.__call__')

    def __str__(self):
        raise NotImplementedError(f'{self.__class__}.__str__')
    
    def __repr__(self):
        raise NotImplementedError(f'{self.__class__}.__repr__')

class _InspectApply_getattr(_InspectApply):

    def __init__(self, attr):
        self.attr = attr

    def __call__(self, obj):
        return getattr(obj, self.attr)
    
    def __str__(self):
        return f'_InspectApply_getattr({repr(self.attr)})'

    def __repr__(self):
        return f'.{self.attr}'

class _InspectApply_call(_InspectApply):

    def __init__(self, args):
        self.args_str = args
        comma = '' if not args or args.endswith(',') else ','
        self.args_eval = eval('(' + args + comma + ')')
    
    def __call__(self, obj):
        return obj(*self.args_eval)

    def __str__(self):
        return f'_InspectApply_call({repr(self.args_str)})'
    
    def __repr__(self):
        return f'({self.args_str})'
    
class _InspectApply_index(_InspectApply):

    def __init__(self, index):
        self.index_str = index
        self.index_eval = eval(index)
    
    def __call__(self, obj):
        return obj[self.index_eval]

    def __str__(self):
        return f'_InspectApply_index({repr(self.index_str)})'
    
    def __repr__(self):
        return f'[{self.index_str}]'

################

class _InspectObj:
    
    def __init__(self, obj, **kwargs):
        self.obj = obj
        self.obj_o = kwargs['obj_o'] if 'obj_o' in kwargs else obj
        self.attr_hist = kwargs['attr_hist'] if 'attr_hist' in kwargs else []
    
    def __str__(self):
        return f'_InspectObj({repr(self.obj)})'
    
    def __repr__(self):
        return ''.join([repr(x) for x in [self.obj_o] + self.attr_hist])

    def __call__(self, *apps):
        obj = self.obj
        for app in apps:
            obj = app(obj)
        self.obj = obj
        self.attr_hist.extend(apps)

    def recompute_obj(self):
        self.obj = self.obj_o
        for app in self.attr_hist:
            self.obj = app(self.obj)
        return self
    
    def select_from_hist(self, attr_index):
        'Go back to attr_index attrs'
        self.attr_hist = self.attr_hist[:attr_index]
        return self.recompute_obj()

################

#def _on_click(b):
#    x = b.metadata
#    print(f'Clicked {b.description}, with metadata {x}')
#    x = b.metadata
#    attr_name = b.description
#    x(_InspectApply_getattr(attr_name))
#    _inspect(x)

def _on_input_apply(x, text):
    try:
        x(*_parse_apps(text))
        _inspect(x)
    except EOFError as e:
        pass
    except Exception as e:
        tp = str(e.__class__)[8:-2]
        print(f'{tp}: {e}', file=sys.stderr)
        if not _is_ipython:
            _make_prompt(x)
    
def _display_one_attr_hist(x, app, attr_index):
    button = ipywidgets.Button(description=repr(app), layout=ipywidgets.Layout(width='auto'))
    button.on_click(lambda b: _inspect(x.select_from_hist(attr_index)))
    return button
    
def _display_inspect(x):
    print('\nInspect:')
    apps_is = list(enumerate([x.obj_o] + x.attr_hist))
    if _is_ipython:
        text = ipywidgets.Text(value='', placeholder='apply')
        text.on_submit(lambda _: _on_input_apply(x, text.value))
        hist_buttons = [_display_one_attr_hist(x, app, i) for i, app in apps_is]
        IPython.display.display(ipywidgets.HBox(hist_buttons + [text]))
    else:
        print('  ' + ''.join([f'{i:>{len(repr(app))}}' for i, app in apps_is]))
        print('  ' + ''.join([f'{repr(app)}' for i, app in apps_is]))

def _make_grouped_grid(*groups, output_width = 80, column_padding=1, pad_beginning=True):
    acc = []
    column_width = max(len(text) for text in sum(groups, start=[]))
    num_columns = (output_width - column_padding*pad_beginning) // (column_width + column_padding)
    for group in groups:
        i = 0
        for text in group:
            if pad_beginning and i % num_columns == 0:
                acc.append(' ' * column_padding)
            acc.append(f'{text:>{column_width}}  ')
            if i % num_columns == num_columns - 1:
                acc.append('\n')
            i += 1
        if group:
            acc.append('\n\n')
    acc.pop() # remove final '\n\n'
    return ''.join(acc)
        
    
def _display_attrs(x):
    print('\nAttributes:')
    
    buttons = []
    xdir = dir(x.obj)
    __attrs = []
    _attrs = []
    attrs = []
    for attr in dir(x.obj):
        if attr.startswith('__'):
            __attrs.append(attr)
        elif attr.startswith('_'):
            _attrs.append(attr)
        else:
            attrs.append(attr)
    print(_make_grouped_grid(attrs, _attrs, __attrs))
    
def _display_details(x):
    print(f'Value: {repr(x.obj)}')
    print(f'Type: {repr(type(x.obj))}')
    if hasattr(x.obj, '__text_signature__'):
        print('Args:', x.obj.__text_signature__ or '(...)')
    if '__doc__' in dir(x.obj):
        print('\nDocumentation:')
        print('  ' + x.obj.__doc__.replace('\n', '\n  '))

def _clear_output():
    if _is_ipython:
        IPython.display.clear_output()

def _make_prompt(x):
    if not _is_ipython:
        print('\n')
        inp = input('Apply: ')
        if inp.isnumeric():
            _inspect(x.select_from_hist(int(inp)))
        else:
            _on_input_apply(x, inp)
    
def _inspect(x):
    _clear_output()
    _display_inspect(x)
    _display_details(x)
    _display_attrs(x)
    _make_prompt(x)
        
def inspect(obj):
    '''
    Opens an interactive explorer on obj, listing such info as its documentation,
    attributes, and arguments (if callable), and allows easy exploration of those
    attributes, etc...
    '''
    _inspect(_InspectObj(obj))
