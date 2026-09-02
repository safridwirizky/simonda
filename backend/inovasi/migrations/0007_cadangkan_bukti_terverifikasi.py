from django.db import migrations


def cadangkan(apps, schema_editor):
    """Untuk baris yang sudah punya keputusan (diterima/ditolak) sebelum
    migrasi ini, isi cuplikan bukti dengan kondisi SEKARANG -- supaya
    keputusan lama tidak langsung dianggap "menunggu" begitu
    verifikasi_efektif mulai dipakai. Baris baru setelah ini selalu diisi
    oleh endpoint /verifikasi saat keputusan benar-benar dibuat."""
    NilaiSID = apps.get_model('inovasi', 'NilaiSID')
    for n in NilaiSID.objects.exclude(verifikasi='menunggu'):
        n.verifikasi_bukti_berkas = sorted(n.daftar_berkas.values_list('id', flat=True))
        n.verifikasi_bukti_tautan = n.tautan
        n.verifikasi_bukti_pilihan = n.pilihan
        n.save(update_fields=[
            'verifikasi_bukti_berkas', 'verifikasi_bukti_tautan', 'verifikasi_bukti_pilihan',
        ])


def batalkan(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inovasi', '0006_pengikat_verifikasi_bukti'),
    ]

    operations = [
        migrations.RunPython(cadangkan, batalkan),
    ]
