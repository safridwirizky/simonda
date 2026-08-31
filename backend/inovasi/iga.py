"""Katalog indikator dan mesin skor Indeks Inovasi Daerah 2026.

Sumber tunggal: Lampiran I dan Lampiran II Surat Kepala BSKDN Kemendagri
Nomor 400.10.11/1887/BSKDN tanggal 29 April 2026.

Angka maksimum di bawah diverifikasi ulang terhadap dokumen: SPD 63,
indikator SID 111, Jumlah Inovasi 76, total 250. Jalankan uji_skor.py
setiap kali katalog diubah.
"""

from decimal import Decimal

# (nomor, sub, variabel, nama, bobot, wajib, (parameter 1, parameter 2, parameter 3))

SPD = [
    (1, "", "Institusi", "Visi dan Misi", "1", True,
     ("Kepala Daerah memiliki Misi Inovasi",
      "Kepala Daerah memiliki Visi Inovasi",
      "Kepala Daerah memiliki Misi dan Visi Inovasi")),
    (2, "a", "Institusi", "Penetapan APBD tepat waktu dalam 3 tahun terakhir", "1", False,
     ("Tepat waktu 1 tahun terakhir", "Tepat waktu 2 tahun terakhir",
      "Tepat waktu 3 tahun terakhir")),
    (2, "b", "Institusi", "Pengalokasian mandatory spending", "1", False,
     ("Memenuhi 2 komponen", "Memenuhi 3 komponen", "Memenuhi lebih dari 3 komponen")),
    (3, "", "Institusi", "Kualitas peningkatan perizinan", "1", True,
     ("\u2264 -50,32%", "-50,33% s.d. 8,16%", "\u2265 8,17%")),
    (4, "", "Institusi", "Jumlah pendapatan perkapita", "1", True,
     ("\u2264 2,04%", "2,05% s.d. 5,23%", "\u2265 5,23%")),
    (5, "a", "Institusi", "Progres penurunan Tingkat Pengangguran Terbuka", "0.75", True,
     ("\u2264 0,00", "0,01 s.d. 0,36", "\u2265 0,36")),
    (5, "b", "Institusi", "Persentase Tingkat Pengangguran Terbuka (T-1)", "0.75", True,
     ("\u2265 5,91", "2,34 s.d. 5,92", "\u2264 2,35")),
    (6, "", "Institusi", "Jumlah peningkatan investasi", "1.5", True,
     ("\u2264 -47,42%", "-47,43% s.d. 94,75%", "\u2265 94,76%")),
    (7, "", "Institusi", "Jumlah peningkatan PAD", "1.5", True,
     ("\u2264 -5,14%", "-5,15% s.d. 33,84%", "\u2265 33,85%")),
    (8, "", "Institusi", "Opini BPK", "1.5", True,
     ("TMP/Disclaimer atau TW/Adverse", "WDP/Qualified", "WTP/Unqualified")),
    (9, "", "Institusi", "Nilai capaian Lakip", "1", True,
     ("Nilai LAKIP D atau C", "Nilai LAKIP B", "Nilai LAKIP A")),
    (10, "a", "Institusi", "Progres penurunan angka kemiskinan", "0.75", True,
     ("\u2264 0,07", "0,08 s.d. 1,15", "\u2265 1,16")),
    (10, "b", "Institusi", "Persentase penduduk miskin (T-1)", "0.75", True,
     ("\u2265 13,10", "4,81 s.d. 13,11", "\u2264 4,82")),
    (11, "a", "Sumber Daya Manusia", "Peningkatan IPM dua tahun terakhir", "0.75", True,
     ("\u2264 0,55", "0,56 s.d. 0,90", "\u2265 0,90")),
    (11, "b", "Sumber Daya Manusia", "Capaian IPM tahun terakhir", "0.75", True,
     ("\u2264 69,99", "70,00 s.d. 79,99", "\u2265 80,00")),
    (12, "", "Sumber Daya Manusia", "Penghargaan bagi inovator", "2", False,
     ("Piagam penghargaan bagi inovator",
      "Piagam dan reward/insentif bagi inovator",
      "Piagam, insentif, dan mekanisme kontrol pembudayaan inovasi")),
    (13, "a", "Ekosistem Inovasi dan Kajian",
     "Jumlah rekomendasi kebijakan yang mendukung inovasi", "1", False,
     ("1-3 rekomendasi kebijakan", "4-7 rekomendasi kebijakan",
      "Lebih dari 7 rekomendasi kebijakan")),
    (13, "b", "Ekosistem Inovasi dan Kajian", "Capaian Nilai Indeks Kualitas Kebijakan", "1", False,
     ("Cukup atau Kurang", "Baik", "Unggul atau Sangat Baik")),
    (14, "", "Ekosistem Inovasi dan Kajian",
     "Rencana Induk dan Peta Jalan Pemajuan Iptek Daerah (RIPJ PID)", "1", False,
     ("Masih berbentuk rancangan", "Dokumen selesai dan disepakati",
      "Ditetapkan dalam Perkada")),
    (15, "", "Ekosistem Inovasi dan Kajian",
     "Fasilitasi Pengakuan Hak Kekayaan Intelektual atas Inovasi Daerah", "1", False,
     ("Sosialisasi HAKI", "Sosialisasi dan fasilitasi administrasi",
      "Sosialisasi, fasilitasi, dan insentif pembiayaan")),
]

SID = [
    (16, "", "Infrastruktur", "Regulasi Inovasi Daerah", "3", True,
     ("SK Kepala Daerah atau SK Kepala Perangkat Daerah a.n. Kepala Daerah",
      "Peraturan Kepala Daerah", "Peraturan Daerah")),
    (17, "", "Infrastruktur", "Ketersediaan dan peran SDM terhadap inovasi daerah", "2", True,
     ("1-10 SDM", "11-30 SDM", "Lebih dari 30 SDM")),
    (18, "", "Infrastruktur", "Dukungan anggaran", "2", False,
     ("Satu tahun anggaran", "Dua tahun berturut-turut", "T-0, T-1, dan T-2")),
    (19, "", "Kecanggihan Produk", "Alat Kerja", "2", False,
     ("Manual atau non elektronik", "Didukung perangkat elektronik",
      "Didukung sistem informasi daring atau AI")),
    (20, "", "Infrastruktur", "Bimtek inovasi", "1", False,
     ("1 kali dalam 3 tahun", "2 kali dalam 3 tahun", "3 kali atau lebih")),
    (21, "", "Infrastruktur", "Integrasi program dan kegiatan inovasi dalam RKPD", "2", False,
     ("RKPD T-1 atau T-2", "RKPD T-1 dan T-2", "RKPD T-1, T-2, dan T-0")),
    (22, "", "Output Pengetahuan dan Teknologi", "Keterlibatan aktor inovasi", "1", False,
     ("3 aktor termasuk pelaksana", "4 aktor", "5 aktor atau lebih")),
    (23, "", "Output Pengetahuan dan Teknologi", "Pelaksana inovasi daerah", "1", False,
     ("Ada pelaksana tanpa surat penetapan",
      "Surat Penugasan Kepala Perangkat Daerah atau setara",
      "SK Kepala Daerah atau SK Kepala Perangkat Daerah a.n. Kepala Daerah")),
    (24, "", "Output Pengetahuan dan Teknologi", "Jejaring inovasi", "1", False,
     ("2 Perangkat Daerah", "3-4 Perangkat Daerah", "5 Perangkat Daerah atau lebih")),
    (25, "", "Output Pengetahuan dan Teknologi", "Sosialisasi Inovasi Daerah", "1", False,
     ("Foto kegiatan berlatar spanduk inovasi",
      "Konten media sosial atau pemberitaan milik pemda",
      "Media berita bukan milik pemerintah daerah")),
    (26, "", "Kecepatan Bisnis Proses", "Pedoman teknis", "1", False,
     ("Buku manual cetak", "Buku dalam bentuk elektronik",
      "Buku yang dapat diakses secara daring")),
    (27, "", "Kecepatan Bisnis Proses", "Kemudahan informasi layanan", "1", False,
     ("1 dari 4 metode", "2 dari 4 metode", "3 metode atau lebih")),
    (28, "", "Kecepatan Bisnis Proses", "Kemudahan proses inovasi yang dihasilkan", "2", False,
     ("Hasil diperoleh 6 hari atau lebih", "Hasil diperoleh 2-5 hari",
      "Hasil diperoleh 1 hari")),
    (29, "", "Kecepatan Bisnis Proses", "Penyelesaian layanan pengaduan", "1", False,
     ("\u2264 50% atau tidak ada pengaduan", "51% s.d. 90%", "\u2265 91%")),
    (30, "", "Kecanggihan Produk", "Layanan Terintegrasi", "2", False,
     ("Layanan berjalan terpisah atau independen",
      "Terintegrasi dalam satu portal unit organisasi",
      "Terintegrasi dengan unit organisasi lain")),
    (31, "", "Kecanggihan Produk", "Replikasi", "3", False,
     ("Pernah 1 kali direplikasi", "Pernah 2 kali di daerah berbeda",
      "Pernah 3 kali di daerah berbeda")),
    (32, "", "Kecepatan Bisnis Proses", "Kecepatan penciptaan inovasi", "2", True,
     ("9 bulan atau lebih", "5-8 bulan", "1-4 bulan")),
    (33, "", "Jumlah Inovasi dan Hasil Kreatif", "Kemanfaatan inovasi", "3", True,
     ("Penerima manfaat 1-200 orang", "Penerima manfaat 201-500 orang",
      "Penerima manfaat 501 orang atau lebih")),
    (34, "", "Jumlah Inovasi dan Hasil Kreatif", "Monitoring dan Evaluasi Inovasi Daerah", "2", False,
     ("Laporan monev internal pemda", "Laporan Survei Kepuasan Masyarakat",
      "Monev eksternal berbasis penelitian atau kajian")),
    (35, "", "Jumlah Inovasi dan Hasil Kreatif", "Video inovasi daerah", "4", True,
     ("Memenuhi 1-2 unsur substansi", "Memenuhi 3-4 unsur substansi",
      "Memenuhi 5 unsur substansi")),
]

# Basis ukur alternatif indikator 33 (Kemanfaatan Inovasi), Lampiran II butir 33
# a-f. OPD memilih tepat satu basis -- tiap basis punya ambang parameter 1-3
# sendiri, tidak bisa dicampur.
BASIS_KEMANFAATAN = [
    ("a", "Jumlah penerima manfaat (orang)"),
    ("b", "Cakupan unit penerima manfaat (persentase dari unit sasaran)"),
    ("c", "Efisiensi belanja sebelum dan sesudah inovasi"),
    ("d", "Penambahan pendapatan sebelum dan sesudah inovasi"),
    ("e", "Jumlah produk yang dihasilkan atau diperjualbelikan"),
    ("f", "Tren kinerja positif dalam periode pengukuran"),
]

PARAMETER_KEMANFAATAN = {
    "a": ("Cakupan penerima manfaat 1-200 orang",
          "Cakupan penerima manfaat 201-500 orang",
          "Cakupan penerima manfaat 501 orang atau lebih"),
    "b": ("Cakupan unit penerima manfaat 5,00% s.d. 20,00% dari unit sasaran",
          "Cakupan unit penerima manfaat 20,01% s.d. 50,00% dari unit sasaran",
          "Cakupan unit penerima manfaat di atas 50,00% dari unit sasaran"),
    "c": ("Efisiensi belanja sebesar 0,01% - 10,00%",
          "Efisiensi belanja sebesar 10,01% - 20,00%",
          "Efisiensi belanja sebesar 20,01% - 30,00%"),
    "d": ("Penambahan pendapatan sebesar 0,01% - 9,99%",
          "Penambahan pendapatan sebesar 10,00% - 19,99%",
          "Penambahan pendapatan sebesar ≥20%"),
    "e": ("Jumlah produk dihasilkan/diperjualbelikan 1-100 barang",
          "Jumlah produk dihasilkan/diperjualbelikan 101-200 barang",
          "Jumlah produk dihasilkan/diperjualbelikan lebih dari 200 barang"),
    "f": ("Tren kinerja positif dalam 1 periode waktu pengukuran",
          "Tren kinerja positif dalam 2 periode waktu pengukuran",
          "Tren kinerja positif dalam 3 periode waktu pengukuran"),
}

# --------------------------- konstanta penilaian ---------------------------

MAKS_SPD = Decimal("63")
MAKS_SID_INDIKATOR = Decimal("111")
MAKS_JUMLAH_INOVASI = Decimal("76")
MAKS_TOTAL = Decimal("250")

BOBOT_JUMLAH_INOVASI = Decimal("0.38")
BATAS_INOVASI = 200
PEMBAGI_MINIMAL = 14          # tahun 2027; naik jadi 16 (2028), 18 (2029)
MIN_URUSAN_YANDAS = 6         # tahun 2027 ke atas, seluruh 6 urusan yandas wajib terpenuhi

URUSAN_YANDAS = [
    "Pendidikan",
    "Kesehatan",
    "Pekerjaan Umum dan Penataan Ruang",
    "Perumahan Rakyat dan Kawasan Permukiman",
    "Ketenteraman, Ketertiban Umum, dan Perlindungan Masyarakat",
    "Sosial",
]

KATEGORI = [
    (Decimal("65.01"), "Sangat Inovatif"),
    (Decimal("40.01"), "Inovatif"),
    (Decimal("0.01"), "Kurang Inovatif"),
]

# Jendela pelaporan dan syarat umur inovasi (Lampiran I butir IV.B dan XIII)
PENERAPAN_MULAI = "2024-01-01"
PENERAPAN_SAMPAI = "2025-12-31"


# ------------------------------ perhitungan -------------------------------

def kategori(iid) -> str:
    nilai = Decimal(str(iid))
    for batas, nama in KATEGORI:
        if nilai >= batas:
            return nama
    return "Tidak Dapat Dinilai"


def skor_baris(bobot, pilihan: int) -> Decimal:
    """Satu baris indikator: bobot dikali parameter terpilih (0 bila belum diisi)."""
    p = max(0, min(int(pilihan or 0), 3))
    return Decimal(str(bobot)) * p


def skor_jumlah_inovasi(n: int, urusan_yandas_terpenuhi: int) -> Decimal:
    """Nol bila urusan wajib pelayanan dasar yang dikirim kurang dari 5.

    Ini pasal yang paling mahal: kehilangan seluruh 76 poin, atau 30,4% dari
    skor maksimum, hanya karena sebaran urusan tidak terpenuhi.
    """
    if urusan_yandas_terpenuhi < MIN_URUSAN_YANDAS:
        return Decimal("0")
    return min(n, BATAS_INOVASI) * BOBOT_JUMLAH_INOVASI


def hitung_indeks(skor_spd, skor_sid_tiap_inovasi: list, urusan_yandas_terpenuhi: int) -> dict:
    """Menghitung proyeksi Indeks Inovasi Daerah.

    skor_spd                 : total skor 20 baris indikator SPD
    skor_sid_tiap_inovasi    : daftar skor SID (indikator 16-35) per inovasi
    urusan_yandas_terpenuhi  : jumlah urusan wajib pelayanan dasar yang terisi
    """
    n = len(skor_sid_tiap_inovasi)
    pembagi = max(PEMBAGI_MINIMAL, n)
    total_sid = sum((Decimal(str(s)) for s in skor_sid_tiap_inovasi), Decimal("0"))
    rata_kematangan = total_sid / pembagi if pembagi else Decimal("0")

    skor_jumlah = skor_jumlah_inovasi(n, urusan_yandas_terpenuhi)
    skor_sid = rata_kematangan + skor_jumlah
    skor_total = Decimal(str(skor_spd)) + skor_sid
    iid = skor_total / MAKS_TOTAL * 100

    return {
        "jumlah_inovasi": n,
        "pembagi": pembagi,
        "skor_spd": round(Decimal(str(skor_spd)), 2),
        "rata_kematangan": round(rata_kematangan, 2),
        "skor_jumlah_inovasi": round(skor_jumlah, 2),
        "skor_sid": round(skor_sid, 2),
        "skor_total": round(skor_total, 2),
        "indeks": round(iid, 2),
        "kategori": kategori(iid),
        "yandas_terpenuhi": urusan_yandas_terpenuhi,
        "yandas_kurang": max(0, MIN_URUSAN_YANDAS - urusan_yandas_terpenuhi),
        "kursi_kosong": max(0, PEMBAGI_MINIMAL - n),
    }


def potensi_tambahan(skor_spd, skor_sid_tiap_inovasi: list, urusan_yandas_terpenuhi: int,
                     skor_inovasi_baru) -> Decimal:
    """Berapa poin indeks yang didapat bila satu inovasi lagi ditambahkan.

    Selama jumlah inovasi masih di bawah 12, menambah inovasi hampir selalu
    menguntungkan: pembagi tidak berubah, sehingga skor rata-rata ikut naik.
    """
    sebelum = hitung_indeks(skor_spd, skor_sid_tiap_inovasi, urusan_yandas_terpenuhi)
    sesudah = hitung_indeks(skor_spd, list(skor_sid_tiap_inovasi) + [skor_inovasi_baru],
                            urusan_yandas_terpenuhi)
    return sesudah["indeks"] - sebelum["indeks"]


# ------------------- klasifikasi kematangan per inovasi -------------------
# Bukan bagian dari pedoman resmi BSKDN -- konvensi internal untuk memantau
# kesiapan tiap inovasi berdasarkan skor SID-nya sendiri (skala 0-111),
# terpisah dari kategori Indeks Inovasi Daerah 0-100 di atas.

KLASIFIKASI_KEMATANGAN = [
    ("danger", "Skor Rendah", 0, 65),
    ("warning", "Skor Sedang", 66, 84),
    ("hijau", "Skor Tinggi", 85, 111),
]


def klasifikasi_kematangan(skor_sid) -> str:
    """Kode klasifikasi ('danger'/'warning'/'hijau') dari skor SID satu inovasi (0-111)."""
    nilai = Decimal(str(skor_sid))
    for kode, _label, _bawah, atas in KLASIFIKASI_KEMATANGAN:
        if nilai <= atas:
            return kode
    return "hijau"
