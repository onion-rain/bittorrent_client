from datetime import datetime
import bcodec
import hashlib

from bencoding import Decoder

_READ_MAX_LEN = -1

class BTFormatError(BaseException):
    def __str__(self):
        return 'Torrent File Format Error'

class TorrentFile(object):
    
    def __init__(self):    
        self.__metainfo = {}
        self.__file_name = ''
        self.__bencode_data = None
    
    def read_file(self, filename):
        
        torrent_file = open(filename, 'rb')
        data = torrent_file.read(_READ_MAX_LEN)
        torrent_file.close()
        
        try:
            # metainfo, length = bcodec.bdecode(data)
            metainfo = Decoder(data).decode()
            # print(data)
            # print()
            # print(metainfo)
            self.__file_name = filename
            self.__metainfo = metainfo
            self.__bencode_data = data
        except:
            raise BTFormatError()

    def __is_singlefile(self):

        return self.__get_meta_info('length') != None

    def __decode_text(self, text):
        encoding = 'utf-8'
        resultstr = ''
        if self.get_encoding() != None:
            encoding = self.get_encoding()
        elif self.get_codepage() != None:
            encoding = 'cp' + str(self.get_codepage())
        if text:
            try:
                resultstr = text.decode(encoding=encoding)
            except ValueError:
                return text
        else:
            return None
        return resultstr
    
    def __get_meta_top(self, key):
        if key in self.__metainfo.keys():
            return self.__metainfo[key]
        else:
            return None
    def __get_meta_info(self,key):
        meta_info = self.__get_meta_top('info')
        if meta_info != None and key in meta_info.keys():
                return meta_info[key]
        return None
    
    def get_codepage(self):
        return self.__get_meta_top('codepage')
    def get_encoding(self):
        return self.__get_meta_top('encoding')
    
    def get_announces(self):
        announces = self.__get_meta_top('announce-list')
        if announces != None:
            return announces
        
        announces = [[]]
        ann = self.__get_meta_top('announce')
        if ann:
            announces[0].append(ann)
        return announces
    
    def get_publisher(self):
        return self.__decode_text(self.__get_meta_top('publisher'))
    def get_publisher_url(self):
        return self.__decode_text(self.__get_meta_top('publisher-url'))
    
    def get_creater(self):
        return self.__decode_text(self.__get_meta_top('created by'))
    def get_creation_date(self):
        utc_date = self.__get_meta_top('creation date')
        if utc_date == None:
            return utc_date
        creationdate = datetime.utcfromtimestamp(utc_date)
        return creationdate
    def get_comment(self):
        return self.__get_meta_top('comment')
          
    def get_nodes(self):
        return self.__get_meta_top('nodes')
    
    def get_piece_length(self):
        return self.__get_meta_info('piece length')
    
    def get_piece(self, index):
        pieces = self.__get_meta_info('pieces')
        if pieces == None:
            return None
        
        offset = index*20
        if offset+20 > len(pieces):
            return None
        return pieces[offset:offset+20]

    def get_pieces_num(self):
        return len(self.__get_meta_info('pieces'))/20

    def get_files(self):

        files = []
        name = self.__decode_text(self.__get_meta_info('name'))
        piece_length = self.get_piece_length()
        if name == None:
            return files

        if self.__is_singlefile():
            file_name = name
            file_length = self.__get_meta_info('length')
            if not file_length:
                return files

            pieces_num = file_length/piece_length
            last_piece_offset =  file_length % piece_length
            if last_piece_offset != 0:
                pieces_num = int(pieces_num) + 1
                last_piece_offset -= 1
            else:
                last_piece_offset = piece_length - 1

            first_piece_offset = 0

            files.append({'name':[file_name], 'length':file_length, 'first-piece':(0, first_piece_offset), 'last-piece':(pieces_num-1,last_piece_offset)})
            return files

        folder = name
        meta_files = self.__get_meta_info('files')
        if meta_files == None:
            return files

        total_length = int(0)
        for one_file in self.__get_meta_info('files'):

            file_info = {}
            path_list = []
            path_list.append(folder)

            if 'path' not in one_file.keys():
                break
            for path in one_file['path']:
                path_list.append(self.__decode_text(path))
            file_info['name'] = path_list

            if 'length' not in one_file.keys():
                break

            file_info['length'] =  one_file['length']

            piece_index = total_length / piece_length
            first_piece_offset =  total_length % piece_length
            
            total_length += one_file['length']
            pieces_num = total_length / piece_length - piece_index
            last_piece_offset = total_length % piece_length
            
            if last_piece_offset != 0:
                pieces_num += 1
                last_piece_offset -= 1
            else:
                last_piece_offset = piece_length - 1
            
            file_info['first-piece'] = (piece_index,first_piece_offset)
            file_info['last-piece'] = ((piece_index+pieces_num-1),last_piece_offset)
            files.append(file_info)
        return files
    
    def get_info_hash(self):
        info_index = self.__bencode_data.find('4:info')
        info_data_index = info_index+len('4:info')
        
        info_value, info_data_len = bcodec.bdecode(self.__bencode_data[info_data_index:])
        info_data = self.__bencode_data[info_data_index:info_data_index+info_data_len]
        
        info_hash = hashlib.sha1()
        info_hash.update(info_data)
        return info_hash.digest()


if __name__ == '__main__':
    # filename = r".\narodo.torrent"
    # filename = "data/ubuntu-16.04-desktop-amd64.iso.torrent"
    filename = "data/ubuntu-18.04.3-desktop-amd64.iso.torrent"
    

    torrent = TorrentFile()

    print("begin to read file")
    torrent.read_file(filename)

    print("end to read file")

    print("announces: " , torrent.get_announces() )
    print("info_hash: ", list(torrent.get_info_hash()))
    print("peace length:", torrent.get_piece_length())
    print("code page:" , torrent.get_codepage())
    print("encoding:" , torrent.get_encoding())
    print("publisher:" ,torrent.get_publisher())
    print("publisher url:", torrent.get_publisher_url())
    print("creater:" , torrent.get_creater())
    print("creation date:", torrent.get_creation_date())
    print("commnent:", torrent.get_comment())
    print("nodes:", torrent.get_nodes())
    torrent.get_files()
    for one_file in torrent.get_files():
        print('name:', '\\'.join(one_file['name']))
        print('length:', one_file['length'])
        print('first-piece:', one_file['first-piece'])
        print('last-piece:', one_file['last-piece'])