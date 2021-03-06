import wx

from omni8bit import find_emulator

from .document import EmulationDocument


class EmulatorError(RuntimeError):
    pass


class UnknownEmulatorError(EmulatorError):
    pass


class EmulatorInUseError(EmulatorError):
    pass


def restore_emulator(e):
    # restore emulator from defaults supplied in dictionary
    pass
