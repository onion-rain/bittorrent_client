import asyncio
import time
import logging

from .peer_connection import PeerConnection
from .piece_manager import PieceManager
from .tracker import Tracker


class TorrentClient:
    """
    The torrent client is the local peer that holds peer-to-peer
    connections to download and upload pieces for a given torrent.

    Once started, the client makes periodic announce calls to the tracker
    registered in the torrent meta-data. These calls results in a list of
    peers that should be tried in order to exchange pieces.

    Each received peer is kept in a queue that a pool of PeerConnection
    objects consume. There is a fix number of PeerConnections that can have
    a connection open to a peer. Since we are not creating expensive threads
    (or worse yet processes) we can create them all at once and they will
    be waiting until there is a peer to consume in the queue.
    """
    def __init__(self, torrent, MAX_PEER_CONNECTIONS=40):
        self.tracker = Tracker(torrent)
        # The number of max peer connections per TorrentClient
        self.MAX_PEER_CONNECTIONS = MAX_PEER_CONNECTIONS
        # The list of potential peers is the work queue, consumed by the
        # PeerConnections
        self.available_peers = asyncio.Queue()
        # The list of peers is the list of workers that *might* be connected
        # to a peer. Else they are waiting to consume new remote peers from
        # the `available_peers` queue. These are our workers!
        self.peer_connections = []
        # The piece manager implements the strategy on which pieces to
        # request, as well as the logic to persist received pieces to disk.
        self.piece_manager = PieceManager(torrent)
        self.abort = False

    async def start(self):
        """
        Start downloading the torrent held by this client.

        This results in connecting to the tracker to retrieve the list of
        peers to communicate with. Once the torrent is fully downloaded or
        if the download is aborted this method will complete.
        """
        self.peer_connections = [PeerConnection(self.available_peers,
                                                self.tracker.torrent.info_hash,
                                                self.tracker.peer_id,
                                                self.piece_manager,
                                                self._on_block_retrieved)
                                for _ in range(self.MAX_PEER_CONNECTIONS)]
        
        # The time we last made an announce call (timestamp)
        previous_moment = None
        # Default interval between announce calls made to the tracker (in seconds)
        interval_time = 30*60

        while True:
            # print("====================>>>>>>>>>>>>>>>>client<<<<<<<<<<<<<<<<<<<<==================")
            if self.piece_manager.complete:
                logging.info('Torrent fully downloaded!')
                break
            if self.abort:
                logging.info('Aborting download...')
                break

            current_moment = time.time()

            if (previous_moment is None) or (current_moment > previous_moment + interval_time):
                
                try:
                    response = await self.tracker.connect(
                        first=False if previous_moment else True,
                        uploaded=self.piece_manager.bytes_uploaded,
                        downloaded=self.piece_manager.bytes_downloaded)

                    if response:
                        # print(response)
                        previous_moment = current_moment
                        # interval_time = response.interval
                        self._update_queue(response.peers)
                        print("available_peers: {}".format(len(response.peers)))
                except BaseException:
                    logging.exception('Connect to tracker failed')
            else:
                if self.available_peers.empty():
                    print("TorrentClient.available_peers is enmpty !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    self._update_queue(response.peers)
                await asyncio.sleep(5)

        # print("====================>>>>>>>>>>>>>>>>!!!!!!!!!!!!!!!!!!!!!!!1start STOP!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!1<<<<<<<<<<<<<<<<<<<<==================")
        self.stop()
    
    def _update_queue(self, new_peers):
        while not self.available_peers.empty():
            self.available_peers.get_nowait()
        for peer in new_peers:
            self.available_peers.put_nowait(peer)

    def _on_block_retrieved(self, remote_id, piece_index, block_offset, data):
        """
        Callback function called by the `PeerConnection` when a block is
        retrieved from a peer.

        :param remote_id: The id of the peer the block was retrieved from
        :param piece_index: The piece index this block is a part of
        :param block_offset: The block offset within its piece
        :param data: The binary data retrieved
        """
        self.piece_manager.block_received(
            remote_id=remote_id, piece_index=piece_index,
            block_offset=block_offset, data=data)

    def stop(self):
        """
        Stop the download or seeding process.
        """
        self.abort = True
        for peer_connection in self.peer_connections:
            peer_connection.stop()
        self.piece_manager.close()
        self.tracker.close()
