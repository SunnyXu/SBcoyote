'''
Given a random network, this plugin  will rearrange the network neatly on the screen.
Version 0.01: Author: Carmen Perena Cortes, Herbert M Sauro 2020
Based on THOMAS M. J. FRUCHTERMAN AND EDWARD M. REINGOLD's Graph Drawing by Force-directed Placement
SOFTWARE—PRACTICE AND EXPERIENCE, VOL. 21(1 1), 1129-1164 (NOVEMBER 1991)
Using python's networkx
'''
import wx
from rkplugin.plugins import PluginMetadata, WindowedPlugin
from rkplugin import api
from rkplugin.api import Node, Vec2, Reaction
import math
from dataclasses import field
from typing import List
from random import uniform
from numpy.random import rand
import numpy as np
import random
from dataclasses import dataclass
import networkx as nx

metadata = PluginMetadata(
    name='AutolayoutNetworkX',
    author='Carmen and Herbert M Sauro',
    version='0.5.2',
    short_desc='Auto Layout using networkX.',
    long_desc='Rearrange a random network into a neat auto layout'
)

class LayoutNetworkX(WindowedPlugin):
    def __init__(self):
        '''
        Initialize the RandomNetwork.
        Args:
            self
        '''
        super().__init__(metadata)

    def create_window(self, dialog):
        '''
        Create a window with several inputs and buttons.
        Args:
            self
            dialog
        '''
        # TODO: k, gravity, useMagnetism, useBoundary, useGrid
        window = wx.Panel(dialog, pos=(5,100), size=(350, 200))
        MaxIter = wx.StaticText(window, -1, 'Maximum Number of Iterations', (20 , 20))
        self.MaxIterText = wx.TextCtrl(window, -1, "100", (220, 20), size=(100, -1))
        self.MaxIterText.SetInsertionPoint(0)
        self.MaxIterText.Bind(wx.EVT_TEXT, self.OnText_MaxIter)
        self.MaxIterValue = int(self.MaxIterText.GetValue())
        k = wx.StaticText(window, -1, 'k (float > 0)', (20 , 50))
        self.kText = wx.TextCtrl(window, -1, "70", (220, 50), size=(100, -1))
        self.kText.SetInsertionPoint(0)
        self.kText.Bind(wx.EVT_TEXT, self.OnText_k)
        self.kValue = float(self.kText.GetValue())        
        scale = wx.StaticText(window, -1, 'Scale of Layout', (20 , 80))
        self.scaleText = wx.TextCtrl(window, -1, "550", (220, 80), size=(100, -1))
        self.scaleText.SetInsertionPoint(0)
        self.scaleText.Bind(wx.EVT_TEXT, self.OnText_scale)
        self.scaleValue = float(self.scaleText.GetValue())  
        apply_btn = wx.Button(window, -1, 'Run', (220, 130))
        apply_btn.Bind(wx.EVT_BUTTON, self.Apply)
        window.SetPosition (wx.Point(10,10))
        return window

    def OnText_MaxIter(self, evt):
        try:
          update = evt.GetString()
          if update != '':
              self.MaxIterValue = int(self.MaxIterText.GetValue())
        except ValueError:
           wx.MessageBox('Value must be a number', 'Error', wx.OK | wx.ICON_INFORMATION)

    def OnText_k(self, evt):
        try:
           update = evt.GetString()
           if update != '':
              self.kValue = float(self.kText.GetValue())
        except ValueError:
           wx.MessageBox('Value must be a number', 'Error', wx.OK | wx.ICON_INFORMATION)

    def OnText_scale(self, evt):
        try:
           update = evt.GetString()
           if update != '':
              self.scaleValue = float(self.scaleText.GetValue())
        except ValueError:
           wx.MessageBox('Value must be a number', 'Error', wx.OK | wx.ICON_INFORMATION)
           
    def Apply(self, evt):
        G = nx.Graph()
        nodes = np.array(list(api.get_node_indices(0)))
        reactionsInd =  np.array(list(api.get_reaction_indices(0)))
        originalPos = {}
        def generateGraph():
            nodes = np.array(list(api.get_node_indices(0)))
            reactionsInd =  np.array(list(api.get_reaction_indices(0)))
            cStr = np.empty_like(reactionsInd, dtype=str)
            cStr[:,] = "c"
            centroidId = np.char.add(cStr, reactionsInd.astype(str))
            G.add_nodes_from(centroidId)
            nStr = np.empty_like(nodes, dtype=str)
            nStr[:,] = "n"
            nodesId = np.array(list(np.char.add(nStr, nodes.astype(str))))
            G.add_nodes_from(nodesId)
            for n in nodes:
                centroidsTo = np.array(list(api.get_reactions_as_product(0, n))) # Gets the reactions in which it is a product -> TO 
                cStr = np.empty_like(centroidsTo, dtype=str)
                cStr[:,] = "c"
                centroidsToIn = np.char.add(cStr, centroidsTo.astype(str)) # centroids from which the node is product
                centroidsFrom = np.array(list(api.get_reactions_as_reactant(0, n))) # reactions in which it is a reactanr -> FROM
                cStr = np.empty_like(centroidsFrom, dtype=str)
                cStr[:,] = "c"
                centroidsFromIn = np.char.add(cStr, centroidsFrom.astype(str)) # centroids to which the node is reactant
                nS = np.empty_like(centroidsToIn, dtype = str)
                nS[:,] = "n"
                numS = np.empty_like(centroidsToIn, dtype = int)
                numS[:,] = n
                nodeIndArrayTo = np.char.add(nS, numS.astype(str))
                nS = np.empty_like(centroidsFromIn, dtype = str)
                nS[:,] = "n"
                numS = np.empty_like(centroidsFromIn, dtype = int)
                numS[:,] = n
                nodeIndArrayFrom = np.char.add(nS, numS.astype(str))
                edgesTo = np.array(list(zip(centroidsToIn, nodeIndArrayTo)))
                edgesFrom = np.array(list(zip(nodeIndArrayFrom, centroidsFromIn)))
                G.add_edges_from(edgesTo)
                G.add_edges_from(edgesFrom)
            cn = 0
            for rea in api.get_reactions(0):
                cent = api.compute_centroid(0, rea.sources, rea.targets)
                #originalPos[centroidId[cn]] = list([cent.x, cent.y])
                originalPos[centroidId[cn]] = list([random.randint(0,600), random.randint(0,600)])
                cn = cn + 1
            cn = 0
            for nod in api.get_nodes(0):
                #originalPos[nodesId[cn]] = list([nod.position.x, nod.position.y])
                # random.randint(0,500), nod.position.y+random.randint (0,500)])
                originalPos[nodesId[cn]] = list([random.randint(0,600), random.randint (0,600)])
                cn = cn + 1
        generateGraph()
        print(nx.to_dict_of_lists(G))
        nodeIds = list (api.get_node_indices(0))
        with api.group_action():   
            for t in range(20):
                pos = (nx.fruchterman_reingold_layout(G, k = self.kValue, iterations = self.MaxIterValue, scale = self.scaleValue, pos = originalPos))
                positions = np.array(list(pos.values()))
                centroids = positions[0: len(reactionsInd)]
                nodes = positions[len(reactionsInd): len(positions)]
                minX = 0
                minY = 0
                for p in positions:
                    if p[0] < minX:
                        minX = p[0]
                    if p[1] < minY:
                        minY = p[1]
                nodes = nodes - np.array([minX, minY])
                count = 0
                for n in nodes:
                    newX = float(n[0])
                    newY = float(n[1])
                    api.move_node(0, nodeIds[count], position = Vec2(newX, newY), allowNegativeCoordinates=True)   
                    count = count + 1
                
                '''
                count = 0
                for c in centroids:
                    newX = float(c[0])
                    newY = float(c[1])
                    api.update_reaction(0, reactionsInd[count], center_pos= Vec2(newX, newY))  
                    count = count + 1
                '''
                
                for r in api.get_reactions(0):
                    handles = api.default_handle_positions(0, r.index) # centroid, sources, target
                    api.set_reaction_center_handle(0, r.index, handles[0])
                    count = 1
                    for s in r.sources:
                        api.set_reaction_node_handle(0, r.index, s, True, handles[count])
                        count += 1
                    for t in r.targets:
                        api.set_reaction_node_handle(0, r.index, t, False, handles[count])
                        count += 1
                

            ws = api.window_size()
            offset = Vec2(ws.x/4, ws.y/4)
            api.translate_network(0, offset, check_bounds = True)