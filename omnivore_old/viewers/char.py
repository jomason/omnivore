import os
import sys

import wx

from traits.api import on_trait_change, Bool, Undefined

from omnivore8bit.ui.bitviewscroller import FontMapScroller
from ..byte_edit.commands import ChangeByteCommand

from . import SegmentViewer

import logging
log = logging.getLogger(__name__)


class OldCharViewer(SegmentViewer):
    name = "oldchar"

    pretty_name = "Old Character"

    has_font = True

    @classmethod
    def create_control(cls, parent, linked_base):
        return FontMapScroller(parent, linked_base, size=(160,500), command=ChangeByteCommand)

    @property
    def window_title(self):
        return self.machine.font_renderer.name + ", " + self.machine.font_mapping.name

    @on_trait_change('machine.font_change_event')
    def update_bitmap(self, evt):
        log.debug("CharViewer: machine font changed for %s" % self.control)
        if evt is not Undefined:
            self.control.recalc_view()
