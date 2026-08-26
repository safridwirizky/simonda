"""Uji kontrak antara API dan antarmuka.

Setiap kolom yang dibaca berkas .jsx harus benar-benar ada di respons API.
Ini yang biasanya jebol saat backend berubah tetapi frontend belum ikut.

    DEBUG=1 SECRET_KEY=... ALLOWED_HOSTS=localhost,testserver python uji_kontrak.py
"""
import os
from datetime import date

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "simonda.settings")
django.setup()

from django.test import Client  # noqa: E402

from inovasi.models import OPD, Indikator, Inovasi, Periode, User  # noqa: E402

c = Client()
lolos = gagal = 0
SANDI = "RahasiaKuat2026"


def cek(nama, syarat, tambahan=""):
    global lolos, gagal
    if syarat:
        lolos += 1
        print(f"  OK   {nama}")
    else:
        gagal += 1
        print(f"  GAGAL {nama} {tambahan}")


def punya(nama, obj, kolom):
    """obj harus memuat semua kolom yang dipakai antarmuka."""
    hilang = [k for k in kolom if k not in obj]
    cek(nama, not hilang, f"kolom hilang: {hilang}")


def kepala(t):
    return {"HTTP_AUTHORIZATION": f"Bearer {t}"}


print("\n== Menyiapkan data ==")
periode = Periode.objects.get(aktif=True)
periode.window_buka, periode.window_tutup = date(2027, 6, 1), date(2027, 8, 31)
periode.save()
User.objects.filter(username__startswith="kon_").delete()
Inovasi.objects.all().delete()

opd = OPD.objects.get(kode="DINKES")
User.objects.create_user("kon_opd", password=SANDI, peran=User.OPERATOR, opd=opd,
                         first_name="Operator", last_name="Dinkes")
User.objects.create_user("kon_verif", password=SANDI, peran=User.VERIFIKATOR,
                         opd=OPD.objects.get(kode="BAPPERIDA"), first_name="Verifikator")


def masuk(n):
    return c.post("/api/auth/masuk", {"username": n, "password": SANDI},
                  content_type="application/json").json()["akses"]


t_op, t_vr = masuk("kon_opd"), masuk("kon_verif")
sid = list(Indikator.objects.filter(periode=periode, aspek="sid").order_by("nomor"))
spd = list(Indikator.objects.filter(periode=periode, aspek="spd").order_by("nomor", "sub"))

inv_id = c.post("/api/inovasi", {
    "nama": "SIPADU", "urusan": "Kesehatan", "tahapan": "penerapan",
    "tujuan": "x", "mulai_penerapan": "2024-03-01", "rancang_bangun": "kata " * 300,
    "nama_inisiator": "Tim Yankes", "asta_cita": "4", "pkpn_klaster": "kesehatan",
}, content_type="application/json", **kepala(t_op)).json()["id"]
for ind in sid[:6]:
    c.put(f"/api/inovasi/{inv_id}/nilai/{ind.id}", {"pilihan": 3, "catatan": "SK ada"},
          content_type="application/json", **kepala(t_op))
for ind in spd[:5]:
    c.put(f"/api/spd/{ind.id}", {"pilihan": 2}, content_type="application/json", **kepala(t_vr))
print("  data uji siap")

print("\n== App.jsx dan Masuk.jsx ==")
profil = c.get("/api/auth/saya", **kepala(t_op)).json()
punya("profil", profil, ["id", "username", "nama", "peran", "bisa_verifikasi", "opd"])
punya("profil.opd", profil["opd"], ["id", "kode", "nama"])
cek("operator bukan verifikator", profil["bisa_verifikasi"] is False)
cek("verifikator dikenali",
    c.get("/api/auth/saya", **kepala(t_vr)).json()["bisa_verifikasi"] is True)
cek("lencana antrean terbaca",
    c.get("/api/inovasi", {"status": "diajukan"}, **kepala(t_vr)).status_code == 200)

print("\n== Beranda.jsx ==")
r = c.get("/api/statistik/ringkasan", **kepala(t_vr)).json()
punya("ringkasan", r, ["tahun", "total_inovasi", "layak", "menunggu_verifikasi",
                       "terverifikasi", "opd_terlibat", "opd_belum_lapor",
                       "proyeksi_klaim", "proyeksi_terverifikasi",
                       "per_tahapan", "per_bentuk"])
punya("proyeksi", r["proyeksi_klaim"],
      ["jumlah_inovasi", "pembagi", "kursi_kosong", "skor_spd", "rata_kematangan",
       "skor_jumlah_inovasi", "skor_sid", "skor_total", "indeks", "kategori",
       "yandas_terpenuhi", "yandas_kurang", "yandas_terisi", "yandas_kosong"])
punya("per_tahapan[0]", r["per_tahapan"][0], ["label", "jumlah"])
cek("kategori salah satu dari empat",
    r["proyeksi_klaim"]["kategori"] in
    ("Sangat Inovatif", "Inovatif", "Kurang Inovatif", "Tidak Dapat Dinilai"),
    r["proyeksi_klaim"]["kategori"])
cek("yandas_kosong daftar teks",
    all(isinstance(u, str) for u in r["proyeksi_klaim"]["yandas_kosong"]))

# Batang komposisi tidak boleh melebihi lebar 250 poin.
p = r["proyeksi_klaim"]
lebar = float(p["skor_spd"]) + float(p["rata_kematangan"]) + float(p["skor_jumlah_inovasi"])
cek("komposisi tidak melampaui 250 poin", lebar <= 250, lebar)
cek("skor_total sama dengan jumlah bloknya", abs(lebar - float(p["skor_total"])) < 0.01,
    (lebar, p["skor_total"]))

print("\n== DaftarInovasi.jsx ==")
daftar = c.get("/api/inovasi", **kepala(t_op)).json()
punya("baris daftar", daftar[0],
      ["id", "nama", "opd", "tahapan", "jenis", "bentuk", "urusan", "status",
       "skor_klaim", "skor_terverifikasi", "persen_terverifikasi", "layak",
       "diperbarui_pada"])
punya("baris.opd", daftar[0]["opd"], ["id", "kode", "nama"])
cek("saringan status bekerja",
    c.get("/api/inovasi", {"status": "draft"}, **kepala(t_op)).status_code == 200)
cek("pencarian bekerja",
    len(c.get("/api/inovasi", {"q": "SIPADU"}, **kepala(t_op)).json()) == 1)
cek("daftar OPD tersedia untuk verifikator",
    len(c.get("/api/opd", **kepala(t_vr)).json()) > 0)

print("\n== DetailInovasi.jsx ==")
d = c.get(f"/api/inovasi/{inv_id}", **kepala(t_op)).json()
punya("detail", d,
      ["id", "nama", "opd", "status", "skor_klaim", "skor_terverifikasi", "layak",
       "bisa_diubah", "masalah_kelayakan", "wajib_belum_terisi", "catatan_verifikasi",
       "bukti", "nama_inisiator", "klasifikasi", "asta_cita", "pkpn_klaster",
       "pkpn_program", "pengembangan_terbaru", "mulai_uji_coba", "mulai_penerapan",
       "rancang_bangun", "tujuan", "manfaat", "hasil", "catatan_internal",
       "anggaran", "pic_nama", "inisiator", "tahapan", "jenis", "bentuk", "urusan"])
punya("baris bukti", d["bukti"][0],
      ["indikator_id", "kode", "nomor", "variabel", "nama_indikator", "bobot", "wajib",
       "parameter_1", "parameter_2", "parameter_3", "pilihan", "basis_ukur", "skor",
       "skor_maks", "catatan", "tautan", "berkas_url", "verifikasi",
       "catatan_verifikator"])
cek("20 baris bukti", len(d["bukti"]) == 20, len(d["bukti"]))
cek("bobot bukan nol", all(float(b["bobot"]) > 0 for b in d["bukti"]))
cek("skor_maks = bobot x 3",
    all(abs(float(b["skor_maks"]) - float(b["bobot"]) * 3) < 0.01 for b in d["bukti"]))
cek("ada indikator wajib untuk ditandai", any(b["wajib"] for b in d["bukti"]))
cek("verifikasi salah satu dari tiga",
    all(b["verifikasi"] in ("menunggu", "diterima", "ditolak") for b in d["bukti"]))
cek("masalah_kelayakan daftar teks", isinstance(d["masalah_kelayakan"], list))
cek("wajib_belum_terisi daftar teks",
    all(isinstance(x, str) for x in d["wajib_belum_terisi"]))

# Rusuk lontar memerlukan bobot yang benar-benar berbeda.
bobot = {float(b["bobot"]) for b in d["bukti"]}
cek("bobot beragam sehingga lebar ruas berbeda", len(bobot) >= 4, sorted(bobot))
video = next(b for b in d["bukti"] if b["nomor"] == 35)
cek("ruas Video paling lebar", float(video["bobot"]) == max(bobot), video["bobot"])

print("\n== IndikatorSPD.jsx ==")
s = c.get("/api/spd", **kepala(t_vr)).json()
punya("baris SPD", s[0],
      ["indikator_id", "kode", "variabel", "nama", "bobot", "wajib", "parameter_1",
       "parameter_2", "parameter_3", "pilihan", "skor", "skor_maks", "keterangan",
       "tautan", "berkas_url"])
cek("20 baris SPD", len(s) == 20, len(s))
cek("3 variabel untuk pengelompokan", len({b["variabel"] for b in s}) == 3,
    {b["variabel"] for b in s})
cek("total SPD tidak melebihi 63", sum(float(b["skor"]) for b in s) <= 63)

print("\n== RekapOPD.jsx ==")
rek = c.get("/api/statistik/opd", **kepala(t_vr)).json()
punya("baris rekap", rek[0],
      ["opd", "jumlah", "terverifikasi", "layak", "rata_skor_klaim",
       "rata_skor_terverifikasi"])
punya("rekap.opd", rek[0]["opd"], ["id", "kode", "nama"])

print("\n== FormInovasi.jsx ==")
semua = c.put(f"/api/inovasi/{inv_id}", {
    "nama": "SIPADU", "tahapan": "penerapan", "inisiator": "asn",
    "nama_inisiator": "dr. A", "klasifikasi": "perangkat_daerah", "jenis": "digital",
    "bentuk": "pelayanan_publik", "urusan": "Kesehatan",
    "lintang": "-10.737300", "bujur": "123.074000", "asta_cita": "4",
    "pkpn_klaster": "kesehatan", "pkpn_program": "Pemeriksaan Kesehatan Gratis",
    "mulai_uji_coba": "2023-11-01", "mulai_penerapan": "2024-03-01",
    "pengembangan_terbaru": "2025-06-01", "rancang_bangun": "kata " * 300,
    "tujuan": "t", "manfaat": "m", "hasil": "h", "anggaran": "45000000",
    "sumber_anggaran": "APBD 2025", "pic_nama": "Kasi", "pic_kontak": "0812",
    "catatan_internal": "internal",
}, content_type="application/json", **kepala(t_op))
cek("seluruh kolom formulir diterima", semua.status_code == 200, semua.content[:250])
h = semua.json()
cek("koordinat tersimpan", h["lintang"] is not None and h["bujur"] is not None)
cek("pkpn_program tersimpan", h["pkpn_program"] == "Pemeriksaan Kesehatan Gratis")
cek("kolom kosong boleh null",
    c.put(f"/api/inovasi/{inv_id}", {"nama": "SIPADU", "urusan": "Kesehatan",
                                     "mulai_penerapan": None, "anggaran": None,
                                     "lintang": None, "bujur": None},
          content_type="application/json", **kepala(t_op)).status_code == 200)

print("\n== Galat ditampilkan dengan jelas ==")
r = c.post("/api/auth/masuk", {"username": "kon_opd", "password": "salah"},
           content_type="application/json")
cek("sandi salah memberi pesan terbaca",
    r.status_code == 401 and "detail" in r.json(), r.content[:120])
r = c.post(f"/api/inovasi/{inv_id}/verifikasi", {"keputusan": "revisi", "catatan": ""},
           content_type="application/json", **kepala(t_vr))
cek("revisi tanpa catatan memberi pesan", "detail" in r.json(), r.content[:120])

print(f"\n{'=' * 46}\n  {lolos} lolos, {gagal} gagal\n{'=' * 46}\n")
raise SystemExit(1 if gagal else 0)
