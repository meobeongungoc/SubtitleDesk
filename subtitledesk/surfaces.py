"""Small code-drawn, antialiased surfaces; no image or GUI dependency."""
import base64
import math
import struct
import zlib
import tkinter as tk
from tkinter import font as tkfont


def rgb(value):
    return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))


def mix(a, b, amount):
    return '#' + ''.join(f'{round(x+(y-x)*amount):02x}' for x, y in zip(rgb(a), rgb(b)))


def png(width, height, rgba):
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind+data))
    rows = b''.join(b'\0' + rgba[y*width*4:(y+1)*width*4] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width,height,8,6,0,0,0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def surface(root, width, height, radius, top, bottom, stroke, focus=False):
    """Rounded gradient with a one-pixel lit edge and alpha corners."""
    data = bytearray()
    top_rgb, bottom_rgb, edge = rgb(top), rgb(bottom), rgb(stroke)
    def distance(x, y):
        qx, qy = abs(x-width/2)-(width/2-radius), abs(y-height/2)-(height/2-radius)
        return math.hypot(max(qx,0),max(qy,0)) + min(max(qx,qy),0)-radius
    for y in range(height):
        # The repeatable middle of a ttk nine-slice must be flat.
        t = min(1, y / max(1, 5 if height < 50 else 30))
        fill = tuple(round(a+(b-a)*t) for a,b in zip(top_rgb,bottom_rgb))
        for x in range(width):
            d = distance(x+.5,y+.5)
            alpha = max(0,min(1,.5-d))
            border = max(0,min(1,d+1.5))
            color = tuple(round(a+(b-a)*border) for a,b in zip(fill,edge))
            data.extend((*color,round(alpha*255)))
    return tk.PhotoImage(master=root, data=base64.b64encode(png(width,height,data)))


def install_surfaces(manager):
    """Use native ttk hit testing, labels, focus and keyboard behavior."""
    s, c = manager.style, manager.colors
    unit = max(.8, float(manager.root.tk.call('tk','scaling')) / (96/72))
    p = lambda n: max(1,round(n*unit))
    key = manager.key
    if key not in manager._surfaces:
        images = []
        for variant, base in (('regular',c['control']),('accent',c['accent'])):
            states = []
            for state in ('normal','disabled','pressed','active','focus'):
                color = base
                edge = mix(base,'#ffffff',.19)
                if state == 'disabled': color,edge = c['panel'],c['control']
                if state == 'pressed': color = mix(base,'#000000',.2)
                if state == 'active': color = mix(base,'#ffffff',.10)
                if state == 'focus': edge = mix(c['accent'],'#ffffff',.48)
                img = surface(manager.root,p(24),p(24),p(5),mix(color,'#ffffff',.065),
                              mix(color,'#000000',.12),edge)
                states.append(img)
            images.extend(states)
            element = f'Desk.{key}.{variant}'
            s.element_create(element,'image',states[0],('disabled',states[1]),
                ('pressed',states[2]),('focus',states[4]),('active',states[3]),
                border=p(6), sticky='nsew')
        card = surface(manager.root,p(40),p(100),p(8),mix(c['panel'],'#ffffff',.018),
                       c['panel'],mix(c['control'],'#ffffff',.04))
        images.append(card)
        s.element_create(f'Desk.{key}.card','image',card,border=(p(10),p(42),p(10),p(12)),sticky='nsew')
        for orient in ('Vertical','Horizontal'):
            thumb=surface(manager.root,p(8),p(8),p(4),c['control'],c['control'],c['control'])
            images.append(thumb)
            element=f'Desk.{key}.{orient}.thumb'
            s.element_create(element,'image',thumb,border=p(4),sticky='nsew')
        manager._surfaces[key] = images
    for style,variant in (('TButton','regular'),('Accent.TButton','accent')):
        s.layout(style,[(f'Desk.{key}.{variant}',{'sticky':'nsew','children':[
            ('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]})])
    s.layout('Card.TFrame',[(f'Desk.{key}.card',{'sticky':'nsew'})])
    for orient in ('Vertical','Horizontal'):
        s.layout(orient+'.TScrollbar',[(orient+'.Scrollbar.trough',{'sticky':'ns' if orient=='Vertical' else 'ew',
            'children':[(f'Desk.{key}.{orient}.thumb',{'sticky':'nsew','expand':1})]})])
        s.configure(orient+'.TScrollbar',borderwidth=0,arrowsize=p(8),troughcolor=c['panel'])
    s.layout('Treeview',[('Treeview.treearea',{'sticky':'nsew'})])
    s.layout('Treeview.Heading',[('Treeheading.padding',{'sticky':'nsew','children':[
        ('Treeheading.text',{'sticky':'we'})]})])
    line = tkfont.Font(root=manager.root,font=(manager.font_family,10)).metrics('linespace')
    s.configure('Treeview',rowheight=max(p(25),line+p(6)))
    s.configure('TPanedwindow',sashwidth=p(8))
    return unit

def icon(root, name, color='#e3eaf3', size=16):
    """Tiny monochrome line icons, drawn from code at the current UI scale."""
    shapes = {
        'folder': [(2,5,7,5),(7,5,9,7),(9,7,14,7),(14,7,14,13),(14,13,2,13),(2,13,2,5),(2,9,14,9)],
        'search': [(10.5,10.5,14,14)],
        'close': [(4,4,12,12),(4,12,12,4)],
        'refresh': [(12,3,13,7),(13,7,9,7),(4,13,3,9),(3,9,7,9)],
        'play': [(5,3,13,8),(13,8,5,13),(5,13,5,3)],
        'download': [(8,2,8,10),(4,7,8,11),(8,11,12,7),(3,11,3,14),(3,14,13,14),(13,14,13,11)],
        'film': [(2,2,14,2),(14,2,14,14),(14,14,2,14),(2,14,2,2),(5,2,5,14),(11,2,11,14),(2,6,5,6),(2,10,5,10),(11,6,14,6),(11,10,14,10)],
        'cloud': [(3,12,13,12),(3,12,1,10),(1,10,3,7),(3,7,5,7),(11,7,13,7),(13,7,15,10),(15,10,13,12)],
        'settings': [(8,1,8,3),(8,13,8,15),(1,8,3,8),(13,8,15,8),(3,3,4,4),(12,12,13,13),(3,13,4,12),(12,4,13,3)],
        'appearance': [(2,2,14,2),(14,2,14,14),(14,14,2,14),(2,14,2,2),(8,2,8,14),(8,8,14,8)],
        'edit': [(3,10,10,3),(10,3,13,6),(13,6,6,13),(6,13,2,14),(2,14,3,10)],
    }
    circles = {'search': [(7,7,4.5)], 'refresh':[(8,8,5)],
               'settings':[(8,8,4),(8,8,1)], 'cloud':[(8,6,3)]}
    segments=shapes.get(name,[])
    ink=rgb(color);data=bytearray()
    for y in range(size):
        for x in range(size):
            px,py=(x+.5)*16/size,(y+.5)*16/size
            distance=99
            for ax,ay,bx,by in segments:
                dx,dy=bx-ax,by-ay
                t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
                distance=min(distance,math.hypot(px-ax-t*dx,py-ay-t*dy))
            for cx,cy,radius in circles.get(name,[]):
                distance=min(distance,abs(math.hypot(px-cx,py-cy)-radius))
            alpha=max(0,min(1,(1.05-distance)*size/16))
            data.extend((*ink,round(255*alpha)))
    return tk.PhotoImage(master=root,data=base64.b64encode(png(size,size,data)))
