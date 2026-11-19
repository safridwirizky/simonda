# Identitas eksternal untuk SSO Esa Office (OIDC): kolom pada User, ID perangkat
# daerah pada OPD, dan tiket masuk sekali pakai. Ditulis tangan karena Django
# tidak bisa dijalankan di lingkungan penyusunnya; `python manage.py makemigrations
# --check` harus melaporkan "No changes detected" setelah ini.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inovasi", "0009_ekstensi_berkas"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="identity_provider",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="user",
            name="external_subject",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                condition=models.Q(("external_subject", ""), _negated=True),
                fields=("identity_provider", "external_subject"),
                name="user_identitas_eksternal_unik",
            ),
        ),
        migrations.AddField(
            model_name="opd",
            name="esa_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text='ID perangkat daerah ini di Esa Office (klaim perangkat_daerah.id). Kosong bila belum dipetakan; SANDO mengisinya sendiri saat login pertama bila namanya cocok persis (lihat README, bagian SSO).',
                max_length=100,
            ),
        ),
        migrations.AddConstraint(
            model_name="opd",
            constraint=models.UniqueConstraint(
                condition=models.Q(("esa_id", ""), _negated=True),
                fields=("esa_id",),
                name="opd_esa_id_unik",
            ),
        ),
        migrations.CreateModel(
            name="TiketMasuk",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("sidik", models.CharField(max_length=64, unique=True)),
                ("tantangan", models.CharField(max_length=43)),
                ("kedaluwarsa", models.DateTimeField(db_index=True)),
                (
                    "pengguna",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
