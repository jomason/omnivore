# Standard library imports.
import os

# Enthought library imports.
from envisage.api import ExtensionPoint, Plugin
from envisage.ui.tasks.api import TaskFactory
from traits.api import List, TraitError
from envisage.ui.tasks.tasks_plugin import TasksPlugin
from traits.etsconfig.api import ETSConfig
from apptools.preferences.api import Preferences, PreferencesHelper
from pyface.tasks.action.api import SMenuBar, SMenu, SchemaAddition


class OmnimonTasksPlugin(TasksPlugin):
    # Override the default task extensions that supply redundant Exit and
    # Preferences menu items and the default dock pane viewing group.
    def _my_task_extensions_default(self):
        return []

class FrameworkPlugin(Plugin):
    """ The sample framework plugin.
    """

    #### convenience functions

    def task_factories_from_tasks(self, tasks):
        # Create task factories for each task such that each factory will have
        # the same id as the task
        factories = []
        for cls in tasks:
            task = cls()
            factory = TaskFactory(id=task.id, name=task.name, factory=cls)
            factories.append(factory)
        
        return factories

    def get_helper(self, helper_object, debug=True):
        return self.application.get_preferences(helper_object, debug)
    
    def set_plugin_data(self, data):
        """Store some plugin data in the application so that objects outside
        the plugin can have access to it
        
        The data is stored in a dict keyed on the plugin's id, so make
        sure plugins don't have the same id.  (Perhaps this is enforced in
        Enthought, haven't checked yet.)
        """
        self.application.plugin_data[self.id] = data
    
    def get_plugin_data(self):
        """Return the plugin data previously stored by a call to
        :py:meth:`set_plugin_data`
        
        """
        return self.application.plugin_data[self.id]

    def fire_plugin_event(self, data=None):
        """Send a plugin event.
        
        Plugin events will get fired to all who listen for the
        'application:plugin_event' event, e.g.:
        
            @on_trait_change('application:plugin_event')
        
        The event handler will be passed a tuple of the plugin's ID and some
        data.  All handlers that listen for this event will get called, so
        check the first item in the tuple and for the desired plugin ID.
        """
        self.application.plugin_event = (self.id, data)


class OmnimonMainPlugin(FrameworkPlugin):
    """ The sample framework plugin.
    """

    # Extension point IDs.
    PREFERENCES       = 'envisage.preferences'
    PREFERENCES_PANES = 'envisage.ui.tasks.preferences_panes'
    TASKS             = 'envisage.ui.tasks.tasks'
    OSX_MINIMAL_MENU = 'omnimon.osx_minimal_menu'

    #### 'IPlugin' interface ##################################################

    # The plugin's unique identifier.
    id = 'omnimon.framework.plugin'

    # The plugin's name (suitable for displaying to the user).
    name = 'Omnimon'

    #### Contributions to extension points made by this plugin ################

    preferences = List(contributes_to=PREFERENCES)
    preferences_panes = List(contributes_to=PREFERENCES_PANES)
    tasks = List(contributes_to=TASKS)
    osx_actions = List(contributes_to=OSX_MINIMAL_MENU)

    ###########################################################################
    # Protected interface.
    ###########################################################################

    def _preferences_default(self):
        filename = os.path.join(ETSConfig.application_home, 'preferences.ini')
        if not os.path.exists(filename):
            fh = open(filename, "wb")
            fh.close()
        return [ 'file://' + filename ]

    def _preferences_panes_default(self):
        from preferences import FrameworkPreferencesPane
        from omnimon.tasks.text_edit import TextEditPreferencesPane
        from omnimon.tasks.image_edit import ImageEditPreferencesPane
        from omnimon.tasks.hex_edit import HexEditPreferencesPane
        from omnimon.tasks.html_view import HtmlViewPreferencesPane
        return [ FrameworkPreferencesPane, TextEditPreferencesPane, ImageEditPreferencesPane, HexEditPreferencesPane, HtmlViewPreferencesPane]

    def _tasks_default(self):
        from omnimon.tasks.text_edit import TextEditTask
        from omnimon.tasks.image_edit import ImageEditTask
        from omnimon.tasks.hex_edit import HexEditTask
        from omnimon.tasks.map_edit import MapEditTask
        from omnimon.tasks.html_view import HtmlViewTask

        return self.task_factories_from_tasks([
            TextEditTask,
            ImageEditTask,
            HexEditTask,
            MapEditTask,
            HtmlViewTask,
            ])

    def _osx_actions_default(self):
        from omnimon.framework.actions import NewFileGroup
        
        submenu = lambda: SMenu(
            id='NewFileSubmenu', name="New"
        )
        actions = [
            SchemaAddition(factory=submenu,
                           path='MenuBar/File',
                           before="OpenGroup"
                           ),
            SchemaAddition(factory=NewFileGroup,
                           path='MenuBar/File/NewFileSubmenu',
                           ),
            ]
        
        return actions

