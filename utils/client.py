

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
    # def __init__(self, torrent):
    #     self.tracker = Tracker(torrent)
    def __init__(self, tracker):
        self.tracker = tracker
        # The list of potential peers is the work queue, consumed by the
        # PeerConnections
        self.available_peers = Queue()
        # The list of peers is the list of workers that *might* be connected
        # to a peer. Else they are waiting to consume new remote peers from
        # the `available_peers` queue. These are our workers!
        self.peers = []
        # The piece manager implements the strategy on which pieces to
        # request, as well as the logic to persist received pieces to disk.
        # self.piece_manager = PieceManager(torrent)
        self.abort = False

    async def start(self):
            """
            Start downloading the torrent held by this client.

            This results in connecting to the tracker to retrieve the list of
            peers to communicate with. Once the torrent is fully downloaded or
            if the download is aborted this method will complete.
            """
            self.peers = [PeerConnection(self.available_peers,
                                        self.tracker.torrent.info_hash,
                                        self.tracker.peer_id,
                                        self.piece_manager,
                                        self._on_block_retrieved)
                        for _ in range(MAX_PEER_CONNECTIONS)]

            # The time we last made an announce call (timestamp)
            previous = None
            # Default interval between announce calls (in seconds)
            interval = 30*60

            while True:
                if self.piece_manager.complete:
                    logging.info('Torrent fully downloaded!')
                    break
                if self.abort:
                    logging.info('Aborting download...')
                    break

                current = time.time()
                if (not previous) or (previous + interval < current):
                    response = await self.tracker.connect(
                        first=previous if previous else False,
                        uploaded=self.piece_manager.bytes_uploaded,
                        downloaded=self.piece_manager.bytes_downloaded)

                    if response:
                        previous = current
                        interval = response.interval
                        self._empty_queue()
                        for peer in response.peers:
                            self.available_peers.put_nowait(peer)
                else:
                    await asyncio.sleep(5)
            self.stop()
