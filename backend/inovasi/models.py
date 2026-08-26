from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator, MaxValueValidator
from django.db import models
from django.utils import timezone

from . import iga


class OPD(models.Model):
    kode = models.CharField(max_length=20, unique=True)
    nama = models.CharField(max_length=150)
    singkatan = models.CharField(max_length=40, blank=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "OPD"
        verbose_name_plural = "OPD"
        ordering = ["nama"]

    def __str__(self):
        return self.nama


class User(AbstractUser):
    """Operator OPD hanya menyentuh inovasi miliknya. Verifikator melihat semua."""

    ADMIN, VERIFIKATOR, OPERATOR = "admin", "verifikator", "operator"
    PERAN = [(ADMIN, "Administrator"), (VERIFIKATOR, "Verifikator"), (OPERATOR, "Operator OPD")]

    peran = models.CharField(max_length=20, choices=PERAN, default=OPERATOR)
    opd = models.ForeignKey(OPD, null=True, blank=True, on_delete=models.PROTECT,
                            related_name="pengguna")
    nip = models.CharField(max_length=25, blank=True)
    telepon = models.CharField(max_length=25, blank=True)

    @property
    def bisa_verifikasi(self) -> bool:
        return self.peran in (self.ADMIN, self.VERIFIKATOR)

    def __str__(self):
        return self.get_full_name() or self.username


class Periode(models.Model):
    """Satu tahun penilaian, beserta jendela pelaporan Kemendagri."""

    tahun = models.PositiveIntegerField(unique=True)
    window_buka = models.DateField(null=True, blank=True)
    window_tutup = models.DateField(null=True, blank=True)
    pembagi_minimal = models.PositiveSmallIntegerField(
        default=iga.PEMBAGI_MINIMAL,
        help_text="Jumlah inovasi pembagi rata-rata kematangan. 14 pada 2027, naik ke 16 (2028), 18 (2029).")
    min_urusan_yandas = models.PositiveSmallIntegerField(
        default=iga.MIN_URUSAN_YANDAS,
        help_text="Urusan wajib pelayanan dasar minimal. 6 (seluruhnya) mulai 2027.")
    aktif = models.BooleanField(default=False)
    catatan = models.TextField(blank=True)

    class Meta:
        ordering = ["-tahun"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.aktif:
            Periode.objects.exclude(pk=self.pk).update(aktif=False)

    def __str__(self):
        return f"Periode {self.tahun}"


class Indikator(models.Model):
    """Satu baris skor dalam Lampiran II Pedoman IGA.

    Aspek SPD diisi sekali per tahun oleh perangkat daerah yang membidangi
    inovasi. Aspek SID diisi ulang untuk setiap inovasi yang dilaporkan.
    """

    SPD, SID = "spd", "sid"
    ASPEK = [(SPD, "Satuan Pemerintah Daerah"), (SID, "Satuan Inovasi Daerah")]

    periode = models.ForeignKey(Periode, on_delete=models.CASCADE, related_name="indikator")
    aspek = models.CharField(max_length=3, choices=ASPEK)
    nomor = models.PositiveSmallIntegerField(help_text="1-15 untuk SPD, 16-35 untuk SID")
    sub = models.CharField(max_length=2, blank=True, help_text="a atau b bila indikator dipecah")
    variabel = models.CharField(max_length=60)
    nama = models.CharField(max_length=200)
    bobot = models.DecimalField(max_digits=4, decimal_places=2)
    wajib = models.BooleanField(default=False, help_text="Indikator mandatori")
    parameter_1 = models.CharField(max_length=250)
    parameter_2 = models.CharField(max_length=250)
    parameter_3 = models.CharField(max_length=250)
    panduan = models.TextField(blank=True, help_text="Dokumen dukung yang diminta juknis")
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nomor", "sub"]
        unique_together = [("periode", "nomor", "sub")]
        verbose_name_plural = "Indikator"

    @property
    def kode(self):
        return f"{self.nomor}{self.sub}"

    @property
    def skor_maks(self):
        return self.bobot * 3

    def teks_parameter(self, pilihan):
        return {1: self.parameter_1, 2: self.parameter_2, 3: self.parameter_3}.get(pilihan, "")

    def __str__(self):
        return f"{self.kode}. {self.nama}"


class NilaiSPD(models.Model):
    """Indikator tingkat daerah. Satu baris per indikator per periode."""

    periode = models.ForeignKey(Periode, on_delete=models.CASCADE, related_name="nilai_spd")
    indikator = models.ForeignKey(Indikator, on_delete=models.CASCADE, related_name="nilai_spd")
    pilihan = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(3)],
        help_text="0 belum diisi, 1-3 parameter terpilih")
    keterangan = models.TextField(blank=True)
    tautan = models.URLField(blank=True, max_length=500)
    berkas = models.FileField(upload_to="spd/%Y/", blank=True)
    diperbarui_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                        on_delete=models.SET_NULL, related_name="+")
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("periode", "indikator")]
        ordering = ["indikator__nomor", "indikator__sub"]
        verbose_name = "Nilai SPD"
        verbose_name_plural = "Nilai SPD"

    @property
    def skor(self):
        """Parameter terpilih belum menyumbang skor sampai ada berkas bukti
        dukung yang diunggah -- klaim tanpa dokumen tidak boleh terhitung."""
        if not self.berkas:
            return Decimal("0")
        return iga.skor_baris(self.indikator.bobot, self.pilihan)


class Inovasi(models.Model):
    DRAFT, DIAJUKAN, REVISI, TERVERIFIKASI = "draft", "diajukan", "revisi", "terverifikasi"
    STATUS = [(DRAFT, "Draft"), (DIAJUKAN, "Menunggu verifikasi"),
              (REVISI, "Perlu revisi"), (TERVERIFIKASI, "Terverifikasi")]
    TAHAPAN = [("inisiatif", "Inisiatif"), ("uji_coba", "Uji Coba"), ("penerapan", "Penerapan")]
    JENIS = [("digital", "Digital"), ("non_digital", "Non-Digital")]
    BENTUK = [("tata_kelola", "Inovasi Tata Kelola Pemerintahan Daerah"),
              ("pelayanan_publik", "Inovasi Pelayanan Publik"),
              ("lainnya", "Inovasi Daerah Lainnya")]
    INISIATOR = [("kepala_daerah", "Kepala Daerah"), ("dprd", "Anggota DPRD"), ("asn", "ASN"),
                 ("perangkat_daerah", "Perangkat Daerah"), ("masyarakat", "Masyarakat")]
    KLASIFIKASI = [("perangkat_daerah", "Inovasi Perangkat Daerah"),
                   ("desa", "Inovasi Desa"), ("masyarakat", "Inovasi Masyarakat")]
    ASTA_CITA = [(str(i), f"Asta Cita {i}") for i in range(1, 9)]
    PKPN = [("pangan", "Kedaulatan Pangan"), ("energi", "Kemandirian Energi dan Air"),
            ("pendidikan", "Pendidikan"), ("kesehatan", "Kesehatan"),
            ("hilirisasi", "Hilirisasi dan Industrialisasi"),
            ("infrastruktur", "Infrastruktur Perumahan dan Ketahanan Bencana"),
            ("desa", "Ekonomi Kerakyatan dan Desa"), ("kemiskinan", "Penurunan Kemiskinan"),
            ("non_pkpn", "Non PKPN")]

    periode = models.ForeignKey(Periode, on_delete=models.PROTECT, related_name="inovasi")
    opd = models.ForeignKey(OPD, on_delete=models.PROTECT, related_name="inovasi")

    nama = models.CharField(max_length=250)
    tahapan = models.CharField(max_length=20, choices=TAHAPAN, default="inisiatif")
    inisiator = models.CharField(max_length=25, choices=INISIATOR, default="perangkat_daerah")
    nama_inisiator = models.CharField(max_length=200, blank=True)
    klasifikasi = models.CharField(max_length=20, choices=KLASIFIKASI, default="perangkat_daerah")
    jenis = models.CharField(max_length=15, choices=JENIS, default="non_digital")
    bentuk = models.CharField(max_length=20, choices=BENTUK, default="pelayanan_publik")
    urusan = models.CharField(max_length=100, blank=True, help_text="Urusan pemerintahan utama")
    lintang = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    bujur = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    asta_cita = models.CharField(max_length=2, choices=ASTA_CITA, blank=True)
    pkpn_klaster = models.CharField(max_length=20, choices=PKPN, blank=True)
    pkpn_program = models.CharField(max_length=200, blank=True)

    mulai_uji_coba = models.DateField(null=True, blank=True)
    mulai_penerapan = models.DateField(null=True, blank=True)
    pengembangan_terbaru = models.DateField(
        null=True, blank=True,
        help_text="Wajib bila penerapan awal sebelum 2024 dan inovasi masih dikembangkan")

    rancang_bangun = models.TextField(blank=True, help_text="Minimal 300 kata")
    tujuan = models.TextField(blank=True)
    manfaat = models.TextField(blank=True)
    hasil = models.TextField(blank=True)

    anggaran = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    sumber_anggaran = models.CharField(max_length=100, blank=True)
    pic_nama = models.CharField(max_length=120, blank=True)
    pic_kontak = models.CharField(max_length=60, blank=True)
    catatan_internal = models.TextField(blank=True, help_text="Tidak ikut diekspor ke IGA")

    status = models.CharField(max_length=20, choices=STATUS, default=DRAFT)
    catatan_verifikasi = models.TextField(blank=True)
    diverifikasi_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                          on_delete=models.SET_NULL, related_name="verifikasi")
    diverifikasi_pada = models.DateTimeField(null=True, blank=True)
    diajukan_pada = models.DateTimeField(null=True, blank=True)

    dibuat_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                    on_delete=models.SET_NULL, related_name="inovasi_dibuat")
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-diperbarui_pada"]
        verbose_name_plural = "Inovasi"
        indexes = [models.Index(fields=["periode", "opd", "status"])]

    @property
    def bisa_diubah_opd(self) -> bool:
        return self.status in (self.DRAFT, self.REVISI)

    # ------------------------------ penilaian ------------------------------

    def _skor(self, hanya_terverifikasi: bool) -> Decimal:
        nilai = {n.indikator_id: n for n in self.nilai.all()}
        total = Decimal("0")
        for ind in self.periode.indikator.filter(aspek=Indikator.SID, aktif=True):
            n = nilai.get(ind.id)
            if not n or not n.pilihan:
                continue
            if hanya_terverifikasi and n.verifikasi != NilaiSID.DITERIMA:
                continue
            total += iga.skor_baris(ind.bobot, n.pilihan)
        return total

    @property
    def skor_klaim(self) -> Decimal:
        """Skor SID menurut OPD sendiri, dari maksimum 111."""
        return self._skor(False)

    @property
    def skor_terverifikasi(self) -> Decimal:
        """Skor SID yang sudah dibenarkan verifikator. Angka ini yang dipakai."""
        return self._skor(True)

    @property
    def persen_klaim(self) -> int:
        return round(self.skor_klaim / iga.MAKS_SID_INDIKATOR * 100)

    @property
    def persen_terverifikasi(self) -> int:
        return round(self.skor_terverifikasi / iga.MAKS_SID_INDIKATOR * 100)

    @property
    def wajib_belum_terisi(self):
        """Indikator mandatori yang masih kosong."""
        nilai = {n.indikator_id: n.pilihan for n in self.nilai.all()}
        return [ind for ind in self.periode.indikator.filter(
            aspek=Indikator.SID, wajib=True, aktif=True) if not nilai.get(ind.id)]

    @property
    def masalah_kelayakan(self):
        """Syarat umur inovasi dan panjang rancang bangun, Lampiran I butir IV.B."""
        pesan = []
        batas_awal, batas_akhir = date(2024, 1, 1), date(2025, 12, 31)
        if not self.mulai_penerapan:
            pesan.append("Waktu penerapan awal belum diisi.")
        elif self.mulai_penerapan > batas_akhir:
            pesan.append("Penerapan setelah 31 Desember 2025, belum bisa dilaporkan tahun ini.")
        elif self.mulai_penerapan < batas_awal and not self.pengembangan_terbaru:
            pesan.append("Penerapan sebelum 2024. Isi waktu pengembangan terbaru, "
                         "atau inovasi ini tidak memenuhi syarat.")
        elif self.pengembangan_terbaru and not (batas_awal <= self.pengembangan_terbaru <= batas_akhir):
            pesan.append("Pengembangan terbaru di luar rentang 2024 sampai 2025.")

        kata = len(self.rancang_bangun.split())
        if kata < 300:
            pesan.append(f"Rancang bangun baru {kata} kata, minimal 300.")
        return pesan

    @property
    def layak(self) -> bool:
        return not self.masalah_kelayakan and not self.wajib_belum_terisi

    def __str__(self):
        return self.nama


def path_bukti(instance, filename):
    return (f"bukti/{instance.inovasi.periode.tahun}/{instance.inovasi.opd.kode}/"
            f"{instance.inovasi_id}/{filename}")


class NilaiSID(models.Model):
    """Parameter terpilih untuk satu indikator pada satu inovasi, beserta bukti
    dukungnya. Pilihan 0 berarti belum diisi dan bernilai nol."""

    MENUNGGU, DITERIMA, DITOLAK = "menunggu", "diterima", "ditolak"
    VERIFIKASI = [(MENUNGGU, "Menunggu"), (DITERIMA, "Diterima"), (DITOLAK, "Ditolak")]

    inovasi = models.ForeignKey(Inovasi, on_delete=models.CASCADE, related_name="nilai")
    indikator = models.ForeignKey(Indikator, on_delete=models.CASCADE, related_name="nilai_sid")

    pilihan = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(3)],
        help_text="0 belum diisi, 1-3 parameter terpilih")
    basis_ukur = models.CharField(max_length=2, blank=True,
                                  help_text="Untuk indikator 33, basis a sampai f")
    catatan = models.TextField(blank=True)
    tautan = models.URLField(blank=True, max_length=500)
    berkas = models.FileField(
        upload_to=path_bukti, blank=True,
        validators=[FileExtensionValidator(
            ["pdf", "jpg", "jpeg", "png", "doc", "docx", "xls", "xlsx", "mp4"])])

    verifikasi = models.CharField(max_length=15, choices=VERIFIKASI, default=MENUNGGU)
    catatan_verifikator = models.TextField(blank=True)
    diverifikasi_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                          on_delete=models.SET_NULL, related_name="+")
    diperbarui_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                        on_delete=models.SET_NULL, related_name="+")
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("inovasi", "indikator")]
        ordering = ["indikator__nomor"]
        verbose_name = "Nilai SID"
        verbose_name_plural = "Nilai SID"

    @property
    def skor(self):
        return iga.skor_baris(self.indikator.bobot, self.pilihan)

    def tandai_ulang(self):
        """Nilai yang diubah OPD wajib diverifikasi ulang."""
        self.verifikasi = self.MENUNGGU
        self.catatan_verifikator = ""
        self.diverifikasi_oleh = None


class LogAktivitas(models.Model):
    """Jejak audit. Wajib ada untuk data yang dipakai pengambilan keputusan."""

    pengguna = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    aksi = models.CharField(max_length=60)
    objek = models.CharField(max_length=120, blank=True)
    ringkasan = models.TextField(blank=True)
    waktu = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-waktu"]
        verbose_name_plural = "Log aktivitas"

    @classmethod
    def catat(cls, pengguna, aksi, objek="", ringkasan=""):
        cls.objects.create(pengguna=pengguna, aksi=aksi, objek=str(objek), ringkasan=ringkasan)
