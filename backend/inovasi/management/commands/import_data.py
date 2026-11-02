"""Impor data inovasi dari berkas "Laporan Inovasi Daerah" (PDF resmi IGA/BSKDN)
ke dalam SANDO.

Dipakai untuk memulihkan data yang hilang (mis. db.sqlite3 terhapus) selama
inovasi yang bersangkutan sudah pernah diregistrasikan dan laporan PDF-nya
masih bisa diunduh ulang dari sistem BSKDN -- laporan itu memuat profil
inovasi (1.1-1.21) dan tabel 20 indikator SID (16-35) secara lengkap.

    python manage.py import_data berkas1.pdf berkas2.pdf
    python manage.py import_data folder_laporan/            # semua *.pdf di folder
    python manage.py import_data folder_laporan/ --dry-run   # pratinjau, tidak menyimpan
    python manage.py import_data folder_laporan/ --tahun 2027 --status terverifikasi

BATASAN PENTING -- baca sebelum memakai hasilnya:

1.  Judul berkas pada kolom "Bukti Dukung" di laporan BSKDN ternyata
    adalah TAUTAN (anchor text) ke berkas aslinya -- disimpan sebagai
    anotasi link PDF (tidak kelihatan sebagai teks biru, tapi tetap
    bisa diklik/terbaca lewat pdfplumber). Skrip ini membaca koordinat
    anotasi itu, mencocokkannya ke sel kolom "Bukti Dukung" baris yang
    tepat, dan mengisi `NilaiSID.tautan` dengan tautan tersebut secara
    otomatis -- PERSIS seperti menempelkan tautan manual lewat formulir
    SANDO, tanpa perlu mengunduh lalu mengunggah ulang berkasnya.
    Sebagian tautan mengarah ke domain BSKDN sendiri (indeks.inovasi.
    bskdn.kemendagri.go.id), ada juga yang ke domain pihak ketiga
    (mis. tuxedovation.com pada beberapa laporan) -- keduanya tetap
    ditautkan apa adanya, tapi periksa sendiri apakah tautan pihak
    ketiga itu kredibel/tidak kedaluwarsa sebelum terlalu bergantung
    padanya untuk pelaporan resmi. Baris yang bukti dukungnya "Tidak
    Tersedia" di laporan asli memang tidak punya tautan untuk diisi --
    itu bukan kegagalan skrip.
2.  `pilihan` (1-3) tiap indikator ditentukan dengan mencocokkan teks
    kolom "Informasi" terhadap tiga `parameter_1/2/3` katalog (iga.py),
    pertama lewat kecocokan angka yang unik di antara ketiganya, kalau
    tidak ada baru lewat kemiripan teks (difflib). ini PENCOCOKAN
    OTOMATIS, bukan pembacaan manual -- hasilnya pada umumnya benar
    (diuji cocok 20/20 pada contoh Tulu Fali) tapi bisa meleset kalau
    redaksi "Informasi" di laporan menyimpang jauh dari kalimat
    pedoman. Jalankan dulu dengan --dry-run dan periksa kolom
    "keyakinan" sebelum --tahun yang sama dipakai untuk pelaporan resmi.
3.  Bentuk Inovasi Daerah (1.8 Asta Cita) hanya dipetakan untuk butir
    yang sudah dipastikan teksnya (lihat PETA_ASTA_CITA) -- butir lain
    dibiarkan kosong (bukan ditebak) dan dicatat di laporan akhir.
"""

import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inovasi import iga
from inovasi.models import OPD, Indikator, Inovasi, LogAktivitas, NilaiSID, Periode, User

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None


# ============================================================ util teks ===

def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = (s.replace("\u2265", ">=").replace("\u2264", "<=")
          .replace("\u2013", "-").replace("\u2014", "-"))
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s.rstrip(".")


def _mirip(a: str, b: str) -> float:
    """Skor kemiripan 0..1 antara dua teks, setelah dinormalisasi."""
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


_STOPWORD_OPD = {"dan", "atau", "dari", "yang", "dengan", "serta", "dalam", "pada",
                 "untuk", "kabupaten", "daerah", "rote", "ndao"}


# Ekor boilerplate yang sering ditempel di "1.9 Urusan Inovasi Daerah" kalau
# urusannya adalah fungsi penunjang (mis. "...Fungsi Penunjang lainnya
# sesuai dengan ketentuan peraturan perundang-undangan") -- bukan bagian
# dari nama urusan itu sendiri, jadi dibuang dulu sebelum dihitung kata
# penting-nya, atau kata generik di situ ("sesuai", "ketentuan", dst) akan
# mengencerkan skor kecocokan ke urusan yang sebenarnya jelas (mis.
# "komunikasi dan informatika").
_EKOR_URUSAN = re.compile(
    r"fungsi penunjang.*$|sesuai dengan ketentuan.*$", re.IGNORECASE | re.DOTALL)


def _kata_signifikan(teks: str) -> set:
    teks = _EKOR_URUSAN.sub("", teks or "")
    return {w for w in re.findall(r"[a-z]+", _norm(teks)) if len(w) >= 4 and w not in _STOPWORD_OPD}


# Nama lama/alias OPD yang terbukti dari data: laporan Tulu Fali memakai tag
# akun "Bapelitbang" (nama lama Bapperida sebelum direstrukturisasi) padahal
# "1.5 Nama Inisiator"-nya sendiri sudah memastikan itu Bapperida -- jadi
# alias ini aman dipakai untuk laporan lain yang tag-nya "Bapelitbang" tapi
# tanpa nama inisiator yang jelas.
_ALIAS_TAG_OPD = {"bapelitbang": "BAPPERIDA"}


def _mirip_kata(urusan: str, nama_opd: str) -> float:
    """Kemiripan berbasis kata (bukan karakter) -- lebih tahan terhadap
    urutan kata yang beda antara "Urusan Inovasi Daerah" (mis. "pangan,
    pertanian") dan nama resmi OPD (mis. "Dinas Pertanian dan Ketahanan
    Pangan"). Kemiripan karakter murni (difflib) gampang keliru: "pangan,
    pertanian" pernah lebih mirip-huruf ke "Dinas Perikanan" (0.56) daripada
    ke "Dinas Pertanian dan Ketahanan Pangan" (0.42) padahal yang kedua
    sama sekali jelas lebih tepat -- jadi dipakai hitungan kata di sini.
    Skor = proporsi kata penting di `urusan` yang juga ada di `nama_opd`."""
    wu, wo = _kata_signifikan(urusan), _kata_signifikan(nama_opd)
    if not wu or not wo:
        return 0.0
    return len(wu & wo) / len(wu)


def _angka(teks: str) -> set:
    """Angka dalam teks, TANPA notasi tahun-mundur "T-2/T-1/T-0" (dan
    variannya "T 2", "T0" dst) -- notasi itu muncul berulang sebagai
    boilerplate "dalam 3 tahun (T-2,T-1,T-0) terakhir" pada banyak baris
    Informasi yang sebetulnya tidak sedang membicarakan angka itu (mis.
    jumlah bimtek), sehingga kalau ikut dihitung malah bentrok dengan
    angka 1/2/3 pada parameter pilihan dan membuat pencocokan jadi ambigu."""
    bersih = re.sub(r"\bT[\s-]?\d+\b", " ", teks or "", flags=re.IGNORECASE)
    return set(re.findall(r"\d+(?:[.,]\d+)?", bersih))


def _pilihan_dari_angka_unik(teks: str, params: tuple) -> Optional[int]:
    """Cari angka di `teks` yang HANYA muncul di satu dari ketiga parameter
    (angka boilerplate yang muncul di ketiganya, mis. "3" dari "dalam 3
    tahun" yang berulang di semua pilihan, diabaikan karena tidak
    membedakan apa-apa) -- penanda lebih andal daripada kemiripan kalimat
    untuk indikator berbasis ambang angka/persen/jumlah kejadian."""
    angka_info = _angka(teks)
    if not angka_info:
        return None
    param_sets = [_angka(p) for p in params]
    kandidat = {cocok[0] for a in angka_info
                if len(cocok := [i for i, s in enumerate(param_sets) if a in s]) == 1}
    return kandidat.pop() if len(kandidat) == 1 else None


def tentukan_pilihan(indikator: Indikator, informasi: str, basis: str = "") -> tuple:
    """-> (pilihan 0-3, skor_keyakinan 0-1)."""
    teks = (informasi or "").strip()
    if not teks or teks == "-" or teks.replace(".", "").isdigit():
        return 0, 0.0
    if indikator.nomor == 33:
        params = iga.PARAMETER_KEMANFAATAN.get(basis or "a", iga.PARAMETER_KEMANFAATAN["a"])
    else:
        params = (indikator.parameter_1, indikator.parameter_2, indikator.parameter_3)
    idx = _pilihan_dari_angka_unik(teks, params)
    if idx is not None:
        return idx + 1, 1.0
    skor = [_mirip(teks, p) for p in params]
    terbaik = max(range(3), key=lambda i: skor[i])
    if skor[terbaik] < 0.3:
        return 0, skor[terbaik]
    return terbaik + 1, skor[terbaik]


# ===================================================== label header PDF ===

LABEL_HEADER = [
    ("nama", r"1\.1\.?\s*Nama Inovasi"),
    ("dibuat_oleh", r"1\.2\.?\s*Dibuat Oleh"),
    ("tahapan", r"1\.3\.?\s*Tahapan Inovasi"),
    ("inisiator", r"1\.4\.?\s*Inisiator Inovasi Daerah"),
    ("nama_inisiator", r"1\.5\.?\s*Nama Inisiator"),
    ("jenis", r"1\.6\.?\s*Jenis Inovasi"),
    ("klasifikasi", r"1\.7\.?\s*Klasifikasi Inovasi"),
    ("bentuk", r"1\.7\.?\s*Bentuk Inovasi Daerah"),
    ("asta_cita_teks", r"1\.8\.?\s*Asta Cita"),
    ("urusan", r"1\.9\.?\s*Urusan Inovasi Daerah"),
    ("rancang_bangun", r"1\.10\.?\s*Rancang Bangun dan Pokok Perubahan Yang Dilakukan"),
    ("tujuan", r"1\.11\.?\s*Tujuan Inovasi Daerah"),
    ("manfaat", r"1\.12\.?\s*Manfaat Yang Diperoleh"),
    ("hasil", r"1\.13\.?\s*Hasil Inovasi"),
    ("mulai_uji_coba", r"1\.14\.?\s*Waktu Uji Coba Inovasi Daerah"),
    ("mulai_penerapan", r"1\.15\.?\s*Waktu Implementasi"),
    ("anggaran", r"1\.16\.?\s*Anggaran"),
    ("profil_bisnis", r"1\.17\.?\s*Profil Bisnis"),
    ("haki", r"1\.18\.?\s*Dokumen HAKI"),
    ("penghargaan", r"1\.19\.?\s*Penghargaan"),
    ("koordinat", r"1\.20\.?\s*Koordinat"),
    ("kematangan", r"1\.21\.?\s*Kematangan"),
    ("_akhir", r"2\.\s*INDIKATOR INOVASI"),
]


def parse_header(teks: str) -> dict:
    posisi = []
    for kunci, pola in LABEL_HEADER:
        m = re.search(pola, teks, re.IGNORECASE)
        if m:
            posisi.append((m.start(), m.end(), kunci))
    posisi.sort()
    hasil = {}
    for i, (_, akhir, kunci) in enumerate(posisi):
        batas = posisi[i + 1][0] if i + 1 < len(posisi) else len(teks)
        hasil[kunci] = teks[akhir:batas].strip()
    return hasil


def parse_koordinat(s: str):
    s = (s or "").strip()
    if not s or s == "-":
        return None, None
    bagian = re.split(r"[,;]", s)
    if len(bagian) != 2:
        return None, None
    try:
        return Decimal(bagian[0].strip()), Decimal(bagian[1].strip())
    except InvalidOperation:
        return None, None


def parse_tanggal(s: str):
    s = (s or "").strip()
    if not s or s == "-":
        return None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_anggaran(s: str):
    """"1.16 Anggaran" kadang bukan angka sama sekali -- pernah berisi
    tautan dokumen DPA (mis. "https://.../dpa.pdf"), yang kalau digit-nya
    asal dilucuti jadi "angka" raksasa puluhan digit dan merusak baris di
    database (field anggaran cuma muat 15 digit). Tautan semacam itu
    dibuang di sini, bukan dipaksa jadi angka."""
    s = (s or "").strip()
    if not s or s == "-":
        return None
    if re.search(r"https?://|www\.", s, re.IGNORECASE):
        return None
    angka = re.sub(r"[^\d]", "", s)
    if not angka or len(angka) > 13:  # max_digits=15, decimal_places=2 -> maks 13 digit di depan koma
        return None
    return Decimal(angka)


def parse_no_registrasi(teks_penuh: str) -> str:
    m = re.search(r"Nomor Registrasi:\s*([\w.\-]+)", teks_penuh)
    return m.group(1) if m else ""


# ---------------------------------------------------- peta pilihan ganda ---
# Hanya memetakan nilai yang sudah pasti ditemukan di laporan asli -- nilai
# lain yang tidak dikenal dibiarkan default/kosong (bukan ditebak) dan
# dicatat di laporan akhir supaya diisi manual.

PETA_TAHAPAN = {"inisiasi": "inisiatif", "perencanaan": "inisiatif",
                "uji coba": "uji_coba", "implementasi": "penerapan", "penerapan": "penerapan"}
PETA_INISIATOR = {"opd": "perangkat_daerah", "perangkat daerah": "perangkat_daerah",
                   "kepala daerah": "kepala_daerah", "dprd": "dprd", "anggota dprd": "dprd",
                   "asn": "asn", "masyarakat": "masyarakat"}
PETA_JENIS = {"digital": "digital", "non digital": "non_digital", "non-digital": "non_digital"}
PETA_KLASIFIKASI = {"inovasi perangkat daerah": "perangkat_daerah",
                     "inovasi desa": "desa", "inovasi masyarakat": "masyarakat"}

# Teks resmi Asta Cita yang sudah dipastikan -- tambahkan butir lain begitu
# ditemukan di laporan berikutnya (ada 8 butir seluruhnya).
PETA_ASTA_CITA = {
    "membangun dari desa dan dari bawah untuk pemerataan ekonomi dan "
    "pemberantasan kemiskinan": "5",
}


def _peta(nilai: str, peta: dict, default: str = "") -> str:
    n = _norm(nilai)
    if n in peta:
        return peta[n]
    for k, v in peta.items():
        if k in n or n in k:
            return v
    return default


def peta_bentuk(teks: str) -> str:
    n = _norm(teks)
    if "tata kelola" in n:
        return "tata_kelola"
    if "pelayanan publik" in n:
        return "pelayanan_publik"
    return "lainnya"


# ======================================================== tabel indikator ==

def _tautan_untuk_sel(cell_bbox, hyperlinks) -> list:
    """Tautan (URI) yang anotasi link-nya jatuh di dalam sel tabel ini --
    satu dokumen yang judulnya melebar beberapa baris biasanya punya satu
    anotasi link per baris teks, semuanya menunjuk URL yang sama, jadi
    hasilnya di-dedup sambil mempertahankan urutan kemunculan."""
    if not cell_bbox:
        return []
    x0, top, x1, bottom = cell_bbox
    unik = []
    for h in hyperlinks:
        tengah = (h["top"] + h["bottom"]) / 2
        if top <= tengah <= bottom and x0 - 5 <= h["x0"] <= x1 + 5:
            if h["uri"] not in unik:
                unik.append(h["uri"])
    return unik


def extract_baris_indikator(pdf) -> list:
    """(nama, informasi, bukti, tautan) per baris tabel, digabung lintas
    halaman -- tabel terpotong di batas halaman menghasilkan baris
    lanjutan dengan kolom "No." kosong; baris semacam itu disambung ke
    baris terakhir. `tautan` diambil dari anotasi link PDF yang jatuh di
    sel kolom "Bukti Dukung" (kolom ke-4) -- lihat `_tautan_untuk_sel`."""
    baris = []
    for page in pdf.pages:
        hyperlinks = page.hyperlinks or []
        for tabel in page.find_tables():
            teks_baris = tabel.extract()
            for row, bbox_baris in zip(teks_baris, tabel.rows):
                row = [(c or "").strip() for c in (list(row) + [""] * 4)[:4]]
                no, nama, info, bukti = row
                if no == "No." or not any(row):
                    continue
                if no and not nama and not info and not bukti:
                    # bukan baris tabel indikator sungguhan -- ini "tabel"
                    # satu-kolom yang keliru terdeteksi pdfplumber pada
                    # halaman narasi (profil 1.1-1.21), bukan tabel indikator.
                    continue
                cell_bukti = bbox_baris.cells[3] if len(bbox_baris.cells) > 3 else None
                tautan = _tautan_untuk_sel(cell_bukti, hyperlinks)
                if no:
                    baris.append({"nama": nama.replace("\n", " "),
                                  "informasi": info.replace("\n", " "),
                                  "bukti": bukti.replace("\n", " "),
                                  "tautan": tautan})
                elif baris:
                    if nama:
                        baris[-1]["nama"] += " " + nama.replace("\n", " ")
                    if info:
                        baris[-1]["informasi"] += " " + info.replace("\n", " ")
                    if bukti:
                        baris[-1]["bukti"] += " " + bukti.replace("\n", " ")
                    for u in tautan:
                        if u not in baris[-1]["tautan"]:
                            baris[-1]["tautan"].append(u)
    return baris


# Enam baris "basis ukur" indikator 33 (Lampiran II butir 33 a-f) muncul di
# laporan sebagai baris tabel tersendiri dengan kalimat panjang pada kolom
# "Indikator SID", bukan sebagai nama indikator biasa -- dikenali lewat kata
# kunci, bukan posisi, supaya tidak bergantung urutan baris di laporan.
POLA_BASIS_33 = [
    ("a", r"daftar penerima manfaat|jumlah pengguna.*penerima manfaat"),
    ("b", r"perbandingan rekapitulasi jumlah unit"),
    ("c", r"laporan belanja"),
    ("d", r"laporan keuangan"),
    ("e", r"perbandingan rekapitulasi jumlah produk"),
    ("f", r"dampak atau perubahan yang terukur|tren capaian"),
]

AMBANG_NAMA = 0.55


def cocokkan_baris(baris_list: list, indikator_sid: list) -> tuple:
    """-> (dict indikator_id -> {indikator, informasi, bukti, basis, skor_nama},
    list baris yang tidak berhasil dicocokkan ke indikator manapun)."""
    ind33 = next((i for i in indikator_sid if i.nomor == 33), None)
    hasil, tak_cocok, kandidat_33 = {}, [], []

    for b in baris_list:
        basis_cocok = next((kode for kode, pola in POLA_BASIS_33
                            if re.search(pola, b["nama"], re.IGNORECASE)), None)
        if basis_cocok:
            kandidat_33.append((basis_cocok, b))
            continue
        terbaik, skor_terbaik = None, 0.0
        for ind in indikator_sid:
            skor = _mirip(b["nama"], ind.nama)
            if skor > skor_terbaik:
                terbaik, skor_terbaik = ind, skor
        if terbaik and skor_terbaik >= AMBANG_NAMA:
            hasil[terbaik.id] = {"indikator": terbaik, "informasi": b["informasi"],
                                 "bukti": b["bukti"], "tautan": b.get("tautan", []),
                                 "basis": "", "skor_nama": skor_terbaik}
        else:
            tak_cocok.append((b, skor_terbaik, terbaik.nama if terbaik else None))

    if ind33 and kandidat_33:
        terisi = [(kode, b) for kode, b in kandidat_33
                  if b["informasi"].strip() not in ("", "-")
                  and b["bukti"].strip().lower() != "tidak tersedia"]
        kode, b = terisi[0] if terisi else kandidat_33[0]
        hasil[ind33.id] = {"indikator": ind33, "informasi": b["informasi"],
                           "bukti": b["bukti"], "tautan": b.get("tautan", []),
                           "basis": kode, "skor_nama": 1.0}
    return hasil, tak_cocok


# =============================================================== command ===

@dataclass
class HasilImpor:
    berkas: str
    nama_inovasi: str = ""
    status: str = ""          # dibuat / diperbarui / dilewati / gagal
    pesan: str = ""
    keyakinan_rendah: list = field(default_factory=list)   # (kode, nama, info, skor)
    tak_cocok: list = field(default_factory=list)
    tertaut: int = 0
    perlu_bukti_manual: list = field(default_factory=list)  # (kode, nama) tanpa tautan


class Command(BaseCommand):
    help = ("Impor inovasi dari berkas PDF 'Laporan Inovasi Daerah' (IGA/BSKDN) -- "
            "dipakai memulihkan data setelah database hilang.")

    def add_arguments(self, parser):
        parser.add_argument("sumber", nargs="+",
                            help="Berkas .pdf, atau folder berisi banyak .pdf")
        parser.add_argument("--tahun", type=int, default=None,
                            help="Tahun periode tujuan (default: periode aktif)")
        parser.add_argument("--opd", type=str, default=None,
                            help="Kode OPD cadangan bila nama inisiator di PDF "
                                 "tidak cocok dengan OPD manapun")
        parser.add_argument("--status", type=str, default="terverifikasi",
                            choices=["draft", "diajukan", "revisi", "terverifikasi"],
                            help="Status awal inovasi yang diimpor (default: terverifikasi, "
                                 "karena data ini sudah pernah teregistrasi ke BSKDN)")
        parser.add_argument("--pengguna", type=str, default=None,
                            help="Username yang dicatat sebagai pembuat/pemverifikasi "
                                 "(default: superuser pertama yang ditemukan)")
        parser.add_argument("--perbarui", action="store_true",
                            help="Timpa inovasi yang namanya sudah ada di OPD+periode yang sama "
                                 "(default: dilewati supaya aman dijalankan berulang)")
        parser.add_argument("--dry-run", action="store_true",
                            help="Pratinjau saja -- parsing dan pencocokan ditampilkan, "
                                 "tidak ada yang disimpan ke database")

    # -------------------------------------------------------------- utama --

    def handle(self, *args, **opsi):
        if pdfplumber is None:
            raise CommandError(
                "Paket 'pdfplumber' belum terpasang. Jalankan dulu:\n"
                "  pip install pdfplumber"
            )

        berkas_pdf = self._kumpulkan_berkas(opsi["sumber"])
        if not berkas_pdf:
            raise CommandError("Tidak ada berkas .pdf ditemukan dari argumen yang diberikan.")

        periode = self._ambil_periode(opsi["tahun"])
        indikator_sid = list(periode.indikator.filter(aspek=Indikator.SID, aktif=True))
        if not indikator_sid:
            raise CommandError(
                f"Periode {periode.tahun} belum punya katalog indikator SID. "
                f"Jalankan dulu: python manage.py seed_simonda --tahun {periode.tahun}"
            )
        pengguna = self._ambil_pengguna(opsi["pengguna"])
        opd_cadangan = self._ambil_opd(opsi["opd"]) if opsi["opd"] else None

        hasil_semua = []
        for path in berkas_pdf:
            self.stdout.write(f"\n--- {path.name} ---")
            try:
                hasil = self._proses_satu_berkas(
                    path, periode, indikator_sid, pengguna, opd_cadangan, opsi)
            except Exception as e:  # noqa: BLE001 -- satu berkas gagal tidak menghentikan yang lain
                hasil = HasilImpor(berkas=path.name, status="gagal", pesan=str(e))
                self.stderr.write(self.style.ERROR(f"  Gagal: {e}"))
            hasil_semua.append(hasil)

        self._cetak_ringkasan(hasil_semua, opsi["dry_run"])

    # ----------------------------------------------------------- pembantu --

    def _kumpulkan_berkas(self, sumber) -> list:
        berkas = []
        for s in sumber:
            p = Path(s)
            if p.is_dir():
                berkas.extend(sorted(p.glob("*.pdf")))
            elif p.is_file() and p.suffix.lower() == ".pdf":
                berkas.append(p)
            else:
                self.stderr.write(self.style.WARNING(f"Dilewati, bukan PDF: {s}"))
        return berkas

    def _ambil_periode(self, tahun) -> Periode:
        if tahun:
            try:
                return Periode.objects.get(tahun=tahun)
            except Periode.DoesNotExist:
                raise CommandError(
                    f"Periode {tahun} belum ada. Jalankan dulu: "
                    f"python manage.py seed_simonda --tahun {tahun}")
        periode = Periode.objects.filter(aktif=True).first()
        if not periode:
            raise CommandError("Belum ada periode aktif. Berikan --tahun atau jalankan "
                               "seed_simonda dulu.")
        return periode

    def _ambil_pengguna(self, username) -> Optional[User]:
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f"Pengguna '{username}' tidak ditemukan.")
        return User.objects.filter(is_superuser=True).order_by("id").first()

    def _ambil_opd(self, kode) -> OPD:
        try:
            return OPD.objects.get(kode__iexact=kode)
        except OPD.DoesNotExist:
            raise CommandError(f"OPD dengan kode '{kode}' tidak ditemukan.")

    def _cocokkan_opd(self, nama_inisiator: str, urusan: str, dibuat_oleh: str,
                      cadangan: Optional[OPD]) -> tuple:
        """-> (OPD atau None, catatan).

        Bila "1.4 Inisiator Inovasi Daerah" == OPD, "1.5 Nama Inisiator" betul-
        betul nama OPD-nya dan gampang dicocokkan (langkah 1-2). Tapi bila
        inisiatornya ASN atau Kepala Daerah, "1.5 Nama Inisiator" cuma nama
        ORANG -- dalam keadaan itu "1.9 Urusan Inovasi Daerah" (mis.
        "pekerjaan umum dan penataan ruang") jauh lebih dekat ke nama resmi
        OPD-nya (langkah 3). Kalau urusannya juga terlalu umum untuk satu OPD
        (mis. "Keuangan, Fungsi Penunjang lainnya..." -- bisa banyak OPD),
        langkah terakhir memakai tag akun pada "1.2 Dibuat Oleh", mis.
        "INSPEKTORAT_Yessi" atau "KESBANG_INGE" -- potongan sebelum "_"
        hampir selalu kode/singkatan OPD si pembuat akun (langkah 4)."""
        opd_aktif = list(OPD.objects.filter(aktif=True))
        n = (nama_inisiator or "").strip()

        if n:
            for opd in opd_aktif:
                if _norm(opd.kode) == _norm(n) or _norm(opd.singkatan) == _norm(n):
                    return opd, f"kode OPD persis '{n}'"
            terbaik, skor = max(
                ((opd, max(_mirip(n, opd.nama), _mirip(n, opd.kode), _mirip(n, opd.singkatan)))
                 for opd in opd_aktif), key=lambda x: x[1], default=(None, 0.0))
            if terbaik and skor >= 0.6:
                return terbaik, f"nama inisiator '{n}' (keyakinan {skor:.0%})"

        # Tag akun pada "1.2 Dibuat Oleh" (mis. "PETERNAKAN_MARLIN") dihitung
        # di sini juga, TAPI cuma dipakai langsung kalau langkah urusan di
        # bawah gagal -- tag itu nama AKUN PORTAL, bukan selalu OPD pemilik
        # resminya (satu staf admin kadang membantu input laporan untuk
        # beberapa OPD berbeda, terbukti di data nyata: akun yang sama
        # pernah dipakai untuk laporan Inspektorat MAUPUN laporan Keuangan).
        # Kalau langkah urusan berhasil tapi tag menunjuk OPD LAIN, itu
        # dilaporkan sebagai dugaan konflik untuk diperiksa manual, bukan
        # ditimpa begitu saja oleh salah satu sinyal.
        opd_dari_tag, tag_cocok = None, ""
        m = re.search(r"\(([^)]+)\)", dibuat_oleh or "")
        if m:
            tag_cocok = _norm(re.split(r"[_\s]", m.group(1).strip())[0])
            if tag_cocok in _ALIAS_TAG_OPD:
                opd_dari_tag = next((o for o in opd_aktif
                                     if o.kode == _ALIAS_TAG_OPD[tag_cocok]), None)
            elif len(tag_cocok) >= 4:
                cocok = [opd for opd in opd_aktif
                         if tag_cocok in _norm(opd.kode) or _norm(opd.kode) in tag_cocok
                         or (opd.singkatan and tag_cocok in _norm(opd.singkatan))]
                opd_dari_tag = cocok[0] if len(cocok) == 1 else None

        u = (urusan or "").strip()
        if u:
            kandidat_urusan, catatan_urusan = None, ""
            for opd in opd_aktif:
                if _norm(u) and _norm(u) in _norm(opd.nama):
                    kandidat_urusan, catatan_urusan = opd, f"cocok persis dengan urusan '{u}'"
                    break
            if not kandidat_urusan:
                skor_opd = sorted(((opd, _mirip_kata(u, opd.nama)) for opd in opd_aktif),
                                  key=lambda x: -x[1])
                if len(skor_opd) >= 2 and skor_opd[0][1] >= 0.5 and \
                   skor_opd[0][1] - skor_opd[1][1] >= 0.15:
                    opd, skor = skor_opd[0]
                    kandidat_urusan = opd
                    catatan_urusan = f"dari urusan '{u}' (keyakinan {skor:.0%}), BUKAN dari nama inisiator"
            if kandidat_urusan:
                if opd_dari_tag and opd_dari_tag.id != kandidat_urusan.id:
                    catatan_urusan += (
                        f" -- PERIKSA: tag akun pembuat '{tag_cocok}' justru menunjuk "
                        f"'{opd_dari_tag.nama}' ({opd_dari_tag.kode}), kemungkinan konflik; "
                        f"pakai --opd kalau urusan di atas keliru")
                return kandidat_urusan, catatan_urusan

        if opd_dari_tag:
            return opd_dari_tag, f"dari tag akun pembuat '{tag_cocok}' pada 1.2 Dibuat Oleh"

        return cadangan, (f"inisiator '{n or '-'}' / urusan '{u or '-'}' / tag akun "
                          f"'{dibuat_oleh or '-'}' tidak cocok OPD manapun")

    # ------------------------------------------------------- satu berkas --

    def _proses_satu_berkas(self, path, periode, indikator_sid, pengguna,
                            opd_cadangan, opsi) -> HasilImpor:
        with pdfplumber.open(str(path)) as pdf:
            teks_penuh = "\n".join(p.extract_text() or "" for p in pdf.pages)
            baris = extract_baris_indikator(pdf)

        if not teks_penuh.strip():
            return HasilImpor(berkas=path.name, status="gagal",
                              pesan="tidak ada teks terbaca (PDF hasil pindai/gambar?)")

        h = parse_header(teks_penuh)
        no_registrasi = parse_no_registrasi(teks_penuh)
        nama = h.get("nama", "").strip()
        if not nama:
            return HasilImpor(berkas=path.name, status="gagal",
                              pesan="kolom 1.1 Nama Inovasi tidak terbaca")

        opd, catatan_opd = self._cocokkan_opd(
            h.get("nama_inisiator", ""), h.get("urusan", ""),
            h.get("dibuat_oleh", ""), opd_cadangan)
        if not opd:
            return HasilImpor(berkas=path.name, nama_inovasi=nama, status="gagal",
                              pesan=f"OPD tidak dapat ditentukan ({catatan_opd}); "
                                    f"ulangi dengan --opd <kode>")
        self.stdout.write(f"  OPD: {opd.nama} ({catatan_opd})")

        lintang, bujur = parse_koordinat(h.get("koordinat", ""))
        data_inovasi = dict(
            nama=nama,
            tahapan=_peta(h.get("tahapan", ""), PETA_TAHAPAN, "penerapan"),
            inisiator=_peta(h.get("inisiator", ""), PETA_INISIATOR, "perangkat_daerah"),
            nama_inisiator=h.get("nama_inisiator", "").strip(),
            klasifikasi=_peta(h.get("klasifikasi", ""), PETA_KLASIFIKASI, "perangkat_daerah"),
            jenis=_peta(h.get("jenis", ""), PETA_JENIS, "non_digital"),
            bentuk=peta_bentuk(h.get("bentuk", "")),
            urusan=h.get("urusan", "").strip(),
            lintang=lintang, bujur=bujur,
            asta_cita=PETA_ASTA_CITA.get(_norm(h.get("asta_cita_teks", "")), ""),
            mulai_uji_coba=parse_tanggal(h.get("mulai_uji_coba", "")),
            mulai_penerapan=parse_tanggal(h.get("mulai_penerapan", "")),
            rancang_bangun=h.get("rancang_bangun", "").strip(),
            tujuan=h.get("tujuan", "").strip(),
            manfaat=h.get("manfaat", "").strip(),
            hasil=h.get("hasil", "").strip(),
            anggaran=parse_anggaran(h.get("anggaran", "")),
            pic_nama=h.get("dibuat_oleh", "").strip(),
            catatan_internal=(
                f"Diimpor otomatis dari laporan PDF ({path.name})"
                + (f", No. Registrasi {no_registrasi}" if no_registrasi else "")
                + f". Kematangan menurut laporan asli: {h.get('kematangan', '-')}."
                  f" OPD ditentukan dari: {catatan_opd}."
                  " Bukti dukung yang tidak otomatis tertaut perlu diunggah ulang/"
                  "ditautkan manual -- lihat catatan tiap baris di tab bukti dukung."
            ),
            status=opsi["status"],
        )

        hasil_cocok, tak_cocok = cocokkan_baris(baris, indikator_sid)

        existing = Inovasi.objects.filter(periode=periode, opd=opd, nama=nama).first()
        if existing and not opsi["perbarui"]:
            return HasilImpor(berkas=path.name, nama_inovasi=nama, status="dilewati",
                              pesan="sudah ada (pakai --perbarui untuk menimpa)")

        keyakinan_rendah, tertaut, perlu_bukti_manual = [], 0, []
        for info in hasil_cocok.values():
            ind = info["indikator"]
            pilihan, skor = tentukan_pilihan(ind, info["informasi"], info["basis"])
            info["pilihan"], info["skor_pilihan"] = pilihan, skor
            if pilihan and skor < 0.6:
                keyakinan_rendah.append((ind.kode, ind.nama, info["informasi"], skor))
            if pilihan:
                if info.get("tautan"):
                    tertaut += 1
                elif info["bukti"] and info["bukti"].strip().lower() != "tidak tersedia":
                    perlu_bukti_manual.append((ind.kode, ind.nama))

        if opsi["dry_run"]:
            self.stdout.write(f"  [dry-run] akan {'memperbarui' if existing else 'membuat'} "
                              f"'{nama}' ({opd.kode}, status={opsi['status']}), "
                              f"{len(hasil_cocok)}/{len(indikator_sid)} indikator cocok, "
                              f"{len(tak_cocok)} baris tak cocok")
            return HasilImpor(berkas=path.name, nama_inovasi=nama,
                              status="pratinjau", keyakinan_rendah=keyakinan_rendah,
                              tak_cocok=tak_cocok, tertaut=tertaut,
                              perlu_bukti_manual=perlu_bukti_manual)

        with transaction.atomic():
            if existing:
                for k, v in data_inovasi.items():
                    setattr(existing, k, v)
                existing.save()
                inv = existing
                aksi = "diperbarui"
            else:
                inv = Inovasi.objects.create(
                    periode=periode, opd=opd, dibuat_oleh=pengguna,
                    diverifikasi_oleh=pengguna if opsi["status"] == "terverifikasi" else None,
                    **data_inovasi)
                aksi = "dibuat"

            for info in hasil_cocok.values():
                ind, pilihan = info["indikator"], info["pilihan"]
                tautan = info.get("tautan") or []
                n, _ = NilaiSID.objects.get_or_create(inovasi=inv, indikator=ind)
                n.pilihan = pilihan
                n.basis_ukur = info["basis"]
                n.diperbarui_oleh = pengguna
                if tautan:
                    n.tautan = tautan[0][:500]
                catatan = (
                    f"[Impor otomatis, keyakinan pilihan {info['skor_pilihan']:.0%}] "
                    f"Teks sumber: \u201c{info['informasi']}\u201d."
                )
                if info["bukti"] and info["bukti"].strip().lower() != "tidak tersedia":
                    if tautan:
                        catatan += f" Bukti dukung: {info['bukti']} -- tautan terlampir otomatis."
                        if len(tautan) > 1:
                            catatan += (" Dokumen ini punya tautan lain pada laporan asli "
                                       f"yang belum terlampir di sini: {', '.join(tautan[1:])}.")
                    else:
                        catatan += (f" Bukti dukung pada laporan asli (PERLU diunggah ulang/"
                                   f"ditautkan manual, tidak ada anotasi tautan yang ditemukan "
                                   f"untuk baris ini): {info['bukti']}.")
                n.catatan = catatan
                n.save()

            LogAktivitas.catat(pengguna, f"impor PDF ({aksi})", inv.id,
                               f"{path.name} -> {inv.nama}")

        self.stdout.write(self.style.SUCCESS(
            f"  {aksi.capitalize()}: '{nama}' ({opd.kode}) -- "
            f"{len(hasil_cocok)}/{len(indikator_sid)} indikator terisi, "
            f"{tertaut} dengan tautan bukti dukung otomatis"))
        return HasilImpor(berkas=path.name, nama_inovasi=nama, status=aksi,
                          keyakinan_rendah=keyakinan_rendah, tak_cocok=tak_cocok,
                          tertaut=tertaut, perlu_bukti_manual=perlu_bukti_manual)

    # ------------------------------------------------------------ laporan --

    def _cetak_ringkasan(self, hasil_semua, dry_run):
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("RINGKASAN"))
        for status in ("dibuat", "diperbarui", "pratinjau", "dilewati", "gagal"):
            kelompok = [h for h in hasil_semua if h.status == status]
            if kelompok:
                self.stdout.write(f"  {status}: {len(kelompok)}")
                for h in kelompok:
                    ket = f" -- {h.pesan}" if h.pesan else ""
                    self.stdout.write(f"    - {h.berkas} ({h.nama_inovasi}){ket}")

        perlu_periksa = [(h.berkas, *t) for h in hasil_semua for t in h.keyakinan_rendah]
        if perlu_periksa:
            self.stdout.write(self.style.WARNING(
                f"\n{len(perlu_periksa)} indikator terisi dengan keyakinan rendah "
                "(< 60%) -- periksa manual nilainya di SANDO:"))
            for berkas, kode, nama_ind, info, skor in perlu_periksa:
                self.stdout.write(f"    [{berkas}] {kode} {nama_ind}: "
                                  f"\u201c{info}\u201d (keyakinan {skor:.0%})")

        tak_cocok_semua = [(h.berkas, *t) for h in hasil_semua for t in h.tak_cocok]
        if tak_cocok_semua:
            self.stdout.write(self.style.WARNING(
                f"\n{len(tak_cocok_semua)} baris tabel tidak berhasil dicocokkan ke "
                "indikator manapun -- isi manual lewat formulir SANDO:"))
            for berkas, b, skor, terdekat in tak_cocok_semua:
                self.stdout.write(f"    [{berkas}] '{b['nama']}'"
                                  + (f" (paling mirip: '{terdekat}', {skor:.0%})"
                                     if terdekat else ""))

        total_tertaut = sum(h.tertaut for h in hasil_semua)
        perlu_manual = [(h.berkas, *p) for h in hasil_semua for p in h.perlu_bukti_manual]
        if total_tertaut:
            self.stdout.write(self.style.SUCCESS(
                f"\n{total_tertaut} indikator tertaut otomatis ke bukti dukung aslinya "
                "(dari anotasi tautan di PDF) -- skornya akan ikut terhitung begitu "
                "diverifikasi, tanpa perlu unggah ulang."))
        if perlu_manual:
            kata = "pratinjau" if dry_run else "tersimpan"
            self.stdout.write(self.style.WARNING(
                f"\n{len(perlu_manual)} indikator {kata} dengan pilihan terisi tapi TIDAK "
                "ditemukan anotasi tautan di PDF-nya (biasanya karena dokumen itu disebut "
                "tanpa link di laporan aslinya) -- butuh unggah berkas/tautan manual lewat "
                "SANDO agar skornya ikut terhitung:"))
            for berkas, kode, nama_ind in perlu_manual:
                self.stdout.write(f"    [{berkas}] {kode} {nama_ind}")
