from django.core.management.base import BaseCommand, CommandError

from inovasi import esa_office


class Command(BaseCommand):
    help = ("Periksa SSO Esa Office (OIDC) dari server ini: setelan ESA_OFFICE_*, dokumen discovery, dan JWKS. "
            "Tidak menulis ke basis data dan tidak pernah menampilkan rahasia. Jalankan dari server SANDO "
            "yang sebenarnya, karena daftar putih domain atau pembatas IP bisa berbeda dari mesin lain.")

    def handle(self, *args, **opsi):
        if not esa_office.aktif():
            raise CommandError("ESA_OFFICE_ISSUER kosong, jadi SSO Esa Office tidak menyala. "
                               "Isi variabel ESA_OFFICE_* di backend/.env (lihat .env.example).")
        baris = esa_office.diagnosa()
        for b in baris:
            self.stdout.write(b)
        if any(("GAGAL" in b or "SALAH" in b) for b in baris):
            raise CommandError("Ada masalah pada SSO Esa Office (lihat di atas).")
        self.stdout.write(self.style.SUCCESS("\nKonfigurasi dan Esa Office terbaca dengan benar."))
