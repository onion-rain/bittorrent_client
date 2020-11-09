# 分布式系统大作业 - Bittorrent客户端

目标：

1、实现一个简易的Bittorrent客户端

2、实现对.torrent文件的解析

3、实现与Tracker交互获得peer的IP和端口

4、实现从peer获取pieces，可不实现unchoking激励机制，piece选择策略可选用简单的随机或者顺序策略

5、编写测试程序，进行测试验证

## 参考

[github](https://github.com/eliasson/pieces), [blog](https://markuseliasson.se/article/bittorrent-in-python/)

## bencoding编码

![bencoding字典主键](readme/bencoding字典主键.jpg)

单文件的torrent文件info字段

![bencoding字典主键](readme/info_single_file.jpg)

多文件的torrent文件info字段中的Length变成files dict

![bencoding字典主键](readme/multi_files_Length变成files.jpg)


## 程序结构

### Torrent类

打开.torrent文件，解析出文件meta_info、info_hash

### TrackerResponse类

包装一下tracker的response信息，便于使用

### Tracker类

根据.torrent文件中的和tracker服务器沟通获取peers的ip和port以及interval等信息

### PieceManager类

主要存储missing_pieces、ongoing_pieces、pending_blocks、have_pieces

并由此确定下一个block(文件分解为pieces，pieces分解为blocks)下载什么

### PeerMessage类

peer connection要用到固定message格式基类，

其子类包括Handshake, Interested, BitField, NotInterested, Choke, Unchoke, Have, KeepAlive, Piece, Request, Cancel

### PeerConnection类

先从available_peers中get一个peer

根据PieceManager的决策向peer服务器请求指定pieces(blocks)

如果这个peer连接出错就关闭连接再从从available_peers中get一个peer

### TorrentClient类

通过创建Tracker实例获取available_peers放到available_peers(asyncio.Queue)里，并根据tracker反馈的interval进行刷新

根据available_peers创建多个PeerConnection实例多协程下载
