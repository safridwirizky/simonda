import secrets
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from inovasi import iga
from inovasi.models import OPD, Indikator, Periode, User

SANDI_OPERATOR_DEFAULT = "admin123"

# SOTK Rote Ndao. (kode, nama)
DAFTAR_OPD = [
    ("SETWAN", "Sekretariat DPRD"),
    ("INSPEKTORAT", "Inspektorat"),
    ("DISDIK", "Dinas Pendidikan"),
    ("DISPORA", "Dinas Kepemudaan dan Olahraga"),
    ("DINKES", "Dinas Kesehatan"),
    ("DUKCAPIL", "Dinas Kependudukan dan Pencatatan Sipil"),
    ("DISNAKERTRANS", "Dinas Transmigrasi dan Tenaga Kerja"),
    ("DINSOS", "Dinas Sosial"),
    ("DPMD", "Dinas Pemberdayaan Masyarakat dan Desa"),
    ("DP3AP2KB", "Dinas Pemberdayaan Perempuan dan Perlindungan Anak, "
                 "Pengendalian Penduduk dan Keluarga Berencana"),
    ("DISPUSIP", "Dinas Perpustakaan dan Kearsipan"),
    ("SATPOLPP", "Satuan Polisi Pamong Praja"),
    ("BAGPEMKESRA", "Bagian Pemerintahan dan Kesejahteraan Rakyat"),
    ("BAGHUKUM", "Bagian Hukum"),
    ("BPBD", "Badan Penanggulangan Bencana Daerah"),
    ("KESBANGPOL", "Badan Kesatuan Bangsa dan Politik"),
    ("KECROTEBARAT", "Kecamatan Rote Barat"),
    ("KECROTEBARATDAYA", "Kecamatan Rote Barat Daya"),
    ("KECROTEBARATLAUT", "Kecamatan Rote Barat Laut"),
    ("KECLOBALAIN", "Kecamatan Lobalain"),
    ("KECROTETENGAH", "Kecamatan Rote Tengah"),
    ("KECPANTAIBARU", "Kecamatan Pantai Baru"),
    ("KECROTETIMUR", "Kecamatan Rote Timur"),
    ("KECROTESELATAN", "Kecamatan Rote Selatan"),
    ("KECLANDULEKO", "Kecamatan Landu Leko"),
    ("KECNDAONUSE", "Kecamatan Ndao Nuse"),
    ("KECLOAHOLU", "Kecamatan Loaholu"),
    ("DISPERKIMLH", "Dinas Perumahan, Kawasan Permukiman dan Lingkungan Hidup"),
    ("DPUPR", "Dinas Pekerjaan Umum dan Penataan Ruang"),
    ("DPMPTSP", "Dinas Penanaman Modal dan Pelayanan Terpadu Satu Pintu"),
    ("DISHUB", "Dinas Perhubungan"),
    ("DISBUDPAR", "Dinas Kebudayaan dan Pariwisata"),
    ("DISKOMINFO", "Dinas Komunikasi, Informatika, Statistik dan Persandian"),
    ("DISKOPUKMPERINDAG", "Dinas Koperasi, Usaha Kecil dan Menengah, "
                          "Perindustrian dan Perdagangan"),
    ("DISKAN", "Dinas Perikanan"),
    ("DISTANPANGAN", "Dinas Pertanian dan Ketahanan Pangan"),
    ("DISNAK", "Dinas Peternakan"),
    ("BAPPERIDA", "Badan Perencanaan Pembangunan, Riset dan Inovasi Daerah"),
    ("BAGEKBANG", "Bagian Perekonomian dan Administrasi Pembangunan"),
    ("BAGPBJ", "Bagian Pengadaan Barang/Jasa"),
    ("BKPSDM", "Badan Kepegawaian dan Pengembangan Sumber Daya Manusia Daerah"),
    ("BKAD", "Badan Keuangan dan Aset Daerah"),
    ("BAPENDA", "Badan Pendapatan Daerah"),
    ("BAGORGANISASI", "Bagian Organisasi"),
    ("BAGUMUM", "Bagian Umum"),
    ("RSUD", "Rumah Sakit Umum Daerah"),
]

class Command(BaseCommand):
    help = "Mengisi data awal: OPD, akun operator tiap OPD, periode berjalan, indikator, dan akun administrator."

    def add_arguments(self, parser):
        parser.add_argument("--tahun", type=int, default=date.today().year)
        parser.add_argument("--admin", type=str, default="admin")

    @transaction.atomic
    def handle(self, *args, **opsi):
        tahun, nama_admin = opsi["tahun"], opsi["admin"]

        opd_dibuat = []
        for kode, nama in DAFTAR_OPD:
            opd, baru = OPD.objects.get_or_create(kode=kode, defaults={"nama": nama, "singkatan": kode})
            opd_dibuat.append(opd)
        self.stdout.write(self.style.SUCCESS(f"{len(DAFTAR_OPD)} OPD siap."))

        akun_dibuat = 0
        for opd in opd_dibuat:
            username = opd.kode.lower()
            if not User.objects.filter(username=username).exists():
                user = User(username=username, peran=User.OPERATOR, opd=opd,
                           first_name=f"Operator {opd.nama}")
                user.set_password(SANDI_OPERATOR_DEFAULT)
                user.save()
                akun_dibuat += 1
        self.stdout.write(self.style.SUCCESS(
            f"{akun_dibuat} akun operator baru dibuat (dari {len(DAFTAR_OPD)} OPD). "
            f"Username = kode OPD huruf kecil, sandi awal '{SANDI_OPERATOR_DEFAULT}' untuk semua "
            "— wajib diganti sebelum dipakai sungguhan."))

        periode, baru = Periode.objects.get_or_create(tahun=tahun, defaults={"aktif": True})
        if not periode.aktif:
            periode.aktif = True
            periode.save()

        dibuat = 0
        for aspek, daftar in ((Indikator.SPD, iga.SPD), (Indikator.SID, iga.SID)):
            for nomor, sub, variabel, nama, bobot, wajib, params in daftar:
                Indikator.objects.update_or_create(
                    periode=periode, nomor=nomor, sub=sub,
                    defaults={"aspek": aspek, "variabel": variabel, "nama": nama,
                              "bobot": bobot, "wajib": wajib, "aktif": True,
                              "parameter_1": params[0], "parameter_2": params[1],
                              "parameter_3": params[2]},
                )
                dibuat += 1
        self.stdout.write(self.style.SUCCESS(
            f"Periode {tahun} aktif. {dibuat} baris indikator dimuat "
            f"({len(iga.SPD)} SPD + {len(iga.SID)} SID)."))

        if not User.objects.filter(username=nama_admin).exists():
            sandi = secrets.token_urlsafe(12)
            User.objects.create_superuser(
                username=nama_admin, password=sandi, peran=User.ADMIN, first_name="Administrator"
            )
            self.stdout.write(self.style.WARNING(
                f"\nAkun administrator dibuat.\n  Pengguna : {nama_admin}\n  Kata sandi: {sandi}\n"
                "Catat sekarang, lalu ganti setelah masuk pertama kali.\n"
            ))
        else:
            self.stdout.write("Akun administrator sudah ada, dilewati.")

        self.stdout.write(self.style.SUCCESS(
            "Selesai. Ganti sandi akun operator lewat menu Kelola Akun (verifikator) atau /admin/.\n"
            f"Ingat: laporkan minimal {periode.pembagi_minimal} inovasi dan minimal "
            f"{periode.min_urusan_yandas} dari 6 urusan wajib pelayanan dasar."
        ))
