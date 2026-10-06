"""Independent stdlib encoding of binary numeric list-mode truth fixtures.

Synthetic fixtures are explicitly not vendor-acquisition acceptance evidence.
"""
import struct
import binascii
from pathlib import Path

def write_fixture(path,version='FCS3.2',endian='<',rows=None,types=('I','F','D'),bits=(64,32,64),names=('Index','Fluorescence','Distance'),crc=False,extra=None):
    rows=rows or [(9007199254740993,1.25,2.5),(9007199254740995,-3.5,4.125),(9007199254740997,2.,8.25)]
    meta={'$CYT':'Beckman Cytomics FC500 synthetic fixture','$MODE':'L','$DATATYPE':types[0],'$PAR':str(len(types)),'$TOT':str(len(rows)),
        '$BYTEORD':'1,2,3,4' if endian=='<' else '4,3,2,1','$BEGINANALYSIS':'0','$ENDANALYSIS':'0',
        '$BEGINSTEXT':'0','$ENDSTEXT':'0','$NEXTDATA':'0'}
    for i,(t,w,name) in enumerate(zip(types,bits,names),1):
        meta.update({f'$P{i}B':str(w),f'$P{i}N':name,f'$P{i}R':str(2**w) if t=='I' else '262144.5',f'$P{i}E':'0,0'})
        if version=='FCS3.2':meta[f'$P{i}DATATYPE']=t
    meta.update(extra or {})
    codes={'I':{8:'B',16:'H',32:'I',64:'Q'},'F':{32:'f'},'D':{64:'d'}}
    payload=b''.join(struct.pack(endian+''.join(codes[t][w] for t,w in zip(types,bits)),*row) for row in rows)
    begin=end=0
    for _ in range(25):
        meta['$BEGINDATA']=str(begin);meta['$ENDDATA']=str(end)
        text=('|'+ '|'.join(x for kv in meta.items() for x in kv)+'|').encode()
        nb=58+len(text);ne=nb+len(payload)-1
        if (nb,ne)==(begin,end):break
        begin,end=nb,ne
    header=f'{version}    {58:>8}{58+len(text)-1:>8}{begin:>8}{end:>8}{0:>8}{0:>8}'.encode()
    data=header+text+payload
    if crc:data+=f'{kermit(data):08X}'.encode()
    Path(path).write_bytes(data);return Path(path),rows

def kermit(data):
    # Independent bit implementation used only by synthetic integrity fixture.
    crc=0
    for b in data:
        for bit in range(8):
            carry=(crc ^ (b>>bit)) & 1;crc >>= 1
            if carry:crc ^= 0x8408
    return crc
