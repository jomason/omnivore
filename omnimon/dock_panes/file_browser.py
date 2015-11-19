# Standard library imports.
import os.path

# Enthought library imports.
from pyface.api import PythonEditor
from pyface.tasks.api import TraitsDockPane
from traits.api import Event, File, Instance, List, Str
from traitsui.api import View, Item, FileEditor


class FileBrowserPane(TraitsDockPane):
    """ A simple file browser pane.
    """

    #### TaskPane interface ###################################################

    id = 'omnimon.framework.file_browser_pane'
    name = 'File Browser'

    #### FileBrowserPane interface ############################################

    # Fired when a file is double-clicked.
    activated = Event

    # The list of wildcard filters for filenames.
    filters = List(Str)

    # The currently selected file.
    selected_file = File(os.getcwd())

    # The view used to construct the dock pane's widget.
    view = View(Item('selected_file',
                     editor=FileEditor(dclick_name='activated',
                                       filter_name='filters'),
                     style='custom',
                     width=250,
                     show_label=False),
                resizable=True)
    
    #### trait change handlers
    
    def _activated_changed(self):
        self.task.window.application.load_file(self.selected_file, self.task)


class PythonScriptBrowserPane(FileBrowserPane):
    """ A file browser pane restricted to Python scripts.
    """

    #### TaskPane interface ###################################################

    id = 'omnimon.framework.python_script_browser_pane'
    name = 'Script Browser'

    #### FileBrowserPane interface ############################################

    filters = [ '*.py' ]
