"""Step 2a — road network, travel times and settlement patches.

Patches are the units of the outbreak model and of demand: every city, town and village (OSM 2014),
with neighbourhoods merged into their town and hamlets attached to the patch they reach fastest by road.
"""
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree
from shapely.geometry import Point, shape

from config import BBOX, OUT
import s2_params as P

LAT0 = (BBOX[1] + BBOX[3]) / 2
KX, KY = 111.32 * np.cos(np.radians(LAT0)), 110.57
S2 = OUT.parent / "s2"
S2.mkdir(exist_ok=True)


def km(x, y):
    return np.c_[np.asarray(x) * KX, np.asarray(y) * KY]


@dataclass
class Network:
    xy: np.ndarray            # node lon/lat
    G: csr_matrix             # hours
    G_rain: csr_matrix        # hours, rainy season
    truck: np.ndarray         # node touches a truck-passable road
    tree: cKDTree             # on main-component nodes (km space)
    main: np.ndarray          # indices of main-component nodes

    def snap(self, lon, lat):
        """Nearest main-network node and the walking time to reach it (h)."""
        d, i = self.tree.query(km(lon, lat))
        return self.main[i], d / P.WALK_KMH

    def times(self, nodes, rain=False, limit=np.inf):
        """Travel time (h) from each source node to every node. Shape (len(nodes), n_nodes)."""
        return dijkstra(self.G_rain if rain else self.G, indices=np.atleast_1d(nodes), limit=limit)

    def nearest(self, nodes, offsets=None, rain=False, limit=np.inf):
        """Multi-source: time to the nearest source and which source, for every node."""
        nodes = np.atleast_1d(nodes)
        if offsets is None or not np.any(offsets):
            d, _, src = dijkstra(self.G_rain if rain else self.G, indices=nodes, min_only=True,
                                 return_predecessors=True, limit=limit)
            return d, src
        # add a virtual super-source so walking offsets count
        n = self.G.shape[0]
        G = self.G_rain if rain else self.G
        rows = np.r_[G.nonzero()[0], np.full(len(nodes), n)]
        cols = np.r_[G.nonzero()[1], nodes]
        vals = np.r_[np.asarray(G[G.nonzero()]).ravel(), np.asarray(offsets) + 1e-9]
        H = csr_matrix((vals, (rows, cols)), shape=(n + 1, n + 1))
        d, pred = dijkstra(H, indices=n, return_predecessors=True, limit=limit)
        # recover which source each node came from by walking predecessors once (vectorised by order)
        src = np.full(n + 1, -1)
        src[nodes] = nodes
        order = np.argsort(d)
        for v in order:
            if src[v] == -1 and pred[v] >= 0:
                src[v] = src[pred[v]]
        return d[:n], src[:n]


def build_network():
    # unsimplified 2014 roads (the GeoJSON copy is simplified, which drops junction vertices)
    from shapely.geometry import mapping
    from s1_fetch import _read
    feats = [{"properties": p, "geometry": mapping(g)} for p, g in _read("roads/roads.shp")]
    nid, xy, rows, cols, h_dry, h_rain, truck_nodes = {}, [], [], [], [], [], set()

    def node(p):
        k = (round(p[0], 5), round(p[1], 5))  # ~1 m snap
        if k not in nid:
            nid[k] = len(xy)
            xy.append(k)
        return nid[k]

    for f in feats:
        t = f["properties"].get("type") or "road"
        v = P.SPEED_KMH.get(t, 8)
        vr = v * P.RAINY_FACTOR.get(t, 1.0)
        g = f["geometry"]
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for line in lines:
            prev = None
            for p in line:
                n = node(p)
                if t in P.TRUCK_ROADS:
                    truck_nodes.add(n)
                if prev is not None and prev != n:
                    a, b = xy[prev], xy[n]
                    d = float(np.hypot((a[0] - b[0]) * KX, (a[1] - b[1]) * KY))
                    rows += [prev, n]; cols += [n, prev]
                    h_dry += [d / v] * 2; h_rain += [d / vr] * 2
                prev = n
    n = len(xy)
    G = csr_matrix((h_dry, (rows, cols)), shape=(n, n))
    Gr = csr_matrix((h_rain, (rows, cols)), shape=(n, n))
    G.sum_duplicates(); Gr.sum_duplicates()
    _, lab = connected_components(G, directed=False)
    big = np.bincount(lab).argmax()
    main = np.where(lab == big)[0]
    xy = np.array(xy)
    truck = np.zeros(n, bool); truck[list(truck_nodes)] = True
    print(f"[s2a] road graph: {n:,} nodes, main component {len(main):,}")
    return Network(xy, G, Gr, truck, cKDTree(km(xy[main, 0], xy[main, 1])), main)


def build_patches(net):
    """Cities/towns/villages become patches; neighbourhoods merge into towns; hamlets join by travel time."""
    st = pd.read_csv(OUT / "settlements_population.csv")
    gin = [shape(f["geometry"]) for f in json.load(open(OUT / "admin_adm0.geojson"))["features"]
           if f["properties"]["iso"] == "GIN"][0]
    st = st[[gin.contains(Point(x, y)) for x, y in zip(st.lon, st.lat)]].reset_index(drop=True)
    adm2 = [(f["properties"]["name"], shape(f["geometry"])) for f in
            json.load(open(OUT / "admin_adm2.geojson"))["features"] if f["properties"]["iso"] == "GIN"]
    st["prefecture"] = [next((n for n, g in adm2 if g.contains(Point(x, y))), None) for x, y in zip(st.lon, st.lat)]

    centre = st.type.isin(["city", "town", "village"])
    towns = st[st.type.isin(["city", "town"])]
    # neighbourhoods/suburbs -> nearest city/town within 6 km
    tt = cKDTree(km(towns.lon, towns.lat))
    sub = st.type.isin(["neighbourhood", "suburb"])
    d, j = tt.query(km(st.loc[sub, "lon"], st.loc[sub, "lat"]))
    parent = pd.Series(-1, index=st.index)
    parent[st.index[sub][d < 6]] = towns.index[j[d < 6]]

    patches = st[centre].copy()
    patches["node"], patches["walk_h"] = net.snap(patches.lon, patches.lat)
    st["node"], st["walk_h"] = net.snap(st.lon, st.lat)
    # everything not a patch centre or a merged neighbourhood: nearest patch by road time
    dist, src = net.nearest(patches.node.values, patches.walk_h.values)
    node2patch = dict(zip(patches.node.values, patches.index.values))
    assign = pd.Series([node2patch.get(s, -1) for s in src[st.node.values]], index=st.index)
    assign[centre] = st.index[centre]
    assign[parent >= 0] = parent[parent >= 0]
    st["patch"] = assign
    st["t_to_patch_h"] = dist[st.node.values] + st.walk_h
    pop = st.groupby("patch").pop_hrsl.sum()
    patches["pop"] = pop.reindex(patches.index).fillna(0).values
    patches["n_settlements"] = st.groupby("patch").size().reindex(patches.index).fillna(0).astype(int).values
    patches = patches.reset_index().rename(columns={"index": "settlement_idx"})
    patches["pid"] = np.arange(len(patches))
    st["pid"] = st.patch.map(dict(zip(patches.settlement_idx, patches.pid)))
    patches.to_csv(S2 / "patches.csv", index=False)
    st.to_csv(S2 / "settlements_patches.csv", index=False)
    print(f"[s2a] patches: {len(patches)} (pop {patches['pop'].sum():,.0f}); "
          f"largest {patches.nlargest(4, 'pop')[['name', 'pop']].values.tolist()}")
    return patches, st


if __name__ == "__main__":
    net = build_network()
    build_patches(net)
