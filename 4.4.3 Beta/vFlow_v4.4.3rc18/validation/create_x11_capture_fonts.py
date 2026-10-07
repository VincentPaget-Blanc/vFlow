"""Optional X11 capture fonts for Tk builds without TrueType font support.

Requires installed DejaVu Sans, Pillow, bdftopcf and mkfontdir. Pass an output
directory; use that directory in Xvfb -fp alongside built-ins. This changes
the capture environment only, not app fonts or scientific calculations.
"""
from pathlib import Path
from PIL import Image,ImageFont,ImageDraw
import subprocess,sys
out=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent/'native_capture_fonts'
out.mkdir(parents=True,exist_ok=True)
chars=set(range(32,383))|set(range(0x2000,0x2070))|{0x2192,0x2190,0x2610,0x2611,0x2713,0x2714,0x2715,0x2725,0x25b6,0x25c0,0x25cf,0x2014,0x2212,0x0394,0x03b1}
for size in (13,14,15,16,17,18,19,20,21,23):
 for weight in ('medium','bold'):
  font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if weight=='bold' else '')+'.ttf',size)
  ascent,descent=font.getmetrics();h=ascent+descent
  rows=['STARTFONT 2.1',f'FONT -vflow-DejaVu Sans-{weight}-r-normal--{size}-{round(size*720/100)}-100-100-p-0-iso10646-1',f'SIZE {round(size*72/100)} 100 100',f'FONTBOUNDINGBOX {size*2} {h} 0 {-descent}','STARTPROPERTIES 6','FAMILY_NAME "DejaVu Sans"',f'WEIGHT_NAME "{weight}"',f'FONT_ASCENT {ascent}',f'FONT_DESCENT {descent}','CHARSET_REGISTRY "ISO10646"','CHARSET_ENCODING "1"','ENDPROPERTIES',f'CHARS {len(chars)}']
  for c in sorted(chars):
   ch=chr(c);advance=max(1,round(font.getlength(ch)));w=size*2
   im=Image.new('1',(w,h));ImageDraw.Draw(im).text((0,0),ch,font=font,fill=1)
   box=im.getbbox() or (0,ascent,1,ascent+1);l,t,r,b=box
   bw,bh=r-l,b-t
   rows +=[f'STARTCHAR U{c:04X}',f'ENCODING {c}',f'SWIDTH {round(advance/size*1000)} 0',f'DWIDTH {advance} 0',f'BBX {bw} {bh} {l} {ascent-b}','BITMAP']
   for y in range(t,b):
    bits=''.join('1' if im.getpixel((x,y)) else '0' for x in range(l,r));bits+='0'*((-len(bits))%8)
    rows.append(f'{int(bits,2):0{len(bits)//4}X}')
   rows +=['ENDCHAR']
  rows +=['ENDFONT']
  bdf=out/f'dejavu-{weight}-{size}.bdf';bdf.write_text('\n'.join(rows)+'\n')
  with (out/(bdf.stem+'.pcf')).open('wb') as f:subprocess.run(['bdftopcf',str(bdf)],stdout=f,check=True)
subprocess.run(['mkfontdir',str(out)],check=True)
print(out)
