from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (OPD, Indikator, Inovasi, LogAktivitas, NilaiSID, NilaiSPD,
                     Periode, User)


@admin.register(OPD)
class OPDAdmin(admin.ModelAdmin):
    list_display = ("kode", "nama", "singkatan", "aktif")
    list_filter = ("aktif",)
    search_fields = ("kode", "nama")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "get_full_name", "peran", "opd", "is_active")
    list_filter = ("peran", "opd", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Data SANDO", {"fields": ("peran", "opd", "nip", "telepon")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Data SANDO", {"fields": ("peran", "opd", "nip", "telepon")}),
    )


class IndikatorInline(admin.TabularInline):
    model = Indikator
    extra = 0
    fields = ("aspek", "nomor", "sub", "variabel", "nama", "bobot", "wajib", "aktif")


@admin.register(Periode)
class PeriodeAdmin(admin.ModelAdmin):
    list_display = ("tahun", "window_buka", "window_tutup", "aktif")
    inlines = [IndikatorInline]


class NilaiSIDInline(admin.TabularInline):
    model = NilaiSID
    extra = 0
    fields = ("indikator", "pilihan", "verifikasi", "tautan",
              "nomor_dokumen", "tanggal_dokumen", "catatan_verifikator")


@admin.register(NilaiSPD)
class NilaiSPDAdmin(admin.ModelAdmin):
    list_display = ("periode", "indikator", "pilihan", "skor")
    list_filter = ("periode",)


@admin.register(Inovasi)
class InovasiAdmin(admin.ModelAdmin):
    list_display = ("nama", "opd", "tahapan", "status", "skor_terverifikasi", "layak")
    list_filter = ("periode", "status", "tahapan", "jenis", "bentuk", "opd")
    search_fields = ("nama", "tujuan")
    inlines = [NilaiSIDInline]


@admin.register(LogAktivitas)
class LogAdmin(admin.ModelAdmin):
    list_display = ("waktu", "pengguna", "aksi", "objek", "ringkasan")
    list_filter = ("aksi",)
    readonly_fields = ("waktu", "pengguna", "aksi", "objek", "ringkasan")

    def has_add_permission(self, request):
        return False
