"""Native Cocoa window policy for this app's own Qt windows."""
import ctypes
import sys

if sys.platform == 'darwin':
    objc = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    address = ctypes.cast(objc.objc_msgSend,ctypes.c_void_p).value


def call(obj, selector, restype, argtypes=(), args=()):
    signature = ctypes.CFUNCTYPE(restype,ctypes.c_void_p,ctypes.c_void_p,*argtypes)
    return signature(address)(obj,objc.sel_registerName(selector.encode()),*args)


def keep_on_top(widget):
    if sys.platform != 'darwin' or not widget.isVisible():
        return {}
    view = int(widget.winId())
    window = call(view,'window',ctypes.c_void_p)
    if not window:
        return {}
    # A Qt Tool window normally hides when another application gets focus.
    # Apply Cocoa's policy explicitly, including other Spaces and fullscreen.
    call(window,'setHidesOnDeactivate:',None,(ctypes.c_bool,),(False,))
    call(window,'setLevel:',None,(ctypes.c_long,),(8,))
    behavior = call(window,'collectionBehavior',ctypes.c_ulong)
    behavior = (behavior & ~(2 | 128 | 512)) | 1 | 256
    call(window,'setCollectionBehavior:',None,(ctypes.c_ulong,),(behavior,))
    # Does not activate the app or take keyboard focus from Claude.
    call(window,'orderFrontRegardless',None)
    return {'visible':bool(call(window,'isVisible',ctypes.c_bool)),
            'hides_on_deactivate':bool(call(window,'hidesOnDeactivate',ctypes.c_bool)),
            'level':int(call(window,'level',ctypes.c_long)),
            'all_spaces':bool(call(window,'collectionBehavior',ctypes.c_ulong)&1)}
