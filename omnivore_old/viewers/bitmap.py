import os
import sys

import wx

from traits.api import on_trait_change, Bool, Undefined

from omnivore8bit.ui.bitviewscroller import BitmapScroller, MemoryMapScroller
from ..byte_edit.commands import ChangeByteCommand

from . import SegmentViewer

import logging
log = logging.getLogger(__name__)


class OldBitmapViewer(SegmentViewer):
    name = "oldbitmap"

    pretty_name = "Old Bitmap"

    has_bitmap = True

    @classmethod
    def create_control(cls, parent, linked_base):
        return BitmapScroller(parent, linked_base, size=(64,500))

    @property
    def window_title(self):
        return self.machine.bitmap_renderer.name

    @on_trait_change('machine.bitmap_shape_change_event,machine.bitmap_color_change_event')
    def update_bitmap(self, evt):
        log.debug("BitmapViewer: machine bitmap changed for %s" % self.control)
        if evt is not Undefined:
            self.control.refresh_view()
            self.linked_base.editor.update_pane_names()

    def validate_width(self, width):
        return self.machine.bitmap_renderer.validate_bytes_per_row(width)


class MemoryMapViewer(OldBitmapViewer):
    name = "memmap"

    pretty_name = "Memory Page Map"

    @classmethod
    def create_control(cls, parent, linked_base):
        return MemoryMapScroller(parent, linked_base, size=(500,500))
