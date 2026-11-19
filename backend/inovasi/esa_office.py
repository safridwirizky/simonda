"""SSO dengan Esa Office lewat OpenID Connect (OAuth 2.0 Authorization Code + PKCE).

Esa Office adalah penyedia identitas (IdP); SANDO adalah klien OIDC-nya. SANDO
tidak pernah melihat kata sandi Esa Office: pengguna mengetiknya hanya di
halaman login Esa Office. Alurnya:

  1. Frontend membuat ``verifier`` acak (disimpan di sessionStorage browser itu
     saja) dan mengarahkan browser ke /api/auth/esa/mulai?tantangan=SHA256(verifier).
     ``mulai_login()`` membuat ``state``, ``nonce``, dan pasangan PKCE, menyimpan
     semuanya beserta ``tantangan`` di cookie bertanda tangan (HttpOnly,
     SameSite=Lax, hanya terkirim ke /api/auth/esa/, 10 menit), lalu mengalihkan
     browser ke ``authorization_endpoint``.
  2. Pengguna login di Esa Office, yang mengalihkan browser kembali ke
     /api/auth/esa/callback?code=...&state=....
  3. ``selesai_login()`` mencocokkan ``state`` dengan cookie (mengikat hasil
     login ke browser yang memulainya), menukar ``code`` di ``token_endpoint``
     (client secret + ``code_verifier``), lalu memeriksa ID token: tanda tangan
     lewat JWKS, ``iss``, ``aud``, ``exp``, ``iat``, dan ``nonce``. Nama, NIP,
     dan perangkat daerah dibaca dari klaim (atau dari ``userinfo`` bila tidak
     ada di ID token).
  4. ``sinkronkan_akun()`` mencari atau membuat akun SANDO "bayangan" (tanpa
     kata sandi) untuk (penyedia, subject) itu, dan ``terbitkan_tiket()``
     menyimpan tiket sekali pakai yang terikat ke ``tantangan`` tadi. Browser
     dialihkan ke frontend dengan tiket di fragmen URL (tidak pernah dikirim ke
     server mana pun); frontend menukarnya bersama ``verifier`` lewat
     /api/auth/esa/tukar menjadi JWT SANDO (HS256, 12 jam) yang sama dengan hasil
     login lokal. Tanpa ``verifier`` yang cocok tiket tidak bisa ditukar, jadi
     tiket milik orang lain tidak bisa disodorkan ke korban lewat tautan.
     AuthBearer dan hak akses tidak berubah.

Pembagian tugas: Esa Office menjawab "siapa orang ini" (ASN, NIP, nama,
perangkat daerah); SANDO menjawab "apa yang boleh ia lakukan di sini". Karena
itu peran (admin/verifikator/operator) tidak pernah datang dari Esa Office:
akun baru selalu operator OPD, dan SuperUser awal tetap akun yang disediakan
terpisah (boleh masuk dengan kata sandi lokal).

Aturan yang sengaja ketat:
  * Hanya tanda tangan asimetris (bawaan RS256/ES256) yang diterima; ID token
    tanpa tanda tangan atau ber-HMAC ditolak, dan algoritma ditentukan oleh
    konfigurasi SANDO, bukan oleh header token.
  * Akun ditautkan lewat (penyedia, subject), bukan nama, NIP, atau telepon.
    NIP hanya dipakai satu kali, untuk menautkan akun SANDO lama yang belum
    punya identitas eksternal; verifikator/admin dengan kata sandi lokal hanya
    ditautkan bila NIP-nya terdaftar di ``ESA_OFFICE_TAUTKAN_NIP``.
  * Perangkat daerah dipetakan lewat ID stabil (``OPD.esa_id``). Pengisian
    otomatis dari nama hanya bila tepat satu OPD yang cocok persis dan belum
    dipetakan; bila ID itu atau namanya bentrok, login ditolak -- salah
    menempatkan pengguna di OPD lain berarti membuka data OPD itu.
  * Operator selalu mengikuti perangkat daerah dari Esa Office (perpindahan
    ASN tercatat di log aktivitas). Verifikator/admin tidak dipindahkan.
  * Akun yang dinonaktifkan di SANDO tidak pernah diaktifkan kembali oleh login.
"""
import base64
import hashlib
import hmac
import http.client
import json
import logging
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import jwt
from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import OPD, LogAktivitas, TiketMasuk, User

log = logging.getLogger("inovasi.esa_office")

PENYEDIA = "esa-office"      # nilai User.identity_provider
NAMA_COOKIE = "sando_esa"
PATH_COOKIE = "/api/auth/esa/"
MASA_COOKIE = 600            # detik untuk menyelesaikan login di Esa Office
MASA_TIKET = 60              # detik antara callback dan penukaran tiket
MAKS_BADAN = 64 * 1024       # balasan Esa Office dibaca paling banyak sebesar ini
MAKS_SUB = 255               # panjang kolom User.external_subject
MAKS_NAMA = 150              # panjang kolom User.first_name
MAKS_NIP = 25                # panjang kolom User.nip
MAKS_ID_PD = 100             # panjang kolom OPD.esa_id
MAKS_OBJEK = 120             # panjang kolom LogAktivitas.objek (username lama bisa sampai 150)
_LOOPBACK = ("localhost", "127.0.0.1", "::1")
_SALT_COOKIE = "sando.esa-office.oidc"
_POLA_TANTANGAN = re.compile(r"[A-Za-z0-9_-]{43}")        # base64url tanpa padding dari SHA-256 (32 byte)
_POLA_VERIFIER = re.compile(r"[A-Za-z0-9_-]{43,128}")      # panjang yang sama dengan code_verifier RFC 7636
_ASIMETRIS = ("RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512")
_ALGORITMA_BAWAAN = ("RS256", "ES256")
_TTL_DISCOVERY = 3600        # detik
_TTL_JWKS = 3600
_TTL_GAGAL = 15              # setelah discovery gagal, jangan coba lagi selama ini
_JEDA_JWKS = 30              # jarak minimal antar unduhan ulang JWKS saat kid tak dikenal
_TOLERANSI_JAM = 60          # detik selisih jam yang dimaafkan untuk exp/iat/nbf


# ------------------------------- galat -------------------------------------

class EsaOfficeError(Exception):
    """Dasar semua galat SSO. ``kode`` dikirim ke frontend, yang memetakannya ke
    pesan tetap (teks dari luar tidak pernah tampil di UI); ``status`` dan
    ``pesan`` dipakai respons JSON. Argumen konstruktor (``detail``) hanya untuk
    log server."""

    kode = "gagal"
    status = 503
    pesan = "Masuk lewat Esa Office gagal. Coba lagi."

    def __init__(self, detail: str = ""):
        super().__init__(detail or self.pesan)


class KonfigurasiSalah(EsaOfficeError):
    """Setelan ESA_OFFICE_* tidak layak atau Esa Office menolak klien ini."""
    kode = "tidak_tersedia"
    pesan = "Masuk lewat Esa Office belum dikonfigurasi dengan benar. Hubungi administrator."


class EsaOfficeTidakTersedia(EsaOfficeError):
    """Jaringan, waktu habis, 5xx, atau balasan yang tidak dikenali."""
    kode = "tidak_tersedia"
    pesan = "Layanan Esa Office sedang tidak dapat dihubungi. Coba lagi beberapa saat lagi."


class SesiKedaluwarsa(EsaOfficeError):
    kode = "kedaluwarsa"
    status = 400
    pesan = "Sesi masuk kedaluwarsa atau tidak cocok. Mulai lagi dari tombol Masuk dengan Esa Office."


class LoginDibatalkan(EsaOfficeError):
    kode = "dibatalkan"
    status = 400
    pesan = "Masuk dibatalkan."


class TokenTidakValid(EsaOfficeError):
    kode = "gagal"
    status = 502
    pesan = "Jawaban Esa Office tidak dapat dipercaya. Coba lagi atau hubungi administrator."


class IdentitasTidakLengkap(EsaOfficeError):
    kode = "identitas_tidak_lengkap"
    status = 403
    pesan = "Data akun Esa Office Anda belum lengkap (nama atau perangkat daerah). Hubungi administrator."


class AkunDinonaktifkan(EsaOfficeError):
    kode = "akun_nonaktif"
    status = 403
    pesan = "Akun Anda dinonaktifkan di SANDO. Hubungi administrator."


class AkunGanda(EsaOfficeError):
    kode = "akun_ganda"
    status = 409
    pesan = "Ditemukan lebih dari satu akun SANDO untuk identitas ini. Hubungi administrator."


class TautanBelumDiizinkan(EsaOfficeError):
    kode = "belum_ditautkan"
    status = 403
    pesan = ("Akun verifikator/admin dengan NIP ini dibuat di SANDO dengan kata sandi lokal dan belum "
             "ditautkan ke Esa Office. Hubungi administrator.")


class OPDTidakDikenal(EsaOfficeError):
    kode = "opd_tidak_dikenal"
    status = 403
    pesan = "Perangkat daerah Anda di Esa Office belum terdaftar di SANDO. Hubungi administrator."


class TiketTidakValid(EsaOfficeError):
    kode = "tiket"
    status = 401
    pesan = "Tiket masuk tidak valid atau sudah kedaluwarsa. Ulangi masuk dengan Esa Office."


# ------------------------------ konfigurasi --------------------------------

def aktif() -> bool:
    """SSO menyala bila ESA_OFFICE_ISSUER diisi; kosong = login lokal saja."""
    return bool(str(getattr(settings, "ESA_OFFICE_ISSUER", "") or "").strip())


def login_lokal_dibatasi() -> bool:
    """True bila SSO menyala dan sandi lokal hanya untuk administrator."""
    return aktif() and not getattr(settings, "ESA_OFFICE_LOGIN_LOKAL", True)


def boleh_login_lokal(user) -> bool:
    return not login_lokal_dibatasi() or bool(user.is_superuser) or user.peran == User.ADMIN


@dataclass(frozen=True)
class Konfig:
    issuer: str
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str = ""
    scope: str = "openid profile"
    algoritma: Tuple[str, ...] = _ALGORITMA_BAWAAN
    timeout: float = 8.0


def _teks_setelan(nama: str, bawaan: str = "") -> str:
    nilai = str(getattr(settings, nama, "") or bawaan).strip()
    if not nilai:
        raise KonfigurasiSalah(f"{nama} belum diisi")
    if any(ord(c) < 32 or ord(c) == 127 for c in nilai):
        raise KonfigurasiSalah(f"{nama} memuat karakter kontrol")
    return nilai


def _periksa_url(nama: str, url: str, *, boleh_query: bool = True) -> None:
    if "#" in url:
        raise KonfigurasiSalah(
            f"{nama} memuat '#': bagian setelah '#' adalah rute halaman web dan tidak pernah dikirim "
            "ke server. Pakai alamat tanpa '#'.")
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url):
        raise KonfigurasiSalah(f"{nama} tidak boleh memuat spasi atau karakter kontrol.")
    try:
        p = urlsplit(url)
        p.port  # noqa: B018 -- memicu ValueError bila port tidak wajar
    except ValueError:
        raise KonfigurasiSalah(f"{nama} bukan alamat yang wajar.") from None
    if p.username is not None or p.password is not None:
        raise KonfigurasiSalah(f"{nama} tidak boleh memuat user:sandi di dalam alamat.")
    if not boleh_query and p.query:
        raise KonfigurasiSalah(f"{nama} tidak boleh memuat query (?...).")
    if p.scheme == "https" and p.hostname:
        return
    if p.scheme == "http" and p.hostname in _LOOPBACK:  # hanya untuk pengujian lokal
        return
    raise KonfigurasiSalah(f"{nama} harus berupa alamat https:// yang utuh.")


def _daftar(nilai) -> List[str]:
    if isinstance(nilai, str):
        nilai = nilai.split(",")
    return [str(x).strip() for x in (nilai or ()) if str(x).strip()]


def _timeout() -> float:
    try:
        nilai = float(getattr(settings, "ESA_OFFICE_TIMEOUT", 8.0))
    except (TypeError, ValueError):
        return 8.0
    return nilai if nilai > 0 else 8.0


def konfigurasi() -> Konfig:
    """Setelan ESA_OFFICE_* yang sudah diperiksa; melempar KonfigurasiSalah yang
    menyebut variabel mana yang salah."""
    if not jwt.algorithms.has_crypto:
        raise KonfigurasiSalah('paket cryptography belum terpasang (pip install "PyJWT[crypto]")')
    issuer = _teks_setelan("ESA_OFFICE_ISSUER")
    _periksa_url("ESA_OFFICE_ISSUER", issuer, boleh_query=False)
    redirect_uri = _teks_setelan("ESA_OFFICE_REDIRECT_URI")
    _periksa_url("ESA_OFFICE_REDIRECT_URI", redirect_uri)
    scope = " ".join(_teks_setelan("ESA_OFFICE_SCOPE", "openid profile").split())
    if "openid" not in scope.split():
        raise KonfigurasiSalah("ESA_OFFICE_SCOPE harus memuat 'openid'")
    algoritma = tuple(dict.fromkeys(_daftar(getattr(settings, "ESA_OFFICE_ALGORITMA", ())))) or _ALGORITMA_BAWAAN
    salah = [a for a in algoritma if a not in _ASIMETRIS]
    if salah:
        raise KonfigurasiSalah(
            f"ESA_OFFICE_ALGORITMA hanya boleh berisi algoritma asimetris ({', '.join(_ASIMETRIS)}); "
            f"tidak diizinkan: {', '.join(salah)}")
    return Konfig(issuer=issuer, client_id=_teks_setelan("ESA_OFFICE_CLIENT_ID"),
                  client_secret=_teks_setelan("ESA_OFFICE_CLIENT_SECRET"), redirect_uri=redirect_uri,
                  scope=scope, algoritma=algoritma, timeout=_timeout())


def url_frontend(**fragmen: str) -> str:
    """Alamat frontend SANDO dengan ``fragmen`` di belakang '#' (mis. esa_tiket=...)."""
    url = _teks_setelan("ESA_OFFICE_FRONTEND_URL")
    _periksa_url("ESA_OFFICE_FRONTEND_URL", url)
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path or "/", p.query, urlencode(fragmen)))


# ------------------------------ klien HTTP ---------------------------------

def _ringkas(v, n: int = 120) -> str:
    """Teks aman untuk log: tanpa karakter kontrol (cegah pemalsuan baris log) dan dipotong."""
    t = re.sub(r"[\x00-\x1f\x7f]", " ", str(v))
    return t if len(t) <= n else t[:n] + "…"


class _TolakRedirect(urllib.request.HTTPRedirectHandler):
    """Jangan pernah mengikuti redirect: kode, rahasia klien, dan token tidak boleh diteruskan ke alamat lain."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _baca_terbatas(resp, timeout: float) -> bytes:
    """Baca isi balasan paling banyak MAKS_BADAN byte dan paling lama ``timeout``
    detik. ``timeout`` socket hanya membatasi tiap operasi baca; tanpa tenggat
    keseluruhan ini, server yang menetes satu byte tiap beberapa detik bisa
    menahan satu worker selama berjam-jam."""
    tenggat = time.monotonic() + timeout
    baca = getattr(resp, "read1", None) or resp.read
    potongan, jumlah = [], 0
    while jumlah < MAKS_BADAN:
        if time.monotonic() > tenggat:
            raise EsaOfficeTidakTersedia("Esa Office terlalu lambat mengirim isi balasan")
        data = baca(min(4096, MAKS_BADAN - jumlah))
        if not data:
            break
        potongan.append(data)
        jumlah += len(data)
    return b"".join(potongan)


def _http(url: str, *, form: Optional[Dict[str, str]] = None, headers: Optional[Dict[str, str]] = None,
          timeout: float) -> Tuple[int, bytes]:
    """GET, atau POST form bila ``form`` diisi. Status apa pun dikembalikan apa
    adanya; galat dilempar hanya bila Esa Office tidak terjangkau atau terlalu
    lambat. Redirect tidak diikuti. Isi dibaca paling banyak MAKS_BADAN byte
    dalam ``timeout`` detik. Rahasia (client secret, kode, token) hanya lewat
    body/header dan tidak pernah masuk ke pesan galat."""
    permintaan = urllib.request.Request(
        url, method="POST" if form is not None else "GET",
        data=urlencode(form).encode("ascii") if form is not None else None)
    permintaan.add_header("Accept", "application/json")
    permintaan.add_header("User-Agent", "SANDO-SSO/2.0")
    if form is not None:
        permintaan.add_header("Content-Type", "application/x-www-form-urlencoded")
    for k, v in (headers or {}).items():
        permintaan.add_header(k, v)
    penangan = [_TolakRedirect]
    if urlsplit(url).hostname in _LOOPBACK:  # pengujian lokal: jangan lewat proxy
        penangan.insert(0, urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*penangan)  # selain itu tetap memakai proxy dari env bila ada
    try:
        with opener.open(permintaan, timeout=timeout) as resp:
            return resp.status, _baca_terbatas(resp, timeout)
    except urllib.error.HTTPError as e:  # sebelum URLError: HTTPError adalah turunannya
        try:
            mentah = _baca_terbatas(e, timeout)
        except (OSError, http.client.HTTPException, EsaOfficeTidakTersedia):
            mentah = b""  # isi galat tidak menentukan apa pun; statusnya sudah cukup
        finally:
            e.close()
        return e.code, mentah
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
        raise EsaOfficeTidakTersedia(
            f"tidak bisa menghubungi {_ringkas(url, 80)} ({type(e).__name__}: {_ringkas(e)})") from None


def _json(mentah: bytes):
    try:
        return json.loads(mentah) if mentah else None
    except (ValueError, RecursionError):  # ValueError mencakup UnicodeDecodeError dan JSONDecodeError
        return None


# ------------------------------- discovery ---------------------------------

@dataclass(frozen=True)
class Discovery:
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: str          # "" bila Esa Office tidak menyediakannya
    metode_auth: str                # client_secret_basic | client_secret_post
    pkce_diiklankan: bool           # code_challenge_methods_supported memuat S256
    algoritma_diiklankan: Tuple[str, ...]


_lock = threading.Lock()
_cache: Dict[tuple, tuple] = {}     # kunci -> (nilai, berlaku sampai (monotonic))


def reset_cache() -> None:
    with _lock:
        _cache.clear()


def _cache_ambil(kunci):
    with _lock:
        isi = _cache.get(kunci)
    return isi[0] if isi is not None and isi[1] > time.monotonic() else None


def _cache_simpan(kunci, nilai, ttl: float) -> None:
    with _lock:
        _cache[kunci] = (nilai, time.monotonic() + ttl)


def _ambil_discovery(konfig: Konfig) -> Discovery:
    url = konfig.issuer.rstrip("/") + "/.well-known/openid-configuration"
    status, mentah = _http(url, timeout=konfig.timeout)
    if status != 200:
        raise EsaOfficeTidakTersedia(f"dokumen discovery {url} dijawab HTTP {status}")
    isi = _json(mentah)
    if not isinstance(isi, dict):
        raise EsaOfficeTidakTersedia(f"dokumen discovery {url} bukan objek JSON")
    if isi.get("issuer") != konfig.issuer:
        raise KonfigurasiSalah(
            f"issuer pada dokumen discovery ({_ringkas(isi.get('issuer'))!r}) tidak sama persis dengan "
            f"ESA_OFFICE_ISSUER ({konfig.issuer!r})")
    titik = {}
    for nama in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        v = isi.get(nama)
        if not isinstance(v, str) or not v:
            raise KonfigurasiSalah(f"dokumen discovery tidak memuat {nama}")
        _periksa_url(nama, v)
        titik[nama] = v
    userinfo = isi.get("userinfo_endpoint") or ""
    if userinfo:
        if not isinstance(userinfo, str):
            raise KonfigurasiSalah("userinfo_endpoint pada dokumen discovery bukan teks")
        _periksa_url("userinfo_endpoint", userinfo)
    jenis = isi.get("response_types_supported")
    if isinstance(jenis, list) and "code" not in jenis:
        raise KonfigurasiSalah("Esa Office tidak mendukung response_type=code")
    metode_pkce = isi.get("code_challenge_methods_supported")
    if isinstance(metode_pkce, list) and "S256" not in metode_pkce:
        raise KonfigurasiSalah("Esa Office tidak mendukung PKCE S256")
    alg = isi.get("id_token_signing_alg_values_supported")
    diiklankan = tuple(a for a in alg if isinstance(a, str)) if isinstance(alg, list) else ()
    if diiklankan and not set(diiklankan) & set(konfig.algoritma):
        raise KonfigurasiSalah(
            f"Esa Office menandatangani ID token dengan {list(diiklankan)}; tidak ada yang diizinkan "
            f"ESA_OFFICE_ALGORITMA ({', '.join(konfig.algoritma)})")
    metode = isi.get("token_endpoint_auth_methods_supported")
    if metode is None:
        pilihan = "client_secret_basic"  # bawaan OIDC bila tidak diiklankan
    elif isinstance(metode, list) and "client_secret_basic" in metode:
        pilihan = "client_secret_basic"
    elif isinstance(metode, list) and "client_secret_post" in metode:
        pilihan = "client_secret_post"
    else:
        raise KonfigurasiSalah("token endpoint Esa Office tidak menerima client_secret_basic maupun client_secret_post")
    return Discovery(
        authorization_endpoint=titik["authorization_endpoint"], token_endpoint=titik["token_endpoint"],
        jwks_uri=titik["jwks_uri"], userinfo_endpoint=userinfo, metode_auth=pilihan,
        pkce_diiklankan=isinstance(metode_pkce, list) and "S256" in metode_pkce,
        algoritma_diiklankan=diiklankan)


def dokumen_discovery(konfig: Konfig) -> Discovery:
    """Dokumen discovery Esa Office, disimpan sejam per proses. Kegagalan juga
    diingat sebentar supaya Esa Office yang mati tidak menahan tiap permintaan
    selama batas waktu penuh."""
    kunci = ("discovery", konfig.issuer)
    ada = _cache_ambil(kunci)
    if ada is not None:
        if ada is False:
            raise EsaOfficeTidakTersedia("dokumen discovery baru saja gagal diambil; dicoba lagi sebentar lagi")
        return ada
    try:
        disc = _ambil_discovery(konfig)
    except EsaOfficeError:
        _cache_simpan(kunci, False, _TTL_GAGAL)
        raise
    _cache_simpan(kunci, disc, _TTL_DISCOVERY)
    return disc


# --------------------------------- JWKS ------------------------------------

@dataclass(frozen=True)
class _KunciJWK:
    kid: str
    kty: str
    alg: str
    kunci: object = field(repr=False)


def _muat_jwks(konfig: Konfig, disc: Discovery) -> List[_KunciJWK]:
    status, mentah = _http(disc.jwks_uri, timeout=konfig.timeout)
    if status != 200:
        raise EsaOfficeTidakTersedia(f"JWKS dijawab HTTP {status}")
    isi = _json(mentah)
    if not isinstance(isi, dict) or not isinstance(isi.get("keys"), list):
        raise EsaOfficeTidakTersedia('JWKS bukan {"keys": [...]}')
    hasil = []
    for k in isi["keys"][:32]:
        # Hanya kunci publik RSA/EC untuk tanda tangan. Kunci "oct" (HMAC) sengaja
        # tidak pernah dipakai: itu pintu serangan "algorithm confusion".
        if not isinstance(k, dict) or k.get("kty") not in ("RSA", "EC") or k.get("use") not in (None, "sig"):
            continue
        try:
            kunci = jwt.PyJWK(k).key
        except Exception:  # noqa: BLE001 -- satu kunci rusak tidak boleh menggagalkan yang lain
            continue
        hasil.append(_KunciJWK(kid=str(k.get("kid") or ""), kty=k["kty"], alg=str(k.get("alg") or ""), kunci=kunci))
    if not hasil:
        raise EsaOfficeTidakTersedia("JWKS tidak memuat kunci tanda tangan RSA/EC yang bisa dipakai")
    return hasil


def _jwks_segar(konfig: Konfig, disc: Discovery) -> List[_KunciJWK]:
    daftar = _muat_jwks(konfig, disc)
    _cache_simpan(("jwks", konfig.issuer), daftar, _TTL_JWKS)
    _cache_simpan(("jwks-diunduh", konfig.issuer), True, _JEDA_JWKS)
    return daftar


def _kunci_publik(konfig: Konfig, disc: Discovery, kid, alg: str):
    kty = "RSA" if alg.startswith(("RS", "PS")) else "EC"

    def pilih(daftar):
        cocok = [k for k in daftar if k.kty == kty and (not k.alg or k.alg == alg)]
        if kid:
            cocok = [k for k in cocok if k.kid == kid]
        return cocok[0] if len(cocok) == 1 else None  # tanpa kid dan kuncinya >1: ambigu, jangan menebak

    daftar = _cache_ambil(("jwks", konfig.issuer))
    segar = daftar is None
    if segar:
        daftar = _jwks_segar(konfig, disc)
    k = pilih(daftar)
    if k is None and not segar and _cache_ambil(("jwks-diunduh", konfig.issuer)) is None:
        k = pilih(_jwks_segar(konfig, disc))  # Esa Office mungkin baru merotasi kunci
    if k is None:
        raise TokenTidakValid(f"tidak ada kunci JWKS yang cocok untuk kid={_ringkas(kid, 40)!r} alg={alg}")
    return k.kunci


# ------------------------------ PKCE & cookie ------------------------------

def _tantangan_pkce(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def _tambah_query(url: str, pasangan: List[Tuple[str, str]]) -> str:
    p = urlsplit(url)
    ada = parse_qsl(p.query, keep_blank_values=True)
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(ada + pasangan, quote_via=quote), ""))


def mulai_login(paksa_login: bool = False, tantangan: str = "") -> Tuple[str, str]:
    """Awal login. Mengembalikan (alamat otorisasi di Esa Office, nilai cookie
    sesi untuk ``pasang_cookie``). ``paksa_login`` meminta Esa Office menanyakan
    kata sandi lagi (prompt=login), mis. setelah pengguna keluar dari SANDO di
    komputer bersama.

    ``tantangan`` (wajib) adalah SHA-256 dari ``verifier`` acak yang dibuat dan
    disimpan frontend di browsernya sendiri. Ia ikut di cookie bertanda tangan,
    lalu dipasang pada tiket yang terbit di callback: tiket itu hanya bisa
    ditukar oleh pemegang ``verifier`` yang sama (lihat ``tukar_tiket``)."""
    konfig = konfigurasi()
    if not isinstance(tantangan, str) or not _POLA_TANTANGAN.fullmatch(tantangan):
        raise EsaOfficeError("tantangan pengikat dari frontend tidak ada atau bentuknya salah")
    disc = dokumen_discovery(konfig)
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    pasangan = [("response_type", "code"), ("client_id", konfig.client_id),
                ("redirect_uri", konfig.redirect_uri), ("scope", konfig.scope),
                ("state", state), ("nonce", nonce),
                ("code_challenge", _tantangan_pkce(verifier)), ("code_challenge_method", "S256")]
    if paksa_login:
        pasangan.append(("prompt", "login"))
    cookie = signing.dumps({"s": state, "n": nonce, "v": verifier, "t": tantangan}, salt=_SALT_COOKIE, compress=False)
    return _tambah_query(disc.authorization_endpoint, pasangan), cookie


def pasang_cookie(resp, nilai: str) -> None:
    resp.set_cookie(NAMA_COOKIE, nilai, max_age=MASA_COOKIE, path=PATH_COOKIE,
                    secure=not settings.DEBUG, httponly=True, samesite="Lax")


def hapus_cookie(resp) -> None:
    resp.delete_cookie(NAMA_COOKIE, path=PATH_COOKIE, samesite="Lax")


def _baca_cookie(nilai: Optional[str]) -> Dict[str, str]:
    if not nilai:
        raise SesiKedaluwarsa("cookie sesi login tidak ada")
    try:
        isi = signing.loads(nilai, salt=_SALT_COOKIE, max_age=MASA_COOKIE)
    except (signing.BadSignature, ValueError, TypeError):  # SignatureExpired adalah turunan BadSignature
        raise SesiKedaluwarsa("cookie sesi login tidak sah atau sudah kedaluwarsa") from None
    if not isinstance(isi, dict) or not all(isinstance(isi.get(k), str) and isi[k] for k in ("s", "n", "v", "t")):
        raise SesiKedaluwarsa("isi cookie sesi login tidak lengkap")
    return isi


# ------------------------------ token endpoint -----------------------------

def _kode_oauth(isi) -> str:
    v = isi.get("error") if isinstance(isi, dict) else None
    return v if isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", v) else ""


def tukar_kode(konfig: Konfig, disc: Discovery, kode: str, verifier: str) -> dict:
    form = {"grant_type": "authorization_code", "code": kode, "redirect_uri": konfig.redirect_uri,
            "code_verifier": verifier}
    header: Dict[str, str] = {}
    if disc.metode_auth == "client_secret_post":
        form["client_id"], form["client_secret"] = konfig.client_id, konfig.client_secret
    else:  # RFC 6749 2.3.1: id dan rahasia di-form-urlencode dulu, baru Base64
        kredensial = f"{quote(konfig.client_id, safe='')}:{quote(konfig.client_secret, safe='')}"
        header["Authorization"] = "Basic " + base64.b64encode(kredensial.encode("utf-8")).decode("ascii")
    status, mentah = _http(disc.token_endpoint, form=form, headers=header, timeout=konfig.timeout)
    isi = _json(mentah)
    if status != 200:
        galat = _kode_oauth(isi)
        if status == 400 and galat == "invalid_grant":  # kode kedaluwarsa, terpakai, atau PKCE tak cocok
            raise SesiKedaluwarsa("token endpoint menolak kode (invalid_grant)")
        if status in (400, 401):
            raise KonfigurasiSalah(
                f"token endpoint menolak permintaan (HTTP {status}, error={galat or '-'}); periksa "
                "ESA_OFFICE_CLIENT_ID/SECRET, ESA_OFFICE_REDIRECT_URI, dan pendaftaran klien di Esa Office")
        raise EsaOfficeTidakTersedia(f"token endpoint dijawab HTTP {status}")
    if not isinstance(isi, dict) or not isinstance(isi.get("id_token"), str) or not isi["id_token"]:
        raise TokenTidakValid("balasan token endpoint tidak memuat id_token")
    return isi


def periksa_id_token(token: str, konfig: Konfig, disc: Discovery, nonce: str) -> dict:
    """Klaim ID token yang sudah terbukti sah, atau TokenTidakValid."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise TokenTidakValid("ID token bukan JWT yang wajar") from None
    alg, kid = header.get("alg"), header.get("kid")
    if not isinstance(alg, str) or alg not in konfig.algoritma:  # termasuk "none" dan HS*
        raise TokenTidakValid(f"algoritma ID token {_ringkas(alg, 20)!r} tidak diizinkan")
    if kid is not None and not isinstance(kid, str):
        raise TokenTidakValid("kid pada header ID token bukan teks")
    kunci = _kunci_publik(konfig, disc, kid, alg)
    try:
        klaim = jwt.decode(
            token, kunci, algorithms=[alg], audience=konfig.client_id, issuer=konfig.issuer,
            leeway=_TOLERANSI_JAM, options={"require": ["exp", "iat", "iss", "aud", "sub"]})
    except jwt.PyJWTError as e:
        raise TokenTidakValid(f"ID token ditolak: {type(e).__name__}") from None
    n = klaim.get("nonce")
    if not isinstance(n, str) or not hmac.compare_digest(n.encode("utf-8", "replace"), nonce.encode("utf-8")):
        raise TokenTidakValid("nonce ID token tidak cocok")
    aud, azp = klaim.get("aud"), klaim.get("azp")
    if (isinstance(aud, list) and len(aud) > 1 and azp != konfig.client_id) or (
            azp is not None and azp != konfig.client_id):
        raise TokenTidakValid("azp ID token bukan klien ini")
    sub = klaim.get("sub")
    if (not isinstance(sub, str) or not sub or len(sub) > MAKS_SUB or sub != sub.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in sub) or _tak_bisa_dikodekan(sub)):
        raise TokenTidakValid("sub ID token tidak wajar")
    return klaim


def ambil_userinfo(konfig: Konfig, disc: Discovery, access_token: str, sub: str) -> dict:
    status, mentah = _http(disc.userinfo_endpoint, headers={"Authorization": "Bearer " + access_token},
                           timeout=konfig.timeout)
    if status != 200:
        raise EsaOfficeTidakTersedia(f"userinfo dijawab HTTP {status}")
    isi = _json(mentah)
    if not isinstance(isi, dict):
        raise EsaOfficeTidakTersedia("userinfo bukan objek JSON")
    if isi.get("sub") != sub:  # wajib sama (OIDC Core 5.3.2); beda berarti token tertukar
        raise TokenTidakValid("sub pada userinfo tidak sama dengan sub ID token")
    return isi


# -------------------------------- identitas ---------------------------------

@dataclass(frozen=True)
class IdentitasEsa:
    sub: str
    nama: str
    nip: str        # "" bila Esa Office tidak mengirimnya
    pd_id: str      # ID perangkat daerah yang stabil di Esa Office
    pd_nama: str


def _tak_bisa_dikodekan(s: str) -> bool:
    try:
        s.encode("utf-8")
    except UnicodeEncodeError:  # mis. surrogat tunggal dari JSON "\ud800"
        return True
    return False


def _teks(v) -> str:
    """Teks bersih (tanpa karakter kontrol dan surrogat, spasi dirapikan); bukan string -> kosong."""
    if not isinstance(v, str):
        return ""
    v = v.encode("utf-8", "ignore").decode("utf-8")
    return " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", v).split())


def _id_teks(v, maks: int) -> str:
    if isinstance(v, bool) or not isinstance(v, (str, int)):
        return ""
    try:
        t = str(v).strip()
    except ValueError:  # bilangan bulat berdigit ribuan
        return ""
    if not t or len(t) > maks or any(ord(c) < 32 or ord(c) == 127 for c in t) or _tak_bisa_dikodekan(t):
        return ""
    return t


def _nip(v) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, bool) or not isinstance(v, (str, int)):
        raise IdentitasTidakLengkap("klaim nip bukan teks atau angka")
    try:
        t = "".join(str(v).split())
    except ValueError:
        raise IdentitasTidakLengkap("klaim nip tidak wajar") from None
    if not re.fullmatch(r"[0-9]{1,%d}" % MAKS_NIP, t):
        raise IdentitasTidakLengkap("klaim nip tidak wajar (harus angka, tanpa spasi)")
    return t


def ambil_identitas(klaim: dict) -> IdentitasEsa:
    """Baca klaim ``name``, ``nip``, dan ``perangkat_daerah {id, name}``. Nama dan
    ID perangkat daerah wajib; NIP boleh kosong tetapi bila ada harus berupa angka."""
    pd = klaim.get("perangkat_daerah")
    pd = pd if isinstance(pd, dict) else {}
    nama, pd_id = _teks(klaim.get("name")), _id_teks(pd.get("id"), MAKS_ID_PD)
    if not nama:
        raise IdentitasTidakLengkap("klaim name kosong")
    if not pd_id:
        raise IdentitasTidakLengkap("klaim perangkat_daerah.id kosong")
    return IdentitasEsa(sub=klaim["sub"], nama=nama[:MAKS_NAMA], nip=_nip(klaim.get("nip")),
                        pd_id=pd_id, pd_nama=_teks(pd.get("name"))[:150])


def _identitas_dari(klaim: dict, access_token, konfig: Konfig, disc: Discovery) -> IdentitasEsa:
    """Dari klaim ID token; bila ada yang belum ada dan Esa Office punya userinfo,
    dilengkapi dari sana (klaim ID token yang bertanda tangan tetap menang)."""
    tambahan: dict = {}
    kurang = [k for k in ("name", "nip", "perangkat_daerah") if not klaim.get(k)]
    if kurang and disc.userinfo_endpoint and isinstance(access_token, str) and access_token:
        try:
            tambahan = ambil_userinfo(konfig, disc, access_token, klaim["sub"])
        except EsaOfficeTidakTersedia as e:  # kelengkapannya diperiksa di bawah; sub yang tak cocok tetap menggagalkan
            log.warning("SSO Esa Office: userinfo tidak bisa diambil (%s)", e)
    return ambil_identitas({**tambahan, **klaim})


# ------------------------- pemetaan perangkat daerah ------------------------

def _norm(s: Optional[str]) -> str:
    """Huruf kecil, tanda baca dan garis bawah jadi spasi, serta tanpa imbuhan
    "Kabupaten Rote Ndao" (wilayah SANDO ini tetap)."""
    t = re.sub(r"[\W_]+", " ", (s or "").casefold())
    return " ".join(re.sub(r"\b(?:kabupaten|kab) rote ndao\b", " ", t).split())


def petakan_opd(pd_id: str, pd_nama: str) -> Optional[OPD]:
    """OPD SANDO untuk perangkat daerah Esa Office, atau None.

    Utama: ``OPD.esa_id`` sama dengan ID dari Esa Office. Bila belum ada OPD yang
    memegang ID itu (dan ESA_OFFICE_PETAKAN_OPD_OTOMATIS menyala), ID dipasangkan
    dengan tepat satu OPD aktif yang belum punya ``esa_id`` dan namanya (kode,
    singkatan, atau nama; tanpa membedakan huruf dan tanda baca) cocok. Nol atau
    lebih dari satu kecocokan = None: tidak ada tebakan "mirip". Pasangan yang
    sudah terpasang tidak pernah diubah oleh login; yang berubah (pemekaran,
    penggabungan) harus diperbaiki admin di /admin/."""
    terikat = OPD.objects.filter(esa_id=pd_id).first()
    if terikat is not None:
        return terikat if terikat.aktif else None
    if not getattr(settings, "ESA_OFFICE_PETAKAN_OPD_OTOMATIS", True):
        return None
    kunci = {_norm(pd_nama), _norm(pd_id)} - {""}
    if not kunci:
        return None
    cocok = [o for o in OPD.objects.filter(aktif=True, esa_id="")
             if kunci & ({_norm(o.kode), _norm(o.singkatan), _norm(o.nama)} - {""})]
    if len(cocok) != 1:
        return None
    opd = cocok[0]
    try:
        with transaction.atomic():
            opd.esa_id = pd_id
            opd.save(update_fields=["esa_id"])
    except IntegrityError:  # proses lain baru saja memasang ID yang sama
        return OPD.objects.filter(esa_id=pd_id, aktif=True).first()
    log.info("OPD %s dipasangkan dengan perangkat_daerah.id=%r dari Esa Office", opd.kode, _ringkas(pd_id))
    LogAktivitas.catat(None, "petakan OPD Esa Office", opd.kode, f"esa_id={pd_id}")
    return opd


# ------------------------- sinkronisasi akun lokal --------------------------

def _nip_diizinkan(nip: str) -> bool:
    return bool(nip) and nip in {"".join(x.split()) for x in _daftar(getattr(settings, "ESA_OFFICE_TAUTKAN_NIP", ()))}


def _perlu_konfirmasi(user: User, nip: str) -> bool:
    """Akun istimewa (verifikator/admin/staf/superuser) yang masih punya kata sandi
    lokal: bahwa pemilik NIP di Esa Office orang yang sama dengan pemegang akun itu
    belum pernah dipastikan siapa pun kecuali NIP-nya didaftarkan operator."""
    istimewa = user.bisa_verifikasi or user.is_staff or user.is_superuser
    return istimewa and user.has_usable_password() and not _nip_diizinkan(nip)


def _calon_tautan(identitas: IdentitasEsa) -> Optional[User]:
    """Akun SANDO lama (belum punya identitas eksternal) yang NIP-nya sama, atau None."""
    sama = list(User.objects.filter(nip=identitas.nip)[:5])
    if any(u.external_subject for u in sama):  # NIP ini sudah dipegang akun yang ditautkan ke subject lain
        raise AkunGanda(f"NIP sudah ditautkan ke subject Esa Office lain (sub={_ringkas(identitas.sub, 40)!r})")
    if len(sama) > 1:
        raise AkunGanda(f"lebih dari satu akun SANDO ber-NIP sama (sub={_ringkas(identitas.sub, 40)!r})")
    return sama[0] if sama else None


def _username_baru(identitas: IdentitasEsa) -> str:
    """NIP bila ada (mudah dikenali admin), selain itu turunan subject. Bentrok -> turunan subject."""
    kandidat = identitas.nip or "esa-" + hashlib.sha256(identitas.sub.encode("utf-8")).hexdigest()[:16]
    if User.objects.filter(username=kandidat).exists():
        kandidat = "esa-" + hashlib.sha256((PENYEDIA + "|" + identitas.sub).encode("utf-8")).hexdigest()[:24]
    return kandidat


def sinkronkan_akun(identitas: IdentitasEsa, *, _ulang: bool = False) -> User:
    """Akun SANDO untuk identitas dari Esa Office; dibuat sebagai operator bila belum
    ada. Nama selalu, dan OPD bagi operator, mengikuti Esa Office."""
    user = User.objects.filter(identity_provider=PENYEDIA, external_subject=identitas.sub).first()
    tautkan = False
    if user is None and identitas.nip:
        user = _calon_tautan(identitas)
        tautkan = user is not None
    if user is not None:
        if not user.is_active:
            raise AkunDinonaktifkan(f"akun {user.username!r} dinonaktifkan di SANDO")
        if tautkan and _perlu_konfirmasi(user, identitas.nip):
            raise TautanBelumDiizinkan(
                f"akun lokal {user.username!r} (peran={user.peran}) punya kata sandi lokal dan NIP-nya belum "
                "didaftarkan di ESA_OFFICE_TAUTKAN_NIP; daftarkan hanya bila pemilik NIP itu di Esa Office "
                "memang orang yang sama dengan pemegang akun")
    # Pemetaan OPD bisa menulis OPD.esa_id, jadi baru dijalankan setelah akunnya
    # dinyatakan boleh masuk: login yang ditolak tidak meninggalkan jejak apa pun.
    opd = petakan_opd(identitas.pd_id, identitas.pd_nama)
    # Verifikator/admin melihat semua OPD, jadi OPD yang tak dikenal tidak
    # menghalangi mereka; operator tanpa OPD yang jelas harus ditolak.
    if opd is None and (user is None or not user.bisa_verifikasi):
        raise OPDTidakDikenal(f"perangkat_daerah.id={_ringkas(identitas.pd_id, 40)!r} "
                              f"nama={_ringkas(identitas.pd_nama, 60)!r} tidak cocok dengan OPD mana pun")
    if user is None:
        return _buat_akun(identitas, opd, _ulang)

    ubah, catatan_opd = [], None
    if tautkan:
        user.identity_provider, user.external_subject = PENYEDIA, identitas.sub
        ubah += ["identity_provider", "external_subject"]
    if user.first_name != identitas.nama or user.last_name:
        user.first_name, user.last_name = identitas.nama, ""
        ubah += ["first_name", "last_name"]
    if identitas.nip and user.nip != identitas.nip:
        if User.objects.filter(nip=identitas.nip).exclude(pk=user.pk).exists():
            log.warning("SSO Esa Office: NIP baru milik sub=%r sudah dipakai akun SANDO lain; NIP tidak diubah",
                        _ringkas(identitas.sub, 40))
        else:
            user.nip = identitas.nip
            ubah.append("nip")
    if opd is not None and user.opd_id != opd.id and (not user.bisa_verifikasi or user.opd_id is None):
        catatan_opd = f"{user.opd.kode if user.opd_id else '-'} -> {opd.kode}"
        user.opd = opd
        ubah.append("opd")
    if ubah:
        try:
            with transaction.atomic():
                user.save(update_fields=ubah)
        except IntegrityError:
            # Login serentak untuk identitas yang sama: proses lain lebih dulu. Ulangi
            # sekali supaya semua pemeriksaan di atas berlaku juga atas hasilnya.
            if _ulang:
                raise AkunGanda("bentrok saat memperbarui akun yang sama dua kali berturut-turut") from None
            return sinkronkan_akun(identitas, _ulang=True)
    if tautkan:
        LogAktivitas.catat(user, "tautkan akun Esa Office", user.username[:MAKS_OBJEK], "ditautkan lewat NIP")
    if catatan_opd:
        LogAktivitas.catat(user, "pindah OPD via Esa Office", user.username[:MAKS_OBJEK], catatan_opd)
    return user


def _buat_akun(identitas: IdentitasEsa, opd: OPD, ulang: bool) -> User:
    baru = User(username=_username_baru(identitas), peran=User.OPERATOR, opd=opd, first_name=identitas.nama,
                nip=identitas.nip, identity_provider=PENYEDIA, external_subject=identitas.sub)
    baru.set_unusable_password()
    try:
        with transaction.atomic():
            baru.save()
    except IntegrityError:
        if ulang:
            raise AkunGanda("bentrok saat membuat akun, tetapi akunnya tidak ditemukan") from None
        return sinkronkan_akun(identitas, _ulang=True)
    LogAktivitas.catat(baru, "buat akun via Esa Office", baru.username[:MAKS_OBJEK], f"OPD {opd.kode}")
    return baru


# ------------------------------ tiket masuk --------------------------------

def _sidik(tiket: str) -> str:
    return hashlib.sha256(tiket.encode("utf-8")).hexdigest()


def terbitkan_tiket(user: User, tantangan: str) -> str:
    tiket = secrets.token_urlsafe(32)
    sekarang = timezone.now()
    TiketMasuk.objects.filter(kedaluwarsa__lt=sekarang).delete()  # bersih-bersih sambil lalu
    TiketMasuk.objects.create(sidik=_sidik(tiket), pengguna=user, tantangan=tantangan,
                              kedaluwarsa=sekarang + timedelta(seconds=MASA_TIKET))
    return tiket


def tukar_tiket(tiket, verifier) -> Optional[User]:
    """Pengguna pemilik tiket, atau None. Tiket hanya berlaku sekali dan semenit,
    dan hanya untuk pembawa ``verifier`` yang tantangannya (SHA-256) dikirim saat
    login dimulai.

    Pengikat itu menutup login CSRF di tahap terakhir: tanpanya, penyerang yang
    punya akun Esa Office sendiri bisa menyelesaikan login di browsernya, lalu
    menyuruh korban membuka ``https://sando/#esa_tiket=<tiket penyerang>`` dan
    korban masuk sebagai penyerang. ``verifier`` penyerang tidak ada di browser
    korban, jadi penukaran itu gagal."""
    if not isinstance(tiket, str) or not 20 <= len(tiket) <= 200 or _tak_bisa_dikodekan(tiket):
        return None
    if not isinstance(verifier, str) or not _POLA_VERIFIER.fullmatch(verifier):
        return None
    baris = (TiketMasuk.objects.select_related("pengguna")
             .filter(sidik=_sidik(tiket), kedaluwarsa__gt=timezone.now()).first())
    if baris is None:
        return None
    dihapus, _ = TiketMasuk.objects.filter(pk=baris.pk).delete()
    if dihapus != 1:  # penukar lain yang serentak menang
        return None
    # Hapus dulu, baru bandingkan: setiap percobaan, benar atau salah, menghanguskan tiket.
    if not hmac.compare_digest(_tantangan_pkce(verifier).encode("ascii"), baris.tantangan.encode("utf-8")):
        return None
    return baris.pengguna if baris.pengguna.is_active else None


# --------------------------------- alur login -------------------------------

def selesai_login(*, code: str, state: str, galat: str, cookie: Optional[str]) -> str:
    """Selesaikan login setelah Esa Office mengalihkan browser kembali. Mengembalikan
    tiket sekali pakai untuk frontend; melempar EsaOfficeError (``kode``) bila gagal."""
    konfig = konfigurasi()
    sesi = _baca_cookie(cookie)
    # Pengikat ke browser: tanpa ini, orang lain bisa menyuruh korban membuka tautan
    # callback berisi kode miliknya sendiri, dan korban masuk sebagai orang itu.
    if not state or not hmac.compare_digest(state.encode("utf-8", "replace"), sesi["s"].encode("utf-8")):
        raise SesiKedaluwarsa("state tidak cocok dengan cookie sesi")
    if galat:
        alasan = re.sub(r"[^A-Za-z0-9_.:-]", "", galat)[:64]
        if alasan == "access_denied":
            raise LoginDibatalkan("pengguna membatalkan login di Esa Office")
        if alasan in ("temporarily_unavailable", "server_error"):
            raise EsaOfficeTidakTersedia(f"Esa Office melaporkan {alasan}")
        raise EsaOfficeError(f"Esa Office menolak permintaan otorisasi: {alasan or '-'}")
    if not code or len(code) > 2048 or any(ord(c) < 32 or ord(c) == 127 for c in code):
        raise EsaOfficeError("kode otorisasi tidak ada atau tidak wajar")
    disc = dokumen_discovery(konfig)
    tanggapan = tukar_kode(konfig, disc, code, sesi["v"])
    klaim = periksa_id_token(tanggapan["id_token"], konfig, disc, sesi["n"])
    identitas = _identitas_dari(klaim, tanggapan.get("access_token"), konfig, disc)
    return terbitkan_tiket(sinkronkan_akun(identitas), sesi["t"])


def laporkan(e: Exception) -> str:
    """Catat galat di log server dan kembalikan kode untuk frontend. Dipanggil dari
    dalam blok ``except``; galat yang tak terduga (bug) dicatat lengkap dengan
    tracebacknya tetapi ke pengguna hanya tampil sebagai "gagal"."""
    if isinstance(e, EsaOfficeError):
        # Yang dipicu pengguna cukup peringatan; yang menandakan masalah di sisi
        # konfigurasi/Esa Office/token adalah galat yang perlu dilihat admin.
        tingkat = log.error if isinstance(e, (KonfigurasiSalah, EsaOfficeTidakTersedia, TokenTidakValid)) else log.warning
        tingkat("SSO Esa Office: %s [%s]", _ringkas(e, 300), e.kode)
        return e.kode
    log.exception("SSO Esa Office: galat tak terduga")
    return "gagal"


# ------------------------------- diagnosa -----------------------------------

def diagnosa() -> List[str]:
    """Periksa konfigurasi dan Esa Office apa adanya (discovery, JWKS), lalu
    jelaskan apa yang perlu dilakukan. Tidak menulis ke basis data dan tidak
    pernah menampilkan rahasia."""
    try:
        konfig = konfigurasi()
    except EsaOfficeError as e:
        return [f"Konfigurasi        : SALAH -- {e}"]
    baris = [
        f"Issuer             : {konfig.issuer}",
        f"Client ID          : {konfig.client_id}",
        "Client secret      : terisi (tidak ditampilkan)",
        f"Redirect URI       : {konfig.redirect_uri}   <- daftarkan PERSIS ini di Esa Office",
        f"Scope              : {konfig.scope}",
        f"Algoritma diizinkan: {', '.join(konfig.algoritma)}",
    ]
    try:
        baris.append(f"Alamat frontend    : {url_frontend()}")
    except EsaOfficeError as e:
        baris.append(f"Alamat frontend    : SALAH -- {e}")
    reset_cache()
    try:
        disc = dokumen_discovery(konfig)
    except EsaOfficeError as e:
        return baris + [f"Discovery          : GAGAL -- {e}",
                        "Jalankan perintah ini dari server SANDO: firewall/daftar putih domain (mis. "
                        "PythonAnywhere Free) atau pembatas IP di Esa Office bisa menghalangi."]
    baris += [
        "Discovery          : OK",
        f"  authorize        : {disc.authorization_endpoint}",
        f"  token            : {disc.token_endpoint}  (autentikasi klien: {disc.metode_auth})",
        f"  jwks             : {disc.jwks_uri}",
        f"  userinfo         : {disc.userinfo_endpoint or '(tidak ada)'}",
        "  PKCE S256        : " + ("diiklankan" if disc.pkce_diiklankan else
                                   "TIDAK diiklankan (code_challenge_methods_supported kosong); pastikan "
                                   "Esa Office menegakkannya"),
        f"  algoritma token  : {', '.join(disc.algoritma_diiklankan) or '(tidak diiklankan)'}",
    ]
    try:
        kunci = _muat_jwks(konfig, disc)
        baris.append(f"JWKS               : OK, {len(kunci)} kunci tanda tangan")
        baris += [f"  kid={k.kid or '(tanpa kid)'} kty={k.kty} alg={k.alg or '(tidak dinyatakan)'}" for k in kunci]
        if len(kunci) > 1 and not all(k.kid for k in kunci):
            baris.append("  PERINGATAN: ada lebih dari satu kunci tetapi sebagian tanpa kid; token tidak bisa dicocokkan.")
    except EsaOfficeError as e:
        baris.append(f"JWKS               : GAGAL -- {e}")
    baris += ["", "Klaim yang dibutuhkan SANDO (ID token atau userinfo): sub, name, perangkat_daerah.id; "
                  "disarankan nip dan perangkat_daerah.name."]
    return baris
