'''
Created on 2012-9-30

@author: ddt
'''
class DataEncodedError(BaseException):
    def __str__(self):
        return 'Data Encoded Error'

class DataTypeError(BaseException):
    def __str__(self):
        return 'Data Type Error'
    
def bdecode(data):
    try:
        leading_chr = data[0:1]
        #print leading_chr,                 
        if leading_chr.isdigit():
            chunk, length = _read_string(data)
            #print chunk
        elif leading_chr == b'd':
            chunk, length = _read_dict(data)
            #print chunk is None
        elif leading_chr == b'i':
            chunk, length = _read_integer(data)
            #print chunk
        elif leading_chr == b'l':
            chunk, length = _read_list(data)
        else:
            raise DataEncodedError()
        return chunk, length
    except:
        raise DataEncodedError()
    
                           
def _read_dict(data):
    chunk = {} 
    length = 1
    
    while data[length] != 'e':
        key, key_len = bdecode(data[length:])
        length += key_len
        
        value, value_len = bdecode(data[length:])
        length += value_len
        
        chunk[key] = value
        #print key
        
    length += 1
    return chunk, length

def _read_list(data):
    chunk = []
    length = 1
    while data[length] != 'e':
        value, value_len = bdecode(data[length:])
        chunk.append(value)
        length += value_len  
        
    length += 1
    return chunk, length

def _read_string(data):
    comm_index = data.find(':')
    str_len = int(data[:comm_index])
    value = data[comm_index+1:comm_index+1+str_len]
    
    length = comm_index + 1 + str_len
    return ''.join(value), length

def _read_integer(data):

    end_index = data.find('e')
    value = int(data[1:end_index])
    length = end_index + 1
    
    return  value, length

def bencode(data):
    data_type = type(data)
    if data_type == type({}):
        result = _write_dict(data)
    elif data_type == type([]):
        result = _write_list(data)
    elif data_type == type(''):
        result = _write_string(data)
    elif data_type == type(int(0)):
        result = _write_integer(data)
    else:
        raise DataTypeError()
    return result

def _write_dict(data):
    result = 'd'
    for key, value in data.items():
        key_encode = bencode(key)
        value_encode = bencode(value)
        result += key_encode
        result += value_encode

    result += 'e'
    return result

def _write_list(data):
    result = 'l'
    for value in data:
        value_encode = bencode(value)
        result += value_encode
        
    result += 'e'
    return result

def _write_string(data):
    return '%d:%s' %(len(data), data)

def _write_integer(data):
    return 'i%de' %data
 
