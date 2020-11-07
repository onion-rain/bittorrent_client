import struct
import logging

from concurrent.futures import CancelledError

from .peer_message import PeerMessage, Handshake, Interested, BitField, NotInterested, Choke, Unchoke, Have, KeepAlive, Piece, Request, Cancel

class PeerStreamIterator:
    """
    The `PeerStreamIterator` is an async iterator that continuously reads from
    the given stream reader and tries to parse valid BitTorrent messages from
    off that stream of bytes.

    If the connection is dropped, something fails the iterator will abort by
    raising the `StopAsyncIteration` error ending the calling iteration.
    """
    CHUNK_SIZE = 10*1024

    def __init__(self, reader, initial: bytes=None):
        self.reader = reader
        self.buffer = initial if initial else b''

    def __aiter__(self):
        return self

    async def __anext__(self):
        # Read data from the socket. When we have enough data to parse, parse
        # it and return the message. Until then keep reading from stream
        while True:
            try:
                data = await self.reader.read(PeerStreamIterator.CHUNK_SIZE)
                if data:
                    self.buffer += data
                    message = self.parse()
                    if message:
                        return message
                else:
                    # logging.debug('No data read from stream')
                    if self.buffer:
                        message = self.parse()
                        if message:
                            return message
                    raise StopAsyncIteration()
            except ConnectionResetError:
                logging.debug('Connection closed by peer')
                raise StopAsyncIteration()
            except CancelledError:
                raise StopAsyncIteration()
            except StopAsyncIteration as e:
                # Cath to stop logging
                raise e
            except Exception:
                logging.exception('Error when iterating over stream!')
                raise StopAsyncIteration()
        raise StopAsyncIteration()

    def parse(self):
        """
        Tries to parse protocol messages if there is enough bytes read in the
        buffer.

        :return The parsed message, or None if no message could be parsed
        """
        # Each message is structured as:
        #     <length prefix><message ID><payload>
        #
        # The `length prefix` is a four byte big-endian value
        # The `message ID` is a decimal byte
        # The `payload` is the value of `length prefix`
        #
        # The message length is not part of the actual length. So another
        # 4 bytes needs to be included when slicing the buffer.
        header_length = 4

        if len(self.buffer) > 4:  # 4 bytes is needed to identify the message
            message_length = struct.unpack('>I', self.buffer[0:4])[0]

            if message_length == 0:
                return KeepAlive()

            if len(self.buffer) >= message_length:
                message_id = struct.unpack('>b', self.buffer[4:5])[0]

                def _consume():
                    """Consume the current message from the read buffer"""
                    self.buffer = self.buffer[header_length + message_length:]

                def _data():
                    """"Extract the current message from the read buffer"""
                    return self.buffer[:header_length + message_length]

                if message_id is PeerMessage.BitField:
                    data = _data()
                    _consume()
                    return BitField.decode(data)
                elif message_id is PeerMessage.Interested:
                    _consume()
                    return Interested()
                elif message_id is PeerMessage.NotInterested:
                    _consume()
                    return NotInterested()
                elif message_id is PeerMessage.Choke:
                    _consume()
                    return Choke()
                elif message_id is PeerMessage.Unchoke:
                    _consume()
                    return Unchoke()
                elif message_id is PeerMessage.Have:
                    data = _data()
                    _consume()
                    return Have.decode(data)
                elif message_id is PeerMessage.Piece:
                    data = _data()
                    _consume()
                    return Piece.decode(data)
                elif message_id is PeerMessage.Request:
                    data = _data()
                    _consume()
                    return Request.decode(data)
                elif message_id is PeerMessage.Cancel:
                    data = _data()
                    _consume()
                    return Cancel.decode(data)
                else:
                    logging.info('Unsupported message!')
            # else:
            #     logging.debug('Not enough in buffer in order to parse')
        return None

