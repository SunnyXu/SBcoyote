# pylint: disable=maybe-no-member
import wx
import abc
from typing import Any, List, Optional, Set
from .canvas.geometry import Vec2
from .canvas.data import Compartment, Node, Reaction


class IController(abc.ABC):
    """The inteface class for a controller

    The abc.ABC (Abstract Base Class) is used to enforce the MVC interface more
    strictly.

    The methods with name beginning with Try- are usually called by the View after
    some user input. If the action tried in such a method succeeds, the Controller
    should request the view to be redrawn; otherwise, an error message might be shown.
    """

    @abc.abstractmethod
    def start_group(self) -> bool:
        """Try to signal start of group operation"""
        pass

    @abc.abstractmethod
    def end_group(self) -> bool:
        """Try to signal end of group operation"""
        pass

    @abc.abstractmethod
    def in_group(self) -> bool:
        """Returns whether the controller is in the middle of a group operation."""
        pass

    @abc.abstractmethod
    def undo(self) -> bool:
        """Try to undo last operation"""
        pass

    @abc.abstractmethod
    def redo(self) -> bool:
        """Try to redo last undone operation"""
        pass

    @abc.abstractmethod
    def clear_network(self, neti: int):
        pass

    @abc.abstractmethod
    def add_node_g(self, neti: int, node: Node) -> int:
        """Try to add the given Node to the canvas. Return index of the node added."""
        pass

    @abc.abstractmethod
    def add_compartment_g(self, neti: int, compartment: Compartment) -> int:
        """Try to add the given Compartment to the canvas. Return index of added comp."""
        pass

    @abc.abstractmethod
    def move_node(self, neti: int, nodei: int, pos: Vec2, programmatic: bool = False) -> bool:
        """Try to move the give node. TODO only accept node ID and new location"""
        pass

    @abc.abstractmethod
    def set_node_size(self, neti: int, nodei: int, size: Vec2, programmatic: bool = False) -> bool:
        """Try to move the give node. TODO only accept node ID and new location"""
        pass

    @abc.abstractmethod
    def rename_node(self, neti: int, nodei: int, new_id: str) -> bool:
        pass

    @abc.abstractmethod
    def set_node_floating_status(self, neti: int, nodei: int, floatingStatus: bool):
        pass

    @abc.abstractmethod
    def set_node_fill_rgb(self, neti: int, nodei: int, color: wx.Colour) -> bool:
        pass

    @abc.abstractmethod
    def set_node_fill_alpha(self, neti: int, nodei: int, alpha: int) -> bool:
        pass

    @abc.abstractmethod
    def set_node_border_rgb(self, neti: int, nodei: int, color: wx.Colour) -> bool:
        pass

    @abc.abstractmethod
    def set_node_border_alpha(self, neti: int, nodei: int, alpha: int) -> bool:
        pass

    @abc.abstractmethod
    def set_node_border_width(self, neti: int, nodei: int, width: float) -> bool:
        pass

    @abc.abstractmethod
    def rename_reaction(self, neti: int, reai: int, new_id: str) -> bool:
        pass

    @abc.abstractmethod
    def set_reaction_line_thickness(self, neti: int, reai: int, thickness: float) -> bool:
        pass

    @abc.abstractmethod
    def set_reaction_fill_rgb(self, neti: int, reai: int, color: wx.Colour) -> bool:
        pass

    @abc.abstractmethod
    def set_reaction_fill_alpha(self, neti: int, reai: int, alpha: int) -> bool:
        pass

    @abc.abstractmethod
    def set_reaction_ratelaw(self, neti: int, reai: int, ratelaw: str) -> bool:
        pass

    @abc.abstractmethod
    def set_reaction_center(self, neti: int, reai: int, center_pos: Optional[Vec2]):
        pass

    @abc.abstractmethod
    def delete_node(self, neti: int, nodei: int) -> bool:
        pass

    @abc.abstractmethod
    def delete_reaction(self, neti: int, reai: int) -> bool:
        pass

    @abc.abstractmethod
    def delete_compartment(self, neti: int, compi: int) -> bool:
        pass

    @abc.abstractmethod
    def set_src_node_stoich(self, neti: int, reai: int, nodei: int, stoich: float) -> bool:
        pass

    @abc.abstractmethod
    def get_dest_node_stoich(self, neti: int, reai: int, nodei: int) -> float:
        pass

    @abc.abstractmethod
    def set_dest_node_stoich(self, neti: int, reai: int, nodei: int, stoich: float) -> bool:
        pass

    @abc.abstractmethod
    def get_src_node_stoich(self, neti: int, reai: int, nodei: int) -> float:
        pass

    @abc.abstractmethod
    def set_src_node_handle(self, neti: int, reai: int, nodei: int, pos: Vec2):
        pass

    @abc.abstractmethod
    def set_dest_node_handle(self, neti: int, reai: int, nodei: int, pos: Vec2):
        pass

    @abc.abstractmethod
    def set_center_handle(self, neti: int, reai: int, pos: Vec2):
        pass

    @abc.abstractmethod
    def get_src_node_handle(self, neti: int, reai: int, nodei: int) -> Vec2:
        pass

    @abc.abstractmethod
    def get_dest_node_handle(self, neti: int, reai: int, nodei: int) -> Vec2:
        pass

    @abc.abstractmethod
    def get_center_handle(self, neti: int, reai: int) -> Vec2:
        pass

    @abc.abstractmethod
    def get_list_of_src_indices(self, neti: int, reai: int) -> List[int]:
        pass

    @abc.abstractmethod
    def get_list_of_dest_indices(self, neti: int, reai: int) -> List[int]:
        pass

    @abc.abstractmethod
    def get_reactions_as_reactant(self, neti: int, nodei: int) -> Set[int]:
        pass

    @abc.abstractmethod
    def get_reactions_as_product(self, neti: int, nodei: int) -> Set[int]:
        pass

    @abc.abstractmethod
    def get_list_of_node_ids(self, neti: int) -> List[str]:
        """Try getting the list of node IDs"""
        pass

    @abc.abstractmethod
    def get_node_indices(self, neti: int) -> Set[int]:
        pass

    @abc.abstractmethod
    def get_reaction_indices(self, neti: int) -> Set[int]:
        pass

    @abc.abstractmethod
    def get_compartment_indices(self, neti: int) -> Set[int]:
        pass

    @abc.abstractmethod
    def get_list_of_nodes(self, neti: int) -> List[Node]:
        pass

    @abc.abstractmethod
    def get_list_of_reactions(self, neti: int) -> List[Reaction]:
        pass

    @abc.abstractmethod
    def get_list_of_compartments(self, neti: int) -> List[Compartment]:
        pass

    @abc.abstractmethod
    def rename_compartment(self, neti: int, compi: int, new_id: str):
        pass

    @abc.abstractmethod
    def move_compartment(self, neti: int, compi: int, pos: Vec2):
        pass

    @abc.abstractmethod
    def set_compartment_size(self, neti: int, compi: int, size: Vec2):
        pass

    @abc.abstractmethod
    def set_compartment_fill(self, neti: int, compi: int, fill: wx.Colour):
        pass

    @abc.abstractmethod
    def set_compartment_border(self, neti: int, compi: int, fill: wx.Colour):
        pass

    @abc.abstractmethod
    def set_compartment_border_width(self, neti: int, compi: int, width: float):
        pass

    @abc.abstractmethod
    def set_compartment_volume(self, neti: int, compi: int, volume: float):
        pass

    @abc.abstractmethod
    def set_compartment_of_node(self, neti: int, nodei: int, compi: int):
        pass

    @abc.abstractmethod
    def get_compartment_of_node(self, neti: int, nodei: int) -> int:
        pass

    @abc.abstractmethod
    def get_nodes_in_compartment(self, neti: int, cmpi: int) -> List[int]:
        pass

    @abc.abstractmethod
    def get_node_index(self, neti: int, node_id: str) -> int:
        pass

    @abc.abstractmethod
    def get_node_id(self, neti: int, nodei: int) -> str:
        pass

    @abc.abstractmethod
    def get_reaction_index(self, neti: int, rxn_id: str) -> int:
        pass

    @abc.abstractmethod
    def set_reaction_bezier_curves(self, neti: int, bezierCurves: bool) -> Reaction:
        pass

    @abc.abstractmethod
    def add_reaction_g(self, neti: int, reaction: Reaction) -> int:
        pass

    @abc.abstractmethod
    def get_node_by_index(self, neti: int, nodei: int) -> Node:
        pass

    @abc.abstractmethod
    def get_reaction_by_index(self, neti: int, reai: int) -> Reaction:
        pass

    @abc.abstractmethod
    def get_compartment_by_index(self, neti: int, compi: int) -> Compartment:
        pass

    @abc.abstractmethod
    def update_view(self):
        """Immediately update the view with using latest model."""
        pass

    @abc.abstractmethod
    def dump_network(self, neti: int):
        pass

    @abc.abstractmethod
    def load_network(self, json_obj: Any) -> int:
        pass

    @abc.abstractmethod
    def new_network(self):
        """Create a new network.
        
        Since there is only one tab for now, this merely clears the the current network. Also,
        does not clear undo stack.
        """
        pass


class IView(abc.ABC):
    """The inteface class for a controller

    The abc.ABC (Abstract Base Class) is used to enforce the MVC interface more
    strictly.
    """

    @abc.abstractmethod
    def bind_controller(self, controller: IController):
        """Bind the controller. This needs to be called after a controller is 
        created and before any other method is called.
        """
        pass

    @abc.abstractmethod
    def main_loop(self):
        """Run the main loop. This is blocking right now. This may be modified to
        become non-blocking in the future if required.
        """
        pass

    @abc.abstractmethod
    def update_all(self, nodes, reactions, compartments):
        """Update all the graph objects, and redraw everything at the end"""
        pass


class ModelError(Exception):
    """Base class for other exceptions"""
    pass


class IDNotFoundError(ModelError):
    pass


class IDRepeatError(ModelError):
    pass


class NodeNotFreeError(ModelError):
    pass


class NetIndexError(ModelError):
    pass


class ReactionIndexError(ModelError):
    pass


class NodeIndexError(ModelError):
    pass


class CompartmentIndexError(ModelError):
    pass


class StoichError(ModelError):
    pass


class StackEmptyError(ModelError):
    pass


class JSONError(ModelError):
    pass


class FileError(ModelError):
    pass
