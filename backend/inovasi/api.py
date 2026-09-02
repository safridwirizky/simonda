import csv
from datetime import date, datetime, timedelta, timezone as dt_timezone
from typing import List, Optional

import jwt
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal

from ninja import File, NinjaAPI
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja.security import HttpBearer

from . import iga
from .models import (OPD, BerkasSID, BerkasSPD, Indikator, Inovasi, LogAktivitas, NilaiSID,
                     NilaiSPD, Periode, User)
from .schemas import (
    AkunOPDIn, AkunOPDOut, BuktiIn, BuktiOut, HitunganOut, IndikatorOut, InovasiDetail,
    InovasiIn, InovasiRingkas, MasukIn, NilaiSPDIn, NilaiSPDOut, OPDRingkas, PeriodeOut,
    PesanOut, ProfilOut, RekapOPDOut, ResetSandiIn, RingkasanOut, TokenOut,
    VerifikasiBuktiIn, VerifikasiInovasiIn,
)

MASA_TOKEN = timedelta(hours=12)
MAKS_BERKAS = 1 * 1024 * 1024  # 1 MB


def ekstensi_berkas(nama: str) -> str:
    return nama.rsplit(".", 1)[-1].lower() if "." in nama else ""


def pastikan_ekstensi_diizinkan(nama_berkas: str, diizinkan: list, label: str):
    if ekstensi_berkas(nama_berkas) not in diizinkan:
        raise HttpError(
            415,
            f"Tipe berkas tidak didukung untuk {label}. "
            f"Format yang diterima: {', '.join(e.upper() for e in diizinkan)}.",
        )


# ----------------------------- autentikasi ----------------------------

def buat_token(user: User) -> tuple[str, datetime]:
    kedaluwarsa = datetime.now(dt_timezone.utc) + MASA_TOKEN
    muatan = {"sub": str(user.id), "peran": user.peran, "exp": kedaluwarsa}
    return jwt.encode(muatan, settings.SECRET_KEY, algorithm="HS256"), kedaluwarsa


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        try:
            muatan = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user = User.objects.select_related("opd").get(id=muatan["sub"], is_active=True)
        except (jwt.PyJWTError, User.DoesNotExist, KeyError):
            return None
        request.user = user
        return user


api = NinjaAPI(title="SANDO Rote Ndao", version="1.0", auth=AuthBearer(), urls_namespace="simonda")


def wajib_verifikator(request):
    if not request.user.bisa_verifikasi:
        raise HttpError(403, "Hanya verifikator yang boleh melakukan tindakan ini.")


def periode_aktif() -> Periode:
    p = Periode.objects.filter(aktif=True).first()
    if not p:
        raise HttpError(409, "Belum ada periode aktif. Buka Pengaturan dan tetapkan tahun penilaian.")
    return p


def inovasi_terlihat(user: User):
    qs = Inovasi.objects.select_related("opd", "periode").prefetch_related(
        "nilai__indikator", "nilai__daftar_berkas")
    if user.bisa_verifikasi:
        return qs
    if not user.opd_id:
        return qs.none()
    return qs.filter(opd_id=user.opd_id)


def pastikan_boleh_ubah(user: User, inv: Inovasi):
    if user.bisa_verifikasi:
        return
    if inv.opd_id != user.opd_id:
        raise HttpError(403, "Inovasi ini milik OPD lain.")
    if not inv.bisa_diubah_opd:
        raise HttpError(
            409,
            "Inovasi sudah diajukan dan sedang diverifikasi. Minta verifikator mengembalikannya bila perlu diubah.",
        )


# -------------------------------- auth --------------------------------

@api.post("/auth/masuk", auth=None, response=TokenOut)
def masuk(request, data: MasukIn):
    user = authenticate(username=data.username, password=data.password)
    if not user or not user.is_active:
        raise HttpError(401, "Nama pengguna atau kata sandi salah.")
    token, kedaluwarsa = buat_token(user)
    LogAktivitas.catat(user, "masuk")
    return {"akses": token, "kedaluwarsa": kedaluwarsa}


@api.get("/auth/saya", response=ProfilOut)
def saya(request):
    u = request.user
    return {
        "id": u.id, "username": u.username, "nama": u.get_full_name() or u.username,
        "peran": u.peran, "bisa_verifikasi": u.bisa_verifikasi,
        "opd": u.opd and {"id": u.opd.id, "kode": u.opd.kode, "nama": u.opd.nama},
    }


# ------------------------------ referensi ------------------------------

@api.get("/opd", response=List[OPDRingkas])
def daftar_opd(request):
    return OPD.objects.filter(aktif=True)


@api.get("/periode", response=List[PeriodeOut])
def daftar_periode(request):
    return Periode.objects.all()


@api.get("/indikator", response=List[IndikatorOut])
def daftar_indikator(request, periode_id: Optional[int] = None):
    p = Periode.objects.filter(id=periode_id).first() if periode_id else periode_aktif()
    return p.indikator.filter(aktif=True)


# ------------------------------ akun OPD ------------------------------
# Verifikator/admin ("akun daerah") membuat dan mengelola akun operator OPD
# ("akun perangkat daerah") langsung dari SANDO. Akun verifikator/admin
# sendiri tetap dibuat lewat Django Admin — batas kepercayaan lebih tinggi.

def akun_ringkas(u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "nama": u.get_full_name() or u.username,
        "opd": {"id": u.opd.id, "kode": u.opd.kode, "nama": u.opd.nama},
        "nip": u.nip, "telepon": u.telepon, "is_active": u.is_active,
    }


def validasi_sandi(password: str, user: Optional[User] = None):
    try:
        validate_password(password, user=user)
    except DjangoValidationError as e:
        raise HttpError(400, "; ".join(e.messages))


@api.get("/akun-opd", response=List[AkunOPDOut])
def daftar_akun_opd(request):
    wajib_verifikator(request)
    return [akun_ringkas(u) for u in
            User.objects.filter(peran=User.OPERATOR).select_related("opd")
            .order_by("opd__nama", "username")]


@api.post("/akun-opd", response={201: AkunOPDOut})
def buat_akun_opd(request, data: AkunOPDIn):
    wajib_verifikator(request)
    opd = get_object_or_404(OPD, id=data.opd_id, aktif=True)
    if User.objects.filter(username=data.username).exists():
        raise HttpError(400, "Username sudah dipakai.")
    validasi_sandi(data.password)
    user = User(username=data.username, peran=User.OPERATOR, opd=opd,
               first_name=data.nama_depan, nip=data.nip, telepon=data.telepon)
    user.set_password(data.password)
    user.save()
    LogAktivitas.catat(request.user, "buat akun operator", user.id, f"{user.username} ({opd.kode})")
    return 201, akun_ringkas(user)


@api.post("/akun-opd/{user_id}/nonaktifkan", response=PesanOut)
def nonaktifkan_akun_opd(request, user_id: int):
    wajib_verifikator(request)
    user = get_object_or_404(User, id=user_id, peran=User.OPERATOR)
    user.is_active = False
    user.save()
    LogAktivitas.catat(request.user, "nonaktifkan akun operator", user.id, user.username)
    return {"pesan": f"Akun “{user.username}” dinonaktifkan."}


@api.post("/akun-opd/{user_id}/aktifkan", response=PesanOut)
def aktifkan_akun_opd(request, user_id: int):
    wajib_verifikator(request)
    user = get_object_or_404(User, id=user_id, peran=User.OPERATOR)
    user.is_active = True
    user.save()
    LogAktivitas.catat(request.user, "aktifkan akun operator", user.id, user.username)
    return {"pesan": f"Akun “{user.username}” diaktifkan."}


@api.post("/akun-opd/{user_id}/reset-sandi", response=PesanOut)
def reset_sandi_akun_opd(request, user_id: int, data: ResetSandiIn):
    wajib_verifikator(request)
    user = get_object_or_404(User, id=user_id, peran=User.OPERATOR)
    validasi_sandi(data.password, user=user)
    user.set_password(data.password)
    user.save()
    LogAktivitas.catat(request.user, "reset sandi akun operator", user.id, user.username)
    return {"pesan": f"Sandi akun “{user.username}” diperbarui."}


# ------------------------------- inovasi -------------------------------

def daftar_berkas(n) -> list:
    if not n:
        return []
    return [
        {"id": b.id, "url": b.berkas.url,
         "nama_asli": b.nama_asli or b.berkas.name.rsplit("/", 1)[-1],
         "diunggah_pada": b.diunggah_pada}
        for b in n.daftar_berkas.all()
    ]


def parameter_indikator(ind: Indikator, n) -> tuple:
    """Indikator 33 (Kemanfaatan Inovasi) punya 6 basis ukur alternatif
    (Lampiran II butir 33 a-f), masing-masing dengan ambang parameter 1-3
    sendiri. Basis default "a" ditampilkan sebelum OPD memilih basisnya."""
    if ind.nomor == 33:
        basis = (n.basis_ukur if n else "") or "a"
        return iga.PARAMETER_KEMANFAATAN.get(basis, iga.PARAMETER_KEMANFAATAN["a"])
    return ind.parameter_1, ind.parameter_2, ind.parameter_3


def baris_nilai(ind: Indikator, n) -> dict:
    p1, p2, p3 = parameter_indikator(ind, n)
    return {
        "indikator_id": ind.id, "kode": ind.kode, "nomor": ind.nomor,
        "variabel": ind.variabel, "nama_indikator": ind.nama,
        "bobot": ind.bobot, "wajib": ind.wajib,
        "parameter_1": p1, "parameter_2": p2, "parameter_3": p3,
        "pilihan": n.pilihan if n else 0,
        "basis_ukur": n.basis_ukur if n else "",
        "skor": n.skor if n else Decimal("0"),
        "skor_maks": ind.skor_maks,
        "catatan": n.catatan if n else "",
        "tautan": n.tautan if n else "",
        "nomor_dokumen": n.nomor_dokumen if n else "",
        "tanggal_dokumen": n.tanggal_dokumen if n else None,
        "berkas": daftar_berkas(n),
        "verifikasi": n.verifikasi_efektif if n else NilaiSID.MENUNGGU,
        "catatan_verifikator": (
            n.catatan_verifikator if (n and n.verifikasi_efektif != NilaiSID.MENUNGGU) else ""
        ),
        "diperbarui_pada": n.diperbarui_pada if n else None,
    }


def susun_bukti(inv: Inovasi) -> list:
    ada = {n.indikator_id: n for n in inv.nilai.all()}
    return [baris_nilai(ind, ada.get(ind.id))
            for ind in inv.periode.indikator.filter(aspek=Indikator.SID, aktif=True)]


def ringkas(i: Inovasi) -> dict:
    return {
        **{f: getattr(i, f) for f in
           ("id", "nama", "tahapan", "jenis", "bentuk", "urusan", "status", "diperbarui_pada")},
        "opd": {"id": i.opd.id, "kode": i.opd.kode, "nama": i.opd.nama},
        "skor_klaim": i.skor_klaim, "skor_terverifikasi": i.skor_terverifikasi,
        "persen_terverifikasi": i.persen_terverifikasi,
        "klasifikasi_kematangan": i.klasifikasi_kematangan, "layak": i.layak,
    }


def detail(inv: Inovasi, user: User) -> dict:
    data = {f.name: getattr(inv, f.name) for f in Inovasi._meta.fields
            if f.name not in ("periode", "opd", "dibuat_oleh", "diverifikasi_oleh")}
    data.update(ringkas(inv))
    data["bisa_diubah"] = user.bisa_verifikasi or (
        inv.opd_id == user.opd_id and inv.bisa_diubah_opd)
    data["masalah_kelayakan"] = inv.masalah_kelayakan
    data["wajib_belum_terisi"] = [f"{k.kode}. {k.nama}" for k in inv.wajib_belum_terisi]
    data["bukti"] = susun_bukti(inv)
    return data


@api.get("/inovasi", response=List[InovasiRingkas])
def daftar_inovasi(
    request,
    q: Optional[str] = None,
    opd_id: Optional[int] = None,
    status: Optional[str] = None,
    tahapan: Optional[str] = None,
    periode_id: Optional[int] = None,
    klasifikasi: Optional[str] = None,
):
    qs = inovasi_terlihat(request.user).filter(periode_id=periode_id or periode_aktif().id)
    if q:
        qs = qs.filter(Q(nama__icontains=q) | Q(tujuan__icontains=q) | Q(opd__nama__icontains=q))
    if opd_id:
        qs = qs.filter(opd_id=opd_id)
    if status:
        qs = qs.filter(status=status)
    if tahapan:
        qs = qs.filter(tahapan=tahapan)
    hasil = [ringkas(i) for i in qs]
    if klasifikasi:
        hasil = [r for r in hasil if r["klasifikasi_kematangan"] == klasifikasi]
    return hasil


@api.post("/inovasi", response={201: InovasiDetail})
def buat_inovasi(request, data: InovasiIn):
    user = request.user
    opd_id = user.opd_id if not user.bisa_verifikasi else data.opd_id
    if not opd_id:
        raise HttpError(400, "Pilih OPD pelaksana terlebih dahulu.")
    isi = data.dict(exclude={"opd_id"})
    inv = Inovasi.objects.create(periode=periode_aktif(), opd_id=opd_id, dibuat_oleh=user, **isi)
    LogAktivitas.catat(user, "buat inovasi", inv.id, inv.nama)
    return 201, detail(inv, user)


@api.get("/inovasi/{inovasi_id}", response=InovasiDetail)
def ambil_inovasi(request, inovasi_id: int):
    inv = get_object_or_404(inovasi_terlihat(request.user), id=inovasi_id)
    return detail(inv, request.user)


@api.put("/inovasi/{inovasi_id}", response=InovasiDetail)
def ubah_inovasi(request, inovasi_id: int, data: InovasiIn):
    inv = get_object_or_404(inovasi_terlihat(request.user), id=inovasi_id)
    pastikan_boleh_ubah(request.user, inv)
    for k, v in data.dict(exclude={"opd_id"}).items():
        setattr(inv, k, v)
    if request.user.bisa_verifikasi and data.opd_id:
        inv.opd_id = data.opd_id
    inv.save()
    LogAktivitas.catat(request.user, "ubah inovasi", inv.id, inv.nama)
    return detail(inv, request.user)


@api.delete("/inovasi/{inovasi_id}", response=PesanOut)
def hapus_inovasi(request, inovasi_id: int):
    inv = get_object_or_404(inovasi_terlihat(request.user), id=inovasi_id)
    pastikan_boleh_ubah(request.user, inv)
    nama = inv.nama
    inv.delete()
    LogAktivitas.catat(request.user, "hapus inovasi", inovasi_id, nama)
    return {"pesan": f"Inovasi \u201c{nama}\u201d dihapus."}


@api.post("/inovasi/{inovasi_id}/ajukan", response=InovasiDetail)
def ajukan(request, inovasi_id: int):
    inv = get_object_or_404(inovasi_terlihat(request.user), id=inovasi_id)
    if inv.opd_id != request.user.opd_id and not request.user.bisa_verifikasi:
        raise HttpError(403, "Inovasi ini milik OPD lain.")
    if inv.status == Inovasi.DIAJUKAN:
        raise HttpError(409, "Inovasi ini sudah diajukan.")
    if not inv.tujuan.strip():
        raise HttpError(400, "Isi kolom tujuan sebelum mengajukan.")
    inv.status = Inovasi.DIAJUKAN
    inv.diajukan_pada = timezone.now()
    inv.catatan_verifikasi = ""
    inv.save()
    LogAktivitas.catat(request.user, "ajukan inovasi", inv.id, inv.nama)
    return detail(inv, request.user)


@api.post("/inovasi/{inovasi_id}/verifikasi", response=InovasiDetail)
def verifikasi_inovasi(request, inovasi_id: int, data: VerifikasiInovasiIn):
    wajib_verifikator(request)
    inv = get_object_or_404(Inovasi, id=inovasi_id)
    if data.keputusan == "terima":
        inv.status = Inovasi.TERVERIFIKASI
    elif data.keputusan == "revisi":
        if not data.catatan.strip():
            raise HttpError(400, "Tulis catatan agar OPD tahu apa yang harus diperbaiki.")
        inv.status = Inovasi.REVISI
    else:
        raise HttpError(400, "Keputusan harus 'terima' atau 'revisi'.")
    inv.catatan_verifikasi = data.catatan
    inv.diverifikasi_oleh = request.user
    inv.diverifikasi_pada = timezone.now()
    inv.save()
    LogAktivitas.catat(request.user, f"verifikasi: {data.keputusan}", inv.id, data.catatan)
    return detail(inv, request.user)


# ------------------------- nilai indikator SID -------------------------

@api.put("/inovasi/{inovasi_id}/nilai/{indikator_id}", response=BuktiOut)
def ubah_nilai(request, inovasi_id: int, indikator_id: int, data: BuktiIn):
    inv = get_object_or_404(inovasi_terlihat(request.user), id=inovasi_id)
    pastikan_boleh_ubah(request.user, inv)
    ind = get_object_or_404(Indikator, id=indikator_id, periode=inv.periode,
                            aspek=Indikator.SID)
    if not 0 <= data.pilihan <= 3:
        raise HttpError(400, "Pilihan parameter harus 0 sampai 3.")
    if ind.nomor == 33 and data.pilihan > 0 and data.basis_ukur not in dict(iga.BASIS_KEMANFAATAN):
        raise HttpError(
            400,
            "Indikator 33 (Kemanfaatan Inovasi) wajib memilih satu basis ukur "
            "(a-f) dulu -- tiap basis punya ambang parameter yang berbeda.",
        )

    n, _ = NilaiSID.objects.get_or_create(inovasi=inv, indikator=ind)
    n.pilihan, n.catatan, n.tautan = data.pilihan, data.catatan, data.tautan
    n.basis_ukur = data.basis_ukur
    n.nomor_dokumen, n.tanggal_dokumen = data.nomor_dokumen, data.tanggal_dokumen
    n.diperbarui_oleh = request.user
    n.save()
    return baris_nilai(ind, n)


@api.post("/inovasi/{inovasi_id}/nilai/{indikator_id}/berkas", response=PesanOut)
def unggah_berkas(request, inovasi_id: int, indikator_id: int, berkas: UploadedFile = File(...)):
    inv = get_object_or_404(inovasi_terlihat(request.user), id=inovasi_id)
    pastikan_boleh_ubah(request.user, inv)
    if berkas.size > MAKS_BERKAS:
        raise HttpError(413, "Ukuran berkas melebihi 1 MB. Kecilkan dulu atau kirim tautan.")
    ind = get_object_or_404(Indikator, id=indikator_id, periode=inv.periode)
    pastikan_ekstensi_diizinkan(
        berkas.name, iga.ekstensi_sid_diizinkan(ind.nomor), f"indikator {ind.kode}")
    n, _ = NilaiSID.objects.get_or_create(inovasi=inv, indikator=ind)
    BerkasSID.objects.create(nilai=n, berkas=berkas, nama_asli=berkas.name,
                             diunggah_oleh=request.user)
    n.diperbarui_oleh = request.user
    n.save()
    LogAktivitas.catat(request.user, "unggah bukti", inv.id, str(ind))
    return {"pesan": "Berkas tersimpan."}


@api.delete("/inovasi/{inovasi_id}/nilai/{indikator_id}/berkas/{berkas_id}", response=PesanOut)
def hapus_berkas(request, inovasi_id: int, indikator_id: int, berkas_id: int):
    inv = get_object_or_404(inovasi_terlihat(request.user), id=inovasi_id)
    pastikan_boleh_ubah(request.user, inv)
    ind = get_object_or_404(Indikator, id=indikator_id, periode=inv.periode)
    b = get_object_or_404(BerkasSID, id=berkas_id, nilai__inovasi=inv, nilai__indikator=ind)
    b.berkas.delete(save=False)
    b.delete()
    LogAktivitas.catat(request.user, "hapus bukti", inv.id, str(ind))
    return {"pesan": "Berkas dihapus."}


@api.post("/inovasi/{inovasi_id}/nilai/{indikator_id}/verifikasi", response=BuktiOut)
def verifikasi_nilai(request, inovasi_id: int, indikator_id: int, data: VerifikasiBuktiIn):
    wajib_verifikator(request)
    if data.keputusan not in dict(NilaiSID.VERIFIKASI):
        raise HttpError(400, "Keputusan tidak dikenali.")
    inv = get_object_or_404(Inovasi, id=inovasi_id)
    ind = get_object_or_404(Indikator, id=indikator_id, periode=inv.periode)
    n, _ = NilaiSID.objects.get_or_create(inovasi=inv, indikator=ind)
    if data.keputusan == NilaiSID.DITOLAK and not data.catatan.strip():
        raise HttpError(400, "Tulis alasan penolakan agar OPD tahu perbaikannya.")
    n.verifikasi, n.catatan_verifikator = data.keputusan, data.catatan
    n.diverifikasi_oleh = request.user
    # Cuplikan bukti yang sedang diperiksa verifikator saat ini juga -- kalau
    # nanti berkas/tautan/pilihan berubah, verifikasi_efektif otomatis
    # mendeteksinya dan mengembalikan status ke "menunggu".
    n.verifikasi_bukti_berkas = sorted(b.id for b in n.daftar_berkas.all())
    n.verifikasi_bukti_tautan = n.tautan
    n.verifikasi_bukti_pilihan = n.pilihan
    n.save()
    LogAktivitas.catat(request.user, f"nilai {data.keputusan}", inv.id, str(ind))
    return baris_nilai(ind, n)


# ------------------------- indikator SPD daerah -------------------------

@api.get("/spd", response=List[NilaiSPDOut])
def daftar_spd(request):
    wajib_verifikator(request)
    p = periode_aktif()
    ada = {n.indikator_id: n for n in p.nilai_spd.prefetch_related("daftar_berkas")}
    keluar = []
    for ind in p.indikator.filter(aspek=Indikator.SPD, aktif=True):
        n = ada.get(ind.id)
        keluar.append({
            "indikator_id": ind.id, "kode": ind.kode, "variabel": ind.variabel,
            "nama": ind.nama, "bobot": ind.bobot, "wajib": ind.wajib,
            "parameter_1": ind.parameter_1, "parameter_2": ind.parameter_2,
            "parameter_3": ind.parameter_3,
            "pilihan": n.pilihan if n else 0,
            "skor": n.skor if n else Decimal("0"), "skor_maks": ind.skor_maks,
            "keterangan": n.keterangan if n else "", "tautan": n.tautan if n else "",
            "berkas": daftar_berkas(n),
        })
    return keluar


@api.put("/spd/{indikator_id}", response=PesanOut)
def ubah_spd(request, indikator_id: int, data: NilaiSPDIn):
    wajib_verifikator(request)
    p = periode_aktif()
    ind = get_object_or_404(Indikator, id=indikator_id, periode=p, aspek=Indikator.SPD)
    if not 0 <= data.pilihan <= 3:
        raise HttpError(400, "Pilihan parameter harus 0 sampai 3.")
    n, _ = NilaiSPD.objects.get_or_create(periode=p, indikator=ind)
    n.pilihan, n.keterangan, n.tautan = data.pilihan, data.keterangan, data.tautan
    n.diperbarui_oleh = request.user
    n.save()
    LogAktivitas.catat(request.user, "ubah nilai SPD", ind.kode, ind.nama)
    return {"pesan": f"Indikator {ind.kode} tersimpan."}


@api.post("/spd/{indikator_id}/berkas", response=PesanOut)
def unggah_berkas_spd(request, indikator_id: int, berkas: UploadedFile = File(...)):
    wajib_verifikator(request)
    if berkas.size > MAKS_BERKAS:
        raise HttpError(413, "Ukuran berkas melebihi 1 MB. Kecilkan dulu atau kirim tautan.")
    pastikan_ekstensi_diizinkan(berkas.name, iga.EKSTENSI_SPD, "indikator SPD")
    p = periode_aktif()
    ind = get_object_or_404(Indikator, id=indikator_id, periode=p, aspek=Indikator.SPD)
    n, _ = NilaiSPD.objects.get_or_create(periode=p, indikator=ind)
    BerkasSPD.objects.create(nilai=n, berkas=berkas, nama_asli=berkas.name,
                             diunggah_oleh=request.user)
    n.diperbarui_oleh = request.user
    n.save(update_fields=["diperbarui_oleh", "diperbarui_pada"])
    LogAktivitas.catat(request.user, "unggah bukti SPD", ind.kode, ind.nama)
    return {"pesan": "Berkas tersimpan."}


@api.delete("/spd/{indikator_id}/berkas/{berkas_id}", response=PesanOut)
def hapus_berkas_spd(request, indikator_id: int, berkas_id: int):
    wajib_verifikator(request)
    p = periode_aktif()
    ind = get_object_or_404(Indikator, id=indikator_id, periode=p, aspek=Indikator.SPD)
    b = get_object_or_404(BerkasSPD, id=berkas_id, nilai__indikator=ind, nilai__periode=p)
    b.berkas.delete(save=False)
    b.delete()
    LogAktivitas.catat(request.user, "hapus bukti SPD", ind.kode, ind.nama)
    return {"pesan": "Berkas dihapus."}


# ------------------------------ statistik ------------------------------

def hitung_skor_spd(periode) -> Decimal:
    return sum((n.skor for n in periode.nilai_spd.select_related("indikator")), Decimal("0"))


def urusan_yandas_terisi(daftar) -> list:
    dipakai = {i.urusan.strip().lower() for i in daftar if i.urusan}
    return [u for u in iga.URUSAN_YANDAS if u.lower() in dipakai]


def proyeksi(periode, daftar, terverifikasi: bool) -> dict:
    """Proyeksi indeks. Bila terverifikasi, hanya nilai yang sudah disetujui
    verifikator dan inovasi yang lolos syarat kelayakan yang dihitung."""
    dipakai = [i for i in daftar if i.layak] if terverifikasi else list(daftar)
    skor = [i.skor_terverifikasi if terverifikasi else i.skor_klaim for i in dipakai]
    terisi = urusan_yandas_terisi(dipakai)
    hasil = iga.hitung_indeks(hitung_skor_spd(periode), skor, len(terisi))
    hasil["skor_spd_maks"] = iga.MAKS_SPD
    hasil["yandas_terisi"] = terisi
    hasil["yandas_kosong"] = [u for u in iga.URUSAN_YANDAS if u not in terisi]
    return hasil


@api.get("/statistik/ringkasan", response=RingkasanOut)
def ringkasan(request):
    p = periode_aktif()
    qs = list(inovasi_terlihat(request.user).filter(periode=p))

    def hitung(field, pilihan):
        return [{"label": label, "jumlah": sum(1 for i in qs if getattr(i, field) == kode)}
                for kode, label in pilihan]

    return {
        "tahun": p.tahun,
        "total_inovasi": len(qs),
        "layak": sum(1 for i in qs if i.layak),
        "menunggu_verifikasi": sum(1 for i in qs if i.status == Inovasi.DIAJUKAN),
        "terverifikasi": sum(1 for i in qs if i.status == Inovasi.TERVERIFIKASI),
        "opd_terlibat": len({i.opd_id for i in qs}),
        "opd_belum_lapor": OPD.objects.filter(aktif=True).exclude(
            id__in={i.opd_id for i in qs}).count(),
        "proyeksi_klaim": proyeksi(p, qs, False),
        "proyeksi_terverifikasi": proyeksi(p, qs, True),
        "per_tahapan": hitung("tahapan", Inovasi.TAHAPAN),
        "per_bentuk": hitung("bentuk", Inovasi.BENTUK),
    }


@api.get("/statistik/opd", response=List[RekapOPDOut])
def rekap_opd(request):
    wajib_verifikator(request)
    p = periode_aktif()
    hasil = []
    for opd in OPD.objects.filter(aktif=True):
        daftar = list(Inovasi.objects.filter(periode=p, opd=opd)
                      .prefetch_related("nilai__indikator", "nilai__daftar_berkas"))
        n = len(daftar) or 1
        hasil.append({
            "opd": {"id": opd.id, "kode": opd.kode, "nama": opd.nama},
            "jumlah": len(daftar),
            "terverifikasi": sum(1 for i in daftar if i.status == Inovasi.TERVERIFIKASI),
            "layak": sum(1 for i in daftar if i.layak),
            "rata_skor_klaim": round(sum((i.skor_klaim for i in daftar), Decimal("0")) / n, 1),
            "rata_skor_terverifikasi": round(
                sum((i.skor_terverifikasi for i in daftar), Decimal("0")) / n, 1),
        })
    return sorted(hasil, key=lambda x: (-x["jumlah"], -x["rata_skor_terverifikasi"]))


@api.get("/ekspor/iga")
def ekspor_iga(request, periode_id: Optional[int] = None):
    """CSV berkolom formulir IGA, hanya inovasi terverifikasi dan lolos kelayakan."""
    wajib_verifikator(request)
    p = Periode.objects.filter(id=periode_id).first() if periode_id else periode_aktif()
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="inovasi-rote-ndao-{p.tahun}.csv"'
    resp.write("\ufeff")
    w = csv.writer(resp)
    w.writerow(["No", "Nama Inovasi", "OPD Pelaksana", "Tahapan", "Inisiator", "Nama Inisiator",
                "Klasifikasi", "Jenis", "Bentuk", "Asta Cita", "Klaster PKPN", "Urusan",
                "Waktu Uji Coba", "Penerapan Awal", "Pengembangan Terbaru", "Rancang Bangun",
                "Tujuan", "Manfaat", "Hasil", "Anggaran", "Skor SID Terverifikasi"])
    n = 0
    for i in (Inovasi.objects.filter(periode=p, status=Inovasi.TERVERIFIKASI)
              .select_related("opd").prefetch_related("nilai__indikator", "nilai__daftar_berkas")):
        if not i.layak:
            continue
        n += 1
        w.writerow([n, i.nama, i.opd.nama, i.get_tahapan_display(), i.get_inisiator_display(),
                    i.nama_inisiator, i.get_klasifikasi_display(), i.get_jenis_display(),
                    i.get_bentuk_display(), i.get_asta_cita_display() or "",
                    i.get_pkpn_klaster_display() or "", i.urusan,
                    i.mulai_uji_coba or "", i.mulai_penerapan or "",
                    i.pengembangan_terbaru or "", i.rancang_bangun, i.tujuan, i.manfaat,
                    i.hasil, i.anggaran or "", f"{i.skor_terverifikasi} dari 111"])
    LogAktivitas.catat(request.user, "ekspor CSV", p.tahun, f"{n} inovasi")
    return resp
