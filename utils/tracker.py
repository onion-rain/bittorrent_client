import aiohttp
import logging
import socket

from urllib.parse import urlencode

from .misc import calculate_peer_id, decode_port
from .bencoding import Decoder


class TrackerResponse:
    """
    The response from the tracker after a successful connection to the
    trackers announce URL.

    Even though the connection was successful from a network point of view,
    the tracker might have returned an error (stated in the `failure`
    property).
    """

    def __init__(self, response: dict):
        self.response = response

    @property
    def failure(self):
        """
        If this response was a failed response, this is the error message to
        why the tracker request failed.

        If no error occurred this will be None
        """
        if b'failure reason' in self.response:
            return self.response[b'failure reason'].decode('utf-8')
        return None

    @property
    def interval(self) -> int:
        """
        Interval in seconds that the client should wait between sending
        periodic requests to the tracker.
        """
        return self.response.get(b'interval', 0)

    @property
    def complete(self) -> int:
        """
        Number of peers with the entire file, i.e. seeders.
        """
        return self.response.get(b'complete', 0)

    @property
    def incomplete(self) -> int:
        """
        Number of non-seeder peers, aka "leechers".
        """
        return self.response.get(b'incomplete', 0)

    @property
    def peers(self):
        """
        A list of tuples for each peer structured as (ip, port)
        """
        # The BitTorrent specification specifies two types of responses. One
        # where the peers field is a list of dictionaries and one where all
        # the peers are encoded in a single string
        peers = self.response[b'peers']
        if type(peers) == list:
            # TODO Implement support for dictionary peer list
            logging.debug('Dictionary model peers are returned by tracker')
            raise NotImplementedError()
        else:
            logging.debug('Binary model peers are returned by tracker')

            # Split the string in pieces of length 6 bytes, where the first
            # 4 characters is the IP the last 2 is the TCP port.
            peers = [peers[i:i+6] for i in range(0, len(peers), 6)]

            # Convert the encoded address to a list of tuples
            return [(socket.inet_ntoa(p[:4]), decode_port(p[4:])) for p in peers]

    def __str__(self):
        return "incomplete: {incomplete}\n" \
               "complete: {complete}\n" \
               "interval: {interval}\n" \
               "peers: {peers}\n".format(
                   incomplete=self.incomplete,
                   complete=self.complete,
                   interval=self.interval,
                   peers=", ".join([x for (x, _) in self.peers])
                )


class Tracker:
    def __init__(self, torrent):
        self.torrent = torrent
        self.peer_id = calculate_peer_id()
        self.http_client = aiohttp.ClientSession()

    async def connect(self,
                      first: bool = None,
                      uploaded: int = 0,
                      downloaded: int = 0):
        """
        Makes the announce call to the tracker to update with our statistics
        as well as get a list of available peers to connect to.

        If the call was successful, the list of peers will be updated as a
        result of calling this function.

        :param first: Whether or not this is the first announce call
        :param uploaded: The total number of bytes uploaded
        :param downloaded: The total number of bytes downloaded
        """
        # params = {
        #     'info_hash': self.torrent.info_hash,
        #     'peer_id': self.peer_id,
        #     'port': 6881,
        #     'uploaded': uploaded,
        #     'downloaded': downloaded,
        #     'left': self.torrent.total_size - downloaded,
        #     'compact': 1,
        #     # 'no_peer_id': '0',
        #     # 'event': 'started'
        # }
        params = {
            # 'info_hash': b'\x12\x34\x56\x78\x9a\xbc\xde\xf1\x23\x45\x67\x89\xab\xcd\xef\x12\x34\x56\x78\x9a',
            'info_hash': self.torrent.info_hash,
            'peer_id': self.peer_id,
            'port': 6889,
            'uploaded': 0,
            'downloaded': 0,
            'left': 0,
            'compact': 1
        }
        if first:
            params['event'] = 'started'

        # url = self.torrent.announce + '?' + urlencode(params)
        url = 'http://tracker.opentrackr.org:1337/announce' + '?' + urlencode(params)
        logging.info('Connecting to tracker at: ' + url)

        async with self.http_client.get(url) as response:
            if not response.status == 200:
                raise ConnectionError('Unable to connect to tracker: status code {}'.format(response.status))
            data = await response.read()
            self.raise_for_error(data)
            return TrackerResponse(Decoder(data).decode())

    def close(self):
        self.http_client.close()

    def raise_for_error(self, tracker_response):
        """
        A (hacky) fix to detect errors by tracker even when the response has a status code of 200
        """
        try:
            # a tracker response containing an error will have a utf-8 message only.
            # see: https://wiki.theory.org/index.php/BitTorrentSpecification#Tracker_Response
            message = tracker_response.decode("utf-8")
            if "failure" in message:
                raise ConnectionError('Unable to connect to tracker: {}'.format(message))

        # a successful tracker response will have non-uncicode data, so it's a safe to bet ignore this exception.
        except UnicodeDecodeError:
            pass