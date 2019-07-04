#%%
import pytest
import json
import geopandas as gpd
import utils.files as files
import utils.routing as rt
import utils.geometry as geom_utils
import utils.networks as nw
import utils.exposures as exps
import utils.quiet_paths as qp
import utils.utils as utils
import utils.tests as tests
from fiona.crs import from_epsg
import unittest
import time

#%% 
def get_short_quiet_paths(graph, from_latLon, to_latLon, logging=False):
    from_xy = geom_utils.get_xy_from_lat_lon(from_latLon)
    to_xy = geom_utils.get_xy_from_lat_lon(to_latLon)
    # find origin and target nodes from closest edges
    orig_node = rt.get_nearest_node(graph, from_xy, edge_gdf, node_gdf, nts, logging=logging)
    target_node = rt.get_nearest_node(graph, to_xy, edge_gdf, node_gdf, nts, logging=logging, orig_node=orig_node)
    # utils.print_duration(start_time, 'Origin & target nodes set.')
    # start_time = time.time()
    # get shortest path
    path_list = []
    shortest_path = rt.get_shortest_path(graph, orig_node['node'], target_node['node'], 'length')
    path_geom = nw.get_edge_geoms_attrs(graph, shortest_path, 'length', True, True)
    path_list.append({**path_geom, **{'id': 'short_p','type': 'short', 'nt': 0}})
    # get quiet paths to list
    for nt in nts:
        cost_attr = 'nc_'+str(nt)
        shortest_path = rt.get_shortest_path(graph, orig_node['node'], target_node['node'], cost_attr)
        path_geom = nw.get_edge_geoms_attrs(graph, shortest_path, cost_attr, True, True)
        path_list.append({**path_geom, **{'id': 'q_'+str(nt), 'type': 'quiet', 'nt': nt}})
    # remove linking edges of the origin / target nodes
    nw.remove_linking_edges_of_new_node(graph, orig_node)
    nw.remove_linking_edges_of_new_node(graph, target_node)
    # collect quiet paths to gdf
    gdf = gpd.GeoDataFrame(path_list, crs=from_epsg(3879))
    paths_gdf = rt.aggregate_quiet_paths(gdf)
    # get exposures to noises along the paths
    paths_gdf['th_noises'] = [exps.get_th_exposures(noises, [55, 60, 65, 70]) for noises in paths_gdf['noises']]
    # add noise exposure index (same as noise cost with noise tolerance: 1)
    costs = { 50: 0.1, 55: 0.2, 60: 0.3, 65: 0.4, 70: 0.5, 75: 0.6 }
    paths_gdf['nei'] = [round(nw.get_noise_cost(noises, costs, 1), 1) for noises in paths_gdf['noises']]
    paths_gdf['nei_norm'] = paths_gdf.apply(lambda row: round(row.nei / (0.6 * row.total_length), 4), axis=1)
    return paths_gdf

#%% initialize graph
start_time = time.time()
nts = [0.1, 0.15, 0.25, 0.5, 1, 1.5, 2, 4, 6, 10, 20, 40]
# graph = files.get_network_full_noise(version=2)
graph = files.get_network_kumpula_noise(version=2)
print('Graph of', graph.size(), 'edges read.')
edge_gdf = nw.get_edge_gdf(graph, attrs=['geometry', 'length', 'noises'])
node_gdf = nw.get_node_gdf(graph)
print('Network features extracted.')
nw.set_graph_noise_costs(edge_gdf, graph, nts)
edge_gdf = edge_gdf[['uvkey', 'geometry', 'noises']]
print('Noise costs set.')
edges_sind = edge_gdf.sindex
nodes_sind = node_gdf.sindex
print('Spatial index built.')
utils.print_duration(start_time, 'Network initialized.')

def get_od_path_stats(graph, od_dict, logging=False):
    paths = get_short_quiet_paths(graph, od_dict['orig_latLon'], od_dict['dest_latLon'], logging=logging)
    sp = paths[paths['type'] == 'short']
    qp = paths[paths['type'] == 'quiet']
    sp_count = len(sp)
    qp_count = len(qp)
    sp_len = round(sp['total_length'].sum(), 1)
    qp_len_sum = round(qp['total_length'].sum(), 1)
    all_noises = exps.aggregate_exposures(list(paths['noises']))
    noise_total_len = round(exps.get_total_noises_len(all_noises), 1)
    stats = { 'sp_count': sp_count, 'qp_count': qp_count, 'sp_len': sp_len, 'qp_len_sum': qp_len_sum, 'noise_total_len': noise_total_len }
    return stats

#%% read test OD pairs
ods = tests.get_target_ODs()
od_dicts = ods.to_dict(orient='records')

class TestQuietPaths(unittest.TestCase):

    def test_quiet_path_1(self):
        compare_d = { 'sp_count': 1, 'qp_count': 1, 'sp_len': 813.0, 'qp_len_sum': 813.0, 'noise_total_len': 618.5 }
        stats = get_od_path_stats(graph, od_dicts[0])
        self.assertDictEqual(stats, compare_d)

    def test_quiet_path_2(self):
        compare_d = { 'sp_count': 1, 'qp_count': 5, 'sp_len': 1140.8, 'qp_len_sum': 6139.4, 'noise_total_len': 5969.7 }
        stats = get_od_path_stats(graph, od_dicts[1])
        self.assertDictEqual(stats, compare_d)

    def test_quiet_path_3(self):
        compare_d = { 'sp_count': 1, 'qp_count': 4, 'sp_len': 936.5, 'qp_len_sum': 4688.3, 'noise_total_len': 4303.4 }
        stats = get_od_path_stats(graph, od_dicts[2])
        self.assertDictEqual(stats, compare_d)

    def test_quiet_path_4(self):
        compare_d = { 'sp_count': 1, 'qp_count': 5, 'sp_len': 1136.5, 'qp_len_sum': 6562.6, 'noise_total_len': 7263.1 }
        stats = get_od_path_stats(graph, od_dicts[3])
        self.assertDictEqual(stats, compare_d)

    def test_quiet_path_5(self):
        compare_d = { 'sp_count': 1, 'qp_count': 8, 'sp_len': 1648.8, 'qp_len_sum': 14334.3, 'noise_total_len': 11922.9 }
        stats = get_od_path_stats(graph, od_dicts[4])
        self.assertDictEqual(stats, compare_d)

    def test_quiet_path_6(self):
        compare_d = { 'sp_count': 1, 'qp_count': 5, 'sp_len': 1024.9, 'qp_len_sum': 6410.0, 'noise_total_len': 6782.7 }
        stats = get_od_path_stats(graph, od_dicts[5])
        self.assertDictEqual(stats, compare_d)

    def test_quiet_path_7(self):
        compare_d = { 'sp_count': 1, 'qp_count': 4, 'sp_len': 1053.4, 'qp_len_sum': 5120.3, 'noise_total_len': 5523.1 }
        stats = get_od_path_stats(graph, od_dicts[6])
        self.assertDictEqual(stats, compare_d)

    def test_quiet_path_8(self):
        compare_d = { 'sp_count': 1, 'qp_count': 6, 'sp_len': 795.9, 'qp_len_sum': 6318.3, 'noise_total_len': 5385.9 }
        stats = get_od_path_stats(graph, od_dicts[7])
        self.assertDictEqual(stats, compare_d)

    def test_quiet_path_9(self):
        compare_d = { 'sp_count': 1, 'qp_count': 2, 'sp_len': 670.6, 'qp_len_sum': 1364.7, 'noise_total_len': 1218.2 }
        stats = get_od_path_stats(graph, od_dicts[8])
        self.assertDictEqual(stats, compare_d)

    def test_quiet_path_10(self):
        compare_d = { 'sp_count': 1, 'qp_count': 1, 'sp_len': 138.0, 'qp_len_sum': 138.0, 'noise_total_len': 276.0 }
        stats = get_od_path_stats(graph, od_dicts[9])
        self.assertDictEqual(stats, compare_d)

if __name__ == '__main__':
    unittest.main()
