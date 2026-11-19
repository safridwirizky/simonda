"""Esa Office tiruan (penyedia identitas OpenID Connect) untuk uji SSO.

Server HTTP lokal di 127.0.0.1 yang menirukan sisi Esa Office secukupnya untuk
menguji klien SANDO: dokumen discovery, JWKS, /authorize (menolak parameter yang
kurang), /token (autentikasi klien, kode sekali pakai, PKCE S256), /userinfo, dan
ID token bertanda tangan RS256/ES256 sungguhan. Tidak ada halaman login:
/authorize langsung menyetujui ``IdP.masuk_sebagai`` (atau menjawab access_denied
bila None).

Dipakai oleh uji_esa_office.py. Ini bukan bagian aplikasi dan tidak boleh dipakai
di luar pengujian. Butuh PyJWT[crypto], yang memang dipakai aplikasi.
"""
import base64
import hashlib
import json
import secrets
import sys
import threading
import time
from typing import Optional
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote_plus, urlencode, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

# Perangkat daerah dan pegawai contoh di Esa Office tiruan.
PD_DINKES = {"id": "pd-dinkes", "name": "Dinas Kesehatan"}
PD_DISTAN = {"id": "pd-distan", "name": "Dinas Ketahanan Pangan"}
PENGGUNA = {
    "sub-budi": {"name": "Budi Santoso", "nip": "198001012005011001", "phone_number": "081234567890",
                 "email": "budi@example.go.id", "perangkat_daerah": PD_DINKES},
    "sub-sari": {"name": "Sari Wulandari", "nip": "198505052010012002", "phone_number": "081298765432",
                 "email": "sari@example.go.id", "perangkat_daerah": PD_DISTAN},
}


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


class Kunci:
    """Pasangan kunci penandatangan beserta JWK publiknya."""

    def __init__(self, jenis: str, kid: str):
        self.kid, self.jenis = kid, jenis
        if jenis == "RSA":
            self.privat, self.alg, algo = rsa.generate_private_key(65537, 2048), "RS256", RSAAlgorithm
        else:
            self.privat, self.alg, algo = ec.generate_private_key(ec.SECP256R1()), "ES256", ECAlgorithm
        self.jwk = {**algo.to_jwk(self.privat.public_key(), as_dict=True), "kid": kid, "use": "sig", "alg": self.alg}


class IdP:
    CLIENT_ID = "sando-uji"
    # Sengaja memuat karakter yang harus di-form-urlencode pada autentikasi Basic (RFC 6749 2.3.1).
    CLIENT_SECRET = "rahasia uji:+/=&%"

    def __init__(self):
        self.rsa, self.ec = Kunci("RSA", "rsa-1"), Kunci("EC", "ec-1")
        self.rsa_lain = Kunci("RSA", "rsa-2")   # kunci yang TIDAK ada di JWKS: untuk memalsukan tanda tangan
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Penangan)
        self.server.idp = self
        self.server.handle_error = lambda *a: None if isinstance(sys.exc_info()[1], OSError) else _lapor(*a)
        self.port = self.server.server_address[1]
        self.issuer = f"http://127.0.0.1:{self.port}"
        self.redirect_uri = "http://localhost:8000/api/auth/esa/callback"
        self.arsip = {"kode": [], "akses": [], "id_token": []}   # semua rahasia yang pernah terbit (tidak ikut reset)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.reset()

    # -------------------------------- keadaan ---------------------------------
    def reset(self):
        self.rekam = []                  # (metode, path, parameter, header) tiap permintaan masuk
        self.kode = {}                   # kode otorisasi -> info
        self.token_akses = {}            # access_token -> sub
        self.masuk_sebagai: Optional[str] = None   # sub yang "sedang login" di Esa Office
        self.pengguna = {k: json.loads(json.dumps(v)) for k, v in PENGGUNA.items()}
        self.kunci_tanda = self.rsa      # kunci penandatangan ID token
        self.jwks_isi = [self.rsa, self.ec]
        self.override = {}               # path -> fungsi(penangan) -> True bila sudah menjawab
        self.ubah_klaim = None           # fungsi(klaim) yang mengubah klaim sebelum ditandatangani
        self.ubah_discovery = None       # fungsi(dokumen) ...
        self.ubah_jwks = None            # fungsi(dokumen) ...
        self.id_token_ganti = None       # fungsi(klaim) -> teks ID token yang dikirim apa adanya
        self.masa_id_token = 300
        self.sertakan_profil_di_id_token = True

    def permintaan(self, path=None, metode=None):
        return [r for r in self.rekam if (path is None or r[1] == path) and (metode is None or r[0] == metode)]

    # ------------------------------- dokumen ----------------------------------
    def discovery(self):
        d = {"issuer": self.issuer, "authorization_endpoint": f"{self.issuer}/authorize",
             "token_endpoint": f"{self.issuer}/token", "userinfo_endpoint": f"{self.issuer}/userinfo",
             "jwks_uri": f"{self.issuer}/jwks", "response_types_supported": ["code"],
             "subject_types_supported": ["public"],
             "id_token_signing_alg_values_supported": ["RS256", "ES256"],
             "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
             "code_challenge_methods_supported": ["S256"],
             "scopes_supported": ["openid", "profile", "email", "phone"]}
        if self.ubah_discovery:
            self.ubah_discovery(d)
        return d

    def jwks(self):
        d = {"keys": [dict(k.jwk) for k in self.jwks_isi]}  # salinan: uji boleh mengubahnya tanpa merusak kunci
        if self.ubah_jwks:
            self.ubah_jwks(d)
        return d

    def klaim_profil(self, sub):
        return dict(self.pengguna[sub])

    def klaim_id_token(self, sub, nonce):
        sekarang = int(time.time())
        klaim = {"iss": self.issuer, "sub": sub, "aud": self.CLIENT_ID, "iat": sekarang,
                 "exp": sekarang + self.masa_id_token, "nonce": nonce}
        if self.sertakan_profil_di_id_token:
            klaim.update(self.klaim_profil(sub))
        if self.ubah_klaim:
            self.ubah_klaim(klaim)
        return klaim

    def tanda_tangan(self, klaim, *, alg=None, kunci=None, kid="-"):
        """ID token bertanda tangan. ``kunci`` bawaannya kunci aktif; ``kid`` "-" = kid kunci itu, None = tanpa kid."""
        kunci = kunci or self.kunci_tanda
        kid = kunci.kid if kid == "-" else kid
        return jwt.encode(klaim, kunci.privat, algorithm=alg or kunci.alg, headers={"kid": kid} if kid else None)

    # ------------------------- alur (dipanggil penangan) ----------------------
    def terbitkan_kode(self, q, sub):
        kode = secrets.token_urlsafe(24)
        self.kode[kode] = {"sub": sub, "nonce": q["nonce"], "challenge": q["code_challenge"],
                           "redirect_uri": q["redirect_uri"], "client_id": q["client_id"],
                           "kedaluwarsa": time.time() + 60, "dipakai": False}
        self.arsip["kode"].append(kode)
        return kode


def _lapor(request, client_address):
    import traceback
    traceback.print_exc()


class _Penangan(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def kirim(self, kode, isi=None, mentah=None, tipe="application/json", ekstra=None):
        badan = mentah if mentah is not None else (json.dumps(isi).encode() if isi is not None else b"")
        self.send_response(kode)
        self.send_header("Content-Type", tipe)
        self.send_header("Content-Length", str(len(badan)))
        for k, v in (ekstra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(badan)

    def _tangani(self, metode):
        idp = self.server.idp
        p = urlsplit(self.path)
        mentah = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if metode == "POST" else b""
        q = {k: v[-1] for k, v in parse_qs(p.query, keep_blank_values=True).items()}
        form = {k: v[-1] for k, v in parse_qs(mentah.decode("utf-8", "replace"), keep_blank_values=True).items()}
        header = {k.lower(): v for k, v in self.headers.items()}
        idp.rekam.append((metode, p.path, {**q, **form}, header))
        ganti = idp.override.get(p.path)
        if ganti and ganti(self):
            return
        if metode == "GET" and p.path == "/.well-known/openid-configuration":
            return self.kirim(200, idp.discovery())
        if metode == "GET" and p.path == "/jwks":
            return self.kirim(200, idp.jwks())
        if metode == "GET" and p.path == "/authorize":
            return self._otorisasi(idp, q)
        if metode == "POST" and p.path == "/token":
            return self._token(idp, form, header)
        if metode == "GET" and p.path == "/userinfo":
            sub = idp.token_akses.get(header.get("authorization", "")[7:])
            if sub is None or not header.get("authorization", "").startswith("Bearer "):
                return self.kirim(401, {"error": "invalid_token"})
            return self.kirim(200, {"sub": sub, **idp.klaim_profil(sub)})
        self.kirim(404, {"error": "tidak_ada"})

    do_GET = lambda self: self._tangani("GET")    # noqa: E731
    do_POST = lambda self: self._tangani("POST")  # noqa: E731

    def _otorisasi(self, idp, q):
        # Galat pada client_id/redirect_uri tidak boleh dialihkan (OIDC Core 3.1.2.6).
        if q.get("client_id") != idp.CLIENT_ID:
            return self.kirim(400, mentah=b"client_id tidak dikenal", tipe="text/plain")
        if q.get("redirect_uri") != idp.redirect_uri:
            return self.kirim(400, mentah=b"redirect_uri tidak terdaftar", tipe="text/plain")

        def balas(**isi):
            if q.get("state"):
                isi["state"] = q["state"]
            self.kirim(302, mentah=b"", ekstra={"Location": idp.redirect_uri + "?" + urlencode(isi)})

        if q.get("response_type") != "code":
            return balas(error="unsupported_response_type")
        if "openid" not in q.get("scope", "").split():
            return balas(error="invalid_scope")
        if not q.get("state") or not q.get("nonce"):
            return balas(error="invalid_request", error_description="state dan nonce wajib")
        if q.get("code_challenge_method") != "S256" or not q.get("code_challenge"):
            return balas(error="invalid_request", error_description="PKCE S256 wajib")
        if idp.masuk_sebagai is None:
            return balas(error="access_denied")
        balas(code=idp.terbitkan_kode(q, idp.masuk_sebagai))

    def _token(self, idp, form, header):
        # Autentikasi klien: Basic (id:rahasia, masing-masing di-form-urlencode) atau di badan form.
        id_, rahasia = form.get("client_id"), form.get("client_secret")
        auth = header.get("authorization", "")
        if auth.startswith("Basic "):
            try:
                id_, _, rahasia = base64.b64decode(auth[6:]).decode("utf-8").partition(":")
                id_, rahasia = unquote_plus(id_), unquote_plus(rahasia)
            except ValueError:
                id_ = rahasia = None
        if (id_, rahasia) != (idp.CLIENT_ID, idp.CLIENT_SECRET):
            return self.kirim(401, {"error": "invalid_client"}, ekstra={"WWW-Authenticate": "Basic"})
        if form.get("grant_type") != "authorization_code":
            return self.kirim(400, {"error": "unsupported_grant_type"})
        info = idp.kode.get(form.get("code", ""))
        if info is None or info["dipakai"] or info["kedaluwarsa"] < time.time() or info["client_id"] != id_:
            return self.kirim(400, {"error": "invalid_grant"})
        info["dipakai"] = True
        verifier = form.get("code_verifier", "")
        if (form.get("redirect_uri") != info["redirect_uri"] or not 43 <= len(verifier) <= 128
                or _b64(hashlib.sha256(verifier.encode("ascii", "replace")).digest()) != info["challenge"]):
            return self.kirim(400, {"error": "invalid_grant"})
        akses = secrets.token_urlsafe(24)
        idp.token_akses[akses] = info["sub"]
        klaim = idp.klaim_id_token(info["sub"], info["nonce"])
        id_token = idp.id_token_ganti(klaim) if idp.id_token_ganti else idp.tanda_tangan(klaim)
        idp.arsip["akses"].append(akses)
        idp.arsip["id_token"].append(id_token)
        self.kirim(200, {"access_token": akses, "token_type": "Bearer", "expires_in": 300, "id_token": id_token})
