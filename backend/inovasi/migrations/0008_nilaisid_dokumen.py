from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inovasi', '0007_cadangkan_bukti_terverifikasi'),
    ]

    operations = [
        migrations.AddField(
            model_name='nilaisid',
            name='nomor_dokumen',
            field=models.CharField(
                blank=True, max_length=150,
                help_text="Nomor surat/dokumen bukti dukung. Dipakai indikator 16, 17, 18, 20, "
                          "21, 22, 23, 24, 28, 31 (SK, surat penugasan, undangan, dsb)."),
        ),
        migrations.AddField(
            model_name='nilaisid',
            name='tanggal_dokumen',
            field=models.DateField(
                blank=True, null=True, help_text="Tanggal surat/dokumen bukti dukung."),
        ),
    ]
