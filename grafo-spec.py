#!/usr/bin/env python
import networkx as nx
from math import sqrt
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.patches import Circle, Polygon
from matplotlib.collections import PatchCollection
from matplotlib import collections  as mc
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
    # print 'LISTA', l, len(l)
    for g in l:
        # print g, granos[g].center.x, granos[g].center.y
        if abs(granos[g].center.x) < distX:
            distX = abs(granos[g].center.x)
            iL = iR = l.index(g)
    # print 'CENTRO', iL, iR, distX
    limZ = limD = False
    while not (limZ and limD):
        if iL == 0:
            limZ = True
        if iR == len(l) - 1:
            limD = True
        # print 'iter:', iL, limZ, iR, limD
        if (not limZ):
            if granos[l[iL - 1]].center.y > granos[l[iL]].center.y:
                iL = iL - 1
                continue
            if granos[l[iL - 1]].center.x < granos[l[iL]].center.x:
                # print 'iL-', granos[l[iL-1]].center.x,  granos[l[iL]].center.x, iL,'->', iL - 1
                iL = iL -1
            else:
                # print 'iL#',iL-1, iL, granos[l[iL-1]].center.x,  granos[l[iL]].center.x, iL,'-> XX'
                limZ = True
                # print 'limz', limZ
        if (not limD):
            if granos[l[iR + 1]].center.y > granos[l[iR]].center.y:
                iR = iR + 1
                continue
            if granos[l[iR + 1]].center.x > granos[l[iR]].center.x:
                # print 'iR+', granos[l[iR+1]].center.x,  granos[l[iR]].center.x, iR, '->', iR + 1
                iR = iR + 1
            else:
                # print 'iR#',iR, iR+1, granos[l[iR]].center.x,  granos[l[iR+1]].center.x, iR,'-> XX'
                limD = True
                # print 'limd', limD
        # print 'ESTADO', limZ, limD, not (limZ and limD)
    # print 'LIMITES', iL, iR
    arcoL = l[iL:iR+1]
    return arcoL, dist2

    # for g in l[1:-1]:
    # iiz = 0
    # ide = len(l)
    # if granos[l[0]].center.x < -rd:
        # iiz = 1
    # if granos[l[-1]].center.x > rd:
        # ide = -1
    # for g in l[iiz:ide]:
        # if g < 0:
           # pumba
        # if granos[g].center.x < xLeft:
            # xLeft = granos[g].center.x
            # iL = l.index(g)
            # print('iL:', iL, g, granos[g].center, spl)
        # if granos[g].center.x > xRight:
            # xRight = granos[g].center.x
            # iR = l.index(g)
            # print('iR:', iR, g, granos[g].center, spl)
    # iXm = iL
    # for i in l[iL:iR - 1]:
        # if granos[i+1].center.x < granos[i].center.x:
            # iXm = i + 1
    # arcoL = l[iL:iXm]
    # arcoL = l[iL:iR]
    # return arcoL, dist2


parser = argparse.ArgumentParser(description='Programa para graficar arcos.')
parser.add_argument('-f', '--iFile', help='Input file', required=True, action="store", type=str)
args = parser.parse_args()
ifi = args.iFile
fin = open(ifi, 'r')
data = fin.readlines()
fin.close()
# print('Data:', len(data))

patches = []
caja = []
lines = []
fig, ax = plt.subplots()

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
        caja.append(Polygon(bverts, closed=True))
        continue
    nvert = int(l[1])
    granos[gid] = Grano(gid, Point(float(l[2]), float(l[3])))
    conts = []
    verts = []
    if nvert > 1:
        for i in range(nvert):
            verts.append([float(l[4+2*i]), float(l[4+2*i+1])])
        patches.append(Polygon(verts, closed=True))
        dcv = sqrt((float(l[2]) - verts[0][0])**2 + (float(l[3]) - verts[0][1])**2)
        if dcv > maxR:
            maxR = dcv
        for c in l[4+2*nvert:]:
            conts.append(int(c))
            if int(c) < 0:
                gWall.append(gid)
            # if int(c) > 0:
                # conts.append(int(c))
    else:
        radio = float(l[4][:3])
        if radio > maxR:
            maxR = radio
        if len(l[4][3:]) > 0 and int(l[4][3:]) > 0:
            conts.append(int(l[4][3:]))
        patches.append(Circle((float(l[2]),float(l[3])), 0.5, color='g', fill=True))
        for c in l[5:]:
            conts.append(int(c))
            if int(c) < 0:
                gWall.append(gid)
            # if int(c) > 0:
                # conts.append(int(c))
    granos[gid].contacts = conts
# print len(granos)
# print 'gWall', len(gWall)
# print gWall
# for g in granos:
    # print granos[g].id, granos[g].contacts
# print(granos[345].id, granos[345].contacts)
rD = float((data[-2].split())[2])
print 'Radio descarga:', rD

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
        lines.append([(punto_x, punto_y), (xfin, yfin)])
nleft = []  # Lista de nodos a la izquierda (sobre el piso)
nright = []  # Lista de nodos a la derecha (sobre el piso)
maxR = 2 * maxR
for n in G.nodes():
    if n < 0:
        print 'Nodo negativo'
        continue
    if G.node[n]['pos'][1] > maxR:
        continue
    if -10 in granos[n].contacts or -20 in granos[n].contacts:
        if G.node[n]['pos'][0] > 0.0:
            nright.append(n)
        else:
            nleft.append(n)
print 'R', nright, len(nright)
print 'L', nleft, len(nleft)
# print 'Suma', len(gWall) - len(nright) - len(nleft)
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
            # if spList:
                # print('BI', granos[l])
                # print('BD', granos[r])
                # print('dID:', dg)
            for a in spList:
                # print('LEN', len(a), a)
                if len(a) < minL:
                    spl = a
                    dGBase = dg
                    minL = len(a)
                    arcoL, distO = getArco(a, granos, rD)
                    # print 'Arco det! minL', len(arcoL), distO, arcoL
                    continue
                if len(a) == minL and dg < dGBase:
                    spl = a
                    dGBase = dg
                    arcoL, distO = getArco(a, granos, rD)
                    # print 'Arco det! min dg', len(arcoL), distO, arcoL
                if len(a) == minL and abs(dg - dGBase) < 1.0E-8:
                    aTmp, dTmp = getArco(a, granos, rD)
                    if dTmp < distO:
                        arcoL = aTmp
                        distO = dTmp
                        # print 'Arco det! min dO', len(arcoL), distO, arcoL

print('Arco:', minL, arcoL)
larcos = []
if len(arcoL):
    print('GLeft:', granos[arcoL[0]].center.x, granos[arcoL[0]].center.y)
    print('GRigth:', granos[arcoL[-1]].center.x, granos[arcoL[-1]].center.y)
    print('DGBase:', distG(granos[arcoL[0]], granos[arcoL[-1]]))

    maxyArc = -10.0
    for i in range(len(arcoL) - 1):
        x1 = granos[arcoL[i]].center.x
        y1 = granos[arcoL[i]].center.y
        x2 = granos[arcoL[i+1]].center.x
        y2 = granos[arcoL[i+1]].center.y
        if y1 > maxyArc:
            maxyArc = y1
        if y2 > maxyArc:
            maxyArc = y2
        larcos.append([(x1, y1), (x2, y2)])


p = PatchCollection(patches, color='green', alpha=0.5)
bb = PatchCollection(caja, color='black', alpha=0.5)
lc = mc.LineCollection(lines, color='blue', linewidths=2)
if len(larcos):
    la = mc.LineCollection(larcos, color='red', linewidths=3)
    ax1.add_collection(la)
    if maxyArc > 0.0:
        plt.ylim([-1, maxyArc + 2 * rD])
else:
    plt.ylim([-1, 20])

plt.axes().set_aspect('equal')
ax1 = plt.gca()
ax1.add_collection(p)
ax1.add_collection(bb)
ax1.add_collection(lc)
plt.xlim([-10, 10])
plt.ylim([10, 25])
plt.savefig(ifi.split('.')[0] + '.pdf')
# plt.show()

