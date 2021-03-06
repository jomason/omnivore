#!/usr/bin/env python

import sys
import traceback
import wx

import logging
log = logging.getLogger(__name__)


class UndoHistoryPanel(wx.ListBox):
    def __init__(self, parent, task, **kwargs):
        self.task = task
        wx.ListBox.__init__(self, parent, wx.ID_ANY, **kwargs)

        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

    def DoGetBestSize(self):
        """ Base class virtual method for sizer use to get the best size
        """
        width = 300
        height = -1
        best = wx.Size(width, height)

        # Cache the best size so it doesn't need to be calculated again,
        # at least until some properties of the window change
        self.CacheBestSize(best)

        return best

    def set_task(self, task):
        self.task = task

    def recalc_view(self):
        e = self.task.active_editor
        self.editor = e
        if e is not None:
            self.update_history()

    def refresh_view(self):
        editor = self.task.active_editor
        if editor is not None:
            if self.editor != editor:
                self.recalc_view()
            else:
                self.Refresh()

    def update_history(self):
        project = self.task.active_editor
        summary = project.document.undo_stack.history_list()
        self.Set(summary)
        index = project.document.undo_stack.insert_index
        if index > 0:
            self.SetSelection(index - 1)

    def activate_spring_tab(self):
        self.recalc_view()

    def get_notification_count(self):
        return 0

    def on_key_down(self, evt):
        key = evt.GetKeyCode()
        log.debug("evt=%s, key=%s" % (evt, key))
