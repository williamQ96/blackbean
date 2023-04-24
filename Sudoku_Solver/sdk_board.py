"""
Project: Sudoku Solver
Author: William Qiu
For CIS 211, Spring 2022, University of Oregon
"""

"""
A Sudoku board holds a matrix of tiles.
Each row, column, and sub-block is treated as a group.
When solved, each group must contain exactly one occurrence
of each of the symbol choices.
"""

from sdk_config import CHOICES, UNKNOWN, ROOT
from sdk_config import NROWS, NCOLS
import enum
from typing import List, Sequence, Set
import logging

logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class Event:
    """Abstract base class for events."""
    pass


class Listener:
    """Abstract base class for listeners."""

    def __init__(self):
        pass

    def notify(self, event: Event):
        raise NotImplementedError("You must override Listener.notify")


class EventKind(enum.Enum):
    TileChanged = 1
    TileGuessed = 2


class TileEvent(Event):
    """Abstract base class for tile-related events."""

    def __init__(self, tile: "Tile", kind: EventKind):
        self.tile = tile
        self.kind = kind

    def __str__(self):
        return f"{repr(self.tile)}"


class TileListener(Listener):
    def notify(self, event: TileEvent):
        raise NotImplementedError("TileListener subclass needs to override `notify(TileEvent)`")


class Listenable:
    """Objects to which listeners (like a view component) can be attached."""

    def __init__(self):
        self.listeners = []

    def add_listener(self, listener: Listener):
        self.listeners.append(listener)

    def notify_all(self, event: Event):
        for listener in self.listeners:
            listener.notify(event)


class Tile(Listenable):
    """One tile on the Sudoku grid."""

    def __init__(self, row: int, col: int, value=UNKNOWN):
        super().__init__()
        assert value == UNKNOWN or value in CHOICES
        self.row = row
        self.col = col
        self.candidates = None
        self.value = None
        self.set_value(value)

    def set_value(self, value: str):
        if value in CHOICES:
            self.value = value
            self.candidates = {value}
        else:
            self.value = UNKNOWN
            self.candidates = set(CHOICES)
        self.notify_all(TileEvent(self, EventKind.TileChanged))

    def could_be(self, value: str) -> bool:
        """True if value is a candidate value for this tile"""
        return value in self.candidates

    def remove_candidate(self, used_values: Set[str]) -> bool:
        new_candidates = self.candidates.difference(used_values)
        if new_candidates == self.candidates:
            return False
        self.candidates = new_candidates
        if len(self.candidates) == 1:
            self.set_value(new_candidates.pop())
        self.notify_all(TileEvent(self, EventKind.TileChanged))
        return True

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Tile({self.row}, {self.col}, {repr(self.value)})"

    def __hash__(self) -> int:
        """Hash on position only (not value)"""
        return hash((self.row, self.col))


class Board:
    """A Sudoku board has a matrix of tiles."""
    def __init__(self):
        self.tiles: List[List[Tile]] = []
        for row in range(NROWS):
            cols = []
            for col in range(NCOLS):
                cols.append(Tile(row, col))
            self.tiles.append(cols)

        self.groups: List[List[Tile]] = []

        for row in self.tiles:
            self.groups.append(row)

        for col_n in range(NCOLS):
            col = []
            for row in self.tiles:
                element = row[col_n]
                col.append(element)
            self.groups.append(col)

        for block_row in range(ROOT):
            for block_col in range(ROOT):
                group = []
                for row in range(ROOT):
                    for col in range(ROOT):
                        row_addr = (ROOT * block_row) + row
                        col_addr = (ROOT * block_col) + col
                        group.append(self.tiles[row_addr][col_addr])
                self.groups.append(group)

    def set_tiles(self, tile_values: Sequence[Sequence[str]]):
        """Set the tile values a list of lists or a list of strings"""
        for row_num in range(NROWS):
            for col_num in range(NCOLS):
                tile = self.tiles[row_num][col_num]
                tile.set_value(tile_values[row_num][col_num])

    def is_consistent(self) -> bool:
        """Returns true if the board state is valid by Sudoku rules"""
        for group in self.groups:
            used_symbols = set()
            for tile in group:
                if tile.value != UNKNOWN:
                    if tile.value in used_symbols:
                        return False  # The board is inconsistent if there is a duplicate here.
                    else:
                        used_symbols.add(tile.value)
        return True

    def is_complete(self) -> bool:
        """Returns true if each tile is filled; in other words none are UNKNOWN"""
        for row in self.tiles:
            for tile in row:
                if tile.value == UNKNOWN:
                    return False
        return True

    def min_choice_tile(self) -> Tile:
        """Returns a tile with value UNKNOWN and
        minimum number of candidates.
        Precondition: There is at least one tile
        with value UNKNOWN.
        """
        current_min_choice = None
        for row in self.tiles:
            for tile in row:
                if tile.value == UNKNOWN:
                    if current_min_choice is None or len(current_min_choice.candidates) > len(tile.candidates):
                        current_min_choice = tile
        return current_min_choice

    def naked_single(self) -> bool:
        """Eliminate candidates and check for sole remaining possibilities.
        Return value True means we crossed off at least one candidate.
        Return value False means we made no progress.
        """
        progress = False
        for group in self.groups:
            used_symbols = set()
            for tile in group:
                if tile.value != UNKNOWN:
                    used_symbols.add(tile.value)

            for tile in group:
                if tile.value == UNKNOWN:
                    if tile.remove_candidate(used_symbols):
                        progress = True
        return progress

    def hidden_single(self) -> bool:
        """Return true if we filled a tile, otherwise the tile is not filled"""
        progress = False
        for group in self.groups:
            leftovers = set(CHOICES)
            for tile in group:
                if tile.value in leftovers:
                    leftovers.discard(tile.value)

            for symbol in leftovers:
                possible_tiles = set()

                for tile in group:
                    if tile.value == UNKNOWN and symbol in tile.candidates:
                        possible_tiles.add(tile)

                if len(possible_tiles) == 1:
                    tile = possible_tiles.pop()
                    tile.set_value(symbol)
                    progress = True
        return progress

    def solve(self) -> bool:
        """General solver; guess-and-check
        combined with constraint propagation.
        """
        self.propagate()
        if self.is_complete():
            if self.is_consistent():
                return True
            else:
                return False
        elif not self.is_consistent():
            return False
        else:
            state_saved = self.as_list()
            a_guess = self.min_choice_tile()
            for i in a_guess.candidates:
                a_guess.set_value(i)
                if self.solve():
                    return True
                else:
                    self.set_tiles(state_saved)
            # Tried all the possibilities; none worked!
            return False

    def propagate(self):
        """Repeat solution tactics until we
        don't make any progress, whether or not
        the board is solved.
        """
        progress = True
        while progress:
            progress = self.naked_single()
            progress = progress or self.hidden_single()
        return

    def as_list(self) -> List[str]:
        """Tile values in a format compatible with set_tiles."""
        row_syms = []
        for row in self.tiles:
            values = [tile.value for tile in row]
            row_syms.append("".join(values))
        return row_syms

    def __str__(self) -> str:
        """In Sadman Sudoku format"""
        row_syms = self.as_list()
        return "\\n".join(row_syms)

if __name__ == "__main__":
    board = Board()
    # Add a test case to see if the code works
    board.set_tiles([
        "53..7....",
        "6..195...",
        ".98....6.",
        "8...6...3",
        "4..8.3..1",
        "7...2...6",
        ".6....28.",
        "...419..5",
        "....8..79",
    ])

    if board.solve():
        print("Sudoku solved successfully!")
        print(board)
    else:
        print("Couldn't solve the Sudoku.")
