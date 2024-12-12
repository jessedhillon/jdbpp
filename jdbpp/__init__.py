import os
import pdb
import sys
import traceback
import types

from . import debugger
from .debugger import Pdb, _HIDE_FRAME


__author__ = 'Antonio Cuni <anto.cuni@gmail.com>'
__url__ = 'http://github.com/antocuni/pdb'
__version__ = "0.0.1"


def import_from_stdlib(name):
    import code  # arbitrary module which stays in the same dir as pdb
    result = types.ModuleType(name)

    stdlibdir, _ = os.path.split(code.__file__)
    pyfile = os.path.join(stdlibdir, name + '.py')
    with open(pyfile) as f:
        src = f.read()
    co_module = compile(src, pyfile, 'exec', dont_inherit=True)
    exec(co_module, result.__dict__)

    return result


pdb = import_from_stdlib('pdb')


def _newfunc(func, newglobals):
    newfunc = types.FunctionType(func.__code__, newglobals, func.__name__,
                                 func.__defaults__, func.__closure__)
    if sys.version_info >= (3, ):
        newfunc.__annotations__ = func.__annotations__
        newfunc.__kwdefaults__ = func.__kwdefaults__
    return newfunc


def rebind_globals(func, newglobals):
    if hasattr(func, "__code__"):
        return _newfunc(func, newglobals)

    import functools

    if isinstance(func, functools.partial):
        return functools.partial(
            _newfunc(func.func, newglobals), *func.args, **func.keywords
        )

    raise ValueError("cannot handle func {!r}".format(func))


# copy some functions from pdb.py, but rebind the global dictionary
for name in 'run runeval runctx runcall main set_trace'.split():
    func = getattr(pdb, name)
    globals()[name] = rebind_globals(func, globals())
del name, func


# Post-Mortem interface

def post_mortem(t=None, Pdb=Pdb):
    # handling the default
    if t is None:
        # sys.exc_info() returns (type, value, traceback) if an exception is
        # being handled, otherwise it returns None
        t = sys.exc_info()[2]
    if t is None:
        raise ValueError("A valid traceback must be passed if no "
                         "exception is being handled")

    p = Pdb()
    p.reset()
    p.interaction(None, t)


def pm(Pdb=Pdb):
    post_mortem(sys.last_traceback, Pdb=Pdb)


def cleanup():
    debugger.local.GLOBAL_PDB = None
    debugger.local._pdbpp_completing = False

# pdb++ specific interface


def xpm(Pdb=Pdb):
    """
    To be used inside an except clause, enter a post-mortem pdb
    related to the just caught exception.
    """
    info = sys.exc_info()
    print(traceback.format_exc())
    post_mortem(info[2], Pdb)


def enable():
    global set_trace
    set_trace = enable.set_trace
    if debugger.local.GLOBAL_PDB:
        debugger.local.GLOBAL_PDB.disabled = False


enable.set_trace = set_trace


def disable():
    global set_trace
    set_trace = disable.set_trace
    if debugger.local.GLOBAL_PDB:
        debugger.local.GLOBAL_PDB.disabled = True


disable.set_trace = lambda frame=None, Pdb=Pdb: None


def set_tracex():
    print('PDB!')


set_tracex._dont_inline_ = True


def hideframe(func):
    c = func.__code__
    new_co_consts = c.co_consts + (_HIDE_FRAME,)
    c = c.replace(co_consts=new_co_consts)
    func.__code__ = c
    return func


def always(obj, value):
    return True


def break_on_setattr(attrname, condition=always, Pdb=Pdb):
    def decorator(cls):
        old___setattr__ = cls.__setattr__

        @hideframe
        def __setattr__(self, attr, value):
            if attr == attrname and condition(self, value):
                frame = sys._getframe().f_back
                pdb_ = Pdb()
                pdb_.set_trace(frame)
                pdb_.stopframe = frame
                pdb_.interaction(frame, None)
            old___setattr__(self, attr, value)
        cls.__setattr__ = __setattr__
        return cls
    return decorator
