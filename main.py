import asyncio

# from utils.bencoding import Decoder
from utils.torrent import Torrent
from utils.tracker import Tracker

async def start(tracker):
    response = await tracker.connect(
        first=False,
        uploaded=False,
        downloaded=False
    )

if __name__ == "__main__":
    
    # filename = "data/ubuntu-16.04-desktop-amd64.iso.torrent"
    # filename = "data/ubuntu-16.04.1-server-amd64.iso.torrent"
    # filename = "data/ubuntu-18.04.3-desktop-amd64.iso.torrent"
    filename = "data/ubuntu-19.04-desktop-amd64.iso.torrent"
    # meta_info = open(filename, 'rb')
    # torrent = Decoder(meta_info).decode()
    torrent = Torrent(filename)
    tracker = Tracker(torrent)
    
    # 获取EventLoop:
    loop = asyncio.get_event_loop()
    # 执行coroutine
    loop.run_until_complete(start(tracker))
    loop.close()

    print()