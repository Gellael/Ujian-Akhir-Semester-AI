# -- coding: utf-8 --
import os
from datetime import datetime
import requests
from flask import Flask, render_template, request, jsonify
import folium
from folium.plugins import HeatMap
from geopy.distance import geodesic
import logging
import math

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ===================== KONFIGURASI JALAN BENGKULU =====================
class Config:
    NODES = {
        1: {"name": "Simpang Lima (Jl. Soekarno Hatta)", "lat": -3.797347, "lng": 102.265986, "critical": True, "weekend_congestion": True},
        2: {"name": "Bencoolen Mall", "lat": -3.8115102, "lng": 102.2672974, "critical": False, "weekend_congestion": False},
        3: {"name": "Pasar Panorama", "lat": -3.8158167, "lng": 102.2981593, "critical": True, "weekend_congestion": True},
        4: {"name": "Benteng Marlborough", "lat": -3.7878833, "lng": 102.2508915, "critical": False, "weekend_congestion": False},
        5: {"name": "Gerbang Depan UNIB", "lat": -3.7599491, "lng": 102.266921, "critical": False, "weekend_congestion": False},
        6: {"name": "Kantor Gubernur", "lat": -3.8209187, "lng": 102.2839724, "critical": True, "weekend_congestion": False},
        7: {"name": "Gerbang Belakang UNIB", "lat": -3.759583, "lng": 102.275278, "critical": False, "weekend_congestion": False},
        8: {"name": "Masjid Raya Baitul Izzah", "lat": -3.8208245, "lng": 102.287404, "critical": True, "weekend_congestion": True},
        9: {"name": "Megamall Bengkulu", "lat": -3.7933378, "lng": 102.2664841, "critical": True, "weekend_congestion": True},
        10: {"name": "Sport Center", "lat": -3.807732, "lng": 102.2633519, "critical": False, "weekend_congestion": True},
        11: {"name": "Bandara Fatmawati", "lat": -3.860507633240813, "lng": 102.33936230986484, "critical": True, "weekend_congestion": False},
        12: {"name": "Masjid Jamik", "lat": -3.7925189, "lng": 102.2620151, "critical": True, "weekend_congestion": True},
        13: {"name": "Stadion Semarak", "lat": -3.7940007, "lng": 102.2721235, "critical": False, "weekend_congestion": True},
        14: {"name": "Kampus IAIN", "lat": -3.7800, "lng": 102.2900, "critical": False, "weekend_congestion": False},
        15: {"name": "Pelabuhan Pulau Baai", "lat": -3.9073448, "lng": 102.2984753, "critical": True, "weekend_congestion": False}
    }

    OSM_URL = "https://router.project-osrm.org/route/v1/"

    TRANSPORT_PROFILES = {
        'motor': {'base_speed': 40, 'congestion_factor': 0.7, 'icon': 'motorcycle', 'profile': 'driving', 'prefer_narrow': True},
        'mobil': {'base_speed': 50, 'congestion_factor': 0.5, 'icon': 'car', 'profile': 'driving', 'prefer_narrow': False},
        'jalan_kaki': {'base_speed': 5, 'congestion_factor': 1.0, 'icon': 'walking', 'profile': 'walking', 'prefer_narrow': True}
    }

# ===================== SISTEM PREDIKSI KEMACETAN =====================
class TrafficPredictor:
    def __init__(self):
        self.congestion_data = self._init_congestion_data()

    def _init_congestion_data(self):
        return {node_id: {'level': 'lancar', 'updated': datetime.now()} for node_id in Config.NODES}

    def predict_congestion(self, node_id):
        node = Config.NODES[node_id]
        now = datetime.now()
        is_weekend = now.weekday() >= 5

        if is_weekend and node['weekend_congestion']:
            return {'level': 'padat', 'factor': 0.3, 'reason': 'Macet akhir pekan'}
        
        hour = now.hour
        if node['critical']:
            if 7 <= hour <= 9 or 16 <= hour <= 19:
                return {'level': 'padat', 'factor': 0.4, 'reason': 'Jam sibuk'}
            elif 12 <= hour <= 14:
                return {'level': 'sedang', 'factor': 0.7, 'reason': 'Jam makan siang'}
        
        return {'level': 'lancar', 'factor': 1.0, 'reason': 'Lancar'}

# ===================== SISTEM NAVIGASI =====================
class SmartNavigator:
    def __init__(self):
        self.traffic_predictor = TrafficPredictor()

    def calculate_bearing(self, start_coords, end_coords):
        lat1, lon1 = math.radians(start_coords[0]), math.radians(start_coords[1])
        lat2, lon2 = math.radians(end_coords[0]), math.radians(end_coords[1])
        delta_lon = lon2 - lon1
        y = math.sin(delta_lon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
        bearing = math.degrees(math.atan2(y, x))
        bearing = (bearing + 360) % 360
        directions = ['Utara', 'Timur Laut', 'Timur', 'Tenggara', 'Selatan', 'Barat Daya', 'Barat', 'Barat Laut']
        return directions[int((bearing + 22.5) / 45) % 8]

    def get_route_from_api(self, start_coords, end_coords, transport_type):
        if transport_type not in Config.TRANSPORT_PROFILES:
            logger.error(f"Invalid transport type: {transport_type}")
            return None
            
        profile = Config.TRANSPORT_PROFILES[transport_type]['profile']
        base_speed = Config.TRANSPORT_PROFILES[transport_type]['base_speed']
        prefer_narrow = Config.TRANSPORT_PROFILES[transport_type].get('prefer_narrow', False)
        
        url = f"{Config.OSM_URL}{profile}/{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}?overview=full&geometries=geojson&steps=true"
        if prefer_narrow and transport_type == 'motor':
            url_with_narrow = url + "&access=customer"
            try:
                response = requests.get(url_with_narrow)
                data = response.json()
                if response.status_code != 200 or data.get('code') != 'Ok':
                    logger.warning(f"Failed with access=customer, falling back to default: {data.get('message', 'Unknown error')}")
                    response = requests.get(url)
                    data = response.json()
            except Exception as e:
                logger.error(f"Error with access=customer, falling back: {e}")
                response = requests.get(url)
                data = response.json()
        else:
            response = requests.get(url)
            data = response.json()
            
        if response.status_code == 200 and data.get('code') == 'Ok':
            route = data['routes'][0]
            distance = route['distance'] / 1000
            duration = route['duration'] / 60
            geometry = route['geometry']['coordinates']
            
            path = [[coord[1], coord[0]] for coord in geometry]
            
            steps = []
            if 'legs' in route:
                for leg in route.get('legs', []):
                    for i, step in enumerate(leg.get('steps', [])):
                        maneuver = step.get('maneuver', {})
                        instruction = step.get('name', 'Lanjutkan')
                        if maneuver.get('type') == 'turn':
                            direction = maneuver.get('modifier', '')
                            instruction = f"Belok {'kiri' if 'left' in direction else 'kanan'} di {instruction}"
                        # Hitung arah berdasarkan koordinat langkah
                        if i < len(leg.get('steps', [])) - 1:
                            next_coords = [leg['steps'][i + 1]['maneuver']['location'][1], leg['steps'][i + 1]['maneuver']['location'][0]]
                            direction = self.calculate_bearing([step['maneuver']['location'][1], step['maneuver']['location'][0]], next_coords)
                        else:
                            direction = "Lurus"
                        # Hitung waktu per langkah
                        step_distance = step['distance'] / 1000
                        step_duration = (step_distance / base_speed) * 60 / Config.TRANSPORT_PROFILES[transport_type]['congestion_factor']
                        nearest_node = self._find_nearest_node([step['maneuver']['location'][1], step['maneuver']['location'][0]])
                        congestion = self.traffic_predictor.predict_congestion(nearest_node)
                        road_condition = f"Kondisi jalan: {congestion['level']} ({congestion['reason']})"
                        steps.append({
                            'instruction': f"{instruction} menuju arah {direction}",
                            'distance': f"{step_distance:.1f} km",
                            'time': f"{step_duration:.0f} menit",
                            'condition': road_condition
                        })
            
            if not steps:
                nearest_start_node = self._find_nearest_node(start_coords)
                nearest_end_node = self._find_nearest_node(end_coords)
                total_duration = (distance / base_speed) * 60
                steps = [{
                    'instruction': f"Bergerak dari {Config.NODES[nearest_start_node]['name']} ke {Config.NODES[nearest_end_node]['name']}",
                    'distance': f"{distance:.1f} km",
                    'time': f"{total_duration:.0f} menit",
                    'condition': "Kondisi jalan: Tidak tersedia"
                }]
            
            if profile == 'driving':
                speed_adjustment = 50 / base_speed
                adjusted_duration = duration * speed_adjustment
            else:
                adjusted_duration = duration
                fallback_duration = (distance / base_speed) * 60
                adjusted_duration = max(adjusted_duration, fallback_duration)
            
            return {
                'distance': f"{distance:.1f} km",
                'time': f"{adjusted_duration:.0f} menit",
                'path': path,
                'steps': steps,
                'raw_duration': duration,
                'raw_distance': distance,
                'speed_adjusted_duration': adjusted_duration
            }
        logger.error(f"OSRM API error: {data.get('message', 'Unknown error')}")
        return None

    def find_all_routes(self, start, end, transport_type):
        try:
            start = int(start)
            end = int(end)
        except (ValueError, TypeError):
            logger.error(f"Invalid start/end IDs: start={start}, end={end}")
            return {"error": "ID lokasi tidak valid"}

        if start not in Config.NODES or end not in Config.NODES:
            logger.error(f"Invalid nodes: start={start}, end={end}")
            return {"error": "Lokasi tidak valid"}
        
        if transport_type not in Config.TRANSPORT_PROFILES:
            logger.error(f"Invalid transport type: {transport_type}")
            return {"error": f"Moda transportasi '{transport_type}' tidak valid"}
        
        start_coords = (Config.NODES[start]['lat'], Config.NODES[start]['lng'])
        end_coords = (Config.NODES[end]['lat'], Config.NODES[end]['lng'])
        
        primary_route = self.get_route_from_api(start_coords, end_coords, transport_type)
        
        if not primary_route:
            logger.error("Failed to get primary route from OSRM")
            return {"error": "Gagal mendapatkan rute dari layanan peta"}
        
        nearest_start_node = self._find_nearest_node(start_coords)
        nearest_end_node = self._find_nearest_node(end_coords)
        
        congestion_start = self.traffic_predictor.predict_congestion(nearest_start_node)
        congestion_end = self.traffic_predictor.predict_congestion(nearest_end_node)
        
        congestion_factor = min(congestion_start['factor'], congestion_end['factor'])
        final_duration = primary_route['speed_adjusted_duration'] / congestion_factor
        primary_route['time'] = f"{final_duration:.0f} menit"
        
        primary_route.update({
            'transport': transport_type,
            'transport_icon': Config.TRANSPORT_PROFILES[transport_type]['icon'],
            'steps': primary_route['steps'],
            'congestion_levels': {
                Config.NODES[nearest_start_node]['name']: congestion_start,
                Config.NODES[nearest_end_node]['name']: congestion_end
            },
            'is_alternative': False
        })
        
        if congestion_start['level'] == 'padat' or congestion_end['level'] == 'padat':
            alternative_route = self._find_alternative_route(start_coords, end_coords, transport_type)
            
            if alternative_route:
                logger.debug(f"Alternative route found: distance={alternative_route['distance']}, time={alternative_route['time']}")
                return {
                    'primary': primary_route,
                    'alternative': alternative_route,
                    'has_congestion': True
                }
        
        return {
            'primary': primary_route,
            'has_congestion': False
        }

    def _find_alternative_route(self, start_coords, end_coords, transport_type):
        if transport_type not in Config.TRANSPORT_PROFILES:
            logger.error(f"Invalid transport type for alternative route: {transport_type}")
            return None
            
        profile = Config.TRANSPORT_PROFILES[transport_type]['profile']
        base_speed = Config.TRANSPORT_PROFILES[transport_type]['base_speed']
        prefer_narrow = Config.TRANSPORT_PROFILES[transport_type].get('prefer_narrow', False)
        
        mid_point = [
            (start_coords[0] + end_coords[0]) / 2 + 0.005,
            (start_coords[1] + end_coords[1]) / 2 + 0.005
        ]
        
        url = f"{Config.OSM_URL}{profile}/{start_coords[1]},{start_coords[0]};{mid_point[1]},{mid_point[0]};{end_coords[1]},{end_coords[0]}?overview=full&geometries=geojson&steps=true"
        if prefer_narrow and transport_type == 'motor':
            url_with_narrow = url + "&access=customer"
            try:
                response = requests.get(url_with_narrow)
                data = response.json()
                if response.status_code != 200 or data.get('code') != 'Ok':
                    logger.warning(f"Failed with access=customer, falling back to default: {data.get('message', 'Unknown error')}")
                    response = requests.get(url)
                    data = response.json()
            except Exception as e:
                logger.error(f"Error with access=customer, falling back: {e}")
                response = requests.get(url)
                data = response.json()
        else:
            response = requests.get(url)
            data = response.json()
            
        if response.status_code == 200 and data.get('code') == 'Ok':
            route = data['routes'][0]
            distance = route['distance'] / 1000
            duration = route['duration'] / 60
            geometry = route['geometry']['coordinates']
            
            path = [[coord[1], coord[0]] for coord in geometry]
            
            steps = []
            if 'legs' in route:
                for leg in route.get('legs', []):
                    for i, step in enumerate(leg.get('steps', [])):
                        maneuver = step.get('maneuver', {})
                        instruction = step.get('name', 'Lanjutkan')
                        if maneuver.get('type') == 'turn':
                            direction = maneuver.get('modifier', '')
                            instruction = f"Belok {'kiri' if 'left' in direction else 'kanan'} di {instruction}"
                        # Hitung arah berdasarkan koordinat langkah
                        if i < len(leg.get('steps', [])) - 1:
                            next_coords = [leg['steps'][i + 1]['maneuver']['location'][1], leg['steps'][i + 1]['maneuver']['location'][0]]
                            direction = self.calculate_bearing([step['maneuver']['location'][1], step['maneuver']['location'][0]], next_coords)
                        else:
                            direction = "Lurus"
                        # Hitung waktu per langkah
                        step_distance = step['distance'] / 1000
                        step_duration = (step_distance / base_speed) * 60 / Config.TRANSPORT_PROFILES[transport_type]['congestion_factor']
                        nearest_node = self._find_nearest_node([step['maneuver']['location'][1], step['maneuver']['location'][0]])
                        congestion = self.traffic_predictor.predict_congestion(nearest_node)
                        road_condition = f"Kondisi jalan: {congestion['level']} ({congestion['reason']})"
                        steps.append({
                            'instruction': f"{instruction} menuju arah {direction}",
                            'distance': f"{step_distance:.1f} km",
                            'time': f"{step_duration:.0f} menit",
                            'condition': road_condition
                        })
            
            nearest_start_node = self._find_nearest_node(start_coords)
            nearest_end_node = self._find_nearest_node(end_coords)
            
            if not steps:
                steps = [{
                    'instruction': f"Bergerak dari {Config.NODES[nearest_start_node]['name']} ke {Config.NODES[nearest_end_node]['name']}",
                    'distance': f"{distance:.1f} km",
                    'time': f"{duration:.0f} menit",
                    'condition': "Kondisi jalan: Tidak tersedia"
                }]
            
            if profile == 'driving':
                speed_adjustment = 50 / base_speed
                adjusted_duration = duration * speed_adjustment
            else:
                adjusted_duration = duration
                fallback_duration = (distance / base_speed) * 60
                adjusted_duration = max(adjusted_duration, fallback_duration)
            
            congestion_start = self.traffic_predictor.predict_congestion(nearest_start_node)
            congestion_end = self.traffic_predictor.predict_congestion(nearest_end_node)
            congestion_factor = min(congestion_start['factor'], congestion_end['factor'])
            final_duration = adjusted_duration / congestion_factor
            
            return {
                'distance': f"{distance:.1f} km",
                'time': f"{final_duration:.0f} menit",
                'path': path,
                'transport': transport_type,
                'transport_icon': Config.TRANSPORT_PROFILES[transport_type]['icon'],
                'steps': steps,
                'congestion_levels': {
                    Config.NODES[nearest_start_node]['name']: congestion_start,
                    Config.NODES[nearest_end_node]['name']: congestion_end
                },
                'is_alternative': True,
                'avoided_congestion': [Config.NODES[nearest_start_node]['name']] if congestion_start['level'] == 'padat' else []
            }
        logger.error(f"OSRM API error for alternative route: {data.get('message', 'Unknown error')}")
        return None

    def _find_nearest_node(self, coords):
        min_dist = float('inf')
        nearest_node = 1
        
        for node_id, node in Config.NODES.items():
            dist = geodesic(coords, (node['lat'], node['lng'])).km
            if dist < min_dist:
                min_dist = dist
                nearest_node = node_id
                
        return nearest_node

# ===================== VISUALISASI PETA =====================
class TrafficMap:
    def __init__(self, traffic_predictor):
        self.congestion_colors = {'padat': 'red', 'sedang': 'orange', 'lancar': 'green'}
        self.traffic_predictor = traffic_predictor

    def create_map(self, start=None, end=None, route_data=None):
        map_center = [-3.7956, 102.2597]
        traffic_map = folium.Map(location=map_center, zoom_start=14, tiles='cartodbpositron')
        
        heat_data = []
        for node_id, node in Config.NODES.items():
            congestion = self.traffic_predictor.predict_congestion(node_id)
            heat_level = 0.7 if congestion['level'] == 'padat' else 0.3
            heat_data.append([node['lat'], node['lng'], heat_level])
        
        HeatMap(heat_data, radius=15).add_to(traffic_map)
        
        for node_id, node in Config.NODES.items():
            congestion = self.traffic_predictor.predict_congestion(node_id)
            folium.CircleMarker(
                location=[node['lat'], node['lng']],
                radius=6,
                popup=f"{node['name']} - {congestion['level']} ({congestion['reason']})",
                color=self.congestion_colors[congestion['level']],
                fill=True
            ).add_to(traffic_map)
        
        if route_data and 'primary' in route_data:
            self._draw_route(traffic_map, route_data['primary'], 'blue')
            
            if 'alternative' in route_data:
                self._draw_route(traffic_map, route_data['alternative'], 'green')
        
        if start in Config.NODES:
            start_node = Config.NODES[start]
            folium.Marker(
                location=[start_node['lat'], start_node['lng']],
                popup=f"<b>START:</b> {start_node['name']}",
                icon=folium.Icon(color='green', icon='play', prefix='fa')
            ).add_to(traffic_map)
        
        if end in Config.NODES:
            end_node = Config.NODES[end]
            folium.Marker(
                location=[end_node['lat'], end_node['lng']],
                popup=f"<b>END:</b> {end_node['name']}",
                icon=folium.Icon(color='red', icon='stop', prefix='fa')
            ).add_to(traffic_map)
        
        return traffic_map._repr_html_()  # Corrected to _repr_html_()

    def _draw_route(self, map_obj, route, color):
        if 'path' in route and route['path']:
            folium.PolyLine(
                route['path'],
                color=color,
                weight=6,
                popup=f"Rute {'Alternatif' if route.get('is_alternative') else 'Utama'}: {route['distance']} ({route['time']})"
            ).add_to(map_obj)

# ===================== FLASK ROUTES =====================
navigator = SmartNavigator()
map_visualizer = TrafficMap(navigator.traffic_predictor)

@app.route('/', methods=['GET', 'POST'])
def index():
    start = request.form.get('start', type=int)
    end = request.form.get('end', type=int)
    transport = request.form.get('transport', 'mobil')
    
    route_data = None
    error_message = None
    
    if start is not None and end is not None and transport in Config.TRANSPORT_PROFILES:
        if start in Config.NODES and end in Config.NODES:
            route_data = navigator.find_all_routes(start, end, transport)
            if 'error' in route_data:
                error_message = route_data['error']
                route_data = None
        else:
            error_message = "Lokasi awal atau tujuan tidak valid"
    
    map_html = map_visualizer.create_map(start, end, route_data)
    
    return render_template(
        'index.html',
        map_html=map_html,
        nodes=Config.NODES,
        route_data=route_data,
        selected_start=start,
        selected_end=end,
        selected_transport=transport,
        congestion_colors=map_visualizer.congestion_colors,
        error_message=error_message
    )

@app.route('/api/route', methods=['POST'])
def api_route():
    data = request.get_json()
    start = data.get('start') if data else None
    end = data.get('end') if data else None
    transport = data.get('transport', 'mobil') if data else 'mobil'
    
    if not start or not end:
        return jsonify({"error": "Parameter start dan end diperlukan"}), 400
    
    try:
        start = int(start)
        end = int(end)
    except (ValueError, TypeError):
        return jsonify({"error": "ID lokasi tidak valid"}), 400
    
    if transport not in Config.TRANSPORT_PROFILES:
        return jsonify({"error": f"Moda transportasi '{transport}' tidak valid"}), 400
    
    route_data = navigator.find_all_routes(start, end, transport)
    return jsonify(route_data)

if not os.path.exists('templates'):
    os.makedirs('templates')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Traffic Bengkulu</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .route-option {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .route-option:hover {
            background-color: #f8f9fa;
            border-color: #007bff;
        }
        .badge-padat { background-color: #dc3545; }
        .badge-sedang { background-color: #ffc107; }
        .badge-lancar { background-color: #28a745; }
        .transport-icon { font-size: 1.5em; margin-right: 10px; }
        .step-item { margin-left: 20px; }
        .step-details { font-size: 0.9em; color: #666; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row bg-primary text-white p-4">
            <div class="col">
                <h1><i class="fas fa-traffic-light"></i> Smart Traffic Bengkulu</h1>
                <p class="mb-0">Sistem navigasi cerdas berbasis peta digital</p>
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <h5 class="mb-0"><i class="fas fa-search-location"></i> Cari Rute</h5>
                    </div>
                    <div class="card-body">
                        <form method="POST">
                            <div class="mb-3">
                                <label for="start" class="form-label">Lokasi Awal</label>
                                <select class="form-select" id="start" name="start" required>
                                    <option value="">Pilih lokasi awal</option>
                                    {% for id, node in nodes.items() %}
                                    <option value="{{ id }}" {% if selected_start == id %}selected{% endif %}>{{ node.name }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="mb-3">
                                <label for="end" class="form-label">Lokasi Tujuan</label>
                                <select class="form-select" id="end" name="end" required>
                                    <option value="">Pilih lokasi tujuan</option>
                                    {% for id, node in nodes.items() %}
                                    <option value="{{ id }}" {% if selected_end == id %}selected{% endif %}>{{ node.name }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="mb-3">
                                <label for="transport" class="form-label">Moda Transportasi</label>
                                <select class="form-select" id="transport" name="transport">
                                    <option value="motor" {% if selected_transport == 'motor' %}selected{% endif %}>Motor</option>
                                    <option value="mobil" {% if selected_transport == 'mobil' %}selected{% endif %}>Mobil</option>
                                    <option value="jalan_kaki" {% if selected_transport == 'jalan_kaki' %}selected{% endif %}>Jalan Kaki</option>
                                </select>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">
                                <i class="fas fa-route"></i> Cari Rute
                            </button>
                        </form>
                    </div>
                </div>
                
                <div class="card mt-3">
                    <div class="card-header bg-primary text-white">
                        <h5 class="mb-0"><i class="fas fa-info-circle"></i> Legenda</h5>
                    </div>
                    <div class="card-body">
                        <div class="d-flex align-items-center mb-2">
                            <div style="width: 20px; height: 20px; background-color: red; margin-right: 10px;"></div>
                            <span>Padat</span>
                        </div>
                        <div class="d-flex align-items-center mb-2">
                            <div style="width: 20px; height: 20px; background-color: orange; margin-right: 10px;"></div>
                            <span>Sedang</span>
                        </div>
                        <div class="d-flex align-items-center">
                            <div style="width: 20px; height: 20px; background-color: green; margin-right: 10px;"></div>
                            <span>Lancar</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-8">
                <div class="card h-100">
                    <div class="card-header bg-primary text-white">
                        <h5 class="mb-0"><i class="fas fa-map-marked-alt"></i> Peta</h5>
                    </div>
                    <div class="card-body p-0">
                        {{ map_html|safe }}
                    </div>
                </div>
            </div>
        </div>

        {% if error_message %}
        <div class="container mt-4">
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-circle"></i> {{ error_message }}
            </div>
        </div>
        {% endif %}

        {% if route_data %}
        <div class="container mt-4">
            {% if route_data.has_congestion %}
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle"></i> 
                Terdeteksi kemacetan pada rute utama. Berikut alternatifnya:
            </div>
            {% endif %}
            
            <div class="row">
                <div class="col-md-6">
                    <div class="route-option">
                        <h5><i class="fas fa-route"></i> Rute Utama <i class="fas fa-{{ route_data.primary.transport_icon }} transport-icon"></i></h5>
                        <div class="d-flex justify-content-between">
                            <span>{{ route_data.primary.distance }}</span>
                            <span>{{ route_data.primary.time }}</span>
                        </div>
                        {% for step in route_data.primary.steps %}
                        <div class="step-item mb-2">
                            <strong>{{ step.instruction }}</strong>
                            <div class="step-details">
                                <p>Jarak: {{ step.distance }}</p>
                                <p>Waktu: {{ step.time }}</p>
                                <p>{{ step.condition }}</p>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                
                {% if route_data.has_congestion and route_data.alternative %}
                <div class="col-md-6">
                    <div class="route-option">
                        <h5><i class="fas fa-random"></i> Rute Alternatif <i class="fas fa-{{ route_data.alternative.transport_icon }} transport-icon"></i></h5>
                        <div class="d-flex justify-content-between">
                            <span>{{ route_data.alternative.distance }}</span>
                            <span>{{ route_data.alternative.time }}</span>
                        </div>
                        {% if route_data.alternative.avoided_congestion %}
                        <div class="text-muted mb-1">
                            <small><i class="fas fa-check-circle"></i> Menghindari {{ route_data.alternative.avoided_congestion|length }} titik macet</small>
                        </div>
                        {% endif %}
                        {% for step in route_data.alternative.steps %}
                        <div class="step-item mb-2">
                            <strong>{{ step.instruction }}</strong>
                            <div class="step-details">
                                <p>Jarak: {{ step.distance }}</p>
                                <p>Waktu: {{ step.time }}</p>
                                <p>{{ step.condition }}</p>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endif %}
            </div>
        </div>
        {% endif %}
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(HTML_TEMPLATE)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)