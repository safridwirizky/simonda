from django.db import migrations


def pindahkan(apps, schema_editor):
    """Salin berkas tunggal lama ke tabel banyak-berkas yang baru, supaya
    berkas yang sudah diunggah pengguna sebelum migrasi ini tidak hilang."""
    NilaiSPD = apps.get_model('inovasi', 'NilaiSPD')
    BerkasSPD = apps.get_model('inovasi', 'BerkasSPD')
    NilaiSID = apps.get_model('inovasi', 'NilaiSID')
    BerkasSID = apps.get_model('inovasi', 'BerkasSID')

    for n in NilaiSPD.objects.exclude(berkas=''):
        BerkasSPD.objects.create(
            nilai=n, berkas=n.berkas.name,
            nama_asli=n.berkas.name.rsplit('/', 1)[-1],
            diunggah_oleh=n.diperbarui_oleh,
        )

    for n in NilaiSID.objects.exclude(berkas=''):
        BerkasSID.objects.create(
            nilai=n, berkas=n.berkas.name,
            nama_asli=n.berkas.name.rsplit('/', 1)[-1],
            diunggah_oleh=n.diperbarui_oleh,
        )


def batalkan(apps, schema_editor):
    """Kebalikannya tidak masuk akal (berkas mana yang jadi 'satu-satunya'
    kalau baris punya lebih dari satu?) -- cukup no-op saat migrate mundur."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inovasi', '0003_tambah_berkas_multi'),
    ]

    operations = [
        migrations.RunPython(pindahkan, batalkan),
    ]
