"""Uji masuk lewat Esa Office (OpenID Connect) lewat API Django asli, terhadap Esa Office tiruan.

Esa Office tiruan (uji_idp_palsu.py) berjalan di 127.0.0.1 dan menandatangani ID token
RS256/ES256 sungguhan, jadi yang diuji adalah alur nyata: /auth/esa/mulai ->
/authorize -> /auth/esa/callback -> /auth/esa/tukar, termasuk cookie sesi, aturan
akun, batasan unik di basis data, perintah esa_office_cek, dan kecocokan migrasi.

Hanya membuat dan membersihkan data berawalan "uji_esa_" / "UJIESA" / "uji-esa-" (akun,
OPD, tiket, dan log aktivitasnya); data lain tidak disentuh. Setelan ESA_OFFICE_*
dari .env diabaikan selama uji. Seperti uji_alur.py, basis data harus sudah disiapkan
(python manage.py migrate; python manage.py seed_simonda):

    DEBUG=1 SECRET_KEY=... ALLOWED_HOSTS=localhost,testserver python uji_esa_office.py
"""
import base64
import hashlib
import io
import logging
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "simonda.settings")
# Esa Office tiruan ada di loopback: jangan lewat proxy bila lingkungan memasang satu.
os.environ["NO_PROXY"] = os.environ["no_proxy"] = ",".join(
    x for x in (os.environ.get("no_proxy"), os.environ.get("NO_PROXY"), "127.0.0.1,localhost") if x)
django.setup()

from django.conf import settings  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.core.management.base import CommandError  # noqa: E402
from django.db import IntegrityError, transaction  # noqa: E402
from django.db.models import Q  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import override_settings, setup_test_environment  # noqa: E402

import uji_idp_palsu as palsu  # noqa: E402
from inovasi import esa_office  # noqa: E402
from inovasi.models import OPD, LogAktivitas, TiketMasuk, User  # noqa: E402

setup_test_environment()  # menambahkan "testserver" ke ALLOWED_HOSTS untuk Client
# Log operasional modul (galat Esa Office, OPD tak dikenal) sengaja dipicu di sini;
# jangan biarkan ia bercampur dengan keluaran OK/GAGAL.
logging.getLogger("inovasi.esa_office").setLevel(logging.CRITICAL)

idp = palsu.IdP()
SANDI = "RahasiaKuat2026"
FRONTEND = "http://localhost:5173/"
SETELAN = dict(
    ESA_OFFICE_ISSUER=idp.issuer, ESA_OFFICE_CLIENT_ID=idp.CLIENT_ID, ESA_OFFICE_CLIENT_SECRET=idp.CLIENT_SECRET,
    ESA_OFFICE_REDIRECT_URI=idp.redirect_uri, ESA_OFFICE_FRONTEND_URL=FRONTEND, ESA_OFFICE_SCOPE="openid profile",
    ESA_OFFICE_ALGORITMA=["RS256", "ES256"], ESA_OFFICE_TIMEOUT=5.0, ESA_OFFICE_TAUTKAN_NIP=[],
    ESA_OFFICE_PETAKAN_OPD_OTOMATIS=True, ESA_OFFICE_LOGIN_LOKAL=True,
    SECURE_SSL_REDIRECT=False)   # Client memakai http; tanpa ini DEBUG=0 membuat semua permintaan dialihkan ke https

# Identitas contoh di Esa Office tiruan (NIP berawalan 99900 supaya mudah dibersihkan).
AWAL_NIP = "99900"
SUB_BUDI, NIP_BUDI = "uji-esa-budi", "999000000000000001"
SUB_SARI, NIP_SARI = "uji-esa-sari", "999000000000000002"
SUB_LAMA, NIP_LAMA = "uji-esa-lama", "999000000000000003"
SUB_VERIF, NIP_VERIF = "uji-esa-verif", "999000000000000004"
SUB_GAIB, NIP_GAIB = "uji-esa-gaib", "999000000000000005"
PD_A = {"id": "uji-pd-a", "name": "Dinas Uji Esa A"}
PD_B = {"id": "uji-pd-b", "name": "Dinas Uji Esa B"}

lolos = gagal = 0
JEJAK = []    # semua balasan SANDO yang diterima (untuk pemeriksaan kebocoran rahasia)
LOKASI = []   # semua alamat pengalihan (header Location) dari SANDO
TOKEN = []    # semua JWT SANDO yang pernah diterbitkan


def cek(nama, syarat, tambahan: object = ""):
    global lolos, gagal
    if syarat:
        lolos += 1
        print(f"  OK   {nama}")
    else:
        gagal += 1
        print(f"  GAGAL {nama} {tambahan}")


# --------------------------------- bantuan ----------------------------------
def s256(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode()


def verifier_baru():
    """Seperti yang dibuat frontend: 32 byte acak dalam base64url = 43 karakter."""
    return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()


class _TolakRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


_buka = urllib.request.build_opener(urllib.request.ProxyHandler({}), _TolakRedirect)


def http_get(url):
    """GET tanpa mengikuti pengalihan: (status, header, badan). Ini peran browser di Esa Office."""
    try:
        r = _buka.open(urllib.request.Request(url), timeout=5)
        return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def catat(r):
    JEJAK.append(str(dict(r.headers.items())) + "\n" + r.content.decode("utf-8", "replace"))
    if r.has_header("Location"):
        LOKASI.append(r["Location"])
    if r.get("Content-Type", "").startswith("application/json"):
        isi = r.json()
        if isinstance(isi, dict) and isi.get("akses"):
            TOKEN.append(isi["akses"])
    return r


def ambil(klien, path, **parameter):
    return catat(klien.get(path, parameter))


def kirim(klien, path, isi, token=None):
    ekstra = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return catat(klien.post(path, isi, content_type="application/json", **ekstra))


def alur(klien, sub, *, verifier=None, ulang=False):
    """Satu login dari sisi browser: /mulai -> /authorize di Esa Office -> /callback.

    Mengembalikan (respons callback, verifier, fragmen alamat tujuan sebagai dict)."""
    idp.masuk_sebagai = sub
    verifier = verifier or verifier_baru()
    parameter = {"tantangan": s256(verifier)}
    if ulang:
        parameter["ulang"] = "1"
    mulai = ambil(klien, "/api/auth/esa/mulai", **parameter)
    assert mulai.status_code == 302, (mulai.status_code, mulai.content[:200])
    status, header, _ = http_get(mulai["Location"])
    assert status == 302, status
    balik = {k: v[-1] for k, v in parse_qs(urlsplit(header["Location"]).query, keep_blank_values=True).items()}
    callback = ambil(klien, "/api/auth/esa/callback", **balik)
    return callback, verifier, parse_qs(urlsplit(callback["Location"]).fragment)


def tukar(klien, tiket, verifier):
    return kirim(klien, "/api/auth/esa/tukar", {"tiket": tiket, "verifier": verifier})


def masuk_penuh(sub, klien=None):
    """Login lengkap sampai JWT SANDO: (klien, JWT atau None, fragmen)."""
    klien = klien or Client()
    _, verifier, frag = alur(klien, sub)
    if "esa_tiket" not in frag:
        return klien, None, frag
    r = tukar(klien, frag["esa_tiket"][0], verifier)
    return klien, (r.json().get("akses") if r.status_code == 200 else None), frag


def profil(klien, token):
    return catat(klien.get("/api/auth/saya", HTTP_AUTHORIZATION=f"Bearer {token}")).json()


def galat(frag):
    return (frag.get("esa_galat") or [None])[0]


def pelanggaran(fn):
    """True bila fn melanggar batasan basis data (IntegrityError); transaksinya dibatalkan."""
    try:
        with transaction.atomic():
            fn()
    except IntegrityError:
        return True
    return False


def bersihkan():
    pengguna = User.objects.filter(Q(username__startswith="uji_esa_") | Q(external_subject__startswith="uji-esa-")
                                   | Q(nip__startswith=AWAL_NIP))
    LogAktivitas.objects.filter(pengguna__in=pengguna).delete()
    LogAktivitas.objects.filter(objek__startswith="UJIESA").delete()      # pemasangan OPD (tanpa pengguna)
    TiketMasuk.objects.filter(pengguna__in=pengguna).delete()
    pengguna.delete()
    OPD.objects.filter(kode__startswith="UJIESA").delete()


def siapkan():
    """Keadaan awal tiap bagian: data uji bersih, dua OPD uji, Esa Office tiruan baru."""
    esa_office.reset_cache()
    idp.reset()
    bersihkan()
    OPD.objects.create(kode="UJIESA-A", nama=PD_A["name"])
    OPD.objects.create(kode="UJIESA-B", nama=PD_B["name"])
    for sub, nip, nama, pd in ((SUB_BUDI, NIP_BUDI, "Budi Uji", PD_A), (SUB_SARI, NIP_SARI, "Sari Uji", PD_B),
                               (SUB_LAMA, NIP_LAMA, "Lama Uji", PD_A), (SUB_VERIF, NIP_VERIF, "Verif Uji", PD_A),
                               (SUB_GAIB, NIP_GAIB, "Gaib Uji", {"id": "uji-pd-gaib", "name": "Dinas Gaib Uji"})):
        idp.pengguna[sub] = {"name": nama, "nip": nip, "phone_number": "081200000000",
                             "email": f"{sub}@example.go.id", "perangkat_daerah": dict(pd)}


def signing_isi(nilai_cookie):
    """Isi cookie sesi yang sudah diverifikasi tanda tangannya (teks JSON), untuk diperiksa uji."""
    from django.core import signing
    return str(signing.loads(nilai_cookie, salt=esa_office._SALT_COOKIE, max_age=600))


def akun(sub):
    return User.objects.filter(identity_provider="esa-office", external_subject=sub).first()


# ------------------------------------------------------------------ pengujian
def uji_opsi():
    print("\n== pilihan cara masuk ==")
    siapkan()
    c = Client()
    cek("SSO menyala, login lokal terbuka", ambil(c, "/api/auth/opsi").json() == {"esa_office": True, "login_lokal": True})
    with override_settings(ESA_OFFICE_LOGIN_LOKAL=False):
        cek("SSO menyala, sandi lokal dibatasi", ambil(c, "/api/auth/opsi").json() == {"esa_office": True, "login_lokal": False})
    with override_settings(ESA_OFFICE_ISSUER="", ESA_OFFICE_LOGIN_LOKAL=False):
        cek("SSO mati: tombol Esa Office tidak tampil, pembatasan tak berlaku",
            ambil(c, "/api/auth/opsi").json() == {"esa_office": False, "login_lokal": True})
        cek("SSO mati: /auth/esa/mulai -> 404", ambil(c, "/api/auth/esa/mulai", tantangan=s256(verifier_baru())).status_code == 404)


def uji_mulai():
    print("\n== /auth/esa/mulai ==")
    siapkan()
    c = Client()
    verifier = verifier_baru()
    r = ambil(c, "/api/auth/esa/mulai", tantangan=s256(verifier))
    q = {k: v[-1] for k, v in parse_qs(urlsplit(r["Location"]).query).items()}
    cek("mengalihkan (302) ke /authorize di Esa Office", r.status_code == 302 and r["Location"].startswith(idp.issuer + "/authorize?"), r.status_code)
    cek("parameter OIDC lengkap: code + PKCE S256 + state + nonce",
        q.get("response_type") == "code" and q.get("code_challenge_method") == "S256" and q.get("client_id") == idp.CLIENT_ID
        and q.get("redirect_uri") == idp.redirect_uri and len(q.get("state", "")) >= 32 and len(q.get("nonce", "")) >= 32, q)
    cek("rahasia klien dan tantangan frontend tidak ikut ke Esa Office",
        idp.CLIENT_SECRET not in r["Location"] and s256(verifier) not in r["Location"] and verifier not in r["Location"])
    cek("tanpa ulang: tidak ada prompt=login", "prompt" not in q)
    cek("cache dimatikan dan referrer tidak dikirim", r["Cache-Control"] == "no-store" and r["Referrer-Policy"] == "no-referrer")
    m = c.cookies.get(esa_office.NAMA_COOKIE)
    cek("cookie sesi: HttpOnly, SameSite=Lax, path sempit",
        m is not None and m["httponly"] and m["samesite"] == "Lax" and m["path"] == "/api/auth/esa/", m)
    cek("cookie sesi: Secure kecuali DEBUG", m is not None and bool(m["secure"]) == (not settings.DEBUG))
    cek("cookie sesi tidak memuat verifier frontend (hanya tantangannya)", m is not None and verifier not in m.value and s256(verifier) in signing_isi(m.value))
    q2 = {k: v[-1] for k, v in parse_qs(urlsplit(ambil(Client(), "/api/auth/esa/mulai", tantangan=s256(verifier), ulang="1")["Location"]).query).items()}
    cek("ulang=1 menambah prompt=login", q2.get("prompt") == "login")
    for ket, param in (("tanpa tantangan", {}), ("tantangan pendek", {"tantangan": "abc"}), ("tantangan bukan base64url", {"tantangan": "!" * 43})):
        c2 = Client()
        r2 = ambil(c2, "/api/auth/esa/mulai", **param)
        cek(f"{ket}: kembali ke frontend dengan esa_galat=gagal, tanpa cookie",
            r2.status_code == 302 and r2["Location"] == FRONTEND + "#esa_galat=gagal" and esa_office.NAMA_COOKIE not in c2.cookies, r2["Location"])
    esa_office.reset_cache()
    n0 = len(idp.rekam)
    ambil(Client(), "/api/auth/esa/mulai", tantangan="abc")
    cek("tantangan yang salah ditolak sebelum menghubungi Esa Office sama sekali", len(idp.rekam) == n0, idp.rekam[n0:])
    with override_settings(ESA_OFFICE_ISSUER="http://127.0.0.1:1"):
        esa_office.reset_cache()
        c3 = Client()
        r3 = ambil(c3, "/api/auth/esa/mulai", tantangan=s256(verifier))
        cek("Esa Office tak terjangkau -> esa_galat=tidak_tersedia, tanpa teks galat di URL",
            r3["Location"] == FRONTEND + "#esa_galat=tidak_tersedia" and esa_office.NAMA_COOKIE not in c3.cookies, r3["Location"])


def uji_login_baru():
    print("\n== login pertama: akun dibuat dari Esa Office ==")
    siapkan()
    c = Client()
    r, verifier, frag = alur(c, SUB_BUDI)
    cek("berhasil -> 302 ke frontend dengan tiket di FRAGMEN (bukan query)",
        r.status_code == 302 and r["Location"].startswith(FRONTEND + "#esa_tiket=") and "?" not in r["Location"] and list(frag) == ["esa_tiket"], r["Location"])
    cek("cache dimatikan dan referrer tidak dikirim di callback", r["Cache-Control"] == "no-store" and r["Referrer-Policy"] == "no-referrer")
    cek("cookie sesi dihapus setelah callback", esa_office.NAMA_COOKIE in c.cookies and c.cookies[esa_office.NAMA_COOKIE].value == "")
    tiket = frag["esa_tiket"][0]
    cek("hanya SHA-256 tiket yang disimpan, beserta tantangan pengikat",
        not TiketMasuk.objects.filter(sidik=tiket).exists() and TiketMasuk.objects.filter(sidik=hashlib.sha256(tiket.encode()).hexdigest(), tantangan=s256(verifier)).exists())
    cek("kode, state, dan rahasia klien tidak ada di alamat tujuan", idp.CLIENT_SECRET not in r["Location"] and "code=" not in r["Location"] and "state=" not in r["Location"])

    t = tukar(c, tiket, verifier)
    cek("tiket + verifier yang benar -> 200 dengan JWT SANDO", t.status_code == 200 and bool(t.json().get("akses")), (t.status_code, t.content[:200]))
    token = t.json().get("akses")
    cek("tiket sudah terpakai: baris tiket hilang", not TiketMasuk.objects.filter(pengguna__external_subject=SUB_BUDI).exists())
    saya = profil(c, token)
    cek("profil: operator di OPD dari Esa Office", saya.get("peran") == "operator" and saya["opd"]["kode"] == "UJIESA-A" and saya["bisa_verifikasi"] is False, saya)
    u = akun(SUB_BUDI)
    cek("akun dibuat: username = NIP, nama dari Esa Office, NIP tersimpan", u is not None and u.username == NIP_BUDI and u.first_name == "Budi Uji" and u.nip == NIP_BUDI)
    cek("akun baru tanpa kata sandi yang bisa dipakai", u is not None and not u.has_usable_password())
    cek("OPD terpasang ke ID Esa Office saat login pertama (nama cocok persis)", OPD.objects.get(kode="UJIESA-A").esa_id == PD_A["id"])
    cek("pembuatan akun dan login tercatat di log aktivitas",
        LogAktivitas.objects.filter(pengguna=u, aksi="buat akun via Esa Office").exists()
        and LogAktivitas.objects.filter(pengguna=u, aksi="masuk", ringkasan="via Esa Office").exists())

    t2 = tukar(c, tiket, verifier)
    cek("tiket yang sama untuk kedua kali -> 401", t2.status_code == 401 and "akses" not in t2.json(), t2.status_code)

    # Login kedua: akun yang sama dipakai ulang dan namanya mengikuti Esa Office.
    idp.pengguna[SUB_BUDI]["name"] = "Budi Uji Baru"
    _, token2, _ = masuk_penuh(SUB_BUDI)
    cek("login kedua memakai akun yang sama", token2 is not None and User.objects.filter(external_subject=SUB_BUDI).count() == 1)
    cek("nama mengikuti Esa Office", akun(SUB_BUDI).first_name == "Budi Uji Baru")


def uji_pengikat_tiket():
    print("\n== tiket terikat ke browser yang memulai login (login CSRF) ==")
    siapkan()
    penyerang, korban = Client(), Client()
    # Penyerang punya akun Esa Office yang sah; ia menyelesaikan login di browsernya sendiri dan menahan tiketnya.
    _, v_penyerang, frag = alur(penyerang, SUB_SARI)
    tiket_penyerang = frag["esa_tiket"][0]
    # Korban membuka tautan https://sando/#esa_tiket=<tiket penyerang>; verifier di browser korban bukan milik penyerang.
    r = tukar(korban, tiket_penyerang, verifier_baru())
    cek("tiket penyerang dengan verifier korban -> 401, tanpa JWT", r.status_code == 401 and "akses" not in r.json(), r.status_code)
    r = tukar(penyerang, tiket_penyerang, v_penyerang)
    cek("setelah percobaan salah tiket hangus (penyerang pun tak bisa memakainya lagi)", r.status_code == 401)
    # Tanpa penyerang: pemilik browser sah berhasil.
    c = Client()
    _, v, frag = alur(c, SUB_SARI)
    cek("browser yang memulai login berhasil menukar", tukar(c, frag["esa_tiket"][0], v).status_code == 200)
    # Dua login serentak tidak boleh tertukar.
    ca, cb = Client(), Client()
    _, va, fa = alur(ca, SUB_SARI)
    _, vb, fb = alur(cb, SUB_BUDI)
    cek("verifier B tidak membuka tiket A", tukar(cb, fa["esa_tiket"][0], vb).status_code == 401)
    cek("verifier B membuka tiket B", tukar(cb, fb["esa_tiket"][0], vb).status_code == 200)
    for ket, nilai in (("kosong", ""), ("pendek", "abc"), ("terlalu panjang", "x" * 500)):
        c = Client()
        _, v, frag = alur(c, SUB_SARI)
        r = tukar(c, frag["esa_tiket"][0], nilai)
        cek(f"verifier {ket} -> 401", r.status_code == 401, r.status_code)
    for ket, isi in (("tanpa verifier", {"tiket": "x" * 40}), ("tanpa tiket", {"verifier": "x" * 43})):
        r = kirim(Client(), "/api/auth/esa/tukar", isi)
        cek(f"badan {ket} ditolak oleh validasi (422)", r.status_code == 422, r.status_code)


def uji_sesi_dan_callback():
    print("\n== /auth/esa/callback: sesi, state, pembatalan ==")
    siapkan()
    tiket0 = TiketMasuk.objects.count()
    c = Client()
    idp.masuk_sebagai = SUB_BUDI
    verifier = verifier_baru()
    mulai = ambil(c, "/api/auth/esa/mulai", tantangan=s256(verifier))
    balik = {k: v[-1] for k, v in parse_qs(urlsplit(http_get(mulai["Location"])[1]["Location"]).query).items()}
    sebelum = len(idp.permintaan("/token"))
    r = ambil(Client(), "/api/auth/esa/callback", **balik)
    cek("tanpa cookie sesi -> esa_galat=kedaluwarsa (login CSRF ditolak)", r["Location"] == FRONTEND + "#esa_galat=kedaluwarsa", r["Location"])
    cek("tanpa cookie: kode tidak ditukar di Esa Office", len(idp.permintaan("/token")) == sebelum)
    r = ambil(c, "/api/auth/esa/callback", **{**balik, "state": "state-penyerang"})
    cek("state tak cocok -> esa_galat=kedaluwarsa", r["Location"] == FRONTEND + "#esa_galat=kedaluwarsa", r["Location"])
    cek("callback tanpa parameter apa pun -> kedaluwarsa (bukan 500)", ambil(Client(), "/api/auth/esa/callback")["Location"] == FRONTEND + "#esa_galat=kedaluwarsa")
    c2 = Client()
    idp.masuk_sebagai = None
    _, _, frag = alur(c2, None)
    cek("pengguna membatalkan di Esa Office -> esa_galat=dibatalkan", galat(frag) == "dibatalkan", frag)
    cek("tak ada akun atau tiket yang tersisa dari percobaan gagal",
        not User.objects.filter(external_subject__startswith="uji-esa-").exists() and TiketMasuk.objects.count() == tiket0)
    idp.masuk_sebagai = SUB_BUDI
    idp.override["/token"] = lambda h: (h.kirim(503, {"error": "temporarily_unavailable"}), True)[1]
    _, _, frag = alur(Client(), SUB_BUDI)
    cek("Esa Office gagal saat penukaran kode -> galat tetap tanpa teks bebas", galat(frag) in ("tidak_tersedia", "gagal", "kedaluwarsa"), frag)


def uji_aturan_akun():
    print("\n== aturan akun lewat Esa Office ==")
    siapkan()
    # Perpindahan perangkat daerah: operator mengikuti Esa Office dan tercatat.
    _, token, _ = masuk_penuh(SUB_BUDI)
    cek("operator baru masuk ke OPD A", profil(Client(), token)["opd"]["kode"] == "UJIESA-A")
    idp.pengguna[SUB_BUDI]["perangkat_daerah"] = dict(PD_B)
    _, token, _ = masuk_penuh(SUB_BUDI)
    u = akun(SUB_BUDI)
    cek("operator pindah OPD mengikuti Esa Office", token is not None and u.opd.kode == "UJIESA-B")
    cek("perpindahan tercatat di log aktivitas", LogAktivitas.objects.filter(pengguna=u, aksi="pindah OPD via Esa Office").exists())
    cek("peran tidak pernah datang dari Esa Office", u.peran == "operator" and not u.is_staff and not u.is_superuser)

    # Perangkat daerah yang tak dikenal.
    _, token, frag = masuk_penuh(SUB_GAIB)
    cek("OPD tak dikenal -> esa_galat=opd_tidak_dikenal, tanpa akun", token is None and galat(frag) == "opd_tidak_dikenal" and akun(SUB_GAIB) is None, frag)
    with override_settings(ESA_OFFICE_PETAKAN_OPD_OTOMATIS=False):
        OPD.objects.filter(kode__in=("UJIESA-A", "UJIESA-B")).update(esa_id="")
        _, token, frag = masuk_penuh(SUB_SARI)
        cek("pemetaan otomatis dimatikan dan OPD belum dipetakan -> opd_tidak_dikenal, tanpa akun",
            token is None and galat(frag) == "opd_tidak_dikenal" and akun(SUB_SARI) is None, frag)
        cek("OPD tidak dipetakan diam-diam saat pemetaan otomatis mati", OPD.objects.get(kode="UJIESA-B").esa_id == "")
        OPD.objects.filter(kode="UJIESA-B").update(esa_id=PD_B["id"])
        _, token, frag = masuk_penuh(SUB_SARI)
        cek("OPD yang sudah dipetakan admin (esa_id) dikenali", token is not None and akun(SUB_SARI).opd.kode == "UJIESA-B", frag)

    # Akun dinonaktifkan di SANDO tidak pernah dihidupkan lagi oleh Esa Office.
    u = akun(SUB_BUDI)
    u.is_active = False
    u.save()
    _, token, frag = masuk_penuh(SUB_BUDI)
    cek("akun dinonaktifkan -> esa_galat=akun_nonaktif, tetap nonaktif", token is None and galat(frag) == "akun_nonaktif" and not akun(SUB_BUDI).is_active, frag)

    # Akun lama (belum tertaut) yang NIP-nya sama: operator ditautkan otomatis.
    lama = User.objects.create_user("uji_esa_lama", password=SANDI, peran=User.OPERATOR, nip=NIP_LAMA,
                                    opd=OPD.objects.get(kode="UJIESA-A"))
    _, token, frag = masuk_penuh(SUB_LAMA)
    lama.refresh_from_db()
    cek("operator lama ditautkan lewat NIP: akun yang sama, username tetap", token is not None and lama.external_subject == SUB_LAMA
        and lama.identity_provider == "esa-office" and User.objects.filter(nip=NIP_LAMA).count() == 1, frag)
    cek("penautan tercatat di log aktivitas", LogAktivitas.objects.filter(pengguna=lama, aksi="tautkan akun Esa Office").exists())
    cek("kata sandi lokal akun lama tidak disentuh", lama.check_password(SANDI))

    # Akun istimewa dengan kata sandi lokal: tidak ditautkan otomatis lewat NIP.
    verif = User.objects.create_user("uji_esa_verif", password=SANDI, peran=User.VERIFIKATOR, nip=NIP_VERIF,
                                     opd=OPD.objects.get(kode="UJIESA-B"))
    OPD.objects.filter(kode="UJIESA-A").update(esa_id="")
    _, token, frag = masuk_penuh(SUB_VERIF)
    cek("verifikator berkata sandi lokal -> esa_galat=belum_ditautkan", token is None and galat(frag) == "belum_ditautkan", frag)
    cek("login yang ditolak tidak meninggalkan jejak: OPD belum dipetakan, akun belum ditautkan",
        OPD.objects.get(kode="UJIESA-A").esa_id == "" and not User.objects.get(username="uji_esa_verif").external_subject)
    with override_settings(ESA_OFFICE_TAUTKAN_NIP=[NIP_VERIF]):
        _, token, frag = masuk_penuh(SUB_VERIF)
        verif.refresh_from_db()
        cek("NIP didaftarkan operator -> verifikator masuk dengan perannya sendiri",
            token is not None and verif.peran == User.VERIFIKATOR and verif.external_subject == SUB_VERIF and verif.opd.kode == "UJIESA-B", frag)
        cek("peran verifikator tampil di profil", profil(Client(), token)["bisa_verifikasi"] is True)


def uji_login_lokal():
    print("\n== sandi lokal dibatasi untuk administrator ==")
    siapkan()
    op = User.objects.create_user("uji_esa_op", password=SANDI, peran=User.OPERATOR, opd=OPD.objects.get(kode="UJIESA-A"))
    adm = User.objects.create_user("uji_esa_admin", password=SANDI, peran=User.ADMIN)
    c = Client()

    def masuk_lokal(nama, sandi=SANDI):
        return kirim(c, "/api/auth/masuk", {"username": nama, "password": sandi})

    cek("login lokal terbuka: operator masuk", masuk_lokal(op.username).status_code == 200)
    with override_settings(ESA_OFFICE_LOGIN_LOKAL=False):
        r = masuk_lokal(op.username)
        cek("dibatasi: operator ditolak dengan petunjuk memakai Esa Office", r.status_code == 401 and "Esa Office" in r.json().get("detail", ""), r.content[:200])
        salah = masuk_lokal(op.username, "sandi-salah")
        cek("pesan 'sandi benar' dan 'sandi salah' sama persis (tidak membocorkan tebakan)", r.json() == salah.json())
        r = masuk_lokal(adm.username)
        cek("dibatasi: administrator tetap bisa masuk", r.status_code == 200)
        token = r.json()["akses"]
        buat = kirim(c, "/api/akun-opd", {"username": "uji_esa_baru", "password": SANDI, "opd_id": OPD.objects.get(kode="UJIESA-A").id}, token)
        cek("dibatasi: membuat akun operator lokal ditolak (409)", buat.status_code == 409 and not User.objects.filter(username="uji_esa_baru").exists(), buat.status_code)
        reset = kirim(c, f"/api/akun-opd/{op.id}/reset-sandi", {"password": SANDI + "x"}, token)
        cek("dibatasi: reset kata sandi operator ditolak (409)", reset.status_code == 409, reset.status_code)
    r = masuk_lokal(adm.username)
    buat = kirim(c, "/api/akun-opd", {"username": "uji_esa_baru", "password": SANDI, "opd_id": OPD.objects.get(kode="UJIESA-A").id}, r.json()["akses"])
    cek("tidak dibatasi: membuat akun operator lokal berjalan seperti semula (201)", buat.status_code == 201, buat.status_code)
    with override_settings(ESA_OFFICE_ISSUER="", ESA_OFFICE_LOGIN_LOKAL=False):
        cek("SSO mati: pembatasan tidak berlaku (operator tetap bisa masuk lokal)", masuk_lokal(op.username).status_code == 200)


def uji_basis_data():
    print("\n== batasan basis data dan migrasi ==")
    siapkan()
    User.objects.create_user("uji_esa_dup1", identity_provider="esa-office", external_subject="uji-esa-dup")
    cek("pasangan (penyedia, subject) yang sama ditolak basis data",
        pelanggaran(lambda: User.objects.create_user("uji_esa_dup2", identity_provider="esa-office", external_subject="uji-esa-dup")))
    cek("subject yang sama di penyedia lain boleh",
        not pelanggaran(lambda: User.objects.create_user("uji_esa_dup3", identity_provider="lain", external_subject="uji-esa-dup")))
    cek("banyak akun tanpa identitas eksternal tetap boleh",
        not pelanggaran(lambda: User.objects.create_user("uji_esa_dup4")) and not pelanggaran(lambda: User.objects.create_user("uji_esa_dup5")))
    OPD.objects.create(kode="UJIESA-X", nama="Uji X", esa_id="uji-pd-x")
    cek("esa_id OPD yang sama ditolak basis data", pelanggaran(lambda: OPD.objects.create(kode="UJIESA-Y", nama="Uji Y", esa_id="uji-pd-x")))
    cek("banyak OPD tanpa esa_id tetap boleh",
        not pelanggaran(lambda: OPD.objects.create(kode="UJIESA-Z", nama="Uji Z")) and not pelanggaran(lambda: OPD.objects.create(kode="UJIESA-W", nama="Uji W")))
    keluar = io.StringIO()
    try:
        # Hanya aplikasi ini, dan tanpa pertanyaan interaktif: bila migrasi tidak cocok, uji ini harus gagal, bukan menunggu input.
        call_command("makemigrations", "inovasi", "--check", "--dry-run", interactive=False, stdout=keluar, stderr=keluar)
        beres = True
    except SystemExit:
        beres = False
    cek("migrasi sesuai dengan model (makemigrations --check tidak menemukan perubahan)", beres, keluar.getvalue()[:300])


def uji_perintah_cek():
    print("\n== perintah esa_office_cek ==")
    siapkan()
    keluar = io.StringIO()
    try:
        call_command("esa_office_cek", stdout=keluar)
        beres = True
    except CommandError as e:
        beres = False
        keluar.write(str(e))
    teks = keluar.getvalue()
    cek("Esa Office tiruan terbaca dengan benar", beres and "terbaca dengan benar" in teks, teks[-300:])
    cek("rahasia klien tidak pernah ditampilkan", idp.CLIENT_SECRET not in teks)
    with override_settings(ESA_OFFICE_ISSUER="http://127.0.0.1:1"):
        esa_office.reset_cache()
        keluar = io.StringIO()
        try:
            call_command("esa_office_cek", stdout=keluar)
            gagal_cek = False
        except CommandError:
            gagal_cek = True
        cek("Esa Office tak terjangkau -> CommandError", gagal_cek)
    with override_settings(ESA_OFFICE_ISSUER=""):
        try:
            call_command("esa_office_cek", stdout=io.StringIO())
            gagal_cek = False
        except CommandError:
            gagal_cek = True
        cek("SSO belum dikonfigurasi -> CommandError berisi petunjuk", gagal_cek)


def uji_kebocoran():
    print("\n== kebocoran rahasia ==")
    semua = "\n".join(JEJAK)
    cek(f"rahasia klien tidak ada di satu pun dari {len(JEJAK)} balasan SANDO", idp.CLIENT_SECRET not in semua and len(JEJAK) > 20)
    cek(f"JWT SANDO ({len(TOKEN)} diterbitkan) tidak pernah muncul di alamat pengalihan mana pun",
        len(TOKEN) > 5 and all(t not in alamat for t in TOKEN for alamat in LOKASI))
    cek("tiket sekali pakai hanya muncul di fragmen alamat (#), tidak di query", all("esa_tiket=" not in a.split("#")[0] for a in LOKASI))
    cek("ID token dari Esa Office tidak diteruskan ke browser", all(t not in semua for t in idp.arsip["id_token"]) and len(idp.arsip["id_token"]) > 5)
    cek("kode otorisasi tidak pernah ada di balasan SANDO", all(k not in semua for k in idp.arsip["kode"]) and len(idp.arsip["kode"]) > 5)


def main():
    try:
        with override_settings(**SETELAN):
            uji_opsi()
            uji_mulai()
            uji_login_baru()
            uji_pengikat_tiket()
            uji_sesi_dan_callback()
            uji_aturan_akun()
            uji_login_lokal()
            uji_basis_data()
            uji_perintah_cek()
            uji_kebocoran()
    finally:
        bersihkan()
    print(f"\n{lolos} lolos, {gagal} gagal")
    sys.exit(1 if gagal else 0)


if __name__ == "__main__":
    main()
