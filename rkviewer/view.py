"""The main View class and associated widgets.
"""
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple
import json

# pylint: disable=maybe-no-member
# pylint: disable=no-name-in-module
import wx
import wx.lib.agw.flatnotebook as fnb
from commentjson.commentjson import JSONLibraryException
from rkplugin.api import init_api
# import wx.lib.agw.shortcuteditor as sedit
from wx.adv import NotificationMessage

import rkviewer
from rkviewer.canvas.geometry import get_bounding_rect
from rkviewer.plugin_manage import PluginManager

from .canvas.canvas import Canvas
from .canvas.data import Compartment, Node, Reaction
from .canvas.state import InputMode, cstate
from .config import (DEFAULT_SETTING_FMT, INIT_SETTING_TEXT, get_default_raw_settings, get_setting, get_theme,
                     CreateConfigDir, GetConfigDir, GetThemeSettingsPath, load_theme_settings, pop_settings_err)
from .events import (CanvasDidUpdateEvent, DidMoveCompartmentsEvent,
                     DidMoveNodesEvent, DidResizeCompartmentsEvent,
                     DidResizeNodesEvent, SelectionDidUpdateEvent,
                     bind_handler)
from .forms import CompartmentForm, NodeForm, ReactionForm
from .mvc import IController, IView
from .utils import ButtonGroup, get_bundled_path, on_msw, start_file
from rkviewer.config import AppSettings


class EditPanel(fnb.FlatNotebook):
    """Panel that displays and allows editing of the details of a node.

    Attributes
        node_form: The actual form widget. This is at the same level as null_message. TODO
        null_message: The widget displayed in place of the form,  when nothing is selected.
    """
    node_form: NodeForm
    reaction_form: ReactionForm
    comp_form: CompartmentForm
    null_message: wx.Panel
    FNB_STYLE = fnb.FNB_NO_X_BUTTON | fnb.FNB_NO_NAV_BUTTONS | fnb.FNB_NODRAG | fnb.FNB_VC8 | fnb.FNB_DROPDOWN_TABS_LIST

    def __init__(self, parent, canvas: Canvas, controller: IController, **kw):
        super().__init__(parent, agwStyle=EditPanel.FNB_STYLE, **kw)

        self.canvas = canvas

        self.node_form = NodeForm(self, canvas, controller)
        self.reaction_form = ReactionForm(self, canvas, controller)
        self.comp_form = CompartmentForm(self, canvas, controller)

        self.null_message = wx.Panel(self)
        text = wx.StaticText(
            self.null_message, label="Nothing is selected.", style=wx.ALIGN_CENTER)
        null_sizer = wx.BoxSizer(wx.HORIZONTAL)
        null_sizer.Add(text, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL)
        self.null_message.SetSizer(null_sizer)
        self.SetCustomPage(self.null_message)

        self.node_form.Hide()
        self.reaction_form.Hide()
        self.comp_form.Hide()
        # overall sizer for alternating form and "nothing selected" displays
        #sizer = wx.BoxSizer(wx.HORIZONTAL)
        #sizer.Add(null_message, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL)
        # self.SetSizer(sizer)

        bind_handler(CanvasDidUpdateEvent, self.OnCanvasDidUpdate)
        bind_handler(SelectionDidUpdateEvent, self.OnSelectionDidUpdate)
        bind_handler(DidMoveNodesEvent, self.OnNodesDidMove)
        bind_handler(DidResizeNodesEvent, self.OnDidResizeNodes)
        bind_handler(DidMoveCompartmentsEvent, self.OnCompartmentsDidMove)
        bind_handler(DidResizeCompartmentsEvent, self.OnDidResizeCompartments)

    def OnCanvasDidUpdate(self, evt):
        self.node_form.UpdateNodes(self.canvas.nodes)
        self.reaction_form.UpdateReactions(self.canvas.reactions)
        self.comp_form.UpdateCompartments(self.canvas.compartments)

    def OnSelectionDidUpdate(self, evt):
        focused = self.GetTopLevelParent().FindFocus()
        should_show_nodes = len(evt.node_indices) != 0
        should_show_reactions = len(evt.reaction_indices) != 0
        should_show_comps = len(evt.compartment_indices) != 0
        need_update_nodes = self.node_form.selected_idx != evt.node_indices
        need_update_comps = self.comp_form.selected_idx != evt.compartment_indices

        cur_page = self.GetCurrentPage()

        node_index = -1
        for i in range(self.GetPageCount()):
            if self.GetPage(i) == self.node_form:
                node_index = i
                break

        if need_update_nodes or need_update_comps:
            self.node_form.UpdateSelection(evt.node_indices, comps_selected=should_show_comps)
        if should_show_nodes:
            if node_index == -1:
                self.InsertPage(0, self.node_form, 'Nodes')
        elif node_index != -1:
            # find and remove existing page
            self.RemovePage(node_index)
            self.node_form.Hide()

        reaction_index = -1
        for i in range(self.GetPageCount()):
            if self.GetPage(i) == self.reaction_form:
                reaction_index = i
                break

        if self.reaction_form.selected_idx != evt.reaction_indices:
            self.reaction_form.UpdateSelection(evt.reaction_indices)
        if should_show_reactions:
            if reaction_index == -1:
                self.AddPage(self.reaction_form, 'Reactions')
        elif reaction_index != -1:
            self.RemovePage(reaction_index)
            self.reaction_form.Hide()

        comp_index = -1
        for i in range(self.GetPageCount()):
            if self.GetPage(i) == self.comp_form:
                comp_index = i
                break
        if need_update_comps or need_update_nodes:
            self.comp_form.UpdateSelection(evt.compartment_indices,
                                           nodes_selected=should_show_nodes)
        if should_show_comps:
            if comp_index == -1:
                self.AddPage(self.comp_form, 'Compartments')
        elif comp_index != -1:
            self.RemovePage(comp_index)
            self.comp_form.Hide()

        # set the active tab to the same as before
        if cur_page is not None and self.GetCurrentPage() is not None:
            if cur_page is self.GetCurrentPage():
                self.AdvanceSelection()

        # need to reset focus to canvas, since for some reason FlatNotebook sets focus to the first
        # field in a notebook page after it is added.
        self.GetSizer().Layout()

        # restore focus, since otherwise for some reason the newly added page gets the focus
        focused.SetFocus()

        # need to manually show this for some reason
        if not should_show_nodes and not should_show_reactions and not should_show_comps:
            self.null_message.Show()

    def OnNodesDidMove(self, evt):
        self.node_form.NodesMovedOrResized(evt)

    def OnDidResizeNodes(self, evt):
        self.node_form.NodesMovedOrResized(evt)

    def OnCompartmentsDidMove(self, evt):
        self.comp_form.CompsMovedOrResized(evt)

    def OnDidResizeCompartments(self, evt):
        self.comp_form.CompsMovedOrResized(evt)


class Toolbar(wx.Panel):
    """ModePanel at the top of the app."""

    def __init__(self, parent, controller: IController, zoom_callback, edit_panel_callback, **kw):
        super().__init__(parent, **kw)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        zoom_in_btn = wx.Button(self, label="Zoom In")
        # TODO make this a method
        sizerflags = wx.SizerFlags().Align(wx.ALIGN_CENTER_VERTICAL).Border(wx.LEFT, 10)
        undo_button = wx.Button(self, label="Undo")
        sizer.Add(undo_button, sizerflags)
        undo_button.Bind(wx.EVT_BUTTON, lambda _: controller.undo())

        redo_button = wx.Button(self, label="Redo")
        sizer.Add(redo_button, sizerflags)
        redo_button.Bind(wx.EVT_BUTTON, lambda _: controller.redo())

        sizer.Add(zoom_in_btn, sizerflags)
        zoom_in_btn.Bind(wx.EVT_BUTTON, lambda _: zoom_callback(True))

        zoom_out_btn = wx.Button(self, label="Zoom Out")
        sizer.Add(zoom_out_btn, sizerflags)
        zoom_out_btn.Bind(wx.EVT_BUTTON, lambda _: zoom_callback(False))

        # Note: Right align after this
        sizer.Add((0, 0), proportion=1, flag=wx.EXPAND)

        toggle_panel_button = wx.Button(self, label="Toggle Details")
        sizer.Add(toggle_panel_button, wx.SizerFlags().Align(
            wx.ALIGN_CENTER_VERTICAL).Border(wx.RIGHT, 10))
        toggle_panel_button.Bind(wx.EVT_BUTTON, edit_panel_callback)

        self.SetSizer(sizer)


class ModePanel(wx.Panel):
    """ModePanel at the left of the app."""

    def __init__(self, *args, toggle_callback, canvas: Canvas, **kw):
        super().__init__(*args, **kw)

        self.btn_group = ButtonGroup(toggle_callback)

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.AppendModeButton('Select', InputMode.SELECT, sizer)
        self.AppendModeButton('+Nodes', InputMode.ADD_NODES, sizer)
        self.AppendModeButton('+Compts', InputMode.ADD_COMPARTMENTS, sizer)
        self.AppendModeButton('Zoom', InputMode.ZOOM, sizer)

        self.AppendSeparator(sizer)
        self.AppendNormalButton('Reactants', canvas.MarkSelectedAsReactants,
                                sizer, tooltip='Mark selected nodes as reactants')
        self.AppendNormalButton('Products', canvas.MarkSelectedAsProducts,
                                sizer, tooltip='Mark selected nodes as products')
        self.AppendNormalButton('Create Rxn', canvas.CreateReactionFromMarked,
                                sizer, tooltip='Create reaction from marked reactants and products')

        self.SetSizer(sizer)

    def AppendModeButton(self, label: str, mode: InputMode, sizer: wx.Sizer):
        btn = wx.ToggleButton(self, label=label)
        sizer.Add(btn, wx.SizerFlags().Align(
            wx.ALIGN_CENTER).Border(wx.TOP, 10))
        self.btn_group.AddButton(btn, mode)

    def AppendNormalButton(self, label: str, callback, sizer: wx.Sizer, tooltip: str = None):
        btn = wx.Button(self, label=label)
        if tooltip is not None:
            btn.SetToolTip(tooltip)
        btn.Bind(wx.EVT_BUTTON, lambda _: callback())
        sizer.Add(btn, wx.SizerFlags().Align(
            wx.ALIGN_CENTER).Border(wx.TOP, 10))

    def AppendSeparator(self, sizer: wx.Sizer):
        line = wx.StaticLine(self, style=wx.LI_HORIZONTAL)
        sizer.Add(line, wx.SizerFlags().Expand().Border(wx.TOP, 10))


class MainPanel(wx.Panel):
    """The main panel, which is the only chlid of the root Frame."""
    controller: IController
    canvas: Canvas
    mode_panel: ModePanel
    toolbar: Toolbar
    edit_panel: EditPanel

    def __init__(self, parent, controller: IController):
        # ensure the parent's __init__ is called
        super().__init__(parent, style=wx.CLIP_CHILDREN)
        self.SetBackgroundColour(get_theme('overall_bg'))
        self.controller = controller

        self.canvas = Canvas(self.controller, self,
                             size=(get_theme('canvas_width'),
                                   get_theme('canvas_height')),
                             realsize=(4 * get_theme('canvas_width'),
                                       4 * get_theme('canvas_height')),
                             )
        self.canvas.SetScrollRate(10, 10)

        # The bg of the available canvas will be drawn by canvas in OnPaint()
        self.canvas.SetBackgroundColour(get_theme('canvas_outside_bg'))

        def set_input_mode(ident): cstate.input_mode = ident

        # create a panel in the frame
        self.mode_panel = ModePanel(self,
                                    size=(get_theme('mode_panel_width'),
                                          get_theme('canvas_height')),
                                    toggle_callback=set_input_mode,
                                    canvas=self.canvas,
                                    )

        self.mode_panel.SetBackgroundColour(get_theme('toolbar_bg'))

        toolbar_width = get_theme('canvas_width') + \
            get_theme('edit_panel_width') + get_theme('vgap')
        self.toolbar = Toolbar(self, controller,
                               size=(toolbar_width, get_theme('toolbar_height')),
                               zoom_callback=self.canvas.ZoomCenter,
                               edit_panel_callback=self.ToggleEditPanel)
        self.toolbar.SetBackgroundColour(get_theme('toolbar_bg'))

        self.edit_panel = EditPanel(self, self.canvas, self.controller,
                                    size=(get_theme('edit_panel_width'),
                                          get_theme('canvas_height')))
        self.edit_panel.SetBackgroundColour(get_theme('toolbar_bg'))

        # and create a sizer to manage the layout of child widgets
        sizer = wx.GridBagSizer(vgap=get_theme('vgap'), hgap=get_theme('hgap'))

        sizer.Add(self.toolbar, wx.GBPosition(0, 1),
                  wx.GBSpan(1, 2), flag=wx.EXPAND)
        sizer.Add(self.mode_panel, wx.GBPosition(1, 0), flag=wx.EXPAND)
        sizer.Add(self.canvas, wx.GBPosition(1, 1),  flag=wx.EXPAND)
        sizer.Add(self.edit_panel, wx.GBPosition(1, 2), flag=wx.EXPAND)

        # allow the canvas to grow
        sizer.AddGrowableCol(1, 1)
        sizer.AddGrowableRow(1, 1)

        # Set the sizer and *prevent the user from resizing it to a smaller size
        self.SetSizerAndFit(sizer)


    def ToggleEditPanel(self, evt):
        sizer = self.GetSizer()
        if self.edit_panel.IsShown():
            sizer.Detach(self.edit_panel)
            sizer.SetItemSpan(self.canvas, wx.GBSpan(1, 2))
            self.edit_panel.Hide()
        else:
            sizer.SetItemSpan(self.canvas, wx.GBSpan(1, 1))
            sizer.Add(self.edit_panel, wx.GBPosition(1, 2), flag=wx.EXPAND)
            self.edit_panel.Show()

        self.Layout()

class AboutDialog(wx.Dialog):
    def __init__(self, parent: wx.Window):
        pass      
        #super().__init__(parent, title='About RKViewer')
        #sizer = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        #self.left_width = 150
        #elf.right_width = 180
        #self.row_height = 50
        #self.leftflags = wx.SizerFlags().Border(wx.TOP, 10)
        #self.rightflags = wx.SizerFlags().Border(wx.TOP, 10)
        #self.leftfont = wx.Font(wx.FontInfo(10).Bold())
        #self.rightfont = wx.Font(wx.FontInfo(10))
        #elf.AppendRow('PathDesigner', "An Extensible Reaction Network Editors", sizer)
        #self.AppendRow('Version', rkviewer.__version__, sizer)
        #self.SetSizerAndFit(sizer)

    def AppendRow(self, left_text: str, right_text: str, sizer: wx.FlexGridSizer):
        left = wx.StaticText(self, label=left_text, size=(self.left_width, 30),
                             style=wx.ALIGN_RIGHT)
        left.SetFont(self.leftfont)
        right = wx.StaticText(self, label=right_text, size=(self.right_width, 30),
                              style=wx.ALIGN_LEFT)
        right.SetFont(self.rightfont)
        sizer.Add(left, self.leftflags)
        sizer.Add(right, self.rightflags)

class MainFrame(wx.Frame):
    """The main frame."""

    def __init__(self, controller: IController, manager: PluginManager, **kw):
        super().__init__(None, style=wx.DEFAULT_FRAME_STYLE |
                         wx.WS_EX_PROCESS_UI_UPDATES, **kw)
        load_theme_settings()
        self.appSettings = AppSettings()
        self.appSettings.load_appSettings()
        
        self.manager = manager
        status_fields = get_setting('status_fields')
        assert status_fields is not None
        self.CreateStatusBar(len(get_setting('status_fields')))
        self.SetStatusWidths([width for _, width in status_fields])
        self.main_panel = MainPanel(self, controller)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.main_panel, 1, wx.EXPAND)

        canvas = self.main_panel.canvas
        self.controller = controller
        self.canvas = canvas

        entries = list()
        menu_bar = wx.MenuBar()

        self.menu_events = list()
        file_menu = wx.Menu()
      
        self.AddMenuItem(file_menu, '&New...', 'Start a new network', lambda _: self.NewNetwork(),  entries, key=(wx.ACCEL_CTRL, ord('N')))
        file_menu.AppendSeparator() 
        self.AddMenuItem(file_menu, '&Load...', 'Load network from JSON file', lambda _: self.LoadFromJson(), entries, key=(wx.ACCEL_CTRL, ord('O')))
        self.AddMenuItem(file_menu, '&Save', 'Save current network as a JSON file', lambda _: self.SaveJson(), entries, key=(wx.ACCEL_CTRL, ord('S')))
        self.AddMenuItem(file_menu, '&Save As...', 'Save current network as a JSON file', lambda _: self.SaveAsJson(), entries, key=(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('N')))
        file_menu.AppendSeparator()      
        self.AddMenuItem(file_menu, '&Edit Settings', 'Edit settings', lambda _: self.EditSettings(),  entries)
        self.AddMenuItem(file_menu, '&Reload Settings', 'Reload settings', lambda _: self.ReloadSettings(),  entries)
        file_menu.AppendSeparator() 
        self.AddMenuItem(file_menu, '&Export...', 'Export Network as an image or pdf', lambda _: self.ExportNetwork(),  entries)        
        file_menu.AppendSeparator() 
        self.AddMenuItem(file_menu, '&Print...', 'Print Network', lambda _: self.PrintNetwork(),  entries, key=(wx.ACCEL_CTRL, ord('P')))
        file_menu.AppendSeparator()                         
        self.AddMenuItem(file_menu, 'E&xit', 'Exit application', lambda _: self.Close(), entries,  id_=wx.ID_EXIT)

        edit_menu = wx.Menu()
        self.AddMenuItem(edit_menu, '&Undo', 'Undo action', lambda _: controller.undo(),
                         entries, key=(wx.ACCEL_CTRL, ord('Z')))
        self.AddMenuItem(edit_menu, '&Redo', 'Redo action', lambda _: controller.redo(),
                         entries, key=(wx.ACCEL_CTRL, ord('Y')))
        edit_menu.AppendSeparator()
        self.AddMenuItem(edit_menu, '&Copy', 'Copy selected nodes', lambda _: canvas.CopySelected(),
                         entries, key=(wx.ACCEL_CTRL, ord('C')))
        self.AddMenuItem(edit_menu, '&Paste', 'Paste selected nodes',
                         lambda _: canvas.Paste(), entries, key=(wx.ACCEL_CTRL, ord('V')))
        self.AddMenuItem(edit_menu, '&Cut', 'Cut selected nodes',
                         lambda _: canvas.CutSelected(), entries, key=(wx.ACCEL_CTRL, ord('X')))
        edit_menu.AppendSeparator()
        self.AddMenuItem(edit_menu, '&Delete selected', 'Deleted selected',
                         lambda _: canvas.DeleteSelectedItems(), entries,
                         key=(wx.ACCEL_NORMAL, wx.WXK_DELETE))

        select_menu = wx.Menu()
        self.AddMenuItem(select_menu, 'Select &All', 'Select all',
                         lambda _: canvas.SelectAll(), entries, key=(wx.ACCEL_CTRL, ord('A')))
        self.AddMenuItem(select_menu, 'Select All &Nodes', 'Select all nodes',
                         lambda _: canvas.SelectAllNodes(), entries, key=(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('N')))
        self.AddMenuItem(select_menu, 'Select All &Reactions', 'Select all reactions',
                         lambda _: canvas.SelectAllReactions(), entries, key=(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('R')))
        self.AddMenuItem(select_menu, 'Clear Selection', 'Clear the current selection',
                         lambda _: canvas.ClearCurrentSelection(), entries,
                         key=(wx.ACCEL_NORMAL, wx.WXK_ESCAPE))

        view_menu = wx.Menu()
        self.AddMenuItem(view_menu, 'Zoom &In', 'Zoom in canvas', lambda _: canvas.ZoomCenter(True),
                         entries, key=(wx.ACCEL_CTRL, ord('+')))
        self.AddMenuItem(view_menu, 'Zoom &Out', 'Zoom out canvas',
                         lambda _: canvas.ZoomCenter(False), entries, key=(wx.ACCEL_CTRL, ord('-')))
        self.AddMenuItem(view_menu, '&Reset Zoom', 'Reset canva zoom',
                         lambda _: canvas.ResetZoom(), entries, key=(wx.ACCEL_CTRL, ord(' ')))

        reaction_menu = wx.Menu()
        self.AddMenuItem(reaction_menu, 'Mark Selected as &Reactants',
                         'Mark selected nodes as reactants',
                         lambda _: canvas.MarkSelectedAsReactants(), entries,
                         key=(wx.ACCEL_NORMAL, ord('S')))
        self.AddMenuItem(reaction_menu, 'Mark Selected as &Products',
                         'Mark selected nodes as products',
                         lambda _: canvas.MarkSelectedAsProducts(), entries,
                         key=(wx.ACCEL_NORMAL, ord('F')))
        self.AddMenuItem(reaction_menu, '&Create Reaction From Selected',
                         'Create reaction from selected sources and targets',
                         lambda _: canvas.CreateReactionFromMarked(), entries,
                         key=(wx.ACCEL_CTRL, ord('R')))

        plugins_menu = wx.Menu()
        self.AddMenuItem(plugins_menu, '&Plugins...', 'Manage plugins', self.ManagePlugins, entries,
                         key=(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('P')))
        self.manager.register_menu(plugins_menu, self)

        help_menu = wx.Menu()
        self.AddMenuItem(help_menu, '&About...',
                         'Show about dialog', self.onAboutDlg, entries) #self.ShowAbout, entries)
        self.AddMenuItem(help_menu, '&Default settings...', 'View default settings',
                         lambda _: self.ShowDefaultSettings(), entries)

        menu_bar.Append(file_menu, '&File')
        menu_bar.Append(edit_menu, '&Edit')
        menu_bar.Append(select_menu, '&Select')
        menu_bar.Append(view_menu, '&View')
        menu_bar.Append(reaction_menu, '&Reaction')
        menu_bar.Append(plugins_menu, '&Plugins')
        menu_bar.Append(help_menu, '&Help')

        atable = wx.AcceleratorTable(entries)

        self.SetMenuBar(menu_bar)
        self.atable = atable
        canvas.SetAcceleratorTable(atable)

        self.OverrideAccelTable(self)

        self.Bind(wx.EVT_CLOSE, self.OnCloseExit)

        # set sizer at the end, after adding the menus.
        self.SetSizerAndFit(sizer)
        
        self.SetSize (self.appSettings.size)
        self.SetPosition (self.appSettings.position)
        self.Layout()

        #Record the initial position of the window
        self.controller.initial_position = self.GetPosition()


    # Any thing we need to do when the app closes can be included here
    def OnCloseExit (self, evt):
        self.appSettings.size = self.GetSize()
        self.appSettings.position = self.Position
        self.appSettings.save_appSettings()
        self.Destroy()
    

    def AddMenuItem(self, menu: wx.Menu, text: str, help_text: str, callback: Callable,
                    entries: List, key: Tuple[Any, int] = None, id_: int = None):
        if id_ is None:
            id_ = wx.NewIdRef(count=1)

        shortcut = ''
        if key is not None:
            entry = wx.AcceleratorEntry(key[0], key[1], id_)
            entries.append(entry)
            shortcut = entry.ToString()

        item = menu.Append(id_, '{}\t{}'.format(text, shortcut), help_text)
        self.Bind(wx.EVT_MENU, callback, item)
        self.menu_events.append((callback, item))

    def onAboutDlg(self, event):
       info = wx.adv.AboutDialogInfo()
       info.Name = "An Extensible Reaction Network Editor"
       info.Version = "0.0.1 Beta"
       info.Copyright = "(C) 2020"
       info.Description = "Create reaction networks"
       info.WebSite = ("http://www.XXXXX.org", "Home Page")
       info.Developers = ["Gary Geng, Jin Xu, Carmen Pereña Cortés, Herbert Sauro"]
       info.License = "MIT"

       # Show the wx.AboutBox
       wx.adv.AboutBox(info)

    def ReloadSettings(self):
        load_theme_settings()
        err = pop_settings_err()
        if err is None:
            # msg = NotificationMessage('Settings reloaded', 'Some changes may not be applied until the application is restarted.')
            # msg.Show()
            pass
        else:
            if isinstance(err, JSONLibraryException):
                message = 'Failed when parsing settings.json.\n\n'
                message += err.message
            else:
                message = 'Invalid settings in settings.json.\n\n'
                message += str(err)
            message += str(err)
            self.main_panel.canvas.ShowWarningDialog(message)
        
    def EditSettings(self):
        """Open the preferences file for editing."""
        if not CreateConfigDir():
            return

        if not os.path.exists(GetThemeSettingsPath()):
            with open(GetThemeSettingsPath(), 'w') as fp:
                fp.write(INIT_SETTING_TEXT)
        else:
            if not os.path.isfile(GetThemeSettingsPath()):
                self.main_panel.canvas.ShowWarningDialog('Could not open settings file since '
                                                         'a directory already exists at path '
                                                         '{}.'.format(GetThemeSettingsPath()))
                return

        # If we're running windows use notepad
        if os.name == 'nt':
           # Doing it this way allows python to regain control even though notepad hasn't been clsoed 
           import subprocess
           _pid = subprocess.Popen(['notepad.exe', GetThemeSettingsPath()]).pid
        else:
           start_file(GetThemeSettingsPath())

    def ShowDefaultSettings(self):
        if not CreateConfigDir():
            return

        if os.path.exists(os.path.join(GetConfigDir(), '.default-settings.json')) and not os.path.isfile(os.path.join(GetConfigDir(), '.default-settings.json')):
            self.main_panel.canvas.ShowWarningDialog('Could not open default settings file '
                                                        'since a directory already exists at path '
                                                        '{}.'.format(os.path.join(GetConfigDir(), '.default-settings.json')))
            return
        # TODO prepopulate file with help text, i.e link to docs about schema
        json_str = json.dumps(get_default_raw_settings(), indent=4, sort_keys=True)
        with open(os.path.join(GetConfigDir(), '.default-settings.json'), 'w') as fp:
            fp.write(DEFAULT_SETTING_FMT.format(json_str))

        # If we're running windows use notepad
        if os.name == 'nt':
           # Doing it this way allows python to regain control even though notepad hasn't been clsoed 
           import subprocess
           _pid = subprocess.Popen(['notepad.exe', os.path.join(GetConfigDir(), '.default-settings.json')]).pid
        else:
           start_file(os.path.join(GetConfigDir(), '.default-settings.json'))            

    def NewNetwork(self):
        self.controller.new_network()  # This doesn't work, so try different way
        # self.canvas.SelectAll()
        # self.canvas.DeleteSelectedItems()

    def PrintNetwork(self):
        bmp = self.main_panel.canvas.DrawToBitmap()
        bmp.SaveFile('printout.png', type=wx.BITMAP_TYPE_PNG)
       
    def ExportNetwork(self):
        self.main_panel.canvas.ShowWarningDialog("Export not yet implemented")

    def SaveJson(self):
        self.main_panel.canvas.ShowWarningDialog("Not yet implemented")

    def SaveAsJson(self):
        with wx.FileDialog(self, "Save JSON file", wildcard="JSON files (*.json)|*.json",
                    style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # save the current contents in the file
            pathname = fileDialog.GetPath()
            try:
                net_index = 0
                net_json = self.controller.dump_network(net_index)
                with open(pathname, 'w') as file:
                    json.dump(net_json, file)
            except IOError:
                wx.LogError("Cannot save current data in file '{}'.".format(pathname))


    def LoadFromJson(self):
        with wx.FileDialog(self, "Load JSON file", wildcard="JSON files (*.json)|*.json",
                    style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # save the current contents in the file
            pathname = fileDialog.GetPath()
            try:
                with open(pathname, 'r') as file:
                    net_json = json.load(file)
                _net_index = self.controller.load_network(net_json)
            except IOError:
                wx.LogError("Cannot load network from file '{}'.".format(pathname))

    def ManagePlugins(self, evt):
        # TODO create special empty page that says "No plugins loaded"
        with self.manager.create_dialog(self) as dlg:
            dlg.Centre()
            if dlg.ShowModal() == wx.ID_OK:
                pass  # exited normally
            else:
                pass  # exited by clicking some button

    def ShowAbout(self, evt):
        with AboutDialog(self) as dlg:
            dlg.Centre()
            dlg.ShowModal()

    def OverrideAccelTable(self, widget):
        """Set up functions to disable accelerator shortcuts for certain descendants of widgets.

        This is to prevent accelerator shortcuts to be applied in unexpected situations, when
        something other than the canvas is in foucs. For example, if the user is editing the name
        of a node, they may use ctrl+Z to undo some text operation. However, since ctrl+Z is bound
        to the "undo last operation" action on canvas, it will be caught by the canvas instead.
        This prevents that by attaching a temporary, "null" accelerator table when a TextCtrl
        widget goes into focus.
        """
        if isinstance(widget, wx.TextCtrl):
            def OnFocus(evt):
                for cb, item in self.menu_events:
                    self.Unbind(wx.EVT_MENU, handler=cb, source=item)
                # For some reason, we need to do this for both self and menubar to disable the
                # AcceleratorTable. Don't ever lose this sacred knowledge, for it came at the cost
                # of 50 minutes.
                self.SetAcceleratorTable(wx.NullAcceleratorTable)
                self.GetMenuBar().SetAcceleratorTable(wx.NullAcceleratorTable)
                evt.Skip()

            def OnUnfocus(evt):
                for cb, item in self.menu_events:
                    self.Bind(wx.EVT_MENU, handler=cb, source=item)
                self.SetAcceleratorTable(self.atable)
                evt.Skip()

            widget.Bind(wx.EVT_SET_FOCUS, OnFocus)
            widget.Bind(wx.EVT_KILL_FOCUS, OnUnfocus)

        for child in widget.GetChildren():
            self.OverrideAccelTable(child)


class View(IView):
    """Implementation of the view class."""

    def __init__(self):
        self.controller = None
        self.manager = None
        self.app = None

    def bind_controller(self, controller: IController):
        self.controller = controller

    def init(self):
        assert self.controller is not None
        self.app = wx.App()
        self.manager = PluginManager(self.controller)
        self.manager.load_from('plugins')
        self.frame = MainFrame(
            self.controller, self.manager, title='RK Network Viewer')
        init_api(self.frame.main_panel.canvas, self.controller)
        self.canvas_panel = self.frame.main_panel.canvas

    def main_loop(self):
        assert self.app is not None
        self.frame.Show()
        self.app.MainLoop()

    def update_all(self, nodes: List[Node], reactions: List[Reaction],
                   compartments: List[Compartment]):
        """Update the list of nodes.

        Note that View takes ownership of the list of nodes and may modify it.
        """
        self.canvas_panel.Reset(nodes, reactions, compartments)
        self.canvas_panel.LazyRefresh()
