import aiohttp
from urllib.parse import urlencode
from .misc import calculate_peer_id

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

        url = self.torrent.announce + '?' + urlencode(params)
        # logging.info('Connecting to tracker at: ' + url)

        async with self.http_client.get(url) as response:
            if not response.status == 200:
                raise ConnectionError('Unable to connect to tracker: status code {}'.format(response.status))
            data = await response.read()
            self.raise_for_error(data)
            # return TrackerResponse(bencoding.Decoder(data).decode())

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