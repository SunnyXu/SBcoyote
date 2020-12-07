"""
Iodine Network Object Model.

Original author:    RJ Zhou
"Forked" from:      https://github.com/zrj26/go-NOM
Adapted by:         Gary Geng

TODOs
    * Phase out errCode, or at least provide more detalis in error messages.
"""
from __future__ import annotations

from marshmallow.decorators import post_load
from .mvc import (IDNotFoundError, IDRepeatError, NodeNotFreeError, NetIndexError,
                  ReactionIndexError, NodeIndexError, CompartmentIndexError, StoichError,
                  StackEmptyError, JSONError, FileError)
from .canvas.geometry import Vec2
import copy
from dataclasses import dataclass, field
import json
from typing import Any, DefaultDict, Dict, MutableSet, Optional, Set, Tuple, List, cast
from enum import Enum
from collections import defaultdict
from marshmallow import Schema, fields, validate, missing as missing_, ValidationError, pre_dump


@dataclass(frozen=True)
class TColor:
    r: int
    g: int
    b: int
    a: int = 255

    def swapped(self, r: int = None, g: int = None, b: int = None, a: int = None) -> TColor:
        if r is None:
            r = self.r
        if g is None:
            g = self.g
        if b is None:
            b = self.b
        if a is None:
            a = self.a
        return TColor(r, g, b, a)


class TFont:
    pointSize: int
    family: str  # TODO change to enum
    style: str
    weight: str
    name: str
    color: TColor

    def __init__(self):
        self.pointSize = 20
        self.family = "default"
        self.style = "normal"
        self.weight = "default"
        self.name = ""
        self.color = TColor(0, 0, 0, 255)


@dataclass
class TNode:
    id: str
    position: Vec2
    rectSize: Vec2
    floating : bool  # If false it means the node is a boundary node
    compi: int = -1
    fillColor: TColor = TColor(255, 150, 80, 255)
    outlineColor: TColor = TColor(255, 100, 80, 255)
    outlineThickness: float = 3
    font: TFont = TFont()


class TNetwork:
    id: str
    nodes: Dict[int, TNode]
    reactions: Dict[int, TReaction]
    compartments: Dict[int, TCompartment]
    baseNodes: Set[int]  #: Set of node indices not in any compartment
    srcMap: DefaultDict[int, MutableSet[int]]  #: Map nodes to reactions of which it is a source
    destMap: DefaultDict[int, MutableSet[int]]  #: Map nodes to reactions of which it is a target
    lastNodeIdx: int
    lastReactionIdx: int
    lastCompartmentIdx: int

    def __init__(self, id: str, nodes: Dict[int, TNode] = None,
                 reactions: Dict[int, TReaction] = None,
                 compartments: Dict[int, TCompartment] = None):
        if nodes is None:
            nodes = dict()
        if reactions is None:
            reactions = dict()
        if compartments is None:
            compartments = dict()
        self.id = id
        self.nodes = nodes
        self.reactions = reactions
        self.compartments = compartments
        self.baseNodes = set(index for index, n in nodes.items() if n.compi)
        self.srcMap = defaultdict(set)
        self.destMap = defaultdict(set)
        # Initialize srcMap and destMap
        for index, reaction in reactions.items():
            for src in reaction.reactants:
                self.srcMap[src].add(index)
            for dest in reaction.products:
                self.destMap[dest].add(index)

        self.lastNodeIdx = max(nodes.keys(), default=-1) + 1
        self.lastReactionIdx = max(reactions.keys(), default=-1) + 1
        self.lastCompartmentIdx = max(compartments.keys(), default=-1) + 1

    def addNode(self, node: TNode):
        self.nodes[self.lastNodeIdx] = node
        self.baseNodes.add(self.lastNodeIdx)
        self.lastNodeIdx += 1

    def addReaction(self, rea: TReaction):
        self.reactions[self.lastReactionIdx] = rea

        # update nodeToReactions
        for src in rea.reactants:
            self.srcMap[src].add(self.lastReactionIdx)
        for dest in rea.products:
            self.destMap[dest].add(self.lastReactionIdx)

        self.lastReactionIdx += 1

    def addCompartment(self, comp: TCompartment) -> int:
        ind = self.lastCompartmentIdx
        self.compartments[ind] = comp
        self.lastCompartmentIdx += 1
        return ind


@dataclass
class TReaction:
    id: str
    centerPos: Optional[Vec2] = None
    rateLaw: str = ""
    reactants: Dict[int, TSpeciesNode] = field(default_factory=dict)
    products: Dict[int, TSpeciesNode] = field(default_factory=dict)
    fillColor: TColor = TColor(255, 150, 80, 255)
    thickness: float = 3.0
    centerHandlePos: Vec2 = Vec2()
    bezierCurves: bool = True  # If false it means a straight line


@dataclass
class TSpeciesNode:
    stoich: float
    handlePos: Vec2 = Vec2()


@dataclass
class TCompartment:
    id: str
    position: Vec2
    rectSize: Vec2
    node_indices: Set[int] = field(default_factory=set)
    volume: float = 1
    fillColor: TColor = TColor(0, 247, 255, 255)
    outlineColor: TColor = TColor(0, 106, 255, 255)
    outlineThickness: float = 2


class TStack:
    items: List[TNetworkDict]

    def __init__(self):
        self.items = []

    def isEmpty(self):
        return self.items == []

    def push(self, netDict: TNetworkDict):
        theSet = copy.deepcopy(netDict)
        self.items.append(theSet)

    def pop(self):
        return self.items.pop()


class TNetworkDict(Dict[int, TNetwork]):
    def __init__(self):
        super().__init__()
        self.lastNetIndex = 0


class ErrorCode(Enum):
    OK = 0
    OTHER = -1
    ID_NOT_FOUND = -2
    ID_REPEAT = -3
    NODE_NOT_FREE = -4
    NETI_NOT_FOUND = -5
    REAI_NOT_FOUND = -6
    NODEI_NOT_OFUND = -7
    BAD_STOICH = -8
    STACK_EMPTY = -9
    JSON_ERROR = -10
    FILE_ERROR = -11
    OUT_OF_RANGE = -12
    COMPI_NOT_FOUND = -13


errorDict = {
    0: "ok",
    -1: "other",
    -2: "id not found",
    -3: "id repeat",
    -4: "node is not free",
    -5: "net index not found",
    -6: "reaction index not found",
    -7: "node index not found",
    -8: "bad stoich: stoich has to be positive",
    -9: "undo/redo stack is empty",
    -10: "Json convert error",
    -11: "File error",
    -12: "Variable out of range",
    -13: "Compartment index not found",
}


ExceptionDict = {
    -2: IDNotFoundError,
    -3: IDRepeatError,
    -4: NodeNotFreeError,
    -5: NetIndexError,
    -6: ReactionIndexError,
    -7: NodeIndexError,
    -8: StoichError,
    -9: StackEmptyError,
    -10: JSONError,
    -11: FileError,
    -12: ValueError,
    -13: CompartmentIndexError,
}


fontFamilyDict = {
    "default": 0,
    "decorative": 1,
    "roman": 2,
    "script": 3,
    "swiss": 4,
    "modern": 5,
}

fontStyleDict = {
    "normal": 0,
    "italic": 1,
}

fontWeightDict = {
    "default": 0,
    "light": 1,
    "bold": 2,
}


stackFlag: bool = True
errCode: int = 0
networkDict: TNetworkDict = TNetworkDict()
netSetStack: TStack = TStack()
redoStack: TStack = TStack()
lastNetIndex: int = 0


def getErrorCode():
    """get the error code of last function"""
    global errCode
    return errCode


def undo():
    """
    Undo ge back to last state
    errCode: -9: stack is empty
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if netSetStack.isEmpty():
        errCode = -9
    else:
        redoStack.push(networkDict)
        networkDict = netSetStack.pop()
    if errCode < 0:
        raise ExceptionDict[errCode](errorDict[errCode])


def redo():
    """
    Redo redo
    errCode: -9: stack is empty
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    if redoStack.isEmpty():
        errCode = -9
    else:
        netSetStack.push(networkDict)
        networkDict = redoStack.pop()
    if errCode < 0:
        raise ExceptionDict[errCode](errorDict[errCode])


def startGroup():
    """
    StartGroup used at the start of a group operaction or secondary function.
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    redoStack = TStack()
    netSetStack.push(networkDict)
    stackFlag = False


def endGroup():
    """
    EndGroup used at the end of a group operaction or secondary function.
    """
    global stackFlag
    stackFlag = True


def newNetwork(netID: str):
    """
    newNetwork Create a new network
    errCode -3: id repeat, 0 :ok
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack, lastNetIndex
    errCode = 0
    for network in networkDict.values():
        if network.id == netID:
            errCode = -3
            break
    if errCode < 0:
        raise ExceptionDict[errCode](errorDict[errCode])
    else:
        _pushUndoStack()

        newNetwork = TNetwork(netID)
        networkDict[lastNetIndex] = newNetwork
        lastNetIndex += 1


def getNetworkIndex(netID: str) -> int:
    """
    getNetworkIndex
    return: -2: net id can't find
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = -2

    for i, net in networkDict.items():
        if net.id == netID:
            errCode = 0
            return i

    raise ExceptionDict[errCode](errorDict[errCode])


# def saveNetworkAsJSON(neti: int, fileName: str):
#     """
#     SaveNetworkAsJSON SaveNetworkAsJSON
#     errCode: -5: net index out of range
#     -10: "Json convert error", -11: "File error"
#     """
#     global stackFlag, errCode, networkDict, netSetStack, redoStack
#     errCode = 0
#     if neti not in networkDict:
#         errCode = -5
#         raise ExceptionDict[errCode](errorDict[errCode])
#     else:
#         data2 = json.dumps(networkDict[neti],
#                            sort_keys=True, indent=4, separators=(',', ': '))
#         print(data2)


# #ReadNetworkFromJSON ReadNetworkFromJSON
# #errCode -3: id repeat, 0 :ok
# #-10: "Json convert error", -11: "File error",
# def ReadNetworkFromJSON(filePath string) int :
#     errCode = 0
#     file, err1 = ioutil.ReadFile(filePath)
#     if err1 != nil :
#         errCode = -11
#         addErrorMessage(errCode, "(\"" + filePath + "\")", "", "")
#         return errCode

#     newNet = TNetwork{
#     err2 = json.Unmarshal([]byte(file), &newNet)
#     if err2 != nil :
#         errCode = -10
#         addErrorMessage(errCode, "(\"" + filePath + "\")", "", "")
#         return errCode

#     for i = range networkDict :
#         if newNet.id == networkDict[i].id :
#             errCode = -3
#             addErrorMessage(errCode, ("(\"" + filePath + "\")"), newNet.id, "")
#             return errCode


#     if stackFlag :
#         redoStack = TNetSetStack{
#         netSetStack.push(networkDict)

#     networkDict = append(networkDict, newNet)
#     # fmt.Println(networkDict)
#     return errCode


def deleteNetwork(neti: int):
    """
    DeleteNetwork DeleteNetwork
    errCode: -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    if errCode < 0:
        raise ExceptionDict[errCode](errorDict[errCode])
    else:
        _pushUndoStack()

        del networkDict[neti]


def clearNetworks():
    global stackFlag, errCode, networkDict, netSetStack, redoStack, lastNetIndex
    errCode = 0
    _pushUndoStack()
    networkDict = TNetworkDict()
    lastNetIndex = 0


def getNumberOfNetworks():
    return len(networkDict)


def getNetworkID(neti: int):
    """
    GetNetworkID GetID of network
    errCode: -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    if errCode < 0:
        raise ExceptionDict[errCode](errorDict[errCode])
    else:
        return networkDict[neti].id


def getListOfNetworks() -> List[int]:
    return list(networkDict.keys())


def _raiseError(eCode: int):
    global errCode
    assert eCode < 0
    errCode = eCode
    raise ExceptionDict[errCode](errorDict[errCode])


def _addNetwork(network: TNetwork) -> int:
    """Helper function that adds a network object."""
    global lastNetIndex
    for net in networkDict.values():
        if net.id == network.id:
            _raiseError(-3)
    _pushUndoStack()

    networkDict[lastNetIndex] = network
    lastNetIndex += 1
    return lastNetIndex - 1


def _getNetwork(neti: int) -> TNetwork:
    if neti not in networkDict:
        errCode = -5
        raise ExceptionDict[errCode](errorDict[errCode])
    return networkDict[neti]


def _getNode(neti: int, nodei: int) -> TNode:
    net = _getNetwork(neti)
    if nodei not in net.nodes:
        _raiseError(-7)
    return net.nodes[nodei]


def _getReaction(neti: int, reai: int) -> TReaction:
    net = _getNetwork(neti)
    if reai not in net.reactions:
        _raiseError(-6)
    return net.reactions[reai]


def _getCompartment(neti: int, compi: int) -> TCompartment:
    global errCode
    net = _getNetwork(neti)
    if compi not in net.compartments:
        errCode = -13
        raise CompartmentIndexError('Unknown index: {}'.format(compi))
    return net.compartments[compi]


def _pushUndoStack():
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    if stackFlag:
        redoStack = TStack()
        netSetStack.push(networkDict)


def addNode(neti: int, nodeID: str, x: float, y: float, w: float, h: float, floatingNode : bool = False):
    """
    AddNode adds a node to the network
    errCode - 3: id repeat, 0: ok
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    try:
        n = _getNetwork(neti)
        for i in n.nodes.values():
            if i.id == nodeID:
                errCode = -3
                return

        if x < 0 or y < 0 or w <= 0 or h <= 0:
            errCode = -12
            return

        _pushUndoStack()
        newNode = TNode(nodeID, Vec2(x, y), Vec2(w, h), floatingNode)
        n.addNode(newNode)
        networkDict[neti] = n
    finally:
        if errCode < 0:
            raise ExceptionDict[errCode](errorDict[errCode])


def getNodeIndex(neti: int, nodeID: str):
    """
    GetNodeIndex get node index by id
    errCode: -2: node id not found,
    -5: net index out of range
    return: >=0
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = -2
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        for i, node, in n.nodes.items():
            if node.id == nodeID:
                errCode = 0
                return i

    assert errCode < 0
    raise ExceptionDict[errCode](errorDict[errCode])


def deleteNode(neti: int, nodei: int):
    """
    DeleteNode delete the node with index
    return: -7: node index out of range, -4: node is not free
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            # validate that node is not part of a reaction
            if len(n.srcMap[nodei]) == 0 and len(n.destMap[nodei]) == 0:
                errCode = 0
                _pushUndoStack()
                networkDict[neti] = n
                # remove node from associated compartment
                compi = getCompartmentOfNode(neti, nodei)
                if compi == -1:
                    n.baseNodes.remove(nodei)
                else:
                    n.compartments[compi].node_indices.remove(nodei)
                del n.nodes[nodei]
                return
            else:
                errCode = -4

    assert errCode < 0
    raise ExceptionDict[errCode](errorDict[errCode])


def clearNetwork(neti: int):
    """
    ClearNetwork clear all nodes and reactions in this network
    errCode: -5:  net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    if errCode < 0:
        raise ExceptionDict[errCode](errorDict[errCode])
    else:
        _pushUndoStack()
        # networkDict[neti].nodes.clear()
        # networkDict[neti].reactions.clear()
        # networkDict[neti].compartments.clear()
        networkDict[neti] = TNetwork(networkDict[neti].id)


def getNumberOfNodes(neti: int):
    """
    GetNumberOfNodes get the number of nodes in the current network
    num: >= -5:  net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    if errCode < 0:
        raise ExceptionDict[errCode](errorDict[errCode])
    else:
        n = networkDict[neti]
        return len(n.nodes)


def getNodeCenter(neti: int, nodei: int):
    """
    GetNodeCenter Get the X and  Y coordinate of the Center of node
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            X = round(n.nodes[nodei].position.x + n.nodes[nodei].rectSize.x*0.5, 2)
            Y = round(n.nodes[nodei].position.y + n.nodes[nodei].rectSize.y*0.5, 2)
            return (X, Y)

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeID(neti: int, nodei: int):
    """
    GetNodeID Get the id of the node
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return n.nodes[nodei].id

    raise ExceptionDict[errCode](errorDict[errCode])

def IsFloatingNode (neti : int, nodei : int):
    n = _getNetwork(neti)
    return n.nodes[nodei].floating

def IsBoundaryNode(neti : int, nodei : int):
    return not IsFloatingNode(neti, nodei)


def getListOfNodeIDs(neti: int) -> List[str]:
    if neti not in networkDict:
        errCode = -5
        raise ExceptionDict[errCode](errorDict[errCode])
    return [n.id for n in networkDict[neti].nodes.values()]


def getListOfNodeIndices(neti: int) -> Set[int]:
    return cast(Set[int], _getNetwork(neti).nodes.keys())


def getListOfReactionIndices(neti: int) -> Set[int]:
    return cast(Set[int], _getNetwork(neti).reactions.keys())


def getListOfCompartmentIndices(neti: int) -> Set[int]:
    return cast(Set[int], _getNetwork(neti).compartments.keys())


def getSrcReactions(neti: int, nodei: int) -> Set[int]:
    return set(_getNetwork(neti).srcMap[nodei])


def getDestReactions(neti: int, nodei: int) -> Set[int]:
    return set(_getNetwork(neti).destMap[nodei])


def getNodeCoordinateAndSize(neti: int, nodei: int):
    """
    getNodeCoordinateAndSize get the x,y,w,h of the node
    errCode:-7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            X = round(n.nodes[nodei].position.x, 2)
            Y = round(n.nodes[nodei].position.y, 2)
            W = round(n.nodes[nodei].rectSize.x, 2)
            H = round(n.nodes[nodei].rectSize.y, 2)
            return (X, Y, W, H)

    raise ExceptionDict[errCode](errorDict[errCode])


# TODO make this return TColor
def getNodeFillColor(neti: int, nodei: int):
    """
    getNodeFillColor  rgba tulple format, rgb range int[0,255] alpha range float[0,1]
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return (n.nodes[nodei].fillColor.r, n.nodes[nodei].fillColor.g,
                    n.nodes[nodei].fillColor.b,
                    float(n.nodes[nodei].fillColor.a)/255)

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeFillColorRGB(neti: int, nodei: int):
    """
    getNodeFillColorRGB getNodeFillColor rgb int format
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0

    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            color1 = n.nodes[nodei].fillColor.r
            color1 = (color1 << 8) | n.nodes[nodei].fillColor.g
            color1 = (color1 << 8) | n.nodes[nodei].fillColor.b
            return color1

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeFillColorAlpha(neti: int, nodei: int):
    """
    getNodeFillColorAlpha getNodeFillColor alpha value(float)
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return float(n.nodes[nodei].fillColor.a)/255

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeOutlineColor(neti: int, nodei: int):
    """
    getNodeOutlineColor rgba tulple format, rgb range int[0,255] alpha range float[0,1]
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return (n.nodes[nodei].outlineColor.r, n.nodes[nodei].outlineColor.g,
                    n.nodes[nodei].outlineColor.b,
                    float(n.nodes[nodei].outlineColor.a)/255)

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeOutlineColorRGB(neti: int, nodei: int):
    """
    getNodeOutlineColorRGB getNodeOutlineColor rgb int format
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0

    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            color1 = n.nodes[nodei].outlineColor.r
            color1 = (color1 << 8) | n.nodes[nodei].outlineColor.g
            color1 = (color1 << 8) | n.nodes[nodei].outlineColor.b
            return color1

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeOutlineColorAlpha(neti: int, nodei: int):
    """
    getNodeOutlineColorAlpha getNodeOutlineColor alpha value(float)
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0

    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return float(n.nodes[nodei].outlineColor.a)/255

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeOutlineThickness(neti: int, nodei: int):
    """
    getNodeOutlineThickness
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return n.nodes[nodei].outlineThickness

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeFontPointSize(neti: int, nodei: int):
    """
    getNodeFontPointSize
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return n.nodes[nodei].font.pointSize

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeFontFamily(neti: int, nodei: int):
    """
    getNodeFontFamily
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return n.nodes[nodei].font.family

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeFontStyle(neti: int, nodei: int):
    """
    getNodeFontStyle
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return n.nodes[nodei].font.style

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeFontWeight(neti: int, nodei: int):
    """
    getNodeFontWeight
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return n.nodes[nodei].font.weight

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeFontName(neti: int, nodei: int):
    """
    getNodeFontName
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return n.nodes[nodei].font.name

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeFontColor(neti: int, nodei: int):
    """
    getNodeFontColor rgba tulple format, rgb range int[0,255] alpha range float[0,1]
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return (n.nodes[nodei].font.color.r, n.nodes[nodei].font.color.g,
                    n.nodes[nodei].font.color.b,
                    float(n.nodes[nodei].font.color.a)/255)

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeFontColorRGB(neti: int, nodei: int):
    """
    getNodeFontColorRGB getNodeFontColor rgb int format
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0

    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            color1 = n.nodes[nodei].font.color.r
            color1 = (color1 << 8) | n.nodes[nodei].font.color.g
            color1 = (color1 << 8) | n.nodes[nodei].font.color.b
            return color1

    raise ExceptionDict[errCode](errorDict[errCode])


def getNodeFontColorAlpha(neti: int, nodei: int):
    """
    getNodeFontColorAlpha getNodeFontColor alpha value(float)
    errCode: -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0

    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            return float(n.nodes[nodei].font.color.a)/255

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeID(neti: int, nodei: int, newID: str):
    """
    setNodeID set the id of a node
    errCode -3: id repeat
    -5: net index out of range
    -7: node index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        net = networkDict[neti]
        if nodei not in net.nodes.keys():
            errCode = -7
        else:
            if any((n.id == newID for n in net.nodes.values())):
                errCode = -3
            else:
                _pushUndoStack()
                net.nodes[nodei].id = newID
                return
    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeCoordinate(neti: int, nodei: int, x: float, y: float, allowNegativeCoordinates: bool = False):
    """
    setNodeCoordinate setNodeCoordinate
    errCode: -7: node index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0

    if allowNegativeCoordinates:
        lowerLimit = -1E12
    else:
        lowerLimit = 0

    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        elif x < lowerLimit or y < lowerLimit:
            errCode = -12
        else:
            _pushUndoStack()
            n.nodes[nodei].position = Vec2(x, y)
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeSize(neti: int, nodei: int, w: float, h: float):
    """
    setNodeSize setNodeSize
    errCode: -7: node index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        elif w <= 0 or h <= 0:
            errCode = -12
        else:
            _pushUndoStack()
            n.nodes[nodei].rectSize = Vec2(w, h)
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeFloatingStatus (neti: int, nodei: int, floatingStatus : bool):
    """
    setNodeFloatingStatus setNodeFloatingStatus
    errCode: -7: node index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            _pushUndoStack()
            n.nodes[nodei].floating = floatingStatus
            return

    raise ExceptionDict[errCode](errorDict[errCode])

def setNodeFillColorRGB(neti: int, nodei: int, r: int, g: int, b: int):
    """
    setNodeFillColorRGB setNodeFillColorRGB
    errCode: -7: node index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        elif r < 0 or r > 255 or g < 0 or g > 255 or b < 0 or b > 255:
            errCode = -12
        else:
            _pushUndoStack()
            n.nodes[nodei].fillColor = n.nodes[nodei].fillColor.swapped(r, g, b)
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeFillColorAlpha(neti: int, nodei: int, a: float):
    """
    setNodeFillColorAlpha setNodeFillColorAlpha
    errCode: -7: node index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        node = _getNode(neti, nodei)
        if a < 0 or a > 1:
            errCode = -12
        else:
            _pushUndoStack()
            node.fillColor = node.fillColor.swapped(a=int(a*255))
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeOutlineColorRGB(neti: int, nodei: int, r: int, g: int, b: int):
    """
    setNodeOutlineColorRGB setNodeOutlineColorRGB
    errCode: -7: node index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        elif r < 0 or r > 255 or g < 0 or g > 255 or b < 0 or b > 255:
            errCode = -12
        else:
            _pushUndoStack()
            n.nodes[nodei].outlineColor = n.nodes[nodei].outlineColor.swapped(r, g, b)
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeOutlineColorAlpha(neti: int, nodei: int, a: float):
    """
    setNodeOutlineColorAlpha setNodeOutlineColorAlpha, alpha is a float between 0 and 1
    errCode: -7: node index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        elif a < 0 or a > 1:
            errCode = -12
        else:
            _pushUndoStack()
            A1 = int(a * 255)
            n.nodes[nodei].outlineColor = n.nodes[nodei].outlineColor.swapped(a=A1)
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeOutlineThickness(neti: int, nodei: int, thickness: float):
    """
    setNodeOutlineThickness setNodeOutlineThickness
    errCode: -7: node index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        elif thickness <= 0:
            errCode = -12
        else:
            _pushUndoStack()
            n.nodes[nodei].outlineThickness = thickness
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeFontPointSize(neti: int, nodei: int, fontPointSize: int):
    """
    setNodeFontPointSize setNodeFontPointSize
    errCode: -7: node index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        elif fontPointSize <= 0:
            errCode = -12
        else:
            _pushUndoStack()
            n.nodes[nodei].font.pointSize = fontPointSize
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeFontFamily(neti: int, nodei: int, fontFamily: str):
    """
    setNodeFontFamily set the fontFamily of a node
    errCode
    -5: net index out of range
    -7: node index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        elif fontFamily not in fontFamilyDict:
            errCode = -12
        else:
            _pushUndoStack()
            n.nodes[nodei].font.family = fontFamily
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeFontStyle(neti: int, nodei: int, fontStyle: str):
    """
    setNodeFontStyle set the fontStyle of a node
    errCode
    -5: net index out of range
    -7: node index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        elif fontStyle not in fontStyleDict:
            errCode = -12
        else:
            _pushUndoStack()
            n.nodes[nodei].font.style = fontStyle
            return
    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeFontWeight(neti: int, nodei: int, fontWeight: str):
    """
    setNodeFontWeight set the fontWeight of a node
    errCode
    -5: net index out of range
    -7: node index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        elif fontWeight not in fontWeightDict:
            errCode = -12
        else:
            _pushUndoStack()
            n.nodes[nodei].font.weight = fontWeight
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeFontName(neti: int, nodei: int, fontName: str):
    """
    setNodeFontName set the fontName of a node
    errCode
    -5: net index out of range
    -7: node index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        else:
            _pushUndoStack()
            n.nodes[nodei].font.name = fontName
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeFontColorRGB(neti: int, nodei: int, r: int, g: int, b: int):
    """
    setNodeFontColorRGB setNodeFontColorRGB
    errCode: -7: node index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        elif r < 0 or r > 255 or g < 0 or g > 255 or b < 0 or b > 255:
            errCode = -12
        else:
            _pushUndoStack()
            n.nodes[nodei].font.color = n.nodes[nodei].font.color.swapped(r, g, b)
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setNodeFontColorAlpha(neti: int, nodei: int, a: float):
    """
    setNodeFontColorAlpha setNodeFontColorAlpha
    errCode: -7: node index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        n = networkDict[neti]
        if nodei not in n.nodes:
            errCode = -7
        elif a < 0 or a > 1:
            errCode = -12
        else:
            _pushUndoStack()
            node = networkDict[neti].nodes[nodei]
            node.font.color = node.font.color.swapped(a=int(a*255))
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def createReaction(neti: int, reaID: str, sources: List[int], targets: List[int]):
    """
    createReaction create an empty reacton
    errCode: -3: id repeat
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0

    if len(sources) == 0 or len(targets) == 0:
        raise ValueError('Both the sources and targets of a reaction must be nonempty.')

    net = _getNetwork(neti)
    # duplicate ID?
    if any((r.id == reaID for r in net.reactions.values())):
        errCode = -3
    else:
        # ensure nodes exist
        if any(nodei not in net.nodes.keys() for nodei in sources):
            _raiseError(-7)
        if any(nodei not in net.nodes.keys() for nodei in targets):
            _raiseError(-7)

        if set(sources) == set(targets):
            raise ValueError('Reaction source node set and target node set cannot be identical.')
        _pushUndoStack()
        newReact = TReaction(reaID)

        # Add src/target nodes
        for srcNodeIdx in sources:
            newReact.reactants[srcNodeIdx] = TSpeciesNode(1)  # default stoich to 1
        for destNodeIdx in targets:
            newReact.products[destNodeIdx] = TSpeciesNode(1)  # default stoich to 1

        net.addReaction(newReact)
        return

    raise ExceptionDict[errCode](errorDict[errCode])


def getReactionIndex(neti: int, reaID: str):
    """
    getReactionIndex get reaction index by id
    return: -2: id can't find, >=0: ok
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        errCode = -2
        for i, r in networkDict[neti].reactions.items():
            if r.id == reaID:
                errCode = 0
                return i

    raise ExceptionDict[errCode](errorDict[errCode])


def deleteReaction(neti: int, reai: int):
    """
    deleteReaction delete the reaction with index
    errCode:  -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            _pushUndoStack()
            net = _getNetwork(neti)
            reaction = _getReaction(neti, reai)
            for src in reaction.reactants:
                net.srcMap[src].remove(reai)
            for dest in reaction.products:
                net.destMap[dest].remove(reai)
            del networkDict[neti].reactions[reai]
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def clearReactions(neti: int):
    """
    clearReactions clear all reactions in this network
    errCode: -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5

    if errCode < 0:
        raise ExceptionDict[errCode](errorDict[errCode])
    else:
        _pushUndoStack()
        net = _getNetwork(neti)
        net.reactions.clear()
        net.srcMap.clear()
        net.destMap.clear()


def getNumberOfReactions(neti: int):
    """
    getNumberOfReactions get the number of reactions in the current Reactionset
    return: >=0: ok, -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    if neti not in networkDict:
        errCode = -5
    if errCode < 0:
        raise ExceptionDict[errCode](errorDict[errCode])
    else:
        r = networkDict[neti].reactions
        return len(r)


def getReactionID(neti: int, reai: int):
    """
    getReactionID get the id of Reaction
    errCode: -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            return r[reai].id

    raise ExceptionDict[errCode](errorDict[errCode])


def getListOfReactionIDs(neti: int) -> List[str]:
    if neti not in networkDict:
        errCode = -5
        raise ExceptionDict[errCode](errorDict[errCode])
    return [r.id for r in networkDict[neti].reactions.values()]


def getReactionRateLaw(neti: int, reai: int):
    """
    getReactionRateLaw get the ratelaw of Reaction
    errCode: -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            return r[reai].rateLaw

    raise ExceptionDict[errCode](errorDict[errCode])


def getReactionCenterPos(neti: int, reai: int):
    """
    getReactionCenterPos get the center position of the Reaction
    """
    r = _getReaction(neti, reai)
    return r.centerPos


def getReactionFillColor(neti: int, reai: int):
    """
    getReactionFillColor rgba tulple format, rgb range int[0,255] alpha range float[0,1]
    errCode:  -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            return (r[reai].fillColor.r, r[reai].fillColor.g, r[reai].fillColor.b, float(r[reai].fillColor.a)/255)

    raise ExceptionDict[errCode](errorDict[errCode])


def getReactionFillColorRGB(neti: int, reai: int):
    """
    getReactionFillColorRGB getReactionFillColorRGB
    errCode:  -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            color1 = r[reai].fillColor.r
            color1 = (color1 << 8) | r[reai].fillColor.g
            color1 = (color1 << 8) | r[reai].fillColor.b
            return color1

    raise ExceptionDict[errCode](errorDict[errCode])


def getReactionFillColorAlpha(neti: int, reai: int):
    """
    getReactionFillColorAlpha getReactionFillColorAlpha
    errCode:  -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            alpha1 = float(r[reai].fillColor.a) / 255
            return alpha1

    raise ExceptionDict[errCode](errorDict[errCode])


def getReactionLineThickness(neti: int, reai: int):
    """
    getReactionLineThickness getReactionLineThickness
    errCode: -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            return r[reai].thickness

    raise ExceptionDict[errCode](errorDict[errCode])


def getReactionCenterHandlePosition(neti: int, reai: int):
    """
    getReactionCenterHandlePosition getReactionCenterHandlePosition
    errCode: -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            return (round(r[reai].centerHandlePos.x, 2), round(r[reai].centerHandlePos.y, 2))

    raise ExceptionDict[errCode](errorDict[errCode])


def getReactionSrcNodeStoich(neti: int, reai: int, srcNodeIdx: int):
    """
    getReactionSrcNodeStoich get the SrcNode stoichiometry of Reaction
    errCode: -6: reaction index out of range,
    -5: net index out of range, -7: node index not found
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        elif srcNodeIdx not in networkDict[neti].nodes:
            errCode = -7
        elif srcNodeIdx not in r[reai].reactants:
            raise ValueError('The given node index "{}" is not a reactant node of "{}"'.format(
                             srcNodeIdx, reai))
        else:
            return r[reai].reactants[srcNodeIdx].stoich
    raise ExceptionDict[errCode](errorDict[errCode])


def getReactionDestNodeStoich(neti: int, reai: int, destNodeIdx: int):
    """
    getReactionDestNodeStoich get the DestNode stoichiometry of Reaction
    return: positive float : ok, -6: reaction index out of range, -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        elif destNodeIdx not in networkDict[neti].nodes:
            errCode = -7
        elif destNodeIdx not in r[reai].products:
            raise ValueError('The given node index "{}" is not a product node of "{}"'.format(
                             destNodeIdx, reai))
        else:
            s = r[reai].products[destNodeIdx]
            return s.stoich
    raise ExceptionDict[errCode](errorDict[errCode])


def getReactionSrcNodeHandlePosition(neti: int, reai: int, srcNodeIdx: int):
    """
    getReactionSrcNodeHandlePosition get the SrcNode HandlePosition of Reaction
    errCode: -6: reaction index out of range,
    -5: net index out of range, -7: node index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        elif srcNodeIdx not in networkDict[neti].nodes:
            errCode = -7
        elif srcNodeIdx not in r[reai].reactants:
            raise ValueError('The given node index "{}" is not a reactant node of "{}"'.format(
                             srcNodeIdx, reai))
        else:
            return (round(r[reai].reactants[srcNodeIdx].handlePos.x, 2),
                    round(r[reai].reactants[srcNodeIdx].handlePos.y, 2))

    raise ExceptionDict[errCode](errorDict[errCode])


def getReactionDestNodeHandlePosition(neti: int, reai: int, destNodeIdx: int):
    """
    getReactionDestNodeStoich get the DestNode HandlePosition of Reaction
    return: positive float : ok, -6: reaction index out of range, -7: node index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        elif destNodeIdx not in networkDict[neti].nodes:
            errCode = -7
        elif destNodeIdx not in r[reai].products:
            raise ValueError('The given node index "{}" is not a product node of "{}"'.format(
                             destNodeIdx, reai))
        else:
            return (round(r[reai].products[destNodeIdx].handlePos.x, 2),
                    round(r[reai].products[destNodeIdx].handlePos.y, 2))

    raise ExceptionDict[errCode](errorDict[errCode])


def getNumberOfSrcNodes(neti: int, reai: int):
    """
    getNumberOfSrcNodes get the SrcNode length of Reaction
    return: non-negative int: ok, -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            return len(r[reai].reactants)

    raise ExceptionDict[errCode](errorDict[errCode])


def getNumberOfDestNodes(neti: int, reai: int):
    """
    getNumberOfDestNodes get the DestNode length of Reaction
    return: non-negative int: ok, -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            return len(r[reai].products)

    raise ExceptionDict[errCode](errorDict[errCode])


def getListOfReactionSrcNodes(neti: int, reai: int) -> List[int]:
    """
    getListOfReactionSrcNodes getListOfReactionSrcNodes in alphabetical order
    return: non-empty slice : ok, -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        reactions = networkDict[neti].reactions
        if reai not in reactions:
            errCode = -6
        else:
            list1 = []
            for k in reactions[reai].reactants:
                list1.append(k)
            list1.sort()
            return list1

    raise ExceptionDict[errCode](errorDict[errCode])


def getListOfReactionDestNodes(neti: int, reai: int) -> List[int]:
    """
    getListOfReactionDestNodes getListOfReactionDestNodes in alphabetical order
    return: non-empty slice : ok, -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            list1 = []
            for k in r[reai].products:
                list1.append(k)
            list1.sort()
            return list1

    raise ExceptionDict[errCode](errorDict[errCode])


def getListOfReactionSrcStoich(neti: int, reai: int) -> List[float]:
    n = getListOfReactionSrcNodes(neti, reai)
    srcStoichList = []
    for srcNodeID in n:
        srcStoichList.append(getReactionSrcNodeStoich(neti, reai, srcNodeID))
    return srcStoichList


def getListOfReactionDestStoich(neti: int, reai: int) -> List[float]:
    n = getListOfReactionDestNodes(neti, reai)
    destStoichList = []
    for destNodeID in n:
        destStoichList.append(getReactionDestNodeStoich(neti, reai, destNodeID))
    return destStoichList


def printReactionInfo(neti: int, reai: int):
    print("id:", getReactionID(neti, reai))
    print("rateLaw:", getReactionRateLaw(neti, reai))
    print("SrcNodes:", getListOfReactionSrcNodes(neti, reai))
    print("DestNodes:", getListOfReactionDestNodes(neti, reai))
    print("SrcNodeStoichs:", getListOfReactionSrcStoich(neti, reai))
    print("DestNodeStoichs:", getListOfReactionDestStoich(neti, reai))


# def deleteSrcNode(neti: int, reai: int, srcNodeIdx: int):
#     """
#     deleteSrcNode delete src nodes by id(ID).
#     errCode: -6: reaction index out of range,
#     -5: net index out of range
#     -2: id not found
#     """
#     global stackFlag, errCode, networkDict, netSetStack, redoStack
#     errCode = 0
#     if neti not in networkDict:
#         errCode = -5
#     else:
#         r = networkDict[neti].reactions
#         if reai not in networkDict[neti].reactions:
#             errCode = -6
#         else:
#             rea = r[reai]
#             if srcNodeIdx not in rea.reactants:
#                 errCode = -2
#             else:
#                 _pushUndoStack()
#                 del rea.reactants[srcNodeIdx]
#                 networkDict[neti].reactions[reai] = rea
#                 return

#     raise ExceptionDict[errCode](errorDict[errCode])


# def deleteDestNode(neti: int, reai: int, destNodeIdx: int):
#     """
#     deleteDestNode delete all dest nodes by id
#     errCode: -6: reaction index out of range,
#     -5: net index out of range
#     -2: id not found
#     """
#     global stackFlag, errCode, networkDict, netSetStack, redoStack
#     errCode = 0
#     if neti not in networkDict:
#         errCode = -5
#     else:
#         r = networkDict[neti].reactions
#         if reai not in networkDict[neti].reactions:
#             errCode = -6
#         else:
#             rea = r[reai]
#             if destNodeIdx not in rea.products:
#                 errCode = -2
#             else:
#                 _pushUndoStack()
#                 del rea.products[destNodeIdx]
#                 return

#     raise ExceptionDict[errCode](errorDict[errCode])


def setReactionID(neti: int, reai: int, newID: str):
    """
    setReactionID edit id of reaction
    errCode: 0:ok, -6: reaction index out of range
    -5: net index out of range
    -3: id repeat
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        reactions = networkDict[neti].reactions
        if reai not in reactions:
            errCode = -6
        else:
            if any((r.id == newID for r in reactions.values())):
                errCode = -3
            else:
                _pushUndoStack()
                networkDict[neti].reactions[reai].id = newID
                return

    raise ExceptionDict[errCode](errorDict[errCode])


def setRateLaw(neti: int, reai: int, rateLaw: str):
    """
    setRateLaw edit rate law of reaction
    errCode: -6: reaction index out of range
    -5: net index out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            _pushUndoStack()
            networkDict[neti].reactions[reai].rateLaw = rateLaw
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setReactionCenterPos(neti: int, reai: int, centerPos: Optional[Vec2]):
    """
    setReactionCenterPos set the center position of the Reaction
    """
    r = _getReaction(neti, reai)
    r.centerPos = centerPos


def setReactionSrcNodeStoich(neti: int, reai: int, srcNodeIdx: int, newStoich: float):
    """
    setReactionSrcNodeStoich edit Stoich by Reaction srcNodeID
    errCode: -6: reaction index not found,
    -5: net index not found
    -7: node index not found,
    -8: wrong stoich
    raises ValueError if given node index not a dest node
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        elif srcNodeIdx not in networkDict[neti].nodes:
            errCode = -7
        elif srcNodeIdx not in r[reai].reactants:
            raise ValueError('The given node index "{}" is not a reactant node of "{}"'.format(
                             srcNodeIdx, reai))
        elif newStoich <= 0.0:
            errCode = -8
        else:
            _pushUndoStack()
            networkDict[neti].reactions[reai].reactants[srcNodeIdx].stoich = newStoich
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setReactionDestNodeStoich(neti: int, reai: int, destNodeIdx: int, newStoich: float):
    """
    setReactionDestNodeStoich edit Stoich by Reaction destNodeID
    errCode: -6: reaction index out of range,
    -5: net index out of range,
    -7: node index not found,
    -8: wrong stoich
    raises ValueError if given node index not a dest node
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        elif destNodeIdx not in networkDict[neti].nodes:
            errCode = -7
        elif destNodeIdx not in r[reai].products:
            raise ValueError('The given node index "{}" is not a product node of "{}"'.format(
                             destNodeIdx, reai))
        elif newStoich <= 0.0:
            errCode = -8
        else:
            _pushUndoStack()
            networkDict[neti].reactions[reai].products[destNodeIdx].stoich = newStoich
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setReactionSrcNodeHandlePosition(neti: int, reai: int, srcNodeIdx: int, handlePosX: float, handlePosY: float):
    """
    setReactionSrcNodeHandlePosition edit HandlePosition by Reaction srcNodeID
    errCode: -6: reaction index out of range,
    -5: net index out of range, -7: node index not found
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        elif srcNodeIdx not in networkDict[neti].nodes:
            _raiseError(-7)
        elif srcNodeIdx not in r[reai].reactants:
            raise ValueError('The given node index "{}" is not a reactant node of "{}"'.format(
                             srcNodeIdx, reai))
        else:
            _pushUndoStack()
            networkDict[neti].reactions[reai].reactants[srcNodeIdx].handlePos = Vec2(
                handlePosX, handlePosY)
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setReactionDestNodeHandlePosition(neti: int, reai: int, destNodeIdx: int, handlePosX: float, handlePosY: float):
    """
    setReactionDestNodeHandlePosition edit HandlePosition by Reaction destNodeID
    errCode: -6: reaction index out of range,
    -5: net index out of range, -2: id not found
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        elif destNodeIdx not in networkDict[neti].nodes:
            _raiseError(-7)
        elif destNodeIdx not in r[reai].products:
            raise ValueError('The given node index "{}" is not a product node of "{}"'.format(
                             destNodeIdx, reai))
        else:
            _pushUndoStack()
            networkDict[neti].reactions[reai].products[destNodeIdx].handlePos = Vec2(
                handlePosX, handlePosY)
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setReactionFillColorRGB(neti: int, reai: int, R: int, G: int, B: int):
    """
    setReactionFillColorRGB setReactionFillColorRGB
    errCode: -6: reaction index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        elif R < 0 or R > 255 or G < 0 or G > 255 or B < 0 or B > 255:
            errCode = -12
        else:
            _pushUndoStack()
            r[reai].fillColor = r[reai].fillColor.swapped(R, G, B)
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setReactionFillColorAlpha(neti: int, reai: int, a: float):
    """
    setReactionFillColorAlpha setReactionFillColorAlpha
    errCode: -6: reaction index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        elif a < 0 or a > 1:
            errCode = -12
        else:
            _pushUndoStack()
            A1 = int(a * 255)
            r[reai].fillColor = r[reai].fillColor.swapped(a=A1)
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setReactionLineThickness(neti: int, reai: int, thickness: float):
    """
    setReactionLineThickness setReactionLineThickness
    errCode: -6: reaction index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        if reai not in networkDict[neti].reactions:
            errCode = -6
        elif thickness <= 0:
            errCode = -12
        else:
            _pushUndoStack()
            networkDict[neti].reactions[reai].thickness = thickness
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def bezier_curves(neti: int, reai: int):
    errCode = 0
    if neti not in networkDict:	   
        errCode = -5    	          
    r = networkDict[neti]
    if r.reactions[reai].bezierCurves:	 
       return True	       
    else:	    
       return False	

def setReactionBezierCurves(neti: int, reai: int, bezierCurves: bool):
    """
    setReactionBezierCurves setReactionBezierCurves
    errCode: -6: reaction index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        r = networkDict[neti].reactions
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            _pushUndoStack()
            r[reai].bezierCurves = bezierCurves
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def setReactionCenterHandlePosition(neti: int, reai: int, centerHandlePosX: float, centerHandlePosY: float):
    """
    setReactionCenterHandlePosition setReactionCenterHandlePosition
    errCode: -6: reaction index out of range
    -5: net index out of range
    -12: Variable out of range
    """
    global stackFlag, errCode, networkDict, netSetStack, redoStack
    errCode = 0
    if neti not in networkDict:
        errCode = -5
    else:
        if reai not in networkDict[neti].reactions:
            errCode = -6
        else:
            _pushUndoStack()
            networkDict[neti].reactions[reai].centerHandlePos = Vec2(
                centerHandlePosX, centerHandlePosY)
            return

    raise ExceptionDict[errCode](errorDict[errCode])


def addCompartment(neti: int, compID: str, x: float, y: float, w: float, h: float) -> int:
    """
    Create a compartment and add to canvas. Return the index of the compartment added.

    Args:
        neti: network index.
        compID: ID of the compartment.
        x: x coordinate of top-left corner
        y: y coordinate of top-left corner
        w: width
        h: height
    """
    if x < 0 or y < 0 or w < 0 or h < 0:
        _raiseError(-12)
    net = _getNetwork(neti)
    comp = TCompartment(compID, Vec2(x, y), Vec2(w, h))
    if any((compID == c.id for c in net.compartments.values())):
        _raiseError(-3)
    _pushUndoStack()
    return net.addCompartment(comp)


def deleteCompartment(neti: int, compi: int):
    """Delete the compartment of the given index in the given network."""
    net = _getNetwork(neti)
    if compi not in net.compartments:
        _raiseError(-13)

    _pushUndoStack()
    # Put all nodes in compartment in base compartment (-1)
    for nodei in net.compartments[compi].node_indices:
        assert net.nodes[nodei].compi == compi
        # move to base compartment
        net.nodes[nodei].compi = -1
        net.baseNodes.add(nodei)

    del net.compartments[compi]


def getListOfCompartments(neti: int) -> List[int]:
    return list(_getNetwork(neti).compartments.keys())


def getNodesInCompartment(neti: int, compi: int) -> List[int]:
    """Return the list of node indices in the given compartment."""
    if compi == -1:
        return list(_getNetwork(neti).baseNodes)
    return list(_getCompartment(neti, compi).node_indices)  # Make copy in the process


def getCompartmentOfNode(neti: int, nodei: int) -> int:
    """Return the compartment index that the given node is in, or -1 if it is not in any."""
    net = _getNetwork(neti)
    if nodei not in net.nodes:
        _raiseError(-7)

    return net.nodes[nodei].compi


def setCompartmentOfNode(neti: int, nodei: int, compi: int):
    """Set the compartment of the node, or remove it from any compartment if -1 is given."""
    net = _getNetwork(neti)

    node = _getNode(neti, nodei)
    _pushUndoStack()
    if node.compi != -1:
        net.compartments[node.compi].node_indices.remove(nodei)
    else:
        net.baseNodes.remove(nodei)

    if compi != -1:
        newComp = _getCompartment(neti, compi)
        newComp.node_indices.add(nodei)
    else:
        net.baseNodes.add(nodei)

    node.compi = compi


def setCompartmentPosition(neti: int, compi: int, x: float, y: float):
    if x < 0 or y < 0:
        _raiseError(-12)
    _pushUndoStack()
    comp = _getCompartment(neti, compi)
    comp.position = Vec2(x, y)


def getCompartmentPosition(neti: int, compi: int) -> Tuple[float, float]:
    comp = _getCompartment(neti, compi)
    return (comp.position.x, comp.position.y)


def setCompartmentSize(neti: int, compi: int, w: float, h: float):
    if w < 0 or h < 0:
        _raiseError(-12)
    _pushUndoStack()
    comp = _getCompartment(neti, compi)
    comp.rectSize = Vec2(w, h)


def getCompartmentSize(neti: int, compi: int) -> Tuple[float, float]:
    comp = _getCompartment(neti, compi)
    return (comp.rectSize.x, comp.rectSize.y)


def setCompartmentVolume(neti: int, compi: int, volume: float):
    _pushUndoStack()
    _getCompartment(neti, compi).volume = volume


def getCompartmentVolume(neti: int, compi: int) -> float:
    return _getCompartment(neti, compi).volume


def setCompartmentID(neti: int, compi: int, id: str):
    _pushUndoStack()
    _getCompartment(neti, compi).id = id


def getCompartmentID(neti: int, compi: int) -> str:
    return _getCompartment(neti, compi).id


# TODO note that this returns a TColor instead of tuples of numbers. Should change the node &
# reaction color functions to do the same.
def setCompartmentFillColor(neti: int, compi: int, color: TColor):
    _pushUndoStack()
    _getCompartment(neti, compi).fillColor = color


def getCompartmentFillColor(neti: int, compi: int) -> TColor:
    return _getCompartment(neti, compi).fillColor


def setCompartmentOutlineColor(neti: int, compi: int, color: TColor):
    _pushUndoStack()
    _getCompartment(neti, compi).outlineColor = color


def getCompartmentOutlineColor(neti: int, compi: int) -> TColor:
    return _getCompartment(neti, compi).outlineColor


def setCompartmentOutlineThickness(neti: int, compi: int, thickness: float):
    _pushUndoStack()
    _getCompartment(neti, compi).outlineThickness = thickness


def getCompartmentOutlineThickness(neti: int, compi: int) -> float:
    return _getCompartment(neti, compi).outlineThickness


def createUniUni(neti: int, reaID: str, rateLaw: str, srci: int, desti: int, srcStoich: float, destStoich: float):
    startGroup()
    createReaction(neti, reaID, [srci], [desti])
    reai = getReactionIndex(neti, reaID)

    setReactionSrcNodeStoich(neti, reai, srci, srcStoich)
    setReactionDestNodeStoich(neti, reai, desti, destStoich)
    setRateLaw(neti, reai, rateLaw)
    endGroup()


def CreateUniBi(neti: int, reaID: str, rateLaw: str, srci: int, dest1i: int, dest2i: int, srcStoich: float, dest1Stoich: float, dest2Stoich: float):
    startGroup()
    createReaction(neti, reaID, [srci], [dest1i, dest2i])
    reai = getReactionIndex(neti, reaID)

    setReactionSrcNodeStoich(neti, reai, srci, srcStoich)
    setReactionDestNodeStoich(neti, reai, dest1i, dest1Stoich)
    setReactionDestNodeStoich(neti, reai, dest2i, dest2Stoich)
    setRateLaw(neti, reai, rateLaw)
    endGroup()


def CreateBiUni(neti: int, reaID: str, rateLaw: str, src1i: int, src2i: int, desti: int, src1Stoich: float, src2Stoich: float, destStoich: float):
    startGroup()
    createReaction(neti, reaID, [src1i, src2i], [desti])
    reai = getReactionIndex(neti, reaID)

    setReactionSrcNodeStoich(neti, reai, src1i, src1Stoich)
    setReactionSrcNodeStoich(neti, reai, src2i, src2Stoich)
    setReactionDestNodeStoich(neti, reai, desti, destStoich)
    setRateLaw(neti, reai, rateLaw)
    endGroup()


def CreateBiBi(neti: int, reaID: str, rateLaw: str, src1i: int, src2i: int, dest1i: int, dest2i: int, src1Stoich: float, src2Stoich: float, dest1Stoich: float, dest2Stoich: float):
    startGroup()
    createReaction(neti, reaID, [src1i, src2i], [dest1i, dest2i])
    reai = getReactionIndex(neti, reaID)

    setReactionSrcNodeStoich(neti, reai, src1i, src1Stoich)
    setReactionSrcNodeStoich(neti, reai, src2i, src2Stoich)
    setReactionDestNodeStoich(neti, reai, dest1i, dest1Stoich)
    setReactionDestNodeStoich(neti, reai, dest2i, dest2Stoich)
    setRateLaw(neti, reai, rateLaw)
    endGroup()


def reset():
    global stackFlag, errCode, networkDict, netSetStack, redoStack, lastNetIndex
    stackFlag = True
    errCode = 0
    networkDict = TNetworkDict()
    netSetStack = TStack()
    redoStack = TStack()
    lastNetIndex = 0


'''Code for serialization/deserialization.'''


class Color(fields.Field):
    """Field that represents an RGBA color.

    To represent the color red, you would write:
    >>> { "some_color": [255, 0, 0] }

    You may also specify its opacity. To make the color red half transparent:
    >>> { "some": [255, 0, 0, 127] }

    In short, you may specify four integer arguments RGBA in an array, which the alpha value
    being optional and defaulting to 255, or fully opaque. Each value must be in range [0, 255].
    """
    list_field = fields.List(fields.Int(), validate=validate.Length(min=3, max=4))
    range_validate = validate.Range(min=0, max=255, error='RGBA values must be between 0 and 255.')

    def __init__(self, **kw):
        super().__init__(**kw)

    def _serialize(self, value: TColor, attr, obj, **kwargs):
        ret = [value.r, value.g, value.b]
        if value.a != 255:
            ret += [value.a]
        return ret

    def _deserialize(self, value, attr, data, **kwargs):
        self.list_field.validate(value)
        for val in value:
            Color.range_validate(val)
        return TColor(*value)


class Pixel(fields.Int):
    """Field that represents some length in pixels.

    The only current restriction is that this must be a nonnegative integer, or
    >>> { "some_width": 23 }
    """

    def __init__(self):
        super().__init__(validate=validate.Range(min=0))


class Dim(fields.Float):
    """Field that represents some real dimension (length)."""

    def __init__(self):
        # TODO should we allow 0? Also decide for pixel
        super().__init__(validate=validate.Range(min=0))


class Dim2(fields.List):
    def __init__(self):
        super().__init__(Dim(), validate=validate.Length(equal=2))

    def _serialize(self, value: Vec2, attr, obj, **kwargs):
        return (value.x, value.y)

    def _deserialize(self, value, attr, data, **kwargs):
        self._validate(value)
        return Vec2(value)


class FontSchema(Schema):
    # TODO use this after implemented
    pointSize = Pixel()
    family = str  # TODO change to enum
    style: str
    weight: str
    name: str
    color: TColor


class NodeSchema(Schema):
    id = fields.Str()  # TODO assert unique
    # x = Dim()  # TODO validate not out of range of canvas?
    # y = Dim()
    # w = fields.Float(validate=validate.Range(min=get_setting('min_node_width')))
    # h = fields.Float(validate=validate.Range(min=get_setting('min_node_height')))
    position = Dim2()
    rectSize = Dim2()
    floating = fields.Bool()
    compartment = fields.Int()
    fillColor = Color()
    outlineColor = Color()
    outlineThickness = Dim()
    # font: TFont

    @post_load
    def post_load(self, data: Any, **kwargs) -> TNode:
        # return TNode(data['id'], data['position'], data['rectSize'],
        #              data['compartment'], data['fillColor'], data['outlineColor'],
        #              data['outlineThickness'], TFont())
        return TNode(**data)


class SpeciesNode(Schema):
    """Represents a species in a reaction."""
    stoich = fields.Float()
    handlePos = Dim2()

    # @pre_dump
    # def pre_dump(self, data: TSpeciesNode, **kwargs):
    #     assert isinstance(data, TSpeciesNode)
    #     # TODO create schema for SpeciesNode
    #     return {
    #         'stoich': data.stoich,
    #         'handlePos': (data.handlePos.x, data.handlePos.y),
    #     }

    @post_load
    def post_load(self, data: Any, **kwargs) -> TSpeciesNode:
        # return TNode(data['id'], data['position'], data['rectSize'],
        #              data['compartment'], data['fillColor'], data['outlineColor'],
        #              data['outlineThickness'], TFont())
        return TSpeciesNode(**data)


class ReactionSchema(Schema):
    id = fields.Str()
    rateLaw = fields.Str()
    reactants = fields.Dict(fields.Int(), fields.Nested(SpeciesNode))
    products = fields.Dict(fields.Int(), fields.Nested(SpeciesNode))
    fillColor = Color()
    thickness = Dim()
    centerHandlePos = Dim2()

    # @pre_dump
    # def pre_dump(self, data: TReaction, **kwargs):
    #     assert isinstance(data, TReaction)
    #     # TODO create schema for SpeciesNode
    #     return {
    #         'id': data.id,
    #         'rateLaw': data.rateLaw,
    #         'reactants': data.reactants,
    #         'products': data.products,
    #         'fillColor': data.fillColor,
    #         'thickness': data.thickness,
    #         'centerHandlePos': (data.centerHandlePos.x, data.centerHandlePos.y),
    #     }

    @post_load
    def post_load(self, data: Any, **kwargs) -> TReaction:
        return TReaction(**data)


class CompartmentSchema(Schema):
    id = fields.Str()
    position = Dim2()
    rectSize = Dim2()
    nodes = fields.List(fields.Int())
    volume = Dim()
    fillColor = Color()
    outlineColor = Color()
    outlineThickness = Dim()

    # @pre_dump
    # def pre_dump(self, data: TCompartment, **kwargs):
    #     assert isinstance(data, TCompartment)
    #     return {
    #         'id': data.id,
    #         'position': (data.position.x, data.position.y),
    #         'rectSize': (data.rectSize.x, data.rectSize.y),
    #         'nodes': data.node_indices,
    #         'volume': data.volume,
    #         'fillColor': data.fillColor,
    #         'outlineColor': data.outlineColor,
    #         'outlineThickness': data.outlineThickness,
    #     }

    @post_load
    def post_load(self, data: Any, **kwargs) -> TCompartment:
        return TCompartment(**data)


class NetworkSchema(Schema):
    id = fields.Str()
    nodes = fields.Mapping(fields.Int(), fields.Nested(NodeSchema))
    reactions = fields.Mapping(fields.Int(), fields.Nested(ReactionSchema))
    compartments = fields.Mapping(fields.Int(), fields.Nested(CompartmentSchema))

    @post_load
    def post_load(self, data: Any, **kwargs) -> TNetwork:
        return TNetwork(**data)


net_schema = NetworkSchema()


def dumpNetwork(neti: int):
    """Dump the network into an object and return it."""
    # TODO don't construct NetworkSchema every time.
    net = _getNetwork(neti)
    return net_schema.dump(net)


def loadNetwork(net_object) -> int:
    """Load the network object (laoded directly from JSON) and add it, returning the network index.
    
    Note:
        For now this overwrites the network at index 0.
    """
    # TODO save old
    net = net_schema.load(net_object)
    clearNetworks()
    _addNetwork(net)
    return 0
