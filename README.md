# Bennix Investment Intelligence

MVP otomasi riset saham Indonesia dengan kerangka: **tren → causal chain → sektor → emiten → skenario → invalidasi**.

## Fungsi
- Scanner 30+ emiten IDX: skor 0–100, `STUDY / WATCH / AVOID`.
- Regime makro dari IHSG, USD/IDR, minyak, emas, dan US 10Y.
- Peta panas sektor, berita/tren, causal-chain, dan prediksi bull/base/bear.
- Audit JSON, riwayat prediksi, freshness sumber, dan dashboard mobile-first.
- Tidak menjanjikan akurasi atau return; hasil adalah shortlist riset, bukan rekomendasi transaksi.

## Menjalankan
```bash
cd /root/bennix-investment-intelligence
python3 app.py scan        # ambil data publik + generate dashboard
python3 app.py serve       # http://127.0.0.1:8765
python3 -m unittest -v     # tes
```

Data utama memakai endpoint chart publik Yahoo Finance dengan fallback data demo deterministik jika jaringan gagal. Berita memakai Google News RSS. Output berada di `data/latest.json`, `data/history/`, dan `dashboard/index.html`.

## Otomasi
`bash run_daily.sh` aman untuk cron. Sistem menyimpan setiap snapshot agar prediksi kelak bisa dievaluasi. Tambahkan ticker melalui `config.json`.

## Interpretasi
- **STUDY:** prioritas untuk analisis manusia lebih lanjut.
- **WATCH:** pantau katalis/harga; belum cukup kuat.
- **AVOID:** kualitas sinyal/risk-reward sementara lemah.

Skor bukan probabilitas untung. Fundamental dinilai netral bila provider publik tidak menyediakan data; dashboard menandainya sebagai data yang hilang agar tidak menciptakan keyakinan palsu.
