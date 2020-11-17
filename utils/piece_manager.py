import math
import os
import time
import logging

from collections import namedtuple, defaultdict

from .piece import Piece, Block
from .peer_message import REQUEST_SIZE


# The type used for keeping track of pending request that can be re-issued
PendingRequest = namedtuple('PendingRequest', ['block', 'added_moment'])


class PieceManager:
    """
    The PieceManager is responsible for keeping track of all the available
    pieces for the connected peers as well as the pieces we have available for
    other peers.

    The strategy on which piece to request is made as simple as possible in
    this implementation.
    """
    def __init__(self, torrent):
        self.torrent = torrent
        self.total_pieces_len = len(torrent.pieces)
        self.peers = {}
        self.pending_blocks = []
        # self.missing_pieces = []
        self.missing_pieces = self._initiate_pieces()
        self.ongoing_pieces = []
        self.have_pieces = []
        self.max_pending_time = 1 * 60 * 1000  # 5 minutes
        self.fd = os.open(torrent.output_file,  os.O_RDWR | os.O_CREAT | os.O_BINARY)

    def _initiate_pieces(self) -> [Piece]:
        """
        Pre-construct the list of pieces and blocks based on the number of
        pieces and request size for this torrent.
        """
        torrent = self.torrent
        total_pieces_len = self.total_pieces_len
        pieces = []
        n_piece_blocks = math.ceil(torrent.piece_length / REQUEST_SIZE)

        for index, hash_value in enumerate(torrent.pieces):
            # The number of blocks for each piece can be calculated using the
            # request size as divisor for the piece length.
            # The final piece however, will most likely have fewer blocks
            # than 'regular' pieces, and that final block might be smaller
            # than the other blocks.
            if index < (total_pieces_len - 1):
                blocks = [Block(index, block_id * REQUEST_SIZE, REQUEST_SIZE)
                          for block_id in range(n_piece_blocks)]
            else:
                last_length = torrent.total_size % torrent.piece_length
                num_blocks = math.ceil(last_length / REQUEST_SIZE)
                blocks = [Block(index, block_id * REQUEST_SIZE, REQUEST_SIZE)
                          for block_id in range(num_blocks)]

                if last_length % REQUEST_SIZE > 0:
                    # Last block of the last piece might be smaller than
                    # the ordinary request size.
                    last_block = blocks[-1]
                    last_block.length = last_length % REQUEST_SIZE
                    blocks[-1] = last_block
            pieces.append(Piece(index, blocks, hash_value))
        return pieces

    def close(self):
        """
        Close any resources used by the PieceManager (such as open files)
        """
        if self.fd:
            os.close(self.fd)

    @property
    def complete(self):
        """
        Checks whether or not the all pieces are downloaded for this torrent.

        :return: True if all pieces are fully downloaded else False
        """
        return len(self.have_pieces) == self.total_pieces_len

    @property
    def bytes_downloaded(self) -> int:
        """
        Get the number of bytes downloaded.

        This method Only counts full, verified, pieces, not single blocks.
        """
        return len(self.have_pieces) * self.torrent.piece_length

    @property
    def bytes_uploaded(self) -> int:
        # TODO Add support for sending data
        return 0

    def add_peer(self, peer_id, bitfield):
        """
        Adds a peer and the bitfield representing the pieces the peer has.
        """
        self.peers[peer_id] = bitfield

    def update_peer(self, peer_id, index: int):
        """
        Updates the information about which pieces a peer has (reflects a Have
        message).
        """
        if peer_id in self.peers:
            self.peers[peer_id][index] = 1
        # else:
        #     self.peers[peer_id][index] = 1

    def remove_peer(self, peer_id):
        """
        Tries to remove a previously added peer (e.g. used if a peer connection
        is dropped)
        """
        if peer_id in self.peers:
            del self.peers[peer_id]

    def next_request(self, peer_id) -> Block:
        """
        Get the next Block that should be requested from the given peer.

        If there are no more blocks left to retrieve or if this peer does not
        have any of the missing pieces None is returned
        """
        # The algorithm implemented for which piece to retrieve is a simple
        # one. This should preferably be replaced with an implementation of
        # "rarest-piece-first" algorithm instead.
        #
        # The algorithm tries to download the pieces in sequence and will try
        # to finish started pieces before starting with new pieces.
        #
        # 1. Check any pending blocks to see if any request should be reissued
        #    due to timeout
        # 2. Check the ongoing pieces to get the next block to request
        # 3. Check if this peer have any of the missing pieces not yet started
        if peer_id not in self.peers:
            return None

        block = self._expired_requests(peer_id)
        if not block:
            block = self._next_ongoing(peer_id)
            if not block:
                # block = self._get_rarest_piece(peer_id).next_request()
                piece = self._get_rarest_piece(peer_id)
                block = self._next_ongoing(peer_id)
        return block

    def _expired_requests(self, peer_id) -> Block:
        """
        Go through previously requested blocks, if any one have been in the
        requested state for longer than `MAX_PENDING_TIME` return the block to
        be re-requested.

        If no pending blocks exist, None is returned
        """
        current = int(round(time.time() * 1000))
        for request in self.pending_blocks:
            if self.peers[peer_id][request.block.piece]:
                if request.added_moment + self.max_pending_time < current:
                    logging.info('Re-requesting block {block} for '
                                 'piece {piece}'.format(
                                    block=request.block.offset,
                                    piece=request.block.piece))
                    # Reset expiration timer
                    self.pending_blocks.append(PendingRequest(request.block, current))
                    self.pending_blocks.remove(request)
                    return self.pending_blocks[-1].block
        return None

    def _next_ongoing(self, peer_id) -> Block:
        """
        Go through the ongoing pieces and return the next block to be
        requested or None if no block is left to be requested.
        """
        for piece in self.ongoing_pieces:
            if self.peers[peer_id][piece.index]:
                # Is there any blocks left to request in this piece?
                block = piece.next_request()
                if block:
                    self.pending_blocks.append(PendingRequest(block, int(round(time.time() * 1000))))
                    return block
        return None

    def _get_rarest_piece(self, peer_id) -> Piece:
        """
        Given the current list of missing pieces, get the
        rarest one first (i.e. a piece which fewest of its
        neighboring peers have)
        """
        piece_count = defaultdict(int)
        for piece in self.missing_pieces:
            if not self.peers[peer_id][piece.index]:
                continue
            for p in self.peers:
                if self.peers[p][piece.index]:
                    piece_count[piece] += 1

        rarest_piece = min(piece_count, key=lambda p: piece_count[p])
        self.missing_pieces.remove(rarest_piece)
        self.ongoing_pieces.append(rarest_piece)
        return rarest_piece

    def block_received(self, remote_id, piece_index, block_offset, data):
        """
        This method must be called when a block has successfully been retrieved
        by a peer.

        Once a full piece have been retrieved, a SHA1 hash control is made. If
        the check fails all the pieces blocks are put back in missing state to
        be fetched again. If the hash succeeds the partial piece is written to
        disk and the piece is indicated as Have.
        """
        logging.info('Received block {block_offset} for piece {piece_index} '
                      'from peer {remote_id}: '.format(block_offset=block_offset,
                                                     piece_index=piece_index,
                                                     remote_id=remote_id))

        # Remove from pending requests
        for index, request in enumerate(self.pending_blocks):
            if request.block.piece == piece_index and \
               request.block.offset == block_offset:
                del self.pending_blocks[index]
                break

        pieces = [p for p in self.ongoing_pieces if p.index == piece_index]
        piece = pieces[0] if pieces else None
        if piece:
            piece.block_received(block_offset, data)
            if piece.is_complete():
                if piece.is_hash_matching():
                    self._write(piece)
                    self.ongoing_pieces.remove(piece)
                    self.have_pieces.append(piece)
                    complete = len(self.have_pieces)
                    # complete = (self.total_pieces_len -
                    #             len(self.missing_pieces) -
                    #             len(self.ongoing_pieces))
                    print(' ==== >>> ==== >>> {complete} / {total} pieces downloaded {per:.3f} % <<< ==== <<< ===='
                          .format(complete=complete,
                                  total=self.total_pieces_len,
                                  per=(complete/self.total_pieces_len)*100))
                    if (self.total_pieces_len == complete):
                        print(complete)
                else:
                    logging.info('Discarding corrupt piece {index}'
                                 .format(index=piece.index))
                    piece.reset()
        else:
            logging.warning('Trying to update piece that is not ongoing!')

    # def _next_missing(self, peer_id) -> Block:
    #     """
    #     Go through the missing pieces and return the next block to request
    #     or None if no block is left to be requested.

    #     This will change the state of the piece from missing to ongoing - thus
    #     the next call to this function will not continue with the blocks for
    #     that piece, rather get the next missing piece.
    #     """
    #     for index, piece in enumerate(self.missing_pieces):
    #         if self.peers[peer_id][piece.index]:
    #             # Move this piece from missing to ongoing
    #             piece = self.missing_pieces.pop(index)
    #             self.ongoing_pieces.append(piece)
    #             # The missing pieces does not have any previously requested
    #             # blocks (then it is ongoing).
    #             return piece.next_request()
    #     return None

    def _write(self, piece):
        """
        Write the given piece to disk
        """
        pos = piece.index * self.torrent.piece_length
        os.lseek(self.fd, pos, os.SEEK_SET)
        os.write(self.fd, piece.data)
