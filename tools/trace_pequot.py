#!/usr/bin/env python3
"""Trace Levels 1 and 2 of the Mashantucket Pequot Museum from its own guide map (run once: python3 tools/trace_pequot.py).

    tools/data/pequot-trace.json   rooms (polygons), doorways and label points of Levels 1 and 2, in the map's units

The map: "Museum Property Guide Map" (pequotmuseum.org/wp-content/uploads/FOX_100075-1_Jul2023_MuseumProperty_GuideMap_8-5x14-1.pdf,
July 2023), page 1. Each level is drawn in its own colour (Level 3 blue, Level 2 gold, Level 1 brown) as vector lines.
The page is rendered at 220 dpi; every pixel of a level's colour is a wall. The building is everything inside the outer
wall (a few gaps where doors and exits are drawn open are closed by hand: GAPS). Each room grows from a seed point
(SEEDS, where the room's name or number is on the map) until it meets walls or another room (watershed), so rooms
follow the drawn walls; where the map draws no wall between two exhibits, the line between them is a guess.
Map units: pixels of the page at 110 dpi (half the 220 dpi render). Level 3 has few inner walls and is drawn by hand in
build_pequot.py. Needs opencv-python-headless and numpy (only for this step).
"""
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'pequot'
PDF = CACHE / 'FOX_100075-1_Jul2023_MuseumProperty_GuideMap_8-5x14-1.pdf'
URL = 'https://www.pequotmuseum.org/wp-content/uploads/FOX_100075-1_Jul2023_MuseumProperty_GuideMap_8-5x14-1.pdf'
OUT = ROOT / 'tools' / 'data' / 'pequot-trace.json'
DEBUG = False
# level: (wall colour in BGR, crop of the page in map units)
LV = {'2': ((2, 135, 168), (240, 740, 820, 1050)), '1': ((95, 121, 169), (100, 1050, 860, 1370))}
K = {'1': 41, '2': 41}
# level: [room, kind, x, y]: where each room starts growing
SEEDS = {"2": [["The Glacier", "gallery", 765, 930], ["Auditorium", "space", 635, 955], ["Auditorium Lobby", "corridor", 548, 1000], ["Overlook Case", "closed", 528, 920], ["Mashantucket Gallery", "gallery", 425, 995], ["Lower Hall", "corridor", 465, 953], ["Village Overlook", "corridor", 500, 860], ["Escalator Hall", "corridor", 445, 812], ["Fort Theater", "closed", 377, 865], ["Recognition Theater", "closed", 455, 890], ["Life on the Reservation", "gallery", 340, 815], ["The Changing Reservation", "gallery", 292, 885], ["Tribal Portrait Gallery", "gallery", 300, 948], ["Meeting House Mini-Theater", "space", 312, 872], ["Federal Recognition Theater", "gallery", 365, 925], ["Ramp to Level 3", "corridor", 665, 880], ["Exhibit Entrance", "gallery", 700, 915], ["Ramp Lobby", "corridor", 588, 942]], "1": [["Life in a Cold Climate", "gallery", 780, 1325], ["World of Ice", "gallery", 715, 1290], ["Tool Theater", "gallery", 642, 1262], ["Four Seasons", "gallery", 640, 1200], ["Pequot Village", "gallery", 450, 1175], ["Palisaded Fort", "gallery", 340, 1105], ["Clash of Cultures", "gallery", 200, 1180], ["War Theater 1", "gallery", 230, 1255], ["War Theater 2", "gallery", 320, 1290], ["Pequot Daily Life Gallery", "gallery", 575, 1200], ["Pequot Society Gallery", "gallery", 450, 1250], ["South Hall", "corridor", 460, 1285]]}
# lines that close the outer wall where the map leaves it open (exits, doors)
GAPS = {"1": [[762.5, 1240, 778, 1242], [797, 1243, 806, 1252.5], [673.5, 1329.5, 675, 1343.5], [590.5, 1151.5, 597, 1154.5], [525, 1124, 544, 1134], [793, 1340, 802, 1348], [795, 1241, 808, 1254], [725, 1222.5, 762.5, 1240], [762.5, 1240, 797, 1243], [797, 1243, 810, 1255]], "2": [[311.5, 804, 317.5, 792.5], [352.5, 785, 365, 776], [365, 776, 390, 756], [436.5, 765, 455, 815], [455, 815, 480, 840]]}
# map labels drawn just outside the walls, cut away
TEXT = {"1": [[655, 1165, 745, 1190], [605, 1328, 673, 1345], [305, 1318, 335, 1352]]}


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    if not PDF.exists():
        subprocess.run(['curl', '-s', '-f', '-L', '-o', str(PDF), URL], check=True)
    png = CACHE / 'map-220.png'
    if not png.exists():
        subprocess.run(['pdftoppm', '-r', '220', '-f', '1', '-l', '1', '-png', '-singlefile', str(PDF), str(png)[:-4]], check=True)
    im = cv2.imread(str(png))
    out = {}
    for lv,(bgr,(x0,y0,x1,y1)) in [(k, LV[k]) for k in ('1', '2')]:
        c = im[y0*2:y1*2, x0*2:x1*2].astype(int)
        wall = (np.sqrt(((c - np.array(bgr))**2).sum(2)) < 60).astype(np.uint8)
        h,w = wall.shape
        shell = wall.copy()
        for (ax,ay,bx,by) in GAPS.get(lv,[]):
            cv2.line(shell,(int((ax-x0)*2),int((ay-y0)*2)),(int((bx-x0)*2),int((by-y0)*2)),1,3)
        P=60
        padded = cv2.copyMakeBorder(shell,P,P,P,P,cv2.BORDER_CONSTANT,value=0)
        closed = cv2.morphologyEx(padded, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(K[lv],K[lv])))
        ff = closed.copy()*255; mask = np.zeros((h+2*P+2,w+2*P+2),np.uint8)
        cv2.floodFill(ff, mask, (0,0), 128)
        inside = (ff[P:-P,P:-P] != 128).astype(np.uint8)          # building incl. walls
        # thin callout lines and labels drawn against the walls are not rooms
        inside = cv2.morphologyEx(inside, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(25,25)))
        for t in TEXT.get(lv, []):
            cv2.rectangle(inside,(int((t[0]-x0)*2),int((t[1]-y0)*2)),(int((t[2]-x0)*2),int((t[3]-y0)*2)),0,-1)
        markers = np.zeros((h,w),np.int32)
        markers[inside==0] = 1                          # outside
        names = ['__outside__']
        for i,(name,kind,x,y) in enumerate(SEEDS[lv]):
            px,py = int((x-x0)*2), int((y-y0)*2)
            cv2.circle(markers,(px,py),4,i+2,-1)
            names.append(name)
        # watershed image: walls dark
        img = np.full((h,w,3),255,np.uint8); img[wall>0] = 0
        img = cv2.GaussianBlur(img,(5,5),0)
        cv2.watershed(img, markers)
        lab = np.where(markers>1, markers, 0).astype(np.uint16)
        for _ in range(200):
            need = (inside==1) & (lab==0)
            if not need.any(): break
            dil = cv2.dilate(lab, np.ones((3,3),np.uint8))
            lab[need] = dil[need]
        markers = np.where(inside==1, lab, 1).astype(np.int32)
        # visual
        vis = (c.astype(np.uint8)//2+127)
        rng = np.random.default_rng(1)
        cols = rng.integers(60,230,(len(names)+2,3))
        ov = vis.copy()
        for i in range(2,len(names)+1):
            ov[markers==i] = cols[i]
        vis = cv2.addWeighted(vis,0.45,ov.astype(np.uint8),0.55,0)
        vis[wall>0]=(0,0,0)
        polys = {}
        for i,(name,kind,x,y) in enumerate(SEEDS[lv]):
            m = (markers==i+2).astype(np.uint8)
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5,5),np.uint8))
            cs,_ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cs: print('missing',lv,name); continue
            cmax = max(cs,key=cv2.contourArea)
            ap = cv2.approxPolyDP(cmax, 3.0, True)[:,0,:]
            polys[name] = [[round(x0+p[0]/2,1), round(y0+p[1]/2,1)] for p in ap]
            cv2.polylines(vis,[ap],True,(0,0,255),1)
            cv2.putText(vis,name[:22],(int((x-x0)*2)-30,int((y-y0)*2)),cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,0,0),1)
        # adjacency: pixels where label a and b both appear in 3x3 window, excluding walls
        adj = {}
        lab = markers.copy()
        for dy,dx in [(0,4),(4,0),(4,4),(4,-4)]:
            a = lab[max(0,-dy):h-max(0,dy), max(0,-dx):w-max(0,dx)]
            b = lab[max(0,dy):, max(0,dx):][:a.shape[0],:a.shape[1]]
            ok = (a>1)&(b>1)&(a!=b)
            ys,xs = np.nonzero(ok)
            for yy,xx in zip(ys,xs):
                k = tuple(sorted((int(a[yy,xx]),int(b[yy,xx]))))
                adj.setdefault(k,[]).append((xx,yy))
        doors = []
        for (i,j),pts in adj.items():
            # door position: only the stretch not on a wall
            pts = [p for p in pts if wall[min(h-1,p[1]),min(w-1,p[0])]==0]
            if len(pts) < 10: continue
            pts = np.array(pts); mx,my = pts.mean(0)
            # choose the pt nearest the mean
            k = ((pts-[mx,my])**2).sum(1).argmin(); px,py = pts[k]
            doors.append([names[i-1], names[j-1], round(x0+px/2,1), round(y0+py/2,1), len(pts)])
            cv2.circle(vis,(int(px),int(py)),5,(0,200,0),-1)
        if DEBUG: cv2.imwrite(str(CACHE / f'trace{lv}.png'), vis)
        out[lv] = {'polys': polys, 'doors': doors, 'seeds': {name: [x, y] for name, kind, x, y in SEEDS[lv]}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0))
    for lv in out:
        print(lv, len(out[lv]['polys']), 'rooms', len(out[lv]['doors']), 'doorways')


if __name__ == '__main__':
    main()
