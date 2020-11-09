import asyncio
import logging

from concurrent.futures import CancelledError

from .peer_message import PeerMessage, Handshake, Interested, BitField, NotInterested, Choke, Unchoke, Have, KeepAlive, Piece, Request, Cancel
from .peer_stream_iterator import PeerStreamIterator


class ProtocolError(BaseException):
    pass


class PeerConnection:
    """
    A peer connection used to download and upload pieces.

    The peer connection will consume one available peer from the given queue.
    Based on the peer details the PeerConnection will try to open a connection
    and perform a BitTorrent handshake.

    After a successful handshake, the PeerConnection will be in a *choked*
    state, not allowed to request any data from the remote peer. After sending
    an interested message the PeerConnection will be waiting to get *unchoked*.

    Once the remote peer unchoked us, we can start requesting pieces.
    The PeerConnection will continue to request pieces for as long as there are
    pieces left to request, or until the remote peer disconnects.

    If the connection with a remote peer drops, the PeerConnection will consume
    the next available peer from off the queue and try to connect to that one
    instead.
    """
    def __init__(self, available_peers: asyncio.Queue, info_hash,
                 peer_id, piece_manager, on_block_cb=None):
        """
        Constructs a PeerConnection and add it to the asyncio event-loop.

        Use `stop` to abort this connection and any subsequent connection
        attempts

        :param available_peers: The async Queue containing available peers
        :param info_hash: The SHA1 hash for the meta-data's info
        :param peer_id: Our peer ID used to to identify ourselves
        :param piece_manager: The manager responsible to determine which pieces
                              to request
        :param on_block_cb: The callback function to call when a block is
                            received from the remote peer
        """
        self.my_state = []
        # self.peer_state = []
        self.available_peers = available_peers
        self.info_hash = info_hash
        self.peer_id = peer_id
        self.remote_id = None
        self.writer = None
        self.reader = None
        self.piece_manager = piece_manager
        self.on_block_cb = on_block_cb
        self.future = asyncio.ensure_future(self._start())  # Start this worker

    async def _start(self):
        while 'stopped' not in self.my_state:
            # print("<<<<<<<<<<<<<<<<<<<<<<<========================PEER CONNECTION=========================>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
            ip, port = await self.available_peers.get()
            self.ip = ip
            self.port = port
            logging.info('Got assigned peer with: {ip}:{port}'.format(ip=ip, port=port))
            try:
                # TODO For some reason it does not seem to work to open a new
                # connection if the first one drops (i.e. second loop).
                connect = asyncio.open_connection(ip, port)  # connect 为协程，立即返回不阻塞
                self.reader, self.writer = await connect  # 阻塞操作，释放cpu
                logging.info('Connection open to peer: {ip}'.format(ip=ip))

                # It's our responsibility to initiate the handshake.
                buffer = await self._send_handshake()

                # TODO Add support for sending data
                # Sending BitField is optional and not needed when client does
                # not have any pieces. Thus we do not send any bitfield message

                # The default state for a connection is that peer is not
                # interested and we are choked
                self.my_state.append('choked')

                # Let the peer know we're interested in downloading pieces
                await self._send_interested()
                self.my_state.append('interested')

                # Start reading responses as a stream of messages for as
                # long as the connection is open and data is transmitted
                async for message in PeerStreamIterator(self.reader, buffer):
                    # print("i am alive {peer}".format(peer=self.remote_id))
                    if 'stopped' in self.my_state:
                        break
                    if type(message) is BitField:
                        # logging.info("receive BitField from peer {peer}".format(peer=self.remote_id))
                        self.piece_manager.add_peer(self.remote_id, message.bitfield)
                    # elif type(message) is Interested:
                    #     # logging.info("receive Interested from peer {peer}".format(peer=self.remote_id))
                    #     self.peer_state.append('interested')
                    # elif type(message) is NotInterested:
                    #     # logging.info("receive NotInterested from peer {peer}".format(peer=self.remote_id))
                    #     if 'interested' in self.peer_state:
                    #         self.peer_state.remove('interested')
                    elif type(message) is Choke:
                        # logging.info("receive Choke from peer {peer}".format(peer=self.remote_id))
                        self.my_state.append('choked')
                    elif type(message) is Unchoke:
                        # logging.info("receive Unchoke from peer {peer}".format(peer=self.remote_id))
                        if 'choked' in self.my_state:
                            self.my_state.remove('choked')
                    elif type(message) is Have:
                        # logging.info("receive Have from peer {peer}".format(peer=self.remote_id))
                        self.piece_manager.update_peer(self.remote_id, message.index)
                    elif type(message) is KeepAlive:
                        # logging.info("receive KeepAlive from peer {peer}".format(peer=self.remote_id))
                        await asyncio.sleep(1)
                        pass
                    elif type(message) is Piece:
                        # logging.info("receive Piece from peer {peer}".format(peer=self.remote_id))
                        self.my_state.remove('pending_request')
                        self.on_block_cb(
                            remote_id=self.remote_id,
                            piece_index=message.index,
                            block_offset=message.begin,
                            data=message.block
                        )
                    elif type(message) is Request:
                        logging.info("receive Request from peer {peer}".format(peer=self.remote_id))
                        # TODO Add support for sending data
                        logging.info('Ignoring the received Request message.')
                    elif type(message) is Cancel:
                        logging.info("receive Cancel from peer {peer}".format(peer=self.remote_id))
                        # TODO Add support for sending data
                        logging.info('Ignoring the received Cancel message.')

                    # Send block request to remote peer if we're interested
                    if 'choked' not in self.my_state:
                        if 'interested' in self.my_state:
                            if 'pending_request' not in self.my_state:
                                self.my_state.append('pending_request')
                                await self._request_piece()

            except ProtocolError as e:
                logging.exception('Connection to peer with: {ip}:{port} Protocol error'.format(ip=ip, port=port))
                # logging.warning('Connection to peer with: {ip}:{port} Protocol error'.format(ip=ip, port=port))
            except (ConnectionRefusedError):
                logging.warning('Connection to peer with: {ip}:{port} refused'.format(ip=ip, port=port))
            except (TimeoutError):
                logging.warning('Connection to peer with: {ip}:{port} timeout'.format(ip=ip, port=port))
            except (ConnectionResetError, CancelledError):
                logging.warning('Connection to peer with: {ip}:{port} closed'.format(ip=ip, port=port))
            except Exception as e:
                logging.exception('An error occurred')
                self.cancel()
                raise e
            self.cancel()

    def stop(self):
        """
        Stop this connection from the current peer (if a connection exist) and
        from connecting to any new peer.
        """
        # Set state to stopped and cancel our future to break out of the loop.
        # The rest of the cleanup will eventually be managed by loop calling
        # `cancel`.
        self.my_state.append('stopped')
        if not self.future.done():
            self.future.cancel()

    def cancel(self):
        """
        Sends the cancel message to the remote peer and closes the connection.
        """
        logging.warning('Closing peer {id}, {ip}:{port}'.format(id=self.remote_id, ip=self.ip, port=self.port))
        if not self.future.done():
            self.future.cancel()
        if self.writer:
            self.writer.close()

        self.available_peers.task_done()

    async def _send_handshake(self):
        """
        Send the initial handshake to the remote peer and wait for the peer
        to respond with its handshake.
        """
        self.writer.write(Handshake(self.info_hash, self.peer_id).encode())
        await self.writer.drain()

        buf = b''
        tries = 1
        while len(buf) < Handshake.length and tries < 10:
            tries += 1
            buf = await self.reader.read(PeerStreamIterator.CHUNK_SIZE)

        response = Handshake.decode(buf[:Handshake.length])
        if not response:
            raise ProtocolError('Unable receive and parse a handshake : {ip}:{port}'.format(ip=self.ip, port=self.port))
        if not response.info_hash == self.info_hash:
            raise ProtocolError('Handshake with invalid info_hash : {ip}:{port}'.format(ip=self.ip, port=self.port))

        # TODO: According to spec we should validate that the peer_id received
        # from the peer match the peer_id received from the tracker.
        self.remote_id = response.peer_id
        logging.info('Handshake with peer {peer} was successful, {ip}:{port}'.format(peer=self.remote_id, ip=self.ip, port=self.port))

        # We need to return the remaining buffer data, since we might have
        # read more bytes then the size of the handshake message and we need
        # those bytes to parse the next message.
        return buf[Handshake.length:]

    async def _send_interested(self):
        message = Interested()
        logging.info('Sending message: {type} to peer {peer}'.format(type=message, peer=self.remote_id))
        self.writer.write(message.encode())
        await self.writer.drain()

    async def _request_piece(self):
        block = self.piece_manager.next_request(self.remote_id)
        if block:
            message = Request(block.piece, block.offset, block.length).encode()

            logging.info('Requesting block {block} for piece {piece} '
                          'of {length} bytes from peer {peer}'.format(
                            piece=block.piece,
                            block=block.offset,
                            length=block.length,
                            peer=self.remote_id))

            self.writer.write(message)
            await self.writer.drain()