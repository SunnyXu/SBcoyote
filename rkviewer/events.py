"""Custom events dispatched by the canvas.

These events may later be used within a plugin system, where plugins are allowed to bind their own
handlers to these events.
"""
# pylint: disable=maybe-no-member
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, fields, is_dataclass
from typing import (
    Callable,
    DefaultDict,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type, Union,
)

import wx

from rkviewer.canvas.data import Compartment, Node, Reaction
from rkviewer.canvas.geometry import Vec2


class CanvasEvent:
    def to_tuple(self):
        assert is_dataclass(self), "as_tuple requires the CanvasEvent instance to be a dataclass!"

        return tuple(getattr(self, f.name) for f in fields(self))


@dataclass
class SelectionDidUpdateEvent(CanvasEvent):
    """Called after the list of selected nodes and/or reactions has changed.

    Attributes:
        node_indices: The indices of the list of selected nodes.
        reaction_indices: The indices of the list of selected reactions.
        compartment_indices: The indices of the list of selected compartments.
    """
    node_indices: Set[int]
    reaction_indices: Set[int]
    compartment_indices: Set[int]


@dataclass
class CanvasDidUpdateEvent(CanvasEvent):
    """Called after the canvas has been updated by the controller.

    Attributes:
        nodes: The list of nodes.
        reactions: The list of reactions.
        compartments: The list of compartments.
    """
    nodes: List[Node]
    reactions: List[Reaction]
    compartments: List[Compartment]


@dataclass
class DidMoveNodesEvent(CanvasEvent):
    """Called after the position of a node changes but has not been committed to the model.

    This event may be called many times, continuously as the user drags a group of nodes. Note that
    only after the drag operation has ended, is model notified of the move for undo purposes. See
    DidCommitNodePositionsEvent.

    Attributes:
        nodes: The nodes that were moved.
        offset: The position offset. If all nodes were moved by the same offset, then a single Vec2
                is given; otherwise, a list of offsets are given, with each offset matching a node.
    """
    nodes: List[Node]
    offset: Union[Vec2, List[Vec2]]
    dragged: bool


@dataclass
class DidMoveCompartmentsEvent(CanvasEvent):
    """TODO document (same as DidMoveNodesEvent)
    """
    compartments: List[Compartment]
    offset: Union[Vec2, List[Vec2]]
    dragged: bool


@dataclass
class DidResizeNodesEvent(CanvasEvent):
    """Called after the list of selected nodes has been resized.

    Attributes:
        nodes: The list of resized nodes.
        ratio: The resize ratio.
        dragged: Whether the resize operation was done by the user dragging.

    Note:
        This event triggers only if the user has performed a drag operation, and not, for example,
        if the user moved a node in the edit panel.
    """
    nodes: List[Node]
    ratio: Vec2
    dragged: bool


@dataclass
class DidResizeCompartmentsEvent(CanvasEvent):
    """TODO document (same as DidResizeNodesEvent)
    """
    compartments: List[Compartment]
    ratio: Union[Vec2, List[Vec2]]
    dragged: bool


@dataclass
class DidCommitNodePositionsEvent(CanvasEvent):
    """Dispatched after the node positions are commited to the controller.

    This even is emitted only after a node move action has been regsitered with the controller.
    E.g., when a user drag-moves a ndoe, only after they release the left mouse button is the action
    recorded in the undo stack.
    """


@dataclass
class DidMoveBezierHandleEvent(CanvasEvent):
    """Dispatched after a Bezier handle is moved.

    Attributes:
        net_index: The network index.
        reaction_index: The reaction index.
        node_index: The index of the node whose Bezier handle moved, or -1 if the center handle
                    was moved.
        offset: The position offset.
        direct: Whether this event is triggered directly, i.e. by the user dragging on a Bezier
                handle. The event could be triggered *indirectly* when the user moves node(s).
        TODO not implemented
    """
    net_index: int
    reaction_index: int
    node_index: int
    direct: bool


@dataclass
class DidAddNodeEvent(CanvasEvent):
    """Called after a node has been added.

    Attributes:
        node: The node that was added.

    Note:
        This event triggers only if the user has performed a drag operation, and not, for example,
        if the user moved a node in the edit panel.
    """
    node: Node


@dataclass
class DidPaintCanvasEvent(CanvasEvent):
    """Called after the canvas has been painted.

    Attributes:
        gc: The graphics context of the canvas.
    """
    gc: wx.GraphicsContext


class HandlerNode:
    next_: Optional[HandlerNode]
    prev: Optional[HandlerNode]
    handler: EventCallback

    def __init__(self, handler: EventCallback):
        self.handler = handler
        self.next_ = None


EventCallback = Callable[[CanvasEvent], None]
# Maps CanvasElement to a dict that maps events to handler nodes
handler_map: Dict[int, Tuple[HandlerChain, HandlerNode]] = dict()
# Maps event to a chain of handlers
event_chains: DefaultDict[Type[CanvasEvent], HandlerChain] = defaultdict(lambda: HandlerChain())

handler_id = 0


class HandlerChain:
    head: Optional[HandlerNode]
    tail: Optional[HandlerNode]

    def __init__(self):
        self.head = None
        self.tail = None
        self.it_cur = None

    def remove(self, node: HandlerNode):
        if node.prev is not None:
            node.prev.next_ = node.next_
        else:
            self.head = node.next_

        if node.next_ is not None:
            node.next_.prev = node.prev
        else:
            self.tail = node.prev

    def __iter__(self):
        self.it_cur = self.head
        return self

    def __next__(self):
        if self.it_cur is None:
            raise StopIteration()

        ret = self.it_cur.handler
        self.it_cur = self.it_cur.next_
        return ret

    def append(self, handler: EventCallback) -> HandlerNode:
        node = HandlerNode(handler)
        if self.head is None:
            assert self.tail is None
            self.head = self.tail = node
        else:
            assert self.tail is not None
            node.prev = self.tail
            self.tail.next_ = node
            self.tail = node

        return node


def bind_handler(evt_cls: Type[CanvasEvent], callback: EventCallback) -> int:
    global handler_id
    ret = handler_id
    chain = event_chains[evt_cls]
    hnode = chain.append(callback)
    handler_map[ret] = (chain, hnode)
    handler_id += 1
    return ret


def unbind_handler(handler_id: int):
    chain, hnode = handler_map[handler_id]
    chain.remove(hnode)
    del handler_map[handler_id]


def post_event(evt: CanvasEvent):
    for callback in iter(event_chains[type(evt)]):
        callback(evt)
