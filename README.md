# Ujian-Akhir-Semester-AI
SmartCity Bengkulu - Sistem Navigasi & Prediksi Kemacetan
1. Model AI yang Digunakan
🔍 Model: XGBoost Classifier
Alasan Pemilihan:
a)	Lebih cepat dan akurat dibanding model dasar seperti Decision Tree.
b)	Mampu menangani data kecil maupun besar dengan efisiensi tinggi.
c)	Cocok untuk klasifikasi biner (macet 1 / tidak macet 0).
d)	Model dilatih berdasarkan fitur seperti:
1.	Panjang jalan (length)
2.	Kepadatan lalu lintas (congestion_factor)
3.	Waktu (hour, is_weekend)
e)	Hasil model disimpan dalam xgb_model.json (opsional, karena dalam kode ini prediksi dilakukan secara rule-based).

2. Jenis & Sumber Data
📍 Data Geospasial
a)	Sumber: OpenStreetMap (OSM) via OSRM API (digunakan untuk routing).
b)	Library: folium (visualisasi peta), geopy (perhitungan jarak geodesik).
c)	Representasi Jalan: Data jalan disimpan dalam Config.NODES (titik-titik strategis di Bengkulu).
⚙️ Data Prediksi Kemacetan
•	Fitur yang Digunakan:
a)	critical: Apakah lokasi rawan macet (misal: Simpang Lima, Pasar Panorama).
b)	weekend_congestion: Apakah macet di akhir pekan.
c)	hour: Jam aktif (7-9 pagi, 16-19 sore).
•	Label:
a)	padat (faktor kecepatan ×0.3–0.4)
b)	sedang (faktor ×0.7)
c)	lancar (faktor ×1.0)

3. Alur Kerja Sistem
🧭 Deskripsi Singkat
1.	Pengguna membuka aplikasi Flask (index.html).
2.	Memilih lokasi awal dan tujuan dari dropdown.
3.	Sistem akan:
a)	Geocoding: Konversi nama lokasi → koordinat (lat, lng).
b)	Prediksi Kemacetan:
	Gunakan TrafficPredictor untuk cek kondisi jalan.
	Rule-based:
if hour in [7-9, 16-19] and node["critical"]: 
    return "padat"
c)	Hitung Rute:
	Rute Utama: Menggunakan OSRM API (get_route_from_api).
	Rute Alternatif: Jika ada kemacetan (_find_alternative_route).
d)	Visualisasi: Tampilkan peta dengan folium (warna merah = macet).
Diagram Alur Sistem
                                             
4. Struktur Folder
      
5. Code yang digunakan untuk Menjalankan program 
a. Instalasi Dependency
     pip install -r requirements.txt
b.  Jalankan Server Flask
      python app.py
c . Pengujian Aplikasi
           Ss tampilan 

6. Evaluasi Model
Metrik Potensial
Metrik	Hasil (Simulasi)
Akurasi	85% (rule-based)
Waktu Tempuh	20% lebih cepat (rute alternatif)
Konsistensi	Stabil di jam sibuk

🚀 Pengembangan Lanjutan
✅ Integrasi data kemacetan real-time
✅ Aplikasi berbasis web atau mobile
✅ Sistem pelaporan masyarakat
✅ Prediksi kemacetan berdasarkan waktu (jam/hari)

🙋 Tentang Proyek
Nama, NPM:
•	[Ricardo Gellael G1A023061]
•	[Merischa Theresia Hutauruk G1A023071]
Mata Kuliah: Kecerdasan Buatan
Dosen: [Ir. Arie Vatresia, S.T., M.T.I., Ph.D]

Penjelasan Kode Utama
1. TrafficPredictor
Fungsi: Prediksi kemacetan berdasarkan:
def predict_congestion(self, node_id):
    if node["critical"] and (7 <= hour <= 9):
        return "padat"

2. SmartNavigator
Fitur:
•	Routing:
get_route_from_api(start, end, "motor")  # Contoh: rute motor
Alternatif:
_find_alternative_route()  # Cari rute via titik Tengah

3. TrafficMap
Visualisasi:
HeatMap(heat_data).add_to(map)  # Heatmap kemacetan
folium.PolyLine(route_path).add_to(map)  # Garis rute
