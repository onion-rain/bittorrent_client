# import aiohttp
# import asyncio

# async def main():

#     async with aiohttp.ClientSession() as session:
#         async with session.get('http://python.org') as response:

#             print("Status:", response.status)
#             print("Content-type:", response.headers['content-type'])

#             html = await response.text()
#             print("Body:", html[:15], "...")

# loop = asyncio.get_event_loop()
# loop.run_until_complete(main())




import threading
import asyncio
import aiohttp

# @asyncio.coroutine
async def hello():
        print('Hello world! (%s)' % threading.currentThread())
        # 异步调用asyncio.sleep(1):
        r = await asyncio.sleep(1)
        print('Hello again! (%s)' % threading.currentThread())

async def wget(host):
        print('wget %s...' % host)
        connect = asyncio.open_connection(host, 80)
        reader, writer = await connect
        header = 'GET / HTTP/1.0\r\nHost: %s\r\n\r\n' % host
        writer.write(header.encode('utf-8'))
        await writer.drain()
        while True:
            line = await reader.readline()
            if line == b'\r\n':
                break
            print('%s header > %s' % (host, line.decode('utf-8').rstrip()))
        # Ignore the body, close the socket
        writer.close()

async def wget_aiohttp(host):
    async with aiohttp.ClientSession() as session:
        print('wget %s...' % host)
        async with session.get(host) as response:

            print("Status:", response.status)
            print("Content-type:", response.headers['content-type'])

            html = await response.text()
            print("Body:", html[:15], "...")

async def fetch(client,url):
    async with client.get(url) as resp:
        assert resp.status == 200
        text = await resp.text()
        return len(text)

# urls是包含多个url的列表
async def fetch_all(urls):
    async with aiohttp.ClientSession() as client:
        return await asyncio.gather(*[fetch(client,url) for url in urls])


urls = ['http://www.sina.com.cn', 'http://www.sohu.com', 'http://www.163.com']
# 获取EventLoop:
# tasks = [hello(), hello()]
# tasks = [wget(host) for host in ['www.sina.com.cn', 'www.sohu.com', 'www.163.com']]
tasks = [wget_aiohttp(host) for host in urls]
# 执行coroutine
# loop.run_until_complete(hello())
# loop.run_until_complete(asyncio.wait(tasks))
loop = asyncio.get_event_loop()
results = loop.run_until_complete(fetch_all(urls))
print(results)
print(type(results))
# loop.close()
