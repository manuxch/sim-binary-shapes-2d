#!/usr/bin/env python
import networkx as nx
from math import sqrt
import numpy as np
import argparse


class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return '({:.3f}, {:.3f})'.format(self.x, self.y)


class Grano:
    def __init__(self, id, center):
        self.id = id
        self.center = center
        self.contacts = []

    def __repr__(self):
        s = str(self.id) + ' ' + str(self.center) + '['
        for c in self.contacts:
            s += ' ' + str(c)
        s += ' ]'
        return(s)


def distG(a, b):
    d = sqrt((a.center.x - b.center.x)**2 + (a.center.y - b.center.y)**2)
    return d


def getArco(l, granos, rd):
    xLeft = 1000.0
    xRight = -1000.0
    iL = -1
    iR = -1
    O = Grano(-1000, Point(0.0, 0.0))
    dist2 = 0.0
    for g in l:
        dist2 += distG(granos[g], O)

    iR = iL = 0
    distX = 1000
    for g in l:
        if abs(granos[g].center.x) < distX:
            distX = abs(granos[g].center.x)
            iL = iR = l.index(g)
    limZ = limD = False
    while not (limZ and limD):
        if iL == 0:
            limZ = True
        if iR == len(l) - 1:
            limD = True
        if (not limZ):
            if granos[l[iL - 1]].center.y > granos[l[iL]].center.y:
                iL = iL - 1
                continue
            if granos[l[iL - 1]].center.x < granos[l[iL]].center.x:
                iL = iL -1
            else:
                limZ = True
        if (not limD):
            if granos[l[iR + 1]].center.y > granos[l[iR]].center.y:
                iR = iR + 1
                continue
            if granos[l[iR + 1]].center.x > granos[l[iR]].center.x:
                iR = iR + 1
            else:
                limD = True
    arcoL = l[iL:iR+1]
    return arcoL, dist2

parser = argparse.ArgumentParser(description='Programa para graficar arcos.')
parser.add_argument('-f', '--iFile', help='Input file', required=True, action="store", type=str)
args = parser.parse_args()
ifi = args.iFile
fin = open(ifi, 'r')
data = fin.readlines()
fin.close()


granos = {}
gWall = []
maxR = 0.0
for linea in data[2:-1]:
    l = linea.split()
    gid = int(l[0])
    if gid < 0:
        bverts = []
        nv = int(l[1])
        for i in range(nv):
            bverts.append([float(l[2+2*i]), float(l[2+2*i+1])])
        continue
    nvert = int(l[1])
    granos[gid] = Grano(gid, Point(float(l[2]), float(l[3])))
    conts = []
    verts = []
    if nvert > 1:
        for i in range(nvert):
            verts.append([float(l[4+2*i]), float(l[4+2*i+1])])
        dcv = sqrt((float(l[2]) - verts[0][0])**2 + (float(l[3]) - verts[0][1])**2)
        if dcv > maxR:
            maxR = dcv
        for c in l[4+2*nvert:]:
            conts.append(int(c))
            if int(c) < 0:
                gWall.append(gid)
    else:
        radio = float(l[4][:3])
        if radio > maxR:
            maxR = radio
        if len(l[4][3:]) > 0 and int(l[4][3:]) > 0:
            conts.append(int(l[4][3:]))
        for c in l[5:]:
            conts.append(int(c))
            if int(c) < 0:
                gWall.append(gid)
    granos[gid].contacts = conts
rD = float((data[-2].split())[2])
# print '# Radio descarga:', rD

G = nx.Graph()
G.add_nodes_from(granos.keys())
for n in G.nodes():
    if n < 0:
        print('Nodo', n)
        continue
    punto_x = granos[n].center.x
    punto_y = granos[n].center.y
    G.node[n]['pos'] = (punto_x, punto_y)
    for c in granos[n].contacts:
        if c < 0:
            continue
        G.add_edge(n, c)
        xfin = granos[c].center.x
        yfin = granos[c].center.y
nleft = []  # Lista de nodos a la izquierda (sobre el piso)
nright = []  # Lista de nodos a la derecha (sobre el piso)
maxR = 2 * maxR
for n in G.nodes():
    if n < 0:
        print '# Nodo negativo!'
        continue
    if G.node[n]['pos'][1] > maxR:
        continue
    if -10 in granos[n].contacts or -20 in granos[n].contacts:
        if G.node[n]['pos'][0] > 0.0:
            nright.append(n)
        else:
            nleft.append(n)
# print 'R', nright, len(nright)
# print 'L', nleft, len(nleft)
minL = 100000
giMinL = -100
gdMinL = -200
dGBase = 1.0E8
spl = []
distO = 0.0
arcoL = []
for l in nleft:
    for r in nright:
        if nx.has_path(G, l, r):
            dg = distG(granos[l], granos[r])
            spList = nx.all_shortest_paths(G, l, r)
            for a in spList:
                if len(a) < minL:
                    spl = a
                    dGBase = dg
                    minL = len(a)
                    arcoL, distO = getArco(a, granos, rD)
                    continue
                if len(a) == minL and dg < dGBase:
                    spl = a
                    dGBase = dg
                    arcoL, distO = getArco(a, granos, rD)
                if len(a) == minL and abs(dg - dGBase) < 1.0E-8:
                    aTmp, dTmp = getArco(a, granos, rD)
                    if dTmp < distO:
                        arcoL = aTmp
                        distO = dTmp

# print('Arco:', minL, arcoL)
# print('GLeft:', granos[arcoL[0]].center.x, granos[arcoL[0]].center.y)
# print('GRigth:', granos[arcoL[-1]].center.x, granos[arcoL[-1]].center.y)
# print('DGBase:', distG(granos[arcoL[0]], granos[arcoL[-1]]))

# Numero de granos
if len(arcoL):
    print len(arcoL),
else:
    print '# nulo',

xc = []
yc = []
for a in arcoL:
    xc.append(granos[a].center.x)
    yc.append(granos[a].center.y)
xc = np.array(xc)
yc = np.array(yc)

# Altura del arco:
h = yc.max() - yc.min()
print h,

# Centro de masa
xCM = xc.sum() / xc.size
yCM = yc.sum() / yc.size
print xCM, yCM,

# Longitud de arco y tortuosidad
longi = 0.0
for i in range(1, xc.size):
    longi += sqrt((xc[i]-xc[i-1])**2 + (yc[i] - yc[i-1])**2)
lextr = sqrt((xc[-1] - xc[0])**2 + (yc[-1] - yc[0])**2)
print longi, longi/lextr,

# Span (distancia horizontal entre extremos)
span = abs(xc[-1] - xc[0])
print span,

# Aspect ratio
print 0.5 * span / h

