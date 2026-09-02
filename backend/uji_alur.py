"""Uji alur SANDO lewat API, memakai aturan penilaian IGA 2026.

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


def berkas_uji(ind, awalan="sid"):
    """Berkas contoh dengan ekstensi sesuai aturan per indikator (lihat
    iga.ekstensi_sid_diizinkan) -- indikator 35 (Video inovasi daerah) hanya
    menerima video, jadi tidak bisa dipakai bersama .pdf seperti indikator lain."""
    if ind.nomor == 35:
        return SimpleUploadedFile(f"{awalan}-{ind.id}.mp4", b"isi video uji", content_type="video/mp4")
    return SimpleUploadedFile(f"{awalan}-{ind.id}.pdf", b"isi SID uji", content_type="application/pdf")


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
# nol. PERINGATAN: skrip ini menghapus SELURUH baris NilaiSPD periode aktif
# tanpa pengecualian -- jangan pernah dijalankan terhadap basis data yang
# menyimpan berkas bukti dukung sungguhan milik pengguna.
for n in NilaiSPD.objects.filter(periode=periode):
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
total_spd_tanpa_berkas = sum(float(x["skor"]) for x in c.get("/api/spd", **kepala(t_vr)).json())
cek("skor SPD masih nol walau parameter terisi (belum ada berkas)",
    total_spd_tanpa_berkas == 0.0, total_spd_tanpa_berkas)

print("\n== Tautan sebagai pengganti berkas (dokumen di atas 1MB) ==")
r = c.put(f"/api/spd/{spd[2].id}", {"pilihan": 2, "tautan": "https://drive.google.com/uji-tautan-spd"},
          content_type="application/json", **kepala(t_vr))
baris_tautan_spd = next(x for x in c.get("/api/spd", **kepala(t_vr)).json() if x["indikator_id"] == spd[2].id)
cek("skor SPD terhitung lewat tautan saja, tanpa berkas",
    float(baris_tautan_spd["skor"]) == float(baris_tautan_spd["bobot"]) * 2, baris_tautan_spd["skor"])
cek("murni tautan, tidak ada berkas tersimpan", len(baris_tautan_spd["berkas"]) == 0, baris_tautan_spd["berkas"])

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

for ind in spd:
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
    isi = {"pilihan": 3, "catatan": "SK terlampir"}
    if ind.nomor == 33:
        isi["basis_ukur"] = "a"
    c.put(f"/api/inovasi/{inv_id}/nilai/{ind.id}", isi,
          content_type="application/json", **kepala(t_op))
d = c.get(f"/api/inovasi/{inv_id}", **kepala(t_op)).json()
cek("skor SID masih nol walau parameter terisi (belum ada berkas)",
    float(d["skor_klaim"]) == 0.0, d["skor_klaim"])
cek("tidak ada indikator wajib kosong", d["wajib_belum_terisi"] == [])
cek("inovasi jadi layak walau skor masih nol (layak = kelengkapan data, bukan berkas)",
    d["layak"] is True)

print("\n== Tautan sebagai pengganti berkas (dokumen di atas 1MB) ==")
sid_tautan = sid[1]
# pilihan tetap 3 (sama seperti pengisian massal di atas) supaya total 111 di
# bawah tidak berubah -- di sini yang diuji cuma bahwa tautan saja sudah
# cukup untuk membuka skor, bukan mengganti nilai pilihannya.
r = c.put(f"/api/inovasi/{inv_id}/nilai/{sid_tautan.id}",
          {"pilihan": 3, "catatan": "SK terlampir", "tautan": "https://drive.google.com/uji-tautan-sid"},
          content_type="application/json", **kepala(t_op))
baris_tautan_sid = r.json()
cek("skor SID terhitung lewat tautan saja, tanpa berkas",
    float(baris_tautan_sid["skor"]) == float(baris_tautan_sid["bobot"]) * 3, baris_tautan_sid["skor"])
cek("murni tautan, tidak ada berkas tersimpan", len(baris_tautan_sid["berkas"]) == 0, baris_tautan_sid["berkas"])

for ind in sid:
    c.post(f"/api/inovasi/{inv_id}/nilai/{ind.id}/berkas", {"berkas": berkas_uji(ind)}, **kepala(t_op))
d = c.get(f"/api/inovasi/{inv_id}", **kepala(t_op)).json()
cek("skor SID sempurna 111 setelah seluruh berkas diunggah", float(d["skor_klaim"]) == 111.0, d["skor_klaim"])

video = next(x for x in d["bukti"] if x["nomor"] == 35)
cek("indikator 35 Video berbobot 4", float(video["bobot"]) == 4.0, video["bobot"])
cek("skor maksimum video 12", float(video["skor_maks"]) == 12.0)

print("\n== Indikator 33 Kemanfaatan Inovasi: 6 basis ukur alternatif (a-f) ==")
ind33 = next(i for i in sid if i.nomor == 33)
cek("indikator 33 wajib pilih basis ukur sebelum menentukan parameter",
    c.put(f"/api/inovasi/{inv_id}/nilai/{ind33.id}", {"pilihan": 1},
          content_type="application/json", **kepala(t_op)).status_code == 400)
cek("basis ukur tidak dikenal ditolak",
    c.put(f"/api/inovasi/{inv_id}/nilai/{ind33.id}", {"pilihan": 1, "basis_ukur": "z"},
          content_type="application/json", **kepala(t_op)).status_code == 400)

r = c.put(f"/api/inovasi/{inv_id}/nilai/{ind33.id}", {"pilihan": 1, "basis_ukur": "c"},
          content_type="application/json", **kepala(t_op))
cek("basis c diterima", r.status_code == 200, r.content[:200])
baris33 = r.json()
cek("basis c menampilkan ambang efisiensi belanja, bukan jumlah penerima manfaat",
    "Efisiensi belanja" in baris33["parameter_1"], baris33["parameter_1"])
cek("parameter_1 basis c sesuai Lampiran II",
    baris33["parameter_1"] == "Efisiensi belanja sebesar 0,01% - 10,00%", baris33["parameter_1"])

r = c.put(f"/api/inovasi/{inv_id}/nilai/{ind33.id}", {"pilihan": 2, "basis_ukur": "e"},
          content_type="application/json", **kepala(t_op))
baris33e = r.json()
cek("ganti ke basis e langsung mengganti wording parameter",
    baris33e["parameter_2"] == "Jumlah produk dihasilkan/diperjualbelikan 101-200 barang",
    baris33e["parameter_2"])
cek("basis lama (c) tidak lagi muncul setelah ganti basis",
    "Efisiensi belanja" not in baris33e["parameter_1"], baris33e["parameter_1"])

d33 = next(x for x in c.get(f"/api/inovasi/{inv_id}", **kepala(t_op)).json()["bukti"]
          if x["nomor"] == 33)
cek("basis_ukur tersimpan dan terbaca ulang dari GET detail", d33["basis_ukur"] == "e", d33["basis_ukur"])
cek("skor indikator 33 tetap bobot x pilihan terlepas dari basis (2 x 3 = 6)",
    float(d33["skor"]) == 6.0, d33["skor"])

# kembalikan ke basis "a" default (dipakai loop pengisian sebelumnya) supaya
# skor SID total 111 di atas tidak berubah akibat eksplorasi basis ini
c.put(f"/api/inovasi/{inv_id}/nilai/{ind33.id}", {"pilihan": 3, "basis_ukur": "a", "catatan": "SK terlampir"},
      content_type="application/json", **kepala(t_op))

print("\n== Banyak berkas SID pada satu indikator, dan hapus berkas ==")
bukti_awal = next(x for x in c.get(f"/api/inovasi/{inv_id}", **kepala(t_op)).json()["bukti"]
                  if x["indikator_id"] == sid[0].id)
jumlah_awal = len(bukti_awal["berkas"])  # sudah 1 dari pengisian massal di atas

r = c.post(f"/api/inovasi/{inv_id}/nilai/{sid[0].id}/berkas",
           {"berkas": SimpleUploadedFile("sid-satu.pdf", b"berkas SID uji satu",
                                         content_type="application/pdf")},
           **kepala(t_op))
cek("berkas SID tambahan pertama berhasil diunggah", r.status_code == 200, r.content[:200])
r = c.post(f"/api/inovasi/{inv_id}/nilai/{sid[0].id}/berkas",
           {"berkas": SimpleUploadedFile("sid-dua.pdf", b"berkas SID uji dua",
                                         content_type="application/pdf")},
           **kepala(t_op))
cek("berkas SID tambahan kedua berhasil diunggah tanpa menimpa", r.status_code == 200, r.content[:200])
bukti_sid0 = next(x for x in c.get(f"/api/inovasi/{inv_id}", **kepala(t_op)).json()["bukti"]
                  if x["indikator_id"] == sid[0].id)
cek("kedua berkas tambahan tersimpan sekaligus, bukan menimpa yang lama",
    len(bukti_sid0["berkas"]) == jumlah_awal + 2, bukti_sid0["berkas"])

berkas_terbaru_id = bukti_sid0["berkas"][-1]["id"]
cek("OPD lain tidak boleh hapus berkas SID orang lain",
    c.delete(f"/api/inovasi/{inv_id}/nilai/{sid[0].id}/berkas/{berkas_terbaru_id}",
             **kepala(t_op2)).status_code in (403, 404))
r = c.delete(f"/api/inovasi/{inv_id}/nilai/{sid[0].id}/berkas/{berkas_terbaru_id}",
             **kepala(t_op))
cek("pemilik berhasil hapus salah satu berkas SID", r.status_code == 200, r.content[:200])
bukti_sid0_setelah = next(x for x in c.get(f"/api/inovasi/{inv_id}", **kepala(t_op)).json()["bukti"]
                          if x["indikator_id"] == sid[0].id)
cek("satu berkas berkurang setelah hapus, sisanya tetap ada",
    len(bukti_sid0_setelah["berkas"]) == jumlah_awal + 1, bukti_sid0_setelah["berkas"])
cek("skor tetap terhitung karena masih ada berkas lain",
    float(bukti_sid0_setelah["skor"]) == float(bukti_sid0_setelah["bobot"]) * 3, bukti_sid0_setelah["skor"])

print("\n== Ekstensi berkas dibatasi per indikator ==")
ind_biasa = sid[0]          # nomor 16 -- default, hanya PDF
ind_gambar = next(i for i in sid if i.nomor == 25)   # PDF + gambar
ind_video = next(i for i in sid if i.nomor == 35)    # video saja

r = c.post(f"/api/inovasi/{inv_id}/nilai/{ind_biasa.id}/berkas",
           {"berkas": SimpleUploadedFile("bukan-pdf.jpg", b"isi", content_type="image/jpeg")},
           **kepala(t_op))
cek("indikator biasa menolak gambar, cuma terima PDF", r.status_code == 415, r.content[:200])

r = c.post(f"/api/inovasi/{inv_id}/nilai/{ind_gambar.id}/berkas",
           {"berkas": SimpleUploadedFile("foto-sosialisasi.jpg", b"isi", content_type="image/jpeg")},
           **kepala(t_op))
cek("indikator 25 (Sosialisasi) menerima JPG", r.status_code == 200, r.content[:200])
r = c.post(f"/api/inovasi/{inv_id}/nilai/{ind_gambar.id}/berkas",
           {"berkas": SimpleUploadedFile("dokumen.pdf", b"isi", content_type="application/pdf")},
           **kepala(t_op))
cek("indikator 25 tetap menerima PDF juga", r.status_code == 200, r.content[:200])
r = c.post(f"/api/inovasi/{inv_id}/nilai/{ind_gambar.id}/berkas",
           {"berkas": SimpleUploadedFile("video.mp4", b"isi", content_type="video/mp4")},
           **kepala(t_op))
cek("indikator 25 menolak video", r.status_code == 415, r.content[:200])

r = c.post(f"/api/inovasi/{inv_id}/nilai/{ind_video.id}/berkas",
           {"berkas": SimpleUploadedFile("bukan-video.pdf", b"isi", content_type="application/pdf")},
           **kepala(t_op))
cek("indikator 35 (Video) menolak PDF", r.status_code == 415, r.content[:200])
r = c.post(f"/api/inovasi/{inv_id}/nilai/{ind_video.id}/berkas",
           {"berkas": SimpleUploadedFile("dokumentasi.mov", b"isi", content_type="video/quicktime")},
           **kepala(t_op))
cek("indikator 35 menerima format video lain (.mov)", r.status_code == 200, r.content[:200])

r = c.post(f"/api/spd/{spd[0].id}/berkas",
           {"berkas": SimpleUploadedFile("bukan-pdf.png", b"isi", content_type="image/png")},
           **kepala(t_vr))
cek("SPD menolak gambar, cuma terima PDF", r.status_code == 415, r.content[:200])
r = c.post(f"/api/spd/{spd[0].id}/berkas",
           {"berkas": SimpleUploadedFile("sk-tambahan.pdf", b"isi", content_type="application/pdf")},
           **kepala(t_vr))
cek("SPD tetap menerima PDF", r.status_code == 200, r.content[:200])

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

print("\n== Status verifikasi terikat ke bukti spesifik yang diperiksa ==")
ind_ikat = sid[0]


def bukti_sekarang():
    b = next(x for x in c.get(f"/api/inovasi/{inv_id}", **kepala(t_vr)).json()["bukti"]
             if x["indikator_id"] == ind_ikat.id)
    return b


sebelum = bukti_sekarang()
cek("indikator sudah diterima sebelum bukti diutak-atik",
    sebelum["verifikasi"] == "diterima", sebelum["verifikasi"])
berkas_lama_id = sebelum["berkas"][0]["id"]

# Verifikator sendiri yang menghapus berkas yang tadi ia setujui -- ini
# skenario yang dulu tidak memicu reset sama sekali (kode lama cuma
# mereset kalau OPD yang menghapus).
r = c.delete(f"/api/inovasi/{inv_id}/nilai/{ind_ikat.id}/berkas/{berkas_lama_id}", **kepala(t_vr))
cek("verifikator berhasil hapus berkas yang sudah disetujui", r.status_code == 200, r.content[:200])

setelah_hapus = bukti_sekarang()
cek("status otomatis kembali menunggu begitu berkas yang diperiksa hilang",
    setelah_hapus["verifikasi"] == "menunggu", setelah_hapus["verifikasi"])
cek("catatan verifikator lama tidak ikut nampang di status menunggu",
    setelah_hapus["catatan_verifikator"] == "", setelah_hapus["catatan_verifikator"])

skor_setelah_hapus = float(c.get(f"/api/inovasi/{inv_id}", **kepala(t_vr)).json()["skor_terverifikasi"])
cek("skor terverifikasi ikut turun karena bukti yang disetujui sudah tidak ada",
    skor_setelah_hapus == 111.0 - float(ind_ikat.bobot) * 3, skor_setelah_hapus)

# Unggah berkas BARU (bukan berkas lama yang sama) ke indikator yang sama.
r = c.post(f"/api/inovasi/{inv_id}/nilai/{ind_ikat.id}/berkas",
           {"berkas": SimpleUploadedFile("bukti-baru.pdf", b"bukti pengganti",
                                         content_type="application/pdf")},
           **kepala(t_vr))
cek("berkas baru berhasil diunggah menggantikan yang lama", r.status_code == 200, r.content[:200])
setelah_unggah_baru = bukti_sekarang()
cek("berkas baru saja belum otomatis 'diterima' -- verifikator belum memeriksa berkas ini",
    setelah_unggah_baru["verifikasi"] == "menunggu", setelah_unggah_baru["verifikasi"])

# Verifikator memeriksa ulang dan menyetujui bukti yang baru.
c.post(f"/api/inovasi/{inv_id}/nilai/{ind_ikat.id}/verifikasi",
       {"keputusan": "diterima", "catatan": "Bukti pengganti sudah sesuai."},
       content_type="application/json", **kepala(t_vr))
setelah_setuju_lagi = bukti_sekarang()
cek("disetujui lagi setelah verifikator memeriksa bukti barunya",
    setelah_setuju_lagi["verifikasi"] == "diterima", setelah_setuju_lagi["verifikasi"])
skor_pulih = float(c.get(f"/api/inovasi/{inv_id}", **kepala(t_vr)).json()["skor_terverifikasi"])
cek("skor terverifikasi pulih ke 111 setelah bukti baru disetujui", skor_pulih == 111.0, skor_pulih)

# Mengubah pilihan (tanpa menyentuh berkas) pada indikator yang sudah
# disetujui juga harus melepas ikatan verifikasinya.
c.put(f"/api/inovasi/{inv_id}/nilai/{ind_ikat.id}", {"pilihan": 1},
      content_type="application/json", **kepala(t_vr))
setelah_ganti_pilihan = bukti_sekarang()
cek("ganti pilihan pada baris yang sudah disetujui melepas status diterima",
    setelah_ganti_pilihan["verifikasi"] == "menunggu", setelah_ganti_pilihan["verifikasi"])
# kembalikan seperti semula supaya total skor di bawah tidak berubah
c.put(f"/api/inovasi/{inv_id}/nilai/{ind_ikat.id}", {"pilihan": 3},
      content_type="application/json", **kepala(t_vr))
c.post(f"/api/inovasi/{inv_id}/nilai/{ind_ikat.id}/verifikasi",
       {"keputusan": "diterima", "catatan": "Dikembalikan seperti semula."},
       content_type="application/json", **kepala(t_vr))
cek("skor terverifikasi 111 lagi setelah dikembalikan dan disetujui ulang",
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
        isi = {"pilihan": 3}
        if ind.nomor == 33:
            isi["basis_ukur"] = "a"
        c.put(f"/api/inovasi/{iid}/nilai/{ind.id}", isi,
              content_type="application/json", **kepala(token))
        c.post(f"/api/inovasi/{iid}/nilai/{ind.id}/berkas",
               {"berkas": berkas_uji(ind, awalan=f"sk-{iid}")}, **kepala(token))
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
