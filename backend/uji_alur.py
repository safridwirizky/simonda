"""Uji alur SIMONDA lewat API, memakai aturan penilaian IGA 2026.

    DEBUG=1 SECRET_KEY=... ALLOWED_HOSTS=localhost,testserver python uji_alur.py
"""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "simonda.settings")
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import Client  # noqa: E402

from inovasi import iga  # noqa: E402
from inovasi.models import OPD, Indikator, Inovasi, NilaiSPD, Periode, User  # noqa: E402

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


def kepala(t):
    return {"HTTP_AUTHORIZATION": f"Bearer {t}"}


def masuk(nama):
    r = c.post("/api/auth/masuk", {"username": nama, "password": SANDI},
               content_type="application/json")
    return r.json()["akses"]


print("\n== Menyiapkan akun ==")
periode = Periode.objects.get(aktif=True)

User.objects.filter(username__startswith="uji_").delete()
Inovasi.objects.all().delete()
dinkes, distan = OPD.objects.get(kode="DINKES"), OPD.objects.get(kode="DISTANPANGAN")
bappe = OPD.objects.get(kode="BAPPERIDA")
User.objects.create_user("uji_dinkes", password=SANDI, peran=User.OPERATOR, opd=dinkes)
User.objects.create_user("uji_distan", password=SANDI, peran=User.OPERATOR, opd=distan)
User.objects.create_user("uji_verif", password=SANDI, peran=User.VERIFIKATOR, opd=bappe)
t_op, t_op2, t_vr = masuk("uji_dinkes"), masuk("uji_distan"), masuk("uji_verif")
print(f"  periode {periode.tahun}, pembagi minimal {periode.pembagi_minimal}, "
      f"minimal {periode.min_urusan_yandas} urusan yandas")

sid = list(Indikator.objects.filter(periode=periode, aspek="sid").order_by("nomor"))
spd = list(Indikator.objects.filter(periode=periode, aspek="spd").order_by("nomor", "sub"))

# Bersihkan sisa unggahan uji dari run sebelumnya supaya setiap run mulai dari
# nol, KECUALI spd[0] -- indikator itu menyimpan berkas bukti dukung sungguhan
# milik pengguna, skrip uji tidak pernah menyentuhnya sama sekali.
for n in NilaiSPD.objects.filter(periode=periode).exclude(indikator=spd[0]):
    for b in n.daftar_berkas.all():
        b.berkas.delete(save=False)
        b.delete()
    n.pilihan, n.keterangan, n.tautan = 0, "", ""
    n.save()

print("\n== Katalog tersedia lewat API ==")
cek("40 baris indikator", len(c.get("/api/indikator", **kepala(t_op)).json()) == 40)
cek("20 baris SPD", len(c.get("/api/spd", **kepala(t_vr)).json()) == 20)
cek("operator tidak boleh isi SPD",
    c.put(f"/api/spd/{spd[0].id}", {"pilihan": 3}, content_type="application/json",
          **kepala(t_op)).status_code == 403)

print("\n== Mengisi indikator SPD ==")
for ind in spd:
    c.put(f"/api/spd/{ind.id}", {"pilihan": 2, "keterangan": "dokumen terlampir"},
          content_type="application/json", **kepala(t_vr))
# spd[0] dikecualikan dari penjumlahan ini -- baris itu sudah punya berkas
# bukti dukung sungguhan sejak awal (lihat pembersihan di atas), jadi skornya
# sudah lebih dari nol sebelum langkah unggah manapun di skrip ini.
total_spd_tanpa_berkas = sum(float(x["skor"]) for x in c.get("/api/spd", **kepala(t_vr)).json()
                             if x["indikator_id"] != spd[0].id)
cek("skor SPD masih nol walau parameter terisi (belum ada berkas)",
    total_spd_tanpa_berkas == 0.0, total_spd_tanpa_berkas)

cek("operator tidak boleh unggah berkas SPD",
    c.post(f"/api/spd/{spd[1].id}/berkas",
           {"berkas": SimpleUploadedFile("x.pdf", b"isi", content_type="application/pdf")},
           **kepala(t_op)).status_code == 403)
r = c.post(f"/api/spd/{spd[1].id}/berkas",
           {"berkas": SimpleUploadedFile("sk-spd.pdf", b"isi SK SPD uji", content_type="application/pdf")},
           **kepala(t_vr))
cek("verifikator berhasil unggah berkas SPD", r.status_code == 200, r.content[:200])
spd_setelah_satu_berkas = c.get("/api/spd", **kepala(t_vr)).json()
baris_pertama = next(x for x in spd_setelah_satu_berkas if x["indikator_id"] == spd[1].id)
cek("berkas SPD terisi setelah unggah", len(baris_pertama["berkas"]) == 1, baris_pertama["berkas"])
cek("skor baris itu langsung terhitung begitu berkas ada",
    float(baris_pertama["skor"]) == float(baris_pertama["bobot"]) * 2, baris_pertama["skor"])

print("\n== Unggah berkas kedua tidak menimpa yang pertama ==")
r2 = c.post(f"/api/spd/{spd[1].id}/berkas",
            {"berkas": SimpleUploadedFile("sk-spd-kedua.pdf", b"berkas kedua uji", content_type="application/pdf")},
            **kepala(t_vr))
cek("berkas kedua berhasil diunggah", r2.status_code == 200, r2.content[:200])
baris_dua_berkas = next(x for x in c.get("/api/spd", **kepala(t_vr)).json()
                        if x["indikator_id"] == spd[1].id)
cek("kedua berkas tersimpan sekaligus, bukan menimpa", len(baris_dua_berkas["berkas"]) == 2,
    baris_dua_berkas["berkas"])
nama_berkas = {b["nama_asli"] for b in baris_dua_berkas["berkas"]}
cek("nama kedua berkas berbeda dan keduanya ada", nama_berkas == {"sk-spd.pdf", "sk-spd-kedua.pdf"},
    nama_berkas)

print("\n== Hapus salah satu berkas SPD ==")
berkas_pertama_id = baris_dua_berkas["berkas"][0]["id"]
cek("operator tidak boleh hapus berkas SPD",
    c.delete(f"/api/spd/{spd[1].id}/berkas/{berkas_pertama_id}", **kepala(t_op)).status_code == 403)
r3 = c.delete(f"/api/spd/{spd[1].id}/berkas/{berkas_pertama_id}", **kepala(t_vr))
cek("verifikator berhasil hapus satu berkas", r3.status_code == 200, r3.content[:200])
baris_setelah_hapus = next(x for x in c.get("/api/spd", **kepala(t_vr)).json()
                           if x["indikator_id"] == spd[1].id)
cek("tinggal satu berkas tersisa setelah hapus", len(baris_setelah_hapus["berkas"]) == 1,
    baris_setelah_hapus["berkas"])
cek("skor tetap terhitung selama masih ada berkas lain",
    float(baris_setelah_hapus["skor"]) == float(baris_setelah_hapus["bobot"]) * 2,
    baris_setelah_hapus["skor"])

berkas_terakhir_id = baris_setelah_hapus["berkas"][0]["id"]
c.delete(f"/api/spd/{spd[1].id}/berkas/{berkas_terakhir_id}", **kepala(t_vr))
baris_tanpa_berkas = next(x for x in c.get("/api/spd", **kepala(t_vr)).json()
                          if x["indikator_id"] == spd[1].id)
cek("skor kembali nol setelah berkas terakhir dihapus", float(baris_tanpa_berkas["skor"]) == 0.0,
    baris_tanpa_berkas["skor"])

# spd[0] sengaja tidak disentuh skrip uji -- indikator itu memegang berkas
# bukti dukung sungguhan yang sudah diunggah pengguna, bukan data uji.
for ind in spd[1:]:
    c.post(f"/api/spd/{ind.id}/berkas",
           {"berkas": SimpleUploadedFile(f"sk-{ind.id}.pdf", b"isi SK SPD uji", content_type="application/pdf")},
           **kepala(t_vr))
total_spd = sum(float(x["skor"]) for x in c.get("/api/spd", **kepala(t_vr)).json())
cek("skor SPD semua parameter 2 = 42 setelah seluruh berkas diunggah", total_spd == 42.0, total_spd)

print("\n== Membuat inovasi ==")
r = c.post("/api/inovasi", {
    "nama": "SIPADU \u2014 Pendaftaran Pasien Daring", "tahapan": "penerapan",
    "jenis": "digital", "bentuk": "pelayanan_publik", "urusan": "Kesehatan",
    "tujuan": "Memangkas antrean di puskesmas.", "mulai_penerapan": "2024-03-01",
}, content_type="application/json", **kepala(t_op))
cek("inovasi dibuat", r.status_code == 201, r.content[:200])
inv = r.json()
inv_id = inv["id"]
cek("20 baris indikator SID terbentuk", len(inv["bukti"]) == 20, len(inv["bukti"]))
cek("skor awal nol", float(inv["skor_klaim"]) == 0)
cek("5 indikator wajib terdeteksi kosong", len(inv["wajib_belum_terisi"]) == 5,
    inv["wajib_belum_terisi"])

print("\n== Pemeriksaan kelayakan ==")
cek("rancang bangun kurang dari 300 kata ditandai",
    any("300" in m for m in inv["masalah_kelayakan"]), inv["masalah_kelayakan"])
cek("inovasi belum layak", inv["layak"] is False)

dasar = {"nama": inv["nama"], "urusan": "Kesehatan", "tahapan": "penerapan", "tujuan": "x"}
r = c.put(f"/api/inovasi/{inv_id}", {**dasar, "mulai_penerapan": "2026-01-01",
                                     "rancang_bangun": "kata " * 300},
          content_type="application/json", **kepala(t_op))
cek("penerapan 2026 ditolak", any("31 Desember 2025" in m for m in r.json()["masalah_kelayakan"]),
    r.json()["masalah_kelayakan"])

r = c.put(f"/api/inovasi/{inv_id}", {**dasar, "mulai_penerapan": "2021-05-01",
                                     "rancang_bangun": "kata " * 300},
          content_type="application/json", **kepala(t_op))
cek("penerapan sebelum 2024 tanpa pengembangan ditandai",
    any("sebelum 2024" in m for m in r.json()["masalah_kelayakan"]))

r = c.put(f"/api/inovasi/{inv_id}", {**dasar, "mulai_penerapan": "2021-05-01",
                                     "pengembangan_terbaru": "2025-02-01",
                                     "rancang_bangun": "kata " * 300},
          content_type="application/json", **kepala(t_op))
cek("penerapan lama + pengembangan 2025 diterima", r.json()["masalah_kelayakan"] == [],
    r.json()["masalah_kelayakan"])

print("\n== Mengisi parameter indikator SID ==")
cek("pilihan di luar 0-3 ditolak",
    c.put(f"/api/inovasi/{inv_id}/nilai/{sid[0].id}", {"pilihan": 5},
          content_type="application/json", **kepala(t_op)).status_code == 400)

for ind in sid:
    c.put(f"/api/inovasi/{inv_id}/nilai/{ind.id}", {"pilihan": 3, "catatan": "SK terlampir"},
          content_type="application/json", **kepala(t_op))
d = c.get(f"/api/inovasi/{inv_id}", **kepala(t_op)).json()
cek("skor SID sempurna 111", float(d["skor_klaim"]) == 111.0, d["skor_klaim"])
cek("tidak ada indikator wajib kosong", d["wajib_belum_terisi"] == [])
cek("inovasi jadi layak", d["layak"] is True)

video = next(x for x in d["bukti"] if x["nomor"] == 35)
cek("indikator 35 Video berbobot 4", float(video["bobot"]) == 4.0, video["bobot"])
cek("skor maksimum video 12", float(video["skor_maks"]) == 12.0)

print("\n== Banyak berkas SID pada satu indikator, dan hapus berkas ==")
r = c.post(f"/api/inovasi/{inv_id}/nilai/{sid[0].id}/berkas",
           {"berkas": SimpleUploadedFile("sid-satu.pdf", b"berkas SID uji satu",
                                         content_type="application/pdf")},
           **kepala(t_op))
cek("berkas SID pertama berhasil diunggah", r.status_code == 200, r.content[:200])
r = c.post(f"/api/inovasi/{inv_id}/nilai/{sid[0].id}/berkas",
           {"berkas": SimpleUploadedFile("sid-dua.pdf", b"berkas SID uji dua",
                                         content_type="application/pdf")},
           **kepala(t_op))
cek("berkas SID kedua berhasil diunggah tanpa menimpa", r.status_code == 200, r.content[:200])
bukti_sid0 = next(x for x in c.get(f"/api/inovasi/{inv_id}", **kepala(t_op)).json()["bukti"]
                  if x["indikator_id"] == sid[0].id)
cek("kedua berkas SID tersimpan sekaligus", len(bukti_sid0["berkas"]) == 2, bukti_sid0["berkas"])

cek("OPD lain tidak boleh hapus berkas SID orang lain",
    c.delete(f"/api/inovasi/{inv_id}/nilai/{sid[0].id}/berkas/{bukti_sid0['berkas'][0]['id']}",
             **kepala(t_op2)).status_code in (403, 404))
r = c.delete(f"/api/inovasi/{inv_id}/nilai/{sid[0].id}/berkas/{bukti_sid0['berkas'][0]['id']}",
             **kepala(t_op))
cek("pemilik berhasil hapus salah satu berkas SID", r.status_code == 200, r.content[:200])
bukti_sid0_setelah = next(x for x in c.get(f"/api/inovasi/{inv_id}", **kepala(t_op)).json()["bukti"]
                          if x["indikator_id"] == sid[0].id)
cek("tinggal satu berkas SID tersisa", len(bukti_sid0_setelah["berkas"]) == 1, bukti_sid0_setelah["berkas"])

print("\n== Isolasi antar OPD ==")
cek("OPD lain tidak melihat", c.get(f"/api/inovasi/{inv_id}", **kepala(t_op2)).status_code == 404)
cek("operator tidak bisa verifikasi",
    c.post(f"/api/inovasi/{inv_id}/nilai/{sid[0].id}/verifikasi", {"keputusan": "diterima"},
           content_type="application/json", **kepala(t_op)).status_code == 403)

print("\n== Alur pengajuan dan verifikasi ==")
c.post(f"/api/inovasi/{inv_id}/ajukan", **kepala(t_op))
cek("terkunci saat menunggu verifikasi",
    c.put(f"/api/inovasi/{inv_id}/nilai/{sid[0].id}", {"pilihan": 1},
          content_type="application/json", **kepala(t_op)).status_code == 409)
cek("revisi tanpa catatan ditolak",
    c.post(f"/api/inovasi/{inv_id}/verifikasi", {"keputusan": "revisi", "catatan": ""},
           content_type="application/json", **kepala(t_vr)).status_code == 400)
c.post(f"/api/inovasi/{inv_id}/verifikasi", {"keputusan": "terima", "catatan": "Lengkap."},
       content_type="application/json", **kepala(t_vr))
for ind in sid:
    c.post(f"/api/inovasi/{inv_id}/nilai/{ind.id}/verifikasi", {"keputusan": "diterima"},
           content_type="application/json", **kepala(t_vr))
cek("skor terverifikasi 111",
    float(c.get(f"/api/inovasi/{inv_id}", **kepala(t_vr)).json()["skor_terverifikasi"]) == 111.0)

print("\n== Aturan 6 dari 6 urusan wajib pelayanan dasar ==")
pr = c.get("/api/statistik/ringkasan", **kepala(t_vr)).json()["proyeksi_terverifikasi"]
cek("baru 1 urusan yandas", pr["yandas_terpenuhi"] == 1, pr["yandas_terpenuhi"])
cek("kurang 5 urusan", pr["yandas_kurang"] == 5)
cek("skor jumlah inovasi masih nol", float(pr["skor_jumlah_inovasi"]) == 0)
cek("5 urusan yandas dilaporkan kosong", len(pr["yandas_kosong"]) == 5)
print(f"       indeks sekarang: {pr['indeks']} ({pr['kategori']})")


def buat_lengkap(nama, urusan, token):
    r = c.post("/api/inovasi", {"nama": nama, "urusan": urusan, "tahapan": "penerapan",
                                "tujuan": "x", "mulai_penerapan": "2024-06-01",
                                "rancang_bangun": "kata " * 300},
               content_type="application/json", **kepala(token))
    iid = r.json()["id"]
    for ind in sid:
        c.put(f"/api/inovasi/{iid}/nilai/{ind.id}", {"pilihan": 3},
              content_type="application/json", **kepala(token))
        c.post(f"/api/inovasi/{iid}/nilai/{ind.id}/verifikasi", {"keputusan": "diterima"},
               content_type="application/json", **kepala(t_vr))
    c.post(f"/api/inovasi/{iid}/ajukan", **kepala(token))
    c.post(f"/api/inovasi/{iid}/verifikasi", {"keputusan": "terima", "catatan": "ok"},
           content_type="application/json", **kepala(t_vr))
    return iid


# SIPADU sudah memakai Kesehatan, jadi lima urusan berikut melengkapinya jadi enam (semua).
urusan_pelengkap = iga.URUSAN_YANDAS[:1] + iga.URUSAN_YANDAS[2:]
for n, urusan in enumerate(urusan_pelengkap, 1):
    buat_lengkap(f"Inovasi yandas {n}", urusan, t_op)
pr6 = c.get("/api/statistik/ringkasan", **kepala(t_vr)).json()["proyeksi_terverifikasi"]
cek("6 urusan yandas terpenuhi", pr6["yandas_terpenuhi"] == 6, pr6["yandas_terpenuhi"])
cek("skor jumlah inovasi terbuka", float(pr6["skor_jumlah_inovasi"]) > 0)
print(f"       setelah 6 urusan terpenuhi: {pr6['indeks']} ({pr6['kategori']})")
print(f"       lompatan: +{float(pr6['indeks']) - float(pr['indeks']):.2f} poin indeks")

print("\n== Pembagi MAX(14, n) ==")
cek("6 inovasi tetap dibagi 14", pr6["pembagi"] == 14, pr6["pembagi"])
cek("8 kursi kosong terdeteksi", pr6["kursi_kosong"] == 8, pr6["kursi_kosong"])
for n in range(8):
    buat_lengkap(f"Inovasi tambahan {n}", "Pariwisata", t_op2)
pr14 = c.get("/api/statistik/ringkasan", **kepala(t_vr)).json()["proyeksi_terverifikasi"]
cek("14 inovasi, tidak ada kursi kosong", pr14["kursi_kosong"] == 0)
cek("indeks naik tajam", float(pr14["indeks"]) > float(pr6["indeks"]))
print(f"        6 inovasi: {pr6['indeks']}   14 inovasi: {pr14['indeks']}")

print("\n== Klaim versus terverifikasi ==")
ragu = buat_lengkap("Inovasi belum diverifikasi", "Perhubungan", t_op)
for ind in sid:
    c.post(f"/api/inovasi/{ragu}/nilai/{ind.id}/verifikasi",
           {"keputusan": "ditolak", "catatan": "SK belum ditandatangani."},
           content_type="application/json", **kepala(t_vr))
d = c.get(f"/api/inovasi/{ragu}", **kepala(t_vr)).json()
cek("klaim 111 tetapi terverifikasi 0",
    float(d["skor_klaim"]) == 111.0 and float(d["skor_terverifikasi"]) == 0.0,
    (d["skor_klaim"], d["skor_terverifikasi"]))
ring = c.get("/api/statistik/ringkasan", **kepala(t_vr)).json()
cek("proyeksi klaim lebih tinggi dari terverifikasi",
    float(ring["proyeksi_klaim"]["indeks"]) > float(ring["proyeksi_terverifikasi"]["indeks"]))
print(f"       klaim OPD      : {ring['proyeksi_klaim']['indeks']}")
print(f"       terverifikasi  : {ring['proyeksi_terverifikasi']['indeks']}")

print("\n== Ekspor ==")
r = c.get("/api/ekspor/iga", **kepala(t_vr))
cek("CSV berhasil", r.status_code == 200 and b"SIPADU" in r.content)
cek("berawalan BOM untuk Excel", r.content.startswith("\ufeff".encode()))
cek("rekap OPD terbaca", c.get("/api/statistik/opd", **kepala(t_vr)).status_code == 200)

print("\n== Kelola akun OPD (akun daerah membuat akun perangkat daerah) ==")
User.objects.filter(username="uji_akun_baru").delete()
cek("operator tidak boleh lihat daftar akun OPD",
    c.get("/api/akun-opd", **kepala(t_op)).status_code == 403)
cek("operator tidak boleh buat akun OPD",
    c.post("/api/akun-opd", {"username": "x", "password": "SandiPanjang123", "opd_id": dinkes.id},
           content_type="application/json", **kepala(t_op)).status_code == 403)

r = c.post("/api/akun-opd", {
    "username": "uji_akun_baru", "password": "SandiPanjang123",
    "nama_depan": "Operator Uji", "opd_id": dinkes.id,
}, content_type="application/json", **kepala(t_vr))
cek("verifikator berhasil buat akun operator", r.status_code == 201, r.content[:200])
akun_baru_id = r.json()["id"]

cek("username dobel ditolak",
    c.post("/api/akun-opd", {"username": "uji_akun_baru", "password": "SandiPanjang123",
                             "opd_id": dinkes.id}, content_type="application/json",
           **kepala(t_vr)).status_code == 400)
cek("sandi terlalu pendek ditolak",
    c.post("/api/akun-opd", {"username": "uji_akun_lain", "password": "pendek",
                             "opd_id": dinkes.id}, content_type="application/json",
           **kepala(t_vr)).status_code == 400)
cek("daftar akun OPD terbaca verifikator", len(c.get("/api/akun-opd", **kepala(t_vr)).json()) > 0)

def masuk_dengan(nama, sandi):
    r = c.post("/api/auth/masuk", {"username": nama, "password": sandi},
               content_type="application/json")
    return r.json().get("akses")


t_baru = masuk_dengan("uji_akun_baru", "SandiPanjang123")
cek("akun baru bisa masuk dengan sandi yang diketik verifikator", bool(t_baru))
daftar_akun_baru = c.get("/api/inovasi", **kepala(t_baru)).json()
cek("akun baru cuma lihat inovasi OPD sendiri (DINKES)",
    len(daftar_akun_baru) > 0 and all(i["opd"]["kode"] == "DINKES" for i in daftar_akun_baru),
    {i["opd"]["kode"] for i in daftar_akun_baru})

c.post(f"/api/akun-opd/{akun_baru_id}/nonaktifkan", **kepala(t_vr))
cek("akun nonaktif tidak bisa masuk lagi",
    c.post("/api/auth/masuk", {"username": "uji_akun_baru", "password": "SandiPanjang123"},
           content_type="application/json").status_code == 401)

c.post(f"/api/akun-opd/{akun_baru_id}/aktifkan", **kepala(t_vr))
cek("akun aktif kembali bisa masuk dengan sandi lama",
    bool(masuk_dengan("uji_akun_baru", "SandiPanjang123")))

c.post(f"/api/akun-opd/{akun_baru_id}/reset-sandi", {"password": "SandiBaruLagi456"},
       content_type="application/json", **kepala(t_vr))
cek("sandi lama tidak berlaku setelah direset",
    c.post("/api/auth/masuk", {"username": "uji_akun_baru", "password": "SandiPanjang123"},
           content_type="application/json").status_code == 401)
cek("sandi baru berlaku setelah direset",
    bool(masuk_dengan("uji_akun_baru", "SandiBaruLagi456")))

User.objects.filter(username="uji_akun_baru").delete()

print(f"\n{'=' * 46}\n  {lolos} lolos, {gagal} gagal\n{'=' * 46}\n")
raise SystemExit(1 if gagal else 0)
