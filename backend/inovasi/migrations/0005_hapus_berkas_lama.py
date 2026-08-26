from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inovasi', '0004_pindahkan_berkas_lama'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='nilaisid',
            name='berkas',
        ),
        migrations.RemoveField(
            model_name='nilaispd',
            name='berkas',
        ),
    ]
