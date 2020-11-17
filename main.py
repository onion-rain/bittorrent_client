import asyncio
import logging

# from utils.bencoding import Decoder
from utils.torrent import Torrent
# from utils.tracker import Tracker
from utils.client import TorrentClient

# async def start(tracker):
#     response = await tracker.connect(
#         first=False,
#         uploaded=False,
#         downloaded=False
#     )
#     print(response)

if __name__ == "__main__":
    # logging.basicConfig(level=logging.NOTSET)
    logging.basicConfig(level=logging.INFO)
    # logging.basicConfig(level=logging.WARNING)
    # logging.basicConfig(level=logging.ERROR)
    # filename = "data/SXSW_2016_Showcasing_Artists_Part1.torrent"
    # filename = "data/ubuntu-16.04-desktop-amd64.iso.torrent"
    # filename = "data/ubuntu-16.04.1-server-amd64.iso.torrent"
    # filename = "data/ubuntu-18.04.3-desktop-amd64.iso.torrent"
    # filename = "data/ubuntu-19.04-desktop-amd64.iso.torrent"
    # filename = "data/xubuntu-18.04.5-desktop-amd64.iso.torrent"
    # filename = "data/test.torrent"
    filename = "data/ubuntu-20.10-desktop-amd64.iso.torrent"
    # meta_info = open(filename, 'rb')
    # torrent = Decoder(meta_info).decode()
    torrent = Torrent(filename)
    # tracker = Tracker(torrent)
    client = TorrentClient(torrent)
    
    # 获取EventLoop:
    loop = asyncio.get_event_loop()
    # 执行coroutine
    task = loop.create_task(client.start())
    loop.run_until_complete(task)
    loop.close()

    print()
